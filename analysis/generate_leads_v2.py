#!/usr/bin/env python3
"""
Davidson County Appeal Lead Generator v2.

Key difference from v1: Comparables use SALE PRICES of recently sold similar
properties instead of assessed values. This mirrors how appeals boards evaluate
cases — recent arm's-length sales of similar properties are the strongest
evidence of fair market value.

Subject pool (leads): Same as v1 — single family properties not sold in last 730 days.
Comp pool: Single family properties that sold in the specified year range (default: 2025)
           at a valid arm's-length sale price (default: >= $100k).

Comparison: subject.TotlAppr  vs  median(comp.SalePrice)

Usage:
    python generate_leads_v2.py --output leads_v2.csv
    python generate_leads_v2.py --zipcode 37205 --limit 50 --output test.csv
    python generate_leads_v2.py --comp-year-start 2024 --comp-year-end 2025 --output leads_v2.csv
    python generate_leads_v2.py --min-comparables 3 --max-distance 3.0 --output leads_v2.csv
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, List

from google.cloud import bigquery

# Configuration defaults
DEFAULT_MIN_SAVINGS = 1500
DEFAULT_YEAR_RANGE = 10
DEFAULT_SQFT_RANGE = 20
DEFAULT_ACREAGE_RANGE = 10
DEFAULT_MAX_DISTANCE = 3.0
DEFAULT_BED_RANGE = 0
DEFAULT_BATH_RANGE = 0
DEFAULT_MIN_COMPARABLES = 3
DEFAULT_EXCLUDE_RECENT_SALES = 730
DEFAULT_COMP_YEAR_START = 2025
DEFAULT_COMP_YEAR_END = 2025
DEFAULT_MIN_COMP_SALE_PRICE = 100000
DEFAULT_BQ_PROJECT = "public-data-dev"
DEFAULT_BQ_DATASET = "property_tax"

TAX_RATE = 0.03254
ASSESSMENT_RATIO = 0.25


@dataclass
class Lead:
    """A property identified as a potential appeal lead."""
    parid: str
    address: str
    owner_name: str
    owner_address: str
    current_assessment: float
    median_comp_sale_price: float
    over_assessment: float
    estimated_savings: float
    num_comparables: int
    year_built: Optional[int]
    sqft: Optional[float]
    acreage: Optional[float]
    beds: Optional[int]
    baths: Optional[float]
    land_use: str
    zip_code: str
    confidence_score: float
    avg_similarity: float
    avg_comp_distance_miles: float
    in_flood_zone: bool


def build_leads_query(
    project: str,
    dataset: str,
    min_savings: float,
    exclude_recent_sales_days: int,
    min_comparables: int,
    comp_year_start: int,
    comp_year_end: int,
    min_comp_sale_price: float,
    sqft_range: int = DEFAULT_SQFT_RANGE,
    year_range: int = DEFAULT_YEAR_RANGE,
    acreage_range: int = DEFAULT_ACREAGE_RANGE,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    bed_range: int = DEFAULT_BED_RANGE,
    bath_range: int = DEFAULT_BATH_RANGE,
    zipcode: Optional[str] = None,
    require_bed_bath: bool = False,
    limit: Optional[int] = None
) -> str:
    """Build the SQL query using sale prices of recently sold comps as the benchmark."""

    limit_clause = f"LIMIT {limit}" if limit else ""
    zipcode_filter = f"AND p.PropZip = '{zipcode}'" if zipcode else ""
    bed_bath_filter = "AND bb.beds IS NOT NULL" if require_bed_bath else ""

    sqft_min_factor = 1 - (sqft_range / 100)
    sqft_max_factor = 1 + (sqft_range / 100)
    acreage_min_factor = 1 - (acreage_range / 100)
    acreage_max_factor = 1 + (acreage_range / 100)
    max_distance_meters = max_distance * 1609.34
    comp_year_end_exclusive = comp_year_end + 1

    query = f"""
    WITH enriched_parcels AS (
      -- Subject pool: eligible lead candidates (same logic as v1)
      SELECT
        p.ParID,
        p.PropAddr,
        p.PropZip,
        p.LUDesc,
        p.TotlAppr,
        p.Lat,
        p.Lon,
        p.Acres,
        p.Owner,
        p.OwnAddr1,
        p.OwnCity,
        p.OwnState,
        p.OwnZip,
        p.SalePrice,
        p.OwnDate,
        b.year_built,
        b.finished_area,
        bb.beds,
        COALESCE(bb.baths, 0) + COALESCE(bb.half_baths, 0) * 0.5 AS total_baths,
        bb.beds IS NOT NULL AS has_bed_bath_data,
        COALESCE(fz.in_flood_zone, FALSE) AS in_flood_zone
      FROM `{project}.{dataset}.davidson_parcels` p
      LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b ON p.STANPAR = b.apn
      LEFT JOIN `{project}.{dataset}.davidson_bed_bath` bb ON p.ParID = bb.parcel_id
      LEFT JOIN `{project}.{dataset}.v_parcel_floodzone_enrichment` fz ON p.ParID = fz.parcel_id
      WHERE p.TotlAppr > 0
        AND p.LUDesc = 'SINGLE FAMILY'
        AND p.Lat IS NOT NULL AND p.Lon IS NOT NULL
        AND b.year_built IS NOT NULL AND b.finished_area IS NOT NULL
        {zipcode_filter}
        {bed_bath_filter}
        -- Exclude recently sold properties (they know their market value)
        AND (p.OwnDate IS NULL OR p.OwnDate < DATE_SUB(CURRENT_DATE(), INTERVAL {exclude_recent_sales_days} DAY))
        -- Exclude properties where a recent valid sale validates the assessment
        AND (
          p.SalePrice IS NULL
          OR p.SalePrice < 10000
          OR p.OwnDate < '2020-01-01'
          OR p.TotlAppr > p.SalePrice * 1.15
        )
    ),
    recent_sales AS (
      -- Comp pool: properties that sold in the target year range at arm's-length prices
      -- Sale price is used as the market value benchmark instead of assessed value
      SELECT
        p.ParID,
        p.PropZip,
        p.LUDesc,
        p.SalePrice AS sale_price,
        p.Lat,
        p.Lon,
        p.Acres,
        b.year_built,
        b.finished_area,
        bb.beds,
        COALESCE(bb.baths, 0) + COALESCE(bb.half_baths, 0) * 0.5 AS total_baths
      FROM `{project}.{dataset}.davidson_parcels` p
      LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b ON p.STANPAR = b.apn
      LEFT JOIN `{project}.{dataset}.davidson_bed_bath` bb ON p.ParID = bb.parcel_id
      WHERE p.LUDesc = 'SINGLE FAMILY'
        AND p.Lat IS NOT NULL AND p.Lon IS NOT NULL
        AND b.year_built IS NOT NULL AND b.finished_area IS NOT NULL
        AND p.OwnDate >= '{comp_year_start}-01-01'
        AND p.OwnDate < '{comp_year_end_exclusive}-01-01'
        AND p.SalePrice >= {min_comp_sale_price}
    ),
    comparables AS (
      -- Match each subject property against similar recently sold comps
      SELECT
        p.ParID,
        c.ParID AS comp_parid,
        c.sale_price AS comp_sale_price,
        p.has_bed_bath_data,
        ST_DISTANCE(ST_GEOGPOINT(p.Lon, p.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) / 1609.34 AS distance_miles,
        -- Similarity score (lower = more similar)
        -- Weighted: sqft 25%, year 20%, acreage 15%, distance 20%, beds 10%, baths 10%
        ABS(p.year_built - c.year_built) / {year_range} * 0.20 +
        ABS(p.finished_area - c.finished_area) / NULLIF(p.finished_area, 0) * 0.25 +
        CASE
          WHEN p.Acres IS NULL OR p.Acres = 0 OR c.Acres IS NULL OR c.Acres = 0 THEN 0
          ELSE ABS(p.Acres - c.Acres) / NULLIF(p.Acres, 0) * 0.15
        END +
        ST_DISTANCE(ST_GEOGPOINT(p.Lon, p.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) / {max_distance_meters} * 0.20 +
        CASE
          WHEN p.beds IS NULL OR c.beds IS NULL THEN 0.05
          ELSE ABS(p.beds - c.beds) / GREATEST(p.beds, 1) * 0.10
        END +
        CASE
          WHEN p.total_baths IS NULL OR c.total_baths IS NULL THEN 0.05
          ELSE ABS(p.total_baths - c.total_baths) / GREATEST(p.total_baths, 1) * 0.10
        END
        AS similarity_score
      FROM enriched_parcels p
      JOIN recent_sales c ON
        p.LUDesc = c.LUDesc
        AND p.ParID != c.ParID
        AND ST_DISTANCE(ST_GEOGPOINT(p.Lon, p.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) <= {max_distance_meters}
        AND c.finished_area BETWEEN p.finished_area * {sqft_min_factor} AND p.finished_area * {sqft_max_factor}
        AND c.year_built BETWEEN p.year_built - {year_range} AND p.year_built + {year_range}
        AND (
          p.Acres IS NULL OR p.Acres = 0 OR c.Acres IS NULL OR c.Acres = 0
          OR c.Acres BETWEEN p.Acres * {acreage_min_factor} AND p.Acres * {acreage_max_factor}
        )
        AND (
          p.beds IS NULL OR c.beds IS NULL
          OR c.beds BETWEEN p.beds - {bed_range} AND p.beds + {bed_range}
        )
        AND (
          p.total_baths IS NULL OR c.total_baths IS NULL
          OR c.total_baths BETWEEN p.total_baths - {bath_range} AND p.total_baths + {bath_range}
        )
    ),
    ranked_comps AS (
      SELECT *,
        ROW_NUMBER() OVER (PARTITION BY ParID ORDER BY similarity_score) AS rank,
        COUNT(*) OVER (PARTITION BY ParID) AS total_comps
      FROM comparables
    ),
    top_comps AS (
      SELECT * FROM ranked_comps WHERE rank <= 20
    ),
    comp_stats AS (
      SELECT
        ParID,
        total_comps,
        COUNT(*) AS comps_used,
        AVG(similarity_score) AS avg_similarity,
        AVG(distance_miles) AS avg_distance_miles,
        APPROX_QUANTILES(comp_sale_price, 100)[OFFSET(50)] AS median_sale_price,
        LOGICAL_OR(has_bed_bath_data) AS has_bed_bath_data
      FROM top_comps
      GROUP BY ParID, total_comps
    ),
    leads AS (
      SELECT
        p.ParID,
        p.PropAddr,
        p.PropZip,
        p.LUDesc,
        p.TotlAppr,
        p.Acres,
        p.beds,
        p.total_baths,
        p.has_bed_bath_data,
        p.Owner,
        p.OwnAddr1,
        p.OwnCity,
        p.OwnState,
        p.OwnZip,
        p.year_built,
        p.finished_area,
        p.in_flood_zone,
        s.median_sale_price,
        s.comps_used,
        s.total_comps,
        s.avg_similarity,
        s.avg_distance_miles,
        p.TotlAppr - s.median_sale_price AS over_assessment,
        (p.TotlAppr - s.median_sale_price) * {ASSESSMENT_RATIO} * {TAX_RATE} AS estimated_savings,
        LEAST(100, GREATEST(0,
          CASE
            WHEN s.comps_used < 3 THEN s.comps_used * 10
            WHEN s.comps_used < 5 THEN 30 + (s.comps_used - 3) * 10
            WHEN s.comps_used < 10 THEN 50 + (s.comps_used - 5) * 4
            ELSE 70
          END
          + CASE
              WHEN s.avg_similarity < 0.15 THEN 30
              WHEN s.avg_similarity < 0.25 THEN 20
              WHEN s.avg_similarity < 0.40 THEN 10
              ELSE 0
            END
          - CASE WHEN p.has_bed_bath_data THEN 0 ELSE 10 END
        )) AS confidence_score
      FROM enriched_parcels p
      JOIN comp_stats s ON p.ParID = s.ParID
      WHERE p.TotlAppr > s.median_sale_price
        AND s.comps_used >= {min_comparables}
    )
    SELECT *
    FROM leads
    WHERE estimated_savings >= {min_savings}
    ORDER BY estimated_savings DESC
    {limit_clause}
    """
    return query


def fetch_leads(
    client: bigquery.Client,
    project: str,
    dataset: str,
    min_savings: float,
    exclude_recent_sales_days: int,
    min_comparables: int,
    comp_year_start: int,
    comp_year_end: int,
    min_comp_sale_price: float,
    sqft_range: int = DEFAULT_SQFT_RANGE,
    year_range: int = DEFAULT_YEAR_RANGE,
    acreage_range: int = DEFAULT_ACREAGE_RANGE,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    bed_range: int = DEFAULT_BED_RANGE,
    bath_range: int = DEFAULT_BATH_RANGE,
    zipcode: Optional[str] = None,
    require_bed_bath: bool = False,
    limit: Optional[int] = None
) -> List[Lead]:
    """Execute the leads query and return Lead objects."""

    query = build_leads_query(
        project=project,
        dataset=dataset,
        min_savings=min_savings,
        exclude_recent_sales_days=exclude_recent_sales_days,
        min_comparables=min_comparables,
        comp_year_start=comp_year_start,
        comp_year_end=comp_year_end,
        min_comp_sale_price=min_comp_sale_price,
        sqft_range=sqft_range,
        year_range=year_range,
        acreage_range=acreage_range,
        max_distance=max_distance,
        bed_range=bed_range,
        bath_range=bath_range,
        zipcode=zipcode,
        require_bed_bath=require_bed_bath,
        limit=limit
    )

    print(f"Executing query against {project}.{dataset}...", file=sys.stderr)
    results = client.query(query).result()

    leads = []
    for row in results:
        owner_parts = []
        if row.OwnAddr1:
            owner_parts.append(row.OwnAddr1)
        city_state_zip = []
        if row.OwnCity:
            city_state_zip.append(row.OwnCity)
        if row.OwnState:
            city_state_zip.append(row.OwnState)
        if row.OwnZip:
            city_state_zip.append(str(row.OwnZip))
        if city_state_zip:
            owner_parts.append(", ".join(city_state_zip))
        owner_address = ", ".join(owner_parts) if owner_parts else ""

        lead = Lead(
            parid=str(row.ParID),
            address=row.PropAddr or "",
            owner_name=row.Owner or "",
            owner_address=owner_address,
            current_assessment=float(row.TotlAppr),
            median_comp_sale_price=float(row.median_sale_price),
            over_assessment=float(row.over_assessment),
            estimated_savings=float(row.estimated_savings),
            num_comparables=int(row.comps_used),
            year_built=int(row.year_built) if row.year_built else None,
            sqft=float(row.finished_area) if row.finished_area else None,
            acreage=float(row.Acres) if row.Acres else None,
            beds=int(row.beds) if row.beds else None,
            baths=float(row.total_baths) if row.total_baths else None,
            land_use=row.LUDesc or "",
            zip_code=row.PropZip or "",
            confidence_score=float(row.confidence_score),
            avg_similarity=float(row.avg_similarity),
            avg_comp_distance_miles=float(row.avg_distance_miles),
            in_flood_zone=bool(row.in_flood_zone),
        )
        leads.append(lead)

    return leads


def format_csv(leads: List[Lead]) -> str:
    """Format leads as CSV."""
    if not leads:
        return ""

    fieldnames = [
        "parid", "address", "owner_name", "owner_address",
        "current_assessment", "median_comp_sale_price", "over_assessment",
        "estimated_savings", "num_comparables", "confidence_score",
        "year_built", "sqft", "acreage", "beds", "baths", "land_use",
        "avg_similarity", "avg_comp_distance_miles", "in_flood_zone"
    ]

    import io
    string_io = io.StringIO()
    writer = csv.DictWriter(string_io, fieldnames=fieldnames)
    writer.writeheader()

    for lead in leads:
        row = {
            "parid": lead.parid,
            "address": lead.address,
            "owner_name": lead.owner_name,
            "owner_address": lead.owner_address,
            "current_assessment": f"{lead.current_assessment:.0f}",
            "median_comp_sale_price": f"{lead.median_comp_sale_price:.0f}",
            "over_assessment": f"{lead.over_assessment:.0f}",
            "estimated_savings": f"{lead.estimated_savings:.2f}",
            "num_comparables": lead.num_comparables,
            "confidence_score": f"{lead.confidence_score:.0f}",
            "year_built": lead.year_built if lead.year_built else "",
            "sqft": f"{lead.sqft:.0f}" if lead.sqft else "",
            "acreage": f"{lead.acreage:.2f}" if lead.acreage else "",
            "beds": lead.beds if lead.beds else "",
            "baths": f"{lead.baths:.1f}" if lead.baths else "",
            "land_use": lead.land_use,
            "avg_similarity": f"{lead.avg_similarity:.3f}",
            "avg_comp_distance_miles": f"{lead.avg_comp_distance_miles:.2f}",
            "in_flood_zone": "Yes" if lead.in_flood_zone else "No",
        }
        writer.writerow(row)

    return string_io.getvalue()


def format_json(leads: List[Lead]) -> str:
    """Format leads as JSON."""
    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_leads": len(leads),
        "leads": [asdict(lead) for lead in leads]
    }
    return json.dumps(data, indent=2)


def print_summary(leads: List[Lead], file=sys.stderr):
    """Print a summary of the leads found."""
    if not leads:
        print("No leads found matching criteria.", file=file)
        return

    total_savings = sum(lead.estimated_savings for lead in leads)
    avg_savings = total_savings / len(leads)
    max_savings = max(lead.estimated_savings for lead in leads)
    min_savings = min(lead.estimated_savings for lead in leads)
    avg_over_assessment = sum(lead.over_assessment for lead in leads) / len(leads)

    print("", file=file)
    print("=" * 60, file=file)
    print("             LEAD GENERATION SUMMARY (v2)", file=file)
    print("   (comp method: sale price of recently sold properties)", file=file)
    print("=" * 60, file=file)
    print(f"  Total Leads Found:        {len(leads):,}", file=file)
    print(f"  Total Potential Savings:  ${total_savings:,.2f}", file=file)
    print(f"  Average Savings/Lead:     ${avg_savings:,.2f}", file=file)
    print(f"  Max Savings:              ${max_savings:,.2f}", file=file)
    print(f"  Min Savings:              ${min_savings:,.2f}", file=file)
    print(f"  Avg Over-Assessment:      ${avg_over_assessment:,.0f}", file=file)
    print("=" * 60, file=file)

    if len(leads) > 0:
        print("", file=file)
        print("Top 10 Leads by Estimated Savings:", file=file)
        print("-" * 60, file=file)
        for i, lead in enumerate(leads[:10], 1):
            print(f"  {i:2}. ${lead.estimated_savings:>8,.2f} | {lead.address[:35]:<35}", file=file)
        print("", file=file)


def main():
    parser = argparse.ArgumentParser(
        description="Generate appeal leads using sale prices of recently sold comps (v2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test on a single zip code first (fast, cheap)
    python generate_leads_v2.py --zipcode 37205 --limit 50 --output test_leads_v2.csv

    # Default: compare against 2025 sales only
    python generate_leads_v2.py --output leads_v2.csv

    # Expand comp pool to 2024+2025 if lead count is low
    python generate_leads_v2.py --comp-year-start 2024 --comp-year-end 2025 --output leads_v2.csv

    # Loosen thresholds if not enough comps in low-turnover areas
    python generate_leads_v2.py --min-comparables 3 --max-distance 3.0 --sqft-range 20 --output leads_v2.csv

    # Require bed/bath data for stricter matching
    python generate_leads_v2.py --require-bed-bath --output leads_v2.csv
        """
    )

    # Comp year range
    parser.add_argument(
        "--comp-year-start",
        type=int,
        default=DEFAULT_COMP_YEAR_START,
        help=f"Start year for comp sales (default: {DEFAULT_COMP_YEAR_START})"
    )
    parser.add_argument(
        "--comp-year-end",
        type=int,
        default=DEFAULT_COMP_YEAR_END,
        help=f"End year for comp sales (default: {DEFAULT_COMP_YEAR_END})"
    )
    parser.add_argument(
        "--min-comp-sale-price",
        type=float,
        default=DEFAULT_MIN_COMP_SALE_PRICE,
        help=f"Minimum sale price to include a property as a comp (default: ${DEFAULT_MIN_COMP_SALE_PRICE:,})"
    )

    # Lead criteria
    parser.add_argument(
        "--min-savings",
        type=float,
        default=DEFAULT_MIN_SAVINGS,
        help=f"Minimum first-year tax savings to qualify as lead (default: ${DEFAULT_MIN_SAVINGS})"
    )
    parser.add_argument(
        "--year-range",
        type=int,
        default=DEFAULT_YEAR_RANGE,
        help=f"Year built range for comparable grouping (default: {DEFAULT_YEAR_RANGE})"
    )
    parser.add_argument(
        "--sqft-range",
        type=int,
        default=DEFAULT_SQFT_RANGE,
        help=f"Square footage percentage range for comparables (default: {DEFAULT_SQFT_RANGE}%%)"
    )
    parser.add_argument(
        "--acreage-range",
        type=int,
        default=DEFAULT_ACREAGE_RANGE,
        help=f"Acreage percentage range for comparables (default: {DEFAULT_ACREAGE_RANGE}%%)"
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=DEFAULT_MAX_DISTANCE,
        help=f"Maximum distance in miles for comparables (default: {DEFAULT_MAX_DISTANCE})"
    )
    parser.add_argument(
        "--bed-range",
        type=int,
        default=DEFAULT_BED_RANGE,
        help=f"Bedroom range +/- for comparables (default: {DEFAULT_BED_RANGE} = exact match)"
    )
    parser.add_argument(
        "--bath-range",
        type=int,
        default=DEFAULT_BATH_RANGE,
        help=f"Bathroom range +/- for comparables (default: {DEFAULT_BATH_RANGE} = exact match)"
    )
    parser.add_argument(
        "--min-comparables",
        type=int,
        default=DEFAULT_MIN_COMPARABLES,
        help=f"Minimum comparable count for inclusion (default: {DEFAULT_MIN_COMPARABLES})"
    )
    parser.add_argument(
        "--exclude-recent-sales",
        type=int,
        default=DEFAULT_EXCLUDE_RECENT_SALES,
        help=f"Exclude subject properties sold within N days (default: {DEFAULT_EXCLUDE_RECENT_SALES})"
    )
    parser.add_argument(
        "--zipcode",
        type=str,
        default=None,
        help="Restrict to a single zip code (for cost-controlled testing)"
    )
    parser.add_argument(
        "--require-bed-bath",
        action="store_true",
        help="Only include subject properties with bed/bath data"
    )

    # Output options
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format (default: csv)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum leads to return (default: unlimited)"
    )

    # BigQuery options
    parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_BQ_PROJECT,
        help=f"GCP project ID (default: {DEFAULT_BQ_PROJECT})"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=DEFAULT_BQ_DATASET,
        help=f"BigQuery dataset (default: {DEFAULT_BQ_DATASET})"
    )

    # Debug options
    parser.add_argument(
        "--show-query",
        action="store_true",
        help="Print the SQL query without executing"
    )

    args = parser.parse_args()

    if args.show_query:
        query = build_leads_query(
            project=args.project,
            dataset=args.dataset,
            min_savings=args.min_savings,
            exclude_recent_sales_days=args.exclude_recent_sales,
            min_comparables=args.min_comparables,
            comp_year_start=args.comp_year_start,
            comp_year_end=args.comp_year_end,
            min_comp_sale_price=args.min_comp_sale_price,
            sqft_range=args.sqft_range,
            year_range=args.year_range,
            acreage_range=args.acreage_range,
            max_distance=args.max_distance,
            bed_range=args.bed_range,
            bath_range=args.bath_range,
            zipcode=args.zipcode,
            require_bed_bath=args.require_bed_bath,
            limit=args.limit
        )
        print(query)
        return

    print(f"Connecting to BigQuery project: {args.project}", file=sys.stderr)
    client = bigquery.Client(project=args.project)

    zipcode_msg = f" in zip code {args.zipcode}" if args.zipcode else ""
    bed_bath_msg = " (requiring bed/bath data)" if args.require_bed_bath else ""
    print(
        f"Finding leads{zipcode_msg} — comparing against {args.comp_year_start}"
        f"{'–' + str(args.comp_year_end) if args.comp_year_end != args.comp_year_start else ''} "
        f"sales (min ${args.min_comp_sale_price:,.0f}), min savings >= ${args.min_savings:.0f}{bed_bath_msg}...",
        file=sys.stderr
    )

    leads = fetch_leads(
        client=client,
        project=args.project,
        dataset=args.dataset,
        min_savings=args.min_savings,
        exclude_recent_sales_days=args.exclude_recent_sales,
        min_comparables=args.min_comparables,
        comp_year_start=args.comp_year_start,
        comp_year_end=args.comp_year_end,
        min_comp_sale_price=args.min_comp_sale_price,
        sqft_range=args.sqft_range,
        year_range=args.year_range,
        acreage_range=args.acreage_range,
        max_distance=args.max_distance,
        bed_range=args.bed_range,
        bath_range=args.bath_range,
        zipcode=args.zipcode,
        require_bed_bath=args.require_bed_bath,
        limit=args.limit
    )

    print(f"Found {len(leads):,} leads", file=sys.stderr)

    print_summary(leads)

    if args.format == "json":
        output = format_json(leads)
    else:
        output = format_csv(leads)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Output saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
