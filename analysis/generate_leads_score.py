#!/usr/bin/env python3
"""
Davidson County Appeal Lead Generator with Appeal Scoring.

Identifies Single Family properties where:
1. Cohort-based analysis suggests over-assessment (generate_leads approach)
2. Statistical scoring confirms strong appeal case (v_appeal_candidates approach)
3. Recent sales data validates the over-assessment (v_assessment_sale_ratio)

Combines two independent validation signals:
- generate_leads: "will we make money?" (acquisition economics)
- v_appeal_candidates: "should this appeal?" (statistical rigor)

When both signals agree → high confidence lead.

Usage:
    python3 generate_leads_score.py --output leads_with_scores.csv
    python3 generate_leads_score.py --min-savings 500 --min-appeal-score 40 --output premium_leads.csv
    python3 generate_leads_score.py --format json --limit 200
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
DEFAULT_MIN_SAVINGS = 200
DEFAULT_MIN_APPEAL_SCORE = 30
DEFAULT_BQ_PROJECT = "public-data-dev"
DEFAULT_BQ_DATASET = "property_tax"

# Davidson County tax rate (3.254% per $100 of assessed value = 0.03254)
TAX_RATE = 0.03254
ASSESSMENT_RATIO = 0.25


@dataclass
class ScoredLead:
    """A property with both cohort and appeal scores."""
    parid: str
    address: str
    owner_name: str
    owner_address: str
    land_use: str
    zip_code: str
    
    # Cohort-based signals (from generate_leads logic)
    current_assessment: float
    cohort_median: float
    over_assessment: float
    estimated_savings: float
    cohort_size: int
    
    # Appeal-based signals (from v_appeal_candidates)
    appeal_strength_score: float
    land_use_z_score: float
    pct_above_zip_median: float
    pct_above_lu_median: float
    appeal_recommendation: str
    
    # Sale-based signals (from v_assessment_sale_ratio)
    recent_sale_price: Optional[float]
    assessment_sale_ratio: Optional[float]
    sale_ratio_flag: Optional[str]  # OVER_ASSESSED, UNDER_ASSESSED, FAIR
    
    # Building characteristics
    year_built: Optional[int]
    finished_area: Optional[float]
    
    # Combined confidence signal
    confidence_level: str  # HIGH, MODERATE, LOW
    combined_score: float  # 0-100, weighted average


def build_scored_leads_query(
    project: str,
    dataset: str,
) -> str:
    """Build the SQL query for finding and scoring appeal leads."""

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
        b.finished_area
      FROM `{project}.{dataset}.davidson_parcels` p
      LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b ON p.STANPAR = b.apn
      WHERE p.TotlAppr > 0
        AND p.LUDesc = 'SINGLE FAMILY'
    ),
    cohort_assignments AS (
      SELECT *,
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
      HAVING COUNT(*) >= 5
    ),
    cohort_leads AS (
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
        s.median_assessment,
        s.cohort_size,
        c.TotlAppr - s.median_assessment AS over_assessment,
        (c.TotlAppr - s.median_assessment) * {ASSESSMENT_RATIO} * {TAX_RATE} AS estimated_savings,
        c.SalePrice,
        FORMAT_DATE('%Y-%m-%d', c.OwnDate) as sale_date
      FROM cohort_assignments c
      JOIN cohort_stats s USING (cohort_zip, cohort_lu, cohort_decade, cohort_sqft_band)
      WHERE c.TotlAppr > s.median_assessment
    )
    -- Join cohort leads to appeal candidates for scoring
    SELECT
      cl.ParID,
      cl.PropAddr,
      cl.PropZip,
      cl.LUDesc,
      cl.TotlAppr,
      cl.Owner,
      cl.OwnAddr1,
      cl.OwnCity,
      cl.OwnState,
      cl.OwnZip,
      cl.year_built,
      cl.finished_area,
      cl.median_assessment,
      cl.cohort_size,
      cl.over_assessment,
      cl.estimated_savings,
      cl.SalePrice,
      cl.sale_date,
      -- Appeal scores
      ac.appeal_strength_score,
      ac.land_use_z_score,
      ac.pct_above_zip_median,
      ac.pct_above_lu_median,
      ac.appeal_recommendation,
      -- Sale ratio signals
      asr.assessment_ratio,
      asr.ratio_flag
    FROM cohort_leads cl
    LEFT JOIN `{project}.{dataset}.v_appeal_candidates` ac
      ON cl.ParID = ac.ParID
    LEFT JOIN `{project}.{dataset}.v_assessment_sale_ratio` asr
      ON cl.ParID = asr.ParID
    ORDER BY cl.estimated_savings DESC
    """
    return query


def fetch_scored_leads(
    client: bigquery.Client,
    project: str,
    dataset: str,
) -> List[dict]:
    """Execute the scored leads query and return raw rows."""

    query = build_scored_leads_query(project, dataset)
    print(f"Executing query against {project}.{dataset}...", file=sys.stderr)
    results = client.query(query).result()
    return [dict(row) for row in results]


