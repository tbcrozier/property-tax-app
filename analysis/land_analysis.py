#!/usr/bin/env python3
"""
Belle Meade Land Assessment Analysis.

Identifies parcels where land is assessed higher or lower than expected
based on parcel characteristics (acreage, front footage, lot shape, flood zone).

Uses regression modeling to predict expected land value and ranks properties
by their deviation from expected values.

Usage:
    python land_analysis.py --output land_leads.csv
    python land_analysis.py --min-overassessment 200000 --output premium_land_leads.csv
    python land_analysis.py --format json --limit 100
    python land_analysis.py --tax-district USD --output nashville_land.csv
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, List

from google.cloud import bigquery
import numpy as np

# Configuration defaults
DEFAULT_MIN_OVERASSESSMENT = 100000  # Minimum land over-assessment to qualify
DEFAULT_BQ_PROJECT = "public-data-dev"
DEFAULT_BQ_DATASET = "property_tax"
DEFAULT_TAX_DISTRICT = "BM"  # Belle Meade

# Davidson County tax rate
TAX_RATE = 0.03254
ASSESSMENT_RATIO = 0.25


@dataclass
class LandLead:
    """A property identified as potentially over-assessed on land value."""
    parid: str
    address: str
    owner_name: str
    tax_district: str
    land_use: str

    # Land characteristics
    acres: float
    front_footage: float
    side_footage: float
    is_regular_shape: bool
    in_flood_zone: bool
    zoning: str

    # Assessment values
    land_appraisal: float
    improvement_appraisal: float
    total_appraisal: float

    # Computed metrics
    land_per_acre: float
    land_per_front_ft: float
    predicted_land: float
    land_residual: float
    land_residual_pct: float

    # Size band comparison
    size_band: str
    size_band_median: float
    above_size_band_median: float

    # Potential savings
    estimated_land_savings: float


def build_query(
    project: str,
    dataset: str,
    tax_district: str,
    land_use: Optional[str] = None,
) -> str:
    """Build the SQL query for fetching parcel data."""

    land_use_filter = f"AND p.LUDesc = '{land_use}'" if land_use else ""

    query = f"""
    WITH base_parcels AS (
      SELECT
        p.ParID,
        p.PropAddr,
        p.Owner,
        TRIM(p.TaxDist) as TaxDist,
        p.LUDesc,
        p.Acres,
        p.Front,
        p.Side,
        p.IsRegular,
        p.Zoning,
        p.LandAppr,
        p.ImprAppr,
        p.TotlAppr,
        COALESCE(fz.in_flood_zone, FALSE) as in_flood_zone
      FROM `{project}.{dataset}.davidson_parcels` p
      LEFT JOIN `{project}.{dataset}.v_parcel_floodzone_enrichment` fz
        ON p.ParID = fz.parcel_id
      WHERE TRIM(p.TaxDist) = '{tax_district}'
        AND p.Acres > 0
        AND p.LandAppr > 0
        AND p.Front > 0
        {land_use_filter}
    ),
    size_band_stats AS (
      SELECT
        CASE
          WHEN Acres < 0.75 THEN 'Small (<0.75 ac)'
          WHEN Acres < 1.25 THEN 'Medium (0.75-1.25 ac)'
          WHEN Acres < 2.0 THEN 'Large (1.25-2.0 ac)'
          ELSE 'Estate (2+ ac)'
        END as size_band,
        APPROX_QUANTILES(SAFE_DIVIDE(LandAppr, Acres), 100)[OFFSET(50)] as median_land_per_acre
      FROM base_parcels
      GROUP BY size_band
    )
    SELECT
      p.*,
      SAFE_DIVIDE(p.LandAppr, p.Acres) as land_per_acre,
      SAFE_DIVIDE(p.LandAppr, p.Front) as land_per_front_ft,
      CASE
        WHEN p.Acres < 0.75 THEN 'Small (<0.75 ac)'
        WHEN p.Acres < 1.25 THEN 'Medium (0.75-1.25 ac)'
        WHEN p.Acres < 2.0 THEN 'Large (1.25-2.0 ac)'
        ELSE 'Estate (2+ ac)'
      END as size_band,
      s.median_land_per_acre as size_band_median
    FROM base_parcels p
    JOIN size_band_stats s ON (
      CASE
        WHEN p.Acres < 0.75 THEN 'Small (<0.75 ac)'
        WHEN p.Acres < 1.25 THEN 'Medium (0.75-1.25 ac)'
        WHEN p.Acres < 2.0 THEN 'Large (1.25-2.0 ac)'
        ELSE 'Estate (2+ ac)'
      END = s.size_band
    )
    ORDER BY p.Acres
    """
    return query


def fit_land_model(parcels: list) -> tuple:
    """
    Fit a linear regression model to predict land value.

    Returns:
        tuple: (intercept, coefficients dict, r_squared)
    """
    # Build feature matrix
    X = []
    y = []

    for p in parcels:
        features = [
            p['Acres'],
            p['Front'],
            1 if p['IsRegular'] == 'Y' else 0,
            1 if p['in_flood_zone'] else 0,
        ]
        X.append(features)
        y.append(p['LandAppr'])

    X = np.array(X)
    y = np.array(y)

    # Add intercept column
    X_with_intercept = np.column_stack([np.ones(len(X)), X])

    # Solve least squares: (X'X)^-1 X'y
    coeffs = np.linalg.lstsq(X_with_intercept, y, rcond=None)[0]

    # Calculate R-squared
    y_pred = X_with_intercept @ coeffs
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot)

    intercept = coeffs[0]
    coef_dict = {
        'Acres': coeffs[1],
        'Front': coeffs[2],
        'IsRegular': coeffs[3],
        'InFloodZone': coeffs[4],
    }

    return intercept, coef_dict, r_squared


def predict_land_value(parcel: dict, intercept: float, coeffs: dict) -> float:
    """Predict land value for a parcel using the fitted model."""
    return (
        intercept
        + coeffs['Acres'] * parcel['Acres']
        + coeffs['Front'] * parcel['Front']
        + coeffs['IsRegular'] * (1 if parcel['IsRegular'] == 'Y' else 0)
        + coeffs['InFloodZone'] * (1 if parcel['in_flood_zone'] else 0)
    )


def fetch_and_analyze(
    client: bigquery.Client,
    project: str,
    dataset: str,
    tax_district: str,
    land_use: Optional[str],
    min_overassessment: float,
    limit: Optional[int] = None
) -> tuple:
    """
    Fetch parcel data and perform land assessment analysis.

    Returns:
        tuple: (list of LandLead objects, model stats dict)
    """
    query = build_query(project, dataset, tax_district, land_use)

    print(f"Fetching parcels from {project}.{dataset}...", file=sys.stderr)
    results = list(client.query(query).result())

    if not results:
        return [], {}

    # Convert to list of dicts for easier processing
    parcels = []
    for row in results:
        parcels.append({
            'ParID': str(row.ParID),
            'PropAddr': row.PropAddr or "",
            'Owner': row.Owner or "",
            'TaxDist': row.TaxDist or "",
            'LUDesc': row.LUDesc or "",
            'Acres': float(row.Acres) if row.Acres else 0,
            'Front': float(row.Front) if row.Front else 0,
            'Side': float(row.Side) if row.Side else 0,
            'IsRegular': row.IsRegular or "N",
            'Zoning': row.Zoning or "",
            'LandAppr': float(row.LandAppr) if row.LandAppr else 0,
            'ImprAppr': float(row.ImprAppr) if row.ImprAppr else 0,
            'TotlAppr': float(row.TotlAppr) if row.TotlAppr else 0,
            'in_flood_zone': bool(row.in_flood_zone),
            'land_per_acre': float(row.land_per_acre) if row.land_per_acre else 0,
            'land_per_front_ft': float(row.land_per_front_ft) if row.land_per_front_ft else 0,
            'size_band': row.size_band,
            'size_band_median': float(row.size_band_median) if row.size_band_median else 0,
        })

    print(f"Found {len(parcels)} parcels", file=sys.stderr)

    # Fit regression model
    print("Fitting land value model...", file=sys.stderr)
    intercept, coeffs, r_squared = fit_land_model(parcels)

    model_stats = {
        'intercept': intercept,
        'coefficients': coeffs,
        'r_squared': r_squared,
        'total_parcels': len(parcels),
    }

    # Calculate predictions and residuals
    leads = []
    for p in parcels:
        predicted = predict_land_value(p, intercept, coeffs)
        residual = p['LandAppr'] - predicted
        residual_pct = (residual / predicted * 100) if predicted > 0 else 0
        above_median = p['land_per_acre'] - p['size_band_median']

        # Calculate potential tax savings from land reduction
        estimated_savings = residual * ASSESSMENT_RATIO * TAX_RATE if residual > 0 else 0

        lead = LandLead(
            parid=p['ParID'],
            address=p['PropAddr'],
            owner_name=p['Owner'],
            tax_district=p['TaxDist'],
            land_use=p['LUDesc'],
            acres=p['Acres'],
            front_footage=p['Front'],
            side_footage=p['Side'],
            is_regular_shape=(p['IsRegular'] == 'Y'),
            in_flood_zone=p['in_flood_zone'],
            zoning=p['Zoning'],
            land_appraisal=p['LandAppr'],
            improvement_appraisal=p['ImprAppr'],
            total_appraisal=p['TotlAppr'],
            land_per_acre=p['land_per_acre'],
            land_per_front_ft=p['land_per_front_ft'],
            predicted_land=predicted,
            land_residual=residual,
            land_residual_pct=residual_pct,
            size_band=p['size_band'],
            size_band_median=p['size_band_median'],
            above_size_band_median=above_median,
            estimated_land_savings=estimated_savings,
        )
        leads.append(lead)

    # Filter by minimum over-assessment and sort
    leads = [l for l in leads if l.land_residual >= min_overassessment]
    leads.sort(key=lambda x: x.land_residual, reverse=True)

    if limit:
        leads = leads[:limit]

    return leads, model_stats


def format_csv(leads: List[LandLead]) -> str:
    """Format leads as CSV."""
    if not leads:
        return ""

    import io
    fieldnames = [
        "parid", "address", "owner_name", "tax_district", "land_use",
        "acres", "front_footage", "is_regular_shape", "in_flood_zone",
        "land_appraisal", "predicted_land", "land_residual", "land_residual_pct",
        "size_band", "size_band_median", "above_size_band_median",
        "land_per_acre", "estimated_land_savings"
    ]

    string_io = io.StringIO()
    writer = csv.DictWriter(string_io, fieldnames=fieldnames)
    writer.writeheader()

    for lead in leads:
        row = {
            "parid": lead.parid,
            "address": lead.address,
            "owner_name": lead.owner_name,
            "tax_district": lead.tax_district,
            "land_use": lead.land_use,
            "acres": f"{lead.acres:.2f}",
            "front_footage": f"{lead.front_footage:.0f}",
            "is_regular_shape": "Yes" if lead.is_regular_shape else "No",
            "in_flood_zone": "Yes" if lead.in_flood_zone else "No",
            "land_appraisal": f"{lead.land_appraisal:.0f}",
            "predicted_land": f"{lead.predicted_land:.0f}",
            "land_residual": f"{lead.land_residual:.0f}",
            "land_residual_pct": f"{lead.land_residual_pct:.1f}",
            "size_band": lead.size_band,
            "size_band_median": f"{lead.size_band_median:.0f}",
            "above_size_band_median": f"{lead.above_size_band_median:.0f}",
            "land_per_acre": f"{lead.land_per_acre:.0f}",
            "estimated_land_savings": f"{lead.estimated_land_savings:.2f}",
        }
        writer.writerow(row)

    return string_io.getvalue()


def format_json(leads: List[LandLead], model_stats: dict) -> str:
    """Format leads as JSON."""
    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "model": {
            "r_squared": round(model_stats.get('r_squared', 0), 4),
            "intercept": round(model_stats.get('intercept', 0), 2),
            "coefficients": {k: round(v, 2) for k, v in model_stats.get('coefficients', {}).items()},
            "total_parcels_analyzed": model_stats.get('total_parcels', 0),
        },
        "total_leads": len(leads),
        "leads": [asdict(lead) for lead in leads]
    }
    return json.dumps(data, indent=2)


def print_summary(leads: List[LandLead], model_stats: dict, file=sys.stderr):
    """Print a summary of the analysis."""
    print("", file=file)
    print("=" * 70, file=file)
    print("              LAND ASSESSMENT ANALYSIS SUMMARY", file=file)
    print("=" * 70, file=file)

    # Model info
    print(f"\nRegression Model (R² = {model_stats.get('r_squared', 0):.3f}):", file=file)
    print(f"  LandAppr = {model_stats.get('intercept', 0):,.0f}", file=file)
    for name, coef in model_stats.get('coefficients', {}).items():
        print(f"           + {coef:,.0f} * {name}", file=file)

    if not leads:
        print("\nNo leads found matching criteria.", file=file)
        return

    total_overassessment = sum(lead.land_residual for lead in leads)
    total_savings = sum(lead.estimated_land_savings for lead in leads)
    avg_residual = total_overassessment / len(leads)
    max_residual = max(lead.land_residual for lead in leads)

    print(f"\n  Parcels Analyzed:         {model_stats.get('total_parcels', 0):,}", file=file)
    print(f"  Over-Assessed Leads:      {len(leads):,}", file=file)
    print(f"  Total Over-Assessment:    ${total_overassessment:,.0f}", file=file)
    print(f"  Total Potential Savings:  ${total_savings:,.2f}", file=file)
    print(f"  Avg Over-Assessment:      ${avg_residual:,.0f}", file=file)
    print(f"  Max Over-Assessment:      ${max_residual:,.0f}", file=file)
    print("=" * 70, file=file)

    # Top 10 preview
    print("\nTop 10 Over-Assessed Land Parcels:", file=file)
    print("-" * 70, file=file)
    for i, lead in enumerate(leads[:10], 1):
        print(f"  {i:2}. ${lead.land_residual:>10,.0f} ({lead.land_residual_pct:+5.0f}%) | {lead.address[:35]:<35}", file=file)
    print("", file=file)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze land assessments and identify over-assessed parcels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze Belle Meade (default)
    python land_analysis.py --output belle_meade_land.csv

    # Filter by minimum over-assessment
    python land_analysis.py --min-overassessment 500000 --output high_value_leads.csv

    # Analyze different tax district
    python land_analysis.py --tax-district USD --land-use "SINGLE FAMILY" --output nashville_sf.csv

    # Output JSON with model details
    python land_analysis.py --format json --output analysis.json
        """
    )

    # Analysis parameters
    parser.add_argument(
        "--tax-district",
        type=str,
        default=DEFAULT_TAX_DISTRICT,
        help=f"Tax district to analyze (default: {DEFAULT_TAX_DISTRICT} for Belle Meade)"
    )
    parser.add_argument(
        "--land-use",
        type=str,
        default="SINGLE FAMILY",
        help="Land use type to filter (default: SINGLE FAMILY, use 'all' for no filter)"
    )
    parser.add_argument(
        "--min-overassessment",
        type=float,
        default=DEFAULT_MIN_OVERASSESSMENT,
        help=f"Minimum land over-assessment to qualify as lead (default: ${DEFAULT_MIN_OVERASSESSMENT:,})"
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

    # Handle 'all' land use
    land_use = None if args.land_use.lower() == 'all' else args.land_use

    # Show query mode
    if args.show_query:
        query = build_query(args.project, args.dataset, args.tax_district, land_use)
        print(query)
        return

    # Initialize BigQuery client
    print(f"Connecting to BigQuery project: {args.project}", file=sys.stderr)
    client = bigquery.Client(project=args.project)

    # Fetch and analyze
    print(f"Analyzing land assessments in tax district: {args.tax_district}", file=sys.stderr)
    leads, model_stats = fetch_and_analyze(
        client=client,
        project=args.project,
        dataset=args.dataset,
        tax_district=args.tax_district,
        land_use=land_use,
        min_overassessment=args.min_overassessment,
        limit=args.limit
    )

    print(f"Found {len(leads):,} over-assessed parcels", file=sys.stderr)

    # Print summary
    print_summary(leads, model_stats)

    # Format output
    if args.format == "json":
        output = format_json(leads, model_stats)
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
