#!/usr/bin/env python3
"""
Davidson County Appeal Lead Generator.

Identifies Single Family properties across Davidson County where a successful
tax appeal would generate enough first-year savings to cover the $200 acquisition cost.

Uses a hybrid SQL/Python approach:
- SQL: Efficient county-wide calculation of comparable medians and over-assessment
- Python: Additional filtering, ranking, and output formatting

Usage:
    python generate_leads.py --output leads.csv
    python generate_leads.py --min-savings 500 --output premium_leads.csv
    python generate_leads.py --format json --limit 100
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
DEFAULT_SQFT_RANGE = 25
DEFAULT_ACREAGE_RANGE = 15
DEFAULT_MAX_DISTANCE = 3.0  # miles
DEFAULT_BED_RANGE = 0  # exact match by default
DEFAULT_BATH_RANGE = 0  # exact match by default
DEFAULT_MIN_COMPARABLES = 3  # lowered since we now use quality-based confidence
DEFAULT_EXCLUDE_RECENT_SALES = 730  # 2 years in days
DEFAULT_BQ_PROJECT = "public-data-dev"
DEFAULT_BQ_DATASET = "property_tax"

# Davidson County tax rate (3.254% per $100 of assessed value = 0.03254)
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
    median_comparable: float
    over_assessment: float
    estimated_savings: float
    num_comparables: int
    year_built: Optional[int]
    sqft: Optional[float]
    acreage: Optional[float]
    beds: Optional[int]
    baths: Optional[float]  # float to support half baths (e.g., 2.5)
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
    sqft_range: int = DEFAULT_SQFT_RANGE,
    year_range: int = DEFAULT_YEAR_RANGE,
    acreage_range: int = DEFAULT_ACREAGE_RANGE,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    bed_range: int = DEFAULT_BED_RANGE,
    bath_range: int = DEFAULT_BATH_RANGE,
    zipcode: Optional[str] = None,
    limit: Optional[int] = None
) -> str:
    """Build the SQL query for finding appeal leads using percentage-based comparable criteria."""

    limit_clause = f"LIMIT {limit}" if limit else ""

    # Optional zipcode filter for cost-controlled testing
    zipcode_filter = f"AND p.PropZip = '{zipcode}'" if zipcode else ""

    # Convert parameters to decimals for SQL
    sqft_min_factor = 1 - (sqft_range / 100)  # e.g., 0.75 for 25%
    sqft_max_factor = 1 + (sqft_range / 100)  # e.g., 1.25 for 25%
    acreage_min_factor = 1 - (acreage_range / 100)  # e.g., 0.85 for 15%
    acreage_max_factor = 1 + (acreage_range / 100)  # e.g., 1.15 for 15%
    max_distance_meters = max_distance * 1609.34  # Convert miles to meters

    query = f"""
    WITH enriched_parcels AS (
      -- Base property data with building characteristics and bed/bath data
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
        -- Bed/bath data (half baths count as 0.5)
        bb.beds,
        COALESCE(bb.baths, 0) + COALESCE(bb.half_baths, 0) * 0.5 AS total_baths,
        bb.beds IS NOT NULL AS has_bed_bath_data,
        COALESCE(fz.in_flood_zone, FALSE) AS in_flood_zone
      FROM `{project}.{dataset}.davidson_parcels` p
      LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b ON p.STANPAR = b.apn
      LEFT JOIN `{project}.{dataset}.davidson_bed_bath` bb ON CAST(p.ParID AS STRING) = bb.parcel_id
      LEFT JOIN `{project}.{dataset}.v_parcel_floodzone_enrichment` fz ON p.ParID = fz.parcel_id
      WHERE p.TotlAppr > 0
        AND p.LUDesc = 'SINGLE FAMILY'
        AND p.Lat IS NOT NULL AND p.Lon IS NOT NULL
        AND b.year_built IS NOT NULL AND b.finished_area IS NOT NULL
        {zipcode_filter}
        -- Exclude recent sales (last N days)
        AND (p.OwnDate IS NULL OR p.OwnDate < DATE_SUB(CURRENT_DATE(), INTERVAL {exclude_recent_sales_days} DAY))
        -- Exclude properties where a valid recent sale validates the assessment
        -- Valid sale = >= $10k, in market window 2020-01-01 to 2025-01-01
        -- If assessment is within 10% of sale price, the sale proves the assessment is reasonable
        AND (
          p.SalePrice IS NULL
          OR p.SalePrice < 10000
          OR p.OwnDate < '2020-01-01'
          OR p.OwnDate >= '2025-01-01'
          OR p.TotlAppr > p.SalePrice * 1.10  -- Only keep if assessed > 110% of sale (genuine over-assessment)
        )
    ),
    comparables AS (
      -- Self-join: each property to its potential comps within percentage-based ranges
      SELECT
        p.ParID,
        c.ParID AS comp_parid,
        c.TotlAppr AS comp_appraisal,
        p.has_bed_bath_data,
        -- Distance in miles
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
        -- Bed/bath similarity (if data available)
        CASE
          WHEN p.beds IS NULL OR c.beds IS NULL THEN 0.05  -- Small penalty for missing data
          ELSE ABS(p.beds - c.beds) / GREATEST(p.beds, 1) * 0.10
        END +
        CASE
          WHEN p.total_baths IS NULL OR c.total_baths IS NULL THEN 0.05  -- Small penalty for missing data
          ELSE ABS(p.total_baths - c.total_baths) / GREATEST(p.total_baths, 1) * 0.10
        END
        AS similarity_score
      FROM enriched_parcels p
      JOIN enriched_parcels c ON
        p.LUDesc = c.LUDesc
        AND p.ParID != c.ParID
        -- Distance-based: within max distance
        AND ST_DISTANCE(ST_GEOGPOINT(p.Lon, p.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) <= {max_distance_meters}
        -- Sqft: within ±{sqft_range}%
        AND c.finished_area BETWEEN p.finished_area * {sqft_min_factor} AND p.finished_area * {sqft_max_factor}
        -- Year: within ±{year_range} years
        AND c.year_built BETWEEN p.year_built - {year_range} AND p.year_built + {year_range}
        -- Acreage: within ±{acreage_range}% (skip filter if either has null/zero acres)
        AND (
          p.Acres IS NULL OR p.Acres = 0 OR c.Acres IS NULL OR c.Acres = 0
          OR c.Acres BETWEEN p.Acres * {acreage_min_factor} AND p.Acres * {acreage_max_factor}
        )
        -- Beds: exact match or within range (skip filter if either has null beds)
        AND (
          p.beds IS NULL OR c.beds IS NULL
          OR c.beds BETWEEN p.beds - {bed_range} AND p.beds + {bed_range}
        )
        -- Baths: exact match or within range (skip filter if either has null baths)
        AND (
          p.total_baths IS NULL OR c.total_baths IS NULL
          OR c.total_baths BETWEEN p.total_baths - {bath_range} AND p.total_baths + {bath_range}
        )
    ),
    ranked_comps AS (
      -- Rank comps by similarity for each property
      SELECT *,
        ROW_NUMBER() OVER (PARTITION BY ParID ORDER BY similarity_score) AS rank,
        COUNT(*) OVER (PARTITION BY ParID) AS total_comps
      FROM comparables
    ),
    top_comps AS (
      -- Keep only top 20 most similar (quality-based)
      SELECT * FROM ranked_comps WHERE rank <= 20
    ),
    comp_stats AS (
      -- Calculate median and quality metrics from top comps
      SELECT
        ParID,
        total_comps,
        COUNT(*) AS comps_used,
        AVG(similarity_score) AS avg_similarity,
        AVG(distance_miles) AS avg_distance_miles,
        APPROX_QUANTILES(comp_appraisal, 100)[OFFSET(50)] AS median_assessment,
        -- Track if subject has bed/bath data
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
        s.median_assessment,
        s.comps_used,
        s.total_comps,
        s.avg_similarity,
        s.avg_distance_miles,
        p.TotlAppr - s.median_assessment AS over_assessment,
        (p.TotlAppr - s.median_assessment) * {ASSESSMENT_RATIO} * {TAX_RATE} AS estimated_savings,
        -- Confidence calculation (0-100 scale)
        LEAST(100, GREATEST(0,
          -- Base score from comp count (0-70 points)
          CASE
            WHEN s.comps_used < 3 THEN s.comps_used * 10
            WHEN s.comps_used < 5 THEN 30 + (s.comps_used - 3) * 10
            WHEN s.comps_used < 10 THEN 50 + (s.comps_used - 5) * 4
            ELSE 70
          END
          -- Bonus for good similarity (0-30 points)
          + CASE
              WHEN s.avg_similarity < 0.15 THEN 30
              WHEN s.avg_similarity < 0.25 THEN 20
              WHEN s.avg_similarity < 0.40 THEN 10
              ELSE 0
            END
          -- Penalty for missing bed/bath data (-10 points)
          - CASE WHEN p.has_bed_bath_data THEN 0 ELSE 10 END
        )) AS confidence_score
      FROM enriched_parcels p
      JOIN comp_stats s ON p.ParID = s.ParID
      WHERE p.TotlAppr > s.median_assessment
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
    sqft_range: int = DEFAULT_SQFT_RANGE,
    year_range: int = DEFAULT_YEAR_RANGE,
    acreage_range: int = DEFAULT_ACREAGE_RANGE,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    bed_range: int = DEFAULT_BED_RANGE,
    bath_range: int = DEFAULT_BATH_RANGE,
    zipcode: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Lead]:
    """Execute the leads query and return Lead objects."""

    query = build_leads_query(
        project=project,
        dataset=dataset,
        min_savings=min_savings,
        exclude_recent_sales_days=exclude_recent_sales_days,
        min_comparables=min_comparables,
        sqft_range=sqft_range,
        year_range=year_range,
        acreage_range=acreage_range,
        max_distance=max_distance,
        bed_range=bed_range,
        bath_range=bath_range,
        zipcode=zipcode,
        limit=limit
    )

    print(f"Executing query against {project}.{dataset}...", file=sys.stderr)
    results = client.query(query).result()

    leads = []
    for row in results:
        # Build owner address string
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
            median_comparable=float(row.median_assessment),
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
        "current_assessment", "median_comparable", "over_assessment",
        "estimated_savings", "num_comparables", "confidence_score",
        "year_built", "sqft", "acreage", "beds", "baths", "land_use",
        "avg_similarity", "avg_comp_distance_miles", "in_flood_zone"
    ]

    # Create CSV in memory
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
            "median_comparable": f"{lead.median_comparable:.0f}",
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
    print("                   LEAD GENERATION SUMMARY", file=file)
    print("=" * 60, file=file)
    print(f"  Total Leads Found:        {len(leads):,}", file=file)
    print(f"  Total Potential Savings:  ${total_savings:,.2f}", file=file)
    print(f"  Average Savings/Lead:     ${avg_savings:,.2f}", file=file)
    print(f"  Max Savings:              ${max_savings:,.2f}", file=file)
    print(f"  Min Savings:              ${min_savings:,.2f}", file=file)
    print(f"  Avg Over-Assessment:      ${avg_over_assessment:,.0f}", file=file)
    print("=" * 60, file=file)

    # Top 10 preview
    if len(leads) > 0:
        print("", file=file)
        print("Top 10 Leads by Estimated Savings:", file=file)
        print("-" * 60, file=file)
        for i, lead in enumerate(leads[:10], 1):
            print(f"  {i:2}. ${lead.estimated_savings:>8,.2f} | {lead.address[:35]:<35}", file=file)
        print("", file=file)