def calculate_confidence_and_combined_score(row: dict) -> tuple:
    """
    Calculate confidence level and combined score based on both signals.
    
    Returns: (confidence_level: str, combined_score: float)
    """
    savings = row.get('estimated_savings', 0) or 0
    appeal_score = row.get('appeal_strength_score') or 0
    assessment_ratio = row.get('assessment_ratio') or 1.0
    
    signals = []
    
    # Signal 1: Cohort-based savings (0-40 points)
    if savings >= 1000:
        signals.append(40)
    elif savings >= 500:
        signals.append(30)
    elif savings >= 200:
        signals.append(20)
    else:
        signals.append(10)
    
    # Signal 2: Appeal strength score (0-40 points)
    # appeal_score is already 0-100, so scale to 0-40
    signals.append(min(40, appeal_score * 0.4))
    
    # Signal 3: Sale ratio validation (0-20 points)
    # If assessment > 20% above recent sale, strong signal
    if assessment_ratio and assessment_ratio > 1.20:
        signals.append(20)
    elif assessment_ratio and assessment_ratio > 1.10:
        signals.append(15)
    elif assessment_ratio and assessment_ratio > 1.05:
        signals.append(10)
    else:
        signals.append(0)
    
    combined_score = sum(signals)
    
    # Determine confidence level
    if combined_score >= 70:
        confidence = "HIGH"
    elif combined_score >= 50:
        confidence = "MODERATE"
    else:
        confidence = "LOW"
    
    return confidence, combined_score


def build_scored_leads(
    raw_rows: List[dict],
    min_savings: float = DEFAULT_MIN_SAVINGS,
    min_appeal_score: float = DEFAULT_MIN_APPEAL_SCORE,
) -> List[ScoredLead]:
    """Convert raw query results to ScoredLead objects with filtering."""

    leads = []
    for row in raw_rows:
        savings = row.get('estimated_savings') or 0
        appeal_score = row.get('appeal_strength_score') or 0
        
        # Filter: must meet minimum thresholds
        if savings < min_savings:
            continue
        if appeal_score is not None and appeal_score < min_appeal_score:
            continue
        
        # Build owner address
        owner_parts = []
        if row.get('OwnAddr1'):
            owner_parts.append(row['OwnAddr1'])
        city_state_zip = []
        if row.get('OwnCity'):
            city_state_zip.append(row['OwnCity'])
        if row.get('OwnState'):
            city_state_zip.append(row['OwnState'])
        if row.get('OwnZip'):
            city_state_zip.append(str(row['OwnZip']))
        if city_state_zip:
            owner_parts.append(", ".join(city_state_zip))
        owner_address = ", ".join(owner_parts) if owner_parts else ""
        
        # Calculate confidence and combined score
        confidence, combined_score = calculate_confidence_and_combined_score(row)
        
        lead = ScoredLead(
            parid=str(row.get('ParID', '')),
            address=row.get('PropAddr', ''),
            owner_name=row.get('Owner', ''),
            owner_address=owner_address,
            land_use=row.get('LUDesc', ''),
            zip_code=row.get('PropZip', ''),
            current_assessment=float(row.get('TotlAppr', 0)),
            cohort_median=float(row.get('median_assessment', 0)),
            over_assessment=float(row.get('over_assessment', 0)),
            estimated_savings=float(savings),
            cohort_size=int(row.get('cohort_size', 0)),
            appeal_strength_score=float(appeal_score) if appeal_score else None,
            land_use_z_score=float(row.get('land_use_z_score', 0)) if row.get('land_use_z_score') else None,
            pct_above_zip_median=float(row.get('pct_above_zip_median', 0)) if row.get('pct_above_zip_median') else None,
            pct_above_lu_median=float(row.get('pct_above_lu_median', 0)) if row.get('pct_above_lu_median') else None,
            appeal_recommendation=row.get('appeal_recommendation', ''),
            recent_sale_price=float(row.get('SalePrice')) if row.get('SalePrice') else None,
            assessment_sale_ratio=float(row.get('assessment_ratio')) if row.get('assessment_ratio') else None,
            sale_ratio_flag=row.get('ratio_flag'),
            year_built=int(row.get('year_built')) if row.get('year_built') else None,
            finished_area=float(row.get('finished_area')) if row.get('finished_area') else None,
            confidence_level=confidence,
            combined_score=round(combined_score, 1),
        )
        leads.append(lead)
    
    return leads


