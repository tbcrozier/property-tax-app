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
DEFAULT_MIN_COMPARABLES = 5
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
    land_use: str
    zip_code: str
    cohort_decade: Optional[int]
    cohort_sqft_band: Optional[int]
    in_flood_zone: bool


def build_leads_query(
    project: str,
    dataset: str,
    min_savings: float,
    exclude_recent_sales_days: int,
    min_comparables: int,
    limit: Optional[int] = None
) -> str:
    """Build the SQL query for finding appeal leads."""

    limit_clause = f"LIMIT {limit}" if limit else ""

    query = f"""
    WITH enriched_parcels AS (
      SELECT
        p.ParID,
        p.PropAddr,
        p.PropZip,
        p.LUDesc,
        p.TotlAppr,
        p.Owner,
        p.OwnAddr1,
        p.OwnCity,
        p.OwnState,
        p.OwnZip,
        p.SalePrice,
        p.OwnDate,
        b.year_built,
        b.finished_area,
        COALESCE(fz.in_flood_zone, FALSE) AS in_flood_zone
      FROM `{project}.{dataset}.davidson_parcels` p
      LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b ON p.STANPAR = b.apn
      LEFT JOIN `{project}.{dataset}.v_parcel_floodzone_enrichment` fz ON p.ParID = fz.parcel_id
      WHERE p.TotlAppr > 0
        AND p.LUDesc = 'SINGLE FAMILY'
        -- Exclude recent sales (last N days)
        AND (p.OwnDate IS NULL OR p.OwnDate < DATE_SUB(CURRENT_DATE(), INTERVAL {exclude_recent_sales_days} DAY))
        -- Exclude under-assessed properties (appeal could backfire - assessor can use sale price to RAISE assessment)
        -- Only consider sales within the relevant market window (2020-01-01 to 2025-01-01):
        --   - Sales before 2020: too old, market has changed significantly
        --   - Sales after Jan 1, 2025: after the reappraisal valuation date, not relevant to 2025 assessments
        --   - Only applies to valid sales >= $10k (filters out nominal transfers)
        AND (p.SalePrice IS NULL OR p.SalePrice < 10000 OR p.OwnDate < '2020-01-01' OR p.OwnDate >= '2025-01-01' OR p.TotlAppr >= p.SalePrice * 0.95)
    ),
    cohort_assignments AS (
      SELECT
        ParID,
        PropAddr,
        PropZip,
        LUDesc,
        TotlAppr,
        Owner,
        OwnAddr1,
        OwnCity,
        OwnState,
        OwnZip,
        SalePrice,
        OwnDate,
        year_built,
        finished_area,
        in_flood_zone,
        -- Create cohort keys for grouping comparable properties
        PropZip AS cohort_zip,
        LUDesc AS cohort_lu,
        CAST(FLOOR(year_built / 10) * 10 AS INT64) AS cohort_decade,
        CAST(FLOOR(finished_area / 500) * 500 AS INT64) AS cohort_sqft_band
      FROM enriched_parcels
      WHERE year_built IS NOT NULL AND finished_area IS NOT NULL
    ),
    cohort_stats AS (
      SELECT
        cohort_zip,
        cohort_lu,
        cohort_decade,
        cohort_sqft_band,
        APPROX_QUANTILES(TotlAppr, 100)[OFFSET(50)] AS median_assessment,
        COUNT(*) AS cohort_size
      FROM cohort_assignments
      GROUP BY cohort_zip, cohort_lu, cohort_decade, cohort_sqft_band
      HAVING COUNT(*) >= {min_comparables}
    ),
    leads AS (
      SELECT
        c.ParID,
        c.PropAddr,
        c.PropZip,
        c.LUDesc,
        c.TotlAppr,
        c.Owner,
        c.OwnAddr1,
        c.OwnCity,
        c.OwnState,
        c.OwnZip,
        c.year_built,
        c.finished_area,
        c.in_flood_zone,
        c.cohort_decade,
        c.cohort_sqft_band,
        s.median_assessment,
        s.cohort_size,
        c.TotlAppr - s.median_assessment AS over_assessment,
        (c.TotlAppr - s.median_assessment) * {ASSESSMENT_RATIO} * {TAX_RATE} AS estimated_savings
      FROM cohort_assignments c
      JOIN cohort_stats s USING (cohort_zip, cohort_lu, cohort_decade, cohort_sqft_band)
      WHERE c.TotlAppr > s.median_assessment
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
    limit: Optional[int] = None
) -> List[Lead]:
    """Execute the leads query and return Lead objects."""

    query = build_leads_query(
        project=project,
        dataset=dataset,
        min_savings=min_savings,
        exclude_recent_sales_days=exclude_recent_sales_days,
        min_comparables=min_comparables,
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
            num_comparables=int(row.cohort_size),
            year_built=int(row.year_built) if row.year_built else None,
            sqft=float(row.finished_area) if row.finished_area else None,
            land_use=row.LUDesc or "",
            zip_code=row.PropZip or "",
            cohort_decade=int(row.cohort_decade) if row.cohort_decade else None,
            cohort_sqft_band=int(row.cohort_sqft_band) if row.cohort_sqft_band else None,
            in_flood_zone=bool(row.in_flood_zone),
        )
        leads.append(lead)

    return leads


def format_csv(leads: List[Lead]) -> str:
    """Format leads as CSV."""
    if not leads:
        return ""

    output = []
    fieldnames = [
        "parid", "address", "owner_name", "owner_address",
        "current_assessment", "median_comparable", "over_assessment",
        "estimated_savings", "num_comparables", "year_built", "sqft", "land_use",
        "in_flood_zone"
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
            "year_built": lead.year_built if lead.year_built else "",
            "sqft": f"{lead.sqft:.0f}" if lead.sqft else "",
            "land_use": lead.land_use,
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
    # Generate leads with $200 minimum savings (default)
    python generate_leads.py --output leads.csv

    # Generate leads with $500 minimum savings
    python generate_leads.py --min-savings 500 --output premium_leads.csv

    # Output JSON format with limit
    python generate_leads.py --format json --limit 100 --output leads.json
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
        "--min-comparables",
        type=int,
        default=DEFAULT_MIN_COMPARABLES,
        help=f"Minimum cohort size for reliable median (default: {DEFAULT_MIN_COMPARABLES})"
    )
    parser.add_argument(
        "--exclude-recent-sales",
        type=int,
        default=DEFAULT_EXCLUDE_RECENT_SALES,
        help=f"Exclude properties sold within N days (default: {DEFAULT_EXCLUDE_RECENT_SALES})"
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
            limit=args.limit
        )
        print(query)
        return

    # Initialize BigQuery client
    print(f"Connecting to BigQuery project: {args.project}", file=sys.stderr)
    client = bigquery.Client(project=args.project)

    # Fetch leads
    print(f"Finding leads with minimum savings >= ${args.min_savings:.0f}...", file=sys.stderr)
    leads = fetch_leads(
        client=client,
        project=args.project,
        dataset=args.dataset,
        min_savings=args.min_savings,
        exclude_recent_sales_days=args.exclude_recent_sales,
        min_comparables=args.min_comparables,
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