def main():
    parser = argparse.ArgumentParser(
        description="Generate appeal leads for Davidson County single family properties",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test on a single zip code first (fast, cheap)
    python generate_leads.py --zipcode 37205 --limit 50 --output test_leads.csv

    # Generate leads with default settings
    python generate_leads.py --output leads.csv

    # Generate leads with $500 minimum savings
    python generate_leads.py --min-savings 500 --output premium_leads.csv

    # Output JSON format with limit
    python generate_leads.py --format json --limit 100 --output leads.json

    # Custom comparable criteria
    python generate_leads.py --sqft-range 20 --year-range 15 --max-distance 2.0 --output leads.csv
        """
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
        help=f"Exclude properties sold within N days (default: {DEFAULT_EXCLUDE_RECENT_SALES})"
    )
    parser.add_argument(
        "--zipcode",
        type=str,
        default=None,
        help="Restrict to a single zip code (for cost-controlled testing)"
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

    # Show query mode
    if args.show_query:
        query = build_leads_query(
            project=args.project,
            dataset=args.dataset,
            min_savings=args.min_savings,
            exclude_recent_sales_days=args.exclude_recent_sales,
            min_comparables=args.min_comparables,
            sqft_range=args.sqft_range,
            year_range=args.year_range,
            acreage_range=args.acreage_range,
            max_distance=args.max_distance,
            bed_range=args.bed_range,
            bath_range=args.bath_range,
            zipcode=args.zipcode,
            limit=args.limit
        )
        print(query)
        return

    # Initialize BigQuery client
    print(f"Connecting to BigQuery project: {args.project}", file=sys.stderr)
    client = bigquery.Client(project=args.project)

    # Fetch leads
    zipcode_msg = f" in zip code {args.zipcode}" if args.zipcode else ""
    print(f"Finding leads with minimum savings >= ${args.min_savings:.0f}{zipcode_msg}...", file=sys.stderr)
    leads = fetch_leads(
        client=client,
        project=args.project,
        dataset=args.dataset,
        min_savings=args.min_savings,
        exclude_recent_sales_days=args.exclude_recent_sales,
        min_comparables=args.min_comparables,
        sqft_range=args.sqft_range,
        year_range=args.year_range,
        acreage_range=args.acreage_range,
        max_distance=args.max_distance,
        bed_range=args.bed_range,
        bath_range=args.bath_range,
        zipcode=args.zipcode,
        limit=args.limit
    )

    print(f"Found {len(leads):,} leads", file=sys.stderr)

    # Print summary
    print_summary(leads)

    # Format output
    if args.format == "json":
        output = format_json(leads)
    else:
        output = format_csv(leads)

    # Write output
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Output saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