def format_csv(leads: List[ScoredLead]) -> str:
    """Format leads as CSV."""
    if not leads:
        return ""

    import io
    string_io = io.StringIO()
    fieldnames = [
        "parid", "address", "owner_name", "owner_address",
        "land_use", "zip_code",
        "current_assessment", "cohort_median", "over_assessment", "estimated_savings",
        "cohort_size",
        "appeal_strength_score", "land_use_z_score", "pct_above_zip_median",
        "recent_sale_price", "assessment_sale_ratio", "sale_ratio_flag",
        "year_built", "finished_area",
        "confidence_level", "combined_score"
    ]

    writer = csv.DictWriter(string_io, fieldnames=fieldnames)
    writer.writeheader()

    for lead in leads:
        row = {
            "parid": lead.parid,
            "address": lead.address,
            "owner_name": lead.owner_name,
            "owner_address": lead.owner_address,
            "land_use": lead.land_use,
            "zip_code": lead.zip_code,
            "current_assessment": f"{lead.current_assessment:.0f}",
            "cohort_median": f"{lead.cohort_median:.0f}",
            "over_assessment": f"{lead.over_assessment:.0f}",
            "estimated_savings": f"{lead.estimated_savings:.2f}",
            "cohort_size": lead.cohort_size,
            "appeal_strength_score": f"{lead.appeal_strength_score:.1f}" if lead.appeal_strength_score else "",
            "land_use_z_score": f"{lead.land_use_z_score:.2f}" if lead.land_use_z_score else "",
            "pct_above_zip_median": f"{lead.pct_above_zip_median:.1f}" if lead.pct_above_zip_median else "",
            "recent_sale_price": f"{lead.recent_sale_price:.0f}" if lead.recent_sale_price else "",
            "assessment_sale_ratio": f"{lead.assessment_sale_ratio:.3f}" if lead.assessment_sale_ratio else "",
            "sale_ratio_flag": lead.sale_ratio_flag or "",
            "year_built": lead.year_built if lead.year_built else "",
            "finished_area": f"{lead.finished_area:.0f}" if lead.finished_area else "",
            "confidence_level": lead.confidence_level,
            "combined_score": lead.combined_score,
        }
        writer.writerow(row)

    return string_io.getvalue()


def format_json(leads: List[ScoredLead]) -> str:
    """Format leads as JSON."""
    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_leads": len(leads),
        "high_confidence": len([l for l in leads if l.confidence_level == "HIGH"]),
        "moderate_confidence": len([l for l in leads if l.confidence_level == "MODERATE"]),
        "low_confidence": len([l for l in leads if l.confidence_level == "LOW"]),
        "leads": [asdict(lead) for lead in leads]
    }
    return json.dumps(data, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Single Family appeal leads with dual scoring (cohort + appeal)"
    )

    parser.add_argument(
        "--min-savings",
        type=float,
        default=DEFAULT_MIN_SAVINGS,
        help=f"Minimum estimated annual savings (default: {DEFAULT_MIN_SAVINGS})"
    )
    parser.add_argument(
        "--min-appeal-score",
        type=float,
        default=DEFAULT_MIN_APPEAL_SCORE,
        help=f"Minimum appeal strength score 0-100 (default: {DEFAULT_MIN_APPEAL_SCORE})"
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
        help="Maximum number of leads to return"
    )
    parser.add_argument(
        "--confidence",
        choices=["HIGH", "MODERATE", "LOW"],
        help="Filter by confidence level (HIGH, MODERATE, or LOW). If not specified, shows all."
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: stdout)"
    )
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

    args = parser.parse_args()

    # Initialize BigQuery client
    client = bigquery.Client(project=args.project)

    # Fetch raw leads
    raw_leads = fetch_scored_leads(client, args.project, args.dataset)
    print(f"Found {len(raw_leads)} raw candidates", file=sys.stderr)

    # Build scored leads with filtering
    leads = build_scored_leads(
        raw_leads,
        min_savings=args.min_savings,
        min_appeal_score=args.min_appeal_score
    )
    
    # Filter by confidence level if specified
    if args.confidence:
        leads = [l for l in leads if l.confidence_level == args.confidence]
    
    if args.limit:
        leads = leads[:args.limit]

    print(f"Filtered to {len(leads)} leads after scoring", file=sys.stderr)
    
    # Print summary
    high = len([l for l in leads if l.confidence_level == "HIGH"])
    moderate = len([l for l in leads if l.confidence_level == "MODERATE"])
    low = len([l for l in leads if l.confidence_level == "LOW"])
    print(f"  HIGH confidence: {high}", file=sys.stderr)
    print(f"  MODERATE confidence: {moderate}", file=sys.stderr)
    print(f"  LOW confidence: {low}", file=sys.stderr)

    # Format output
    if args.format == "json":
        output = format_json(leads)
    else:
        output = format_csv(leads)

    # Write output
    from pathlib import Path
    
    if args.output:
        output_path = Path(args.output)
    else:
        # Default: save to tests/ folder (at workspace root) with timestamp
        script_dir = Path(__file__).parent  # analysis/
        workspace_root = script_dir.parent   # workspace root
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        extension = "json" if args.format == "json" else "csv"
        output_path = workspace_root / "tests" / f"leads_{timestamp}.{extension}"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output)
    print(f"Report saved to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
