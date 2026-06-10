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
DEFAULT_MIN_SAVINGS = 1000
DEFAULT_YEAR_RANGE = 10
DEFAULT_SQFT_RANGE = 20
DEFAULT_ACREAGE_RANGE = 10
DEFAULT_MAX_DISTANCE = 3.0
DEFAULT_BED_RANGE = 1
DEFAULT_BATH_RANGE = 1
DEFAULT_MIN_COMPARABLES = 3
DEFAULT_EXCLUDE_RECENT_SALES = 730
DEFAULT_COMP_YEAR_START = 2025
DEFAULT_COMP_YEAR_END = 2025
DEFAULT_MIN_COMP_SALE_PRICE = 100000
DEFAULT_BQ_PROJECT = "public-data-dev"
DEFAULT_BQ_DATASET = "property_tax"

TAX_RATE = 0.03254
ASSESSMENT_RATIO = 0.25

# Tight thresholds for the exact (first) pass before falling back to configured values
EXACT_SQFT_RANGE = 15       # ±15% sqft  (fallback: --sqft-range, default 20%)
EXACT_YEAR_RANGE = 7        # ±7 years   (fallback: --year-range, default 10)
EXACT_MAX_DISTANCE = 2.0    # 2.0 miles  (fallback: --max-distance, default 3.0)
EXACT_ACREAGE_RANGE = 10    # ±10% acres (same as fallback default)
# Beds/baths: always exact=0 in the first pass; fallback uses --bed-range / --bath-range


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
    pct_over_median: float  # % the assessment exceeds comp median sale price
    match_type: str  # "exact" = strict bed/bath match, "fallback" = ±1 bed/bath used


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

    # Fallback (loose) pass factors — controlled by CLI params
    sqft_min_factor = 1 - (sqft_range / 100)
    sqft_max_factor = 1 + (sqft_range / 100)
    acreage_min_factor = 1 - (acreage_range / 100)
    acreage_max_factor = 1 + (acreage_range / 100)
    max_distance_meters = max_distance * 1609.34
    comp_year_end_exclusive = comp_year_end + 1
    # Exact (tight) pass factors — from EXACT_* constants
    exact_sqft_min_factor = 1 - (EXACT_SQFT_RANGE / 100)
    exact_sqft_max_factor = 1 + (EXACT_SQFT_RANGE / 100)
    exact_acreage_min_factor = 1 - (EXACT_ACREAGE_RANGE / 100)
    exact_acreage_max_factor = 1 + (EXACT_ACREAGE_RANGE / 100)
    exact_max_distance_meters = EXACT_MAX_DISTANCE * 1609.34

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
      LEFT JOIN (
        SELECT apn, ANY_VALUE(year_built) AS year_built, ANY_VALUE(finished_area) AS finished_area
        FROM `{project}.{dataset}.davidson_building_characteristics`
        GROUP BY apn
        HAVING COUNT(*) = 1
      ) b ON p.STANPAR = b.apn
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
      LEFT JOIN (
        SELECT apn, ANY_VALUE(year_built) AS year_built, ANY_VALUE(finished_area) AS finished_area
        FROM `{project}.{dataset}.davidson_building_characteristics`
        GROUP BY apn
        HAVING COUNT(*) = 1
      ) b ON p.STANPAR = b.apn
      LEFT JOIN `{project}.{dataset}.davidson_bed_bath` bb ON p.ParID = bb.parcel_id
      WHERE p.LUDesc = 'SINGLE FAMILY'
        AND p.Lat IS NOT NULL AND p.Lon IS NOT NULL
        AND b.year_built IS NOT NULL AND b.finished_area IS NOT NULL
        AND p.OwnDate >= '{comp_year_start}-01-01'
        AND p.OwnDate < '{comp_year_end_exclusive}-01-01'
        AND p.SalePrice >= {min_comp_sale_price}
    ),
    exact_comps AS (
      -- Pass 1: strict exact match on beds and baths
      SELECT
        p.ParID,
        c.ParID AS comp_parid,
        c.sale_price AS comp_sale_price,
        p.has_bed_bath_data,
        ST_DISTANCE(ST_GEOGPOINT(p.Lon, p.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) / 1609.34 AS distance_miles,
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
        AND ST_DISTANCE(ST_GEOGPOINT(p.Lon, p.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) <= {exact_max_distance_meters}
        AND c.finished_area BETWEEN p.finished_area * {exact_sqft_min_factor} AND p.finished_area * {exact_sqft_max_factor}
        AND c.year_built BETWEEN p.year_built - {EXACT_YEAR_RANGE} AND p.year_built + {EXACT_YEAR_RANGE}
        AND (
          p.Acres IS NULL OR p.Acres = 0 OR c.Acres IS NULL OR c.Acres = 0
          OR c.Acres BETWEEN p.Acres * {exact_acreage_min_factor} AND p.Acres * {exact_acreage_max_factor}
        )
        AND (p.beds IS NULL OR c.beds IS NULL OR c.beds = p.beds)
        AND (p.total_baths IS NULL OR c.total_baths IS NULL OR c.total_baths = p.total_baths)
    ),
    fallback_comps AS (
      -- Pass 2: relaxed ±bed_range/bath_range, used only when exact finds < min_comparables
      -- Includes exact-match comps so the full set is available when falling back
      SELECT
        p.ParID,
        c.ParID AS comp_parid,
        c.sale_price AS comp_sale_price,
        p.has_bed_bath_data,
        ST_DISTANCE(ST_GEOGPOINT(p.Lon, p.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) / 1609.34 AS distance_miles,
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
    exact_counts AS (
      SELECT ParID, COUNT(*) AS n FROM exact_comps GROUP BY ParID
    ),
    combined_comps AS (
      -- Use exact comps for properties that found enough; fall back to ±1 for the rest
      SELECT ec.*, 'exact' AS match_type
      FROM exact_comps ec
      JOIN exact_counts cn USING (ParID)
      WHERE cn.n >= {min_comparables}

      UNION ALL

      SELECT fc.*, 'fallback' AS match_type
      FROM fallback_comps fc
      LEFT JOIN exact_counts cn ON fc.ParID = cn.ParID
      WHERE COALESCE(cn.n, 0) < {min_comparables}
    ),
    ranked_comps AS (
      SELECT *,
        ROW_NUMBER() OVER (PARTITION BY ParID ORDER BY similarity_score) AS rank,
        COUNT(*) OVER (PARTITION BY ParID) AS total_comps
      FROM combined_comps
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
        LOGICAL_OR(has_bed_bath_data) AS has_bed_bath_data,
        ANY_VALUE(match_type) AS match_type
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
        s.match_type,
        p.TotlAppr - s.median_sale_price AS over_assessment,
        (p.TotlAppr - s.median_sale_price) / s.median_sale_price * 100 AS pct_over_median,
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


def build_debug_query(
    parid: str,
    project: str,
    dataset: str,
    comp_year_start: int,
    comp_year_end: int,
    min_comp_sale_price: float,
    min_comparables: int,
    sqft_range: int,
    year_range: int,
    acreage_range: int,
    max_distance: float,
    bed_range: int,
    bath_range: int,
) -> str:
    """Build a two-pass query that returns the exact comps used for a single property,
    with match_type indicating whether exact or fallback criteria were applied."""

    sqft_min_factor = 1 - (sqft_range / 100)
    sqft_max_factor = 1 + (sqft_range / 100)
    acreage_min_factor = 1 - (acreage_range / 100)
    acreage_max_factor = 1 + (acreage_range / 100)
    max_distance_meters = max_distance * 1609.34
    comp_year_end_exclusive = comp_year_end + 1
    exact_sqft_min_factor = 1 - (EXACT_SQFT_RANGE / 100)
    exact_sqft_max_factor = 1 + (EXACT_SQFT_RANGE / 100)
    exact_acreage_min_factor = 1 - (EXACT_ACREAGE_RANGE / 100)
    exact_acreage_max_factor = 1 + (EXACT_ACREAGE_RANGE / 100)
    exact_max_distance_meters = EXACT_MAX_DISTANCE * 1609.34

    sim_score = f"""
      ABS(s.year_built - c.year_built) / {year_range} * 0.20 +
      ABS(s.finished_area - c.finished_area) / NULLIF(s.finished_area, 0) * 0.25 +
      CASE
        WHEN s.Acres IS NULL OR s.Acres = 0 OR c.Acres IS NULL OR c.Acres = 0 THEN 0
        ELSE ABS(s.Acres - c.Acres) / NULLIF(s.Acres, 0) * 0.15
      END +
      ST_DISTANCE(ST_GEOGPOINT(s.Lon, s.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) / {max_distance_meters} * 0.20 +
      CASE WHEN s.beds IS NULL OR c.beds IS NULL THEN 0.05
           ELSE ABS(s.beds - c.beds) / GREATEST(s.beds, 1) * 0.10 END +
      CASE WHEN s.total_baths IS NULL OR c.total_baths IS NULL THEN 0.05
           ELSE ABS(s.total_baths - c.total_baths) / GREATEST(s.total_baths, 1) * 0.10 END"""

    return f"""
    WITH subject AS (
      SELECT
        p.ParID, p.PropAddr, p.PropZip, p.LUDesc, p.TotlAppr,
        p.Lat, p.Lon, p.Acres,
        b.year_built, b.finished_area,
        bb.beds,
        COALESCE(bb.baths, 0) + COALESCE(bb.half_baths, 0) * 0.5 AS total_baths
      FROM `{project}.{dataset}.davidson_parcels` p
      LEFT JOIN (
        SELECT apn, ANY_VALUE(year_built) AS year_built, ANY_VALUE(finished_area) AS finished_area
        FROM `{project}.{dataset}.davidson_building_characteristics`
        GROUP BY apn
        HAVING COUNT(*) = 1
      ) b ON p.STANPAR = b.apn
      LEFT JOIN `{project}.{dataset}.davidson_bed_bath` bb ON p.ParID = bb.parcel_id
      WHERE p.ParID = '{parid}'
    ),
    recent_sales AS (
      SELECT
        p.ParID, p.PropAddr, p.LUDesc,
        p.TotlAppr AS comp_assessment,
        p.SalePrice AS sale_price,
        FORMAT_DATE('%Y-%m-%d', p.OwnDate) AS sale_date,
        p.Lat, p.Lon, p.Acres,
        b.year_built, b.finished_area,
        bb.beds,
        COALESCE(bb.baths, 0) + COALESCE(bb.half_baths, 0) * 0.5 AS total_baths
      FROM `{project}.{dataset}.davidson_parcels` p
      LEFT JOIN (
        SELECT apn, ANY_VALUE(year_built) AS year_built, ANY_VALUE(finished_area) AS finished_area
        FROM `{project}.{dataset}.davidson_building_characteristics`
        GROUP BY apn
        HAVING COUNT(*) = 1
      ) b ON p.STANPAR = b.apn
      LEFT JOIN `{project}.{dataset}.davidson_bed_bath` bb ON p.ParID = bb.parcel_id
      WHERE p.LUDesc = 'SINGLE FAMILY'
        AND p.Lat IS NOT NULL AND p.Lon IS NOT NULL
        AND b.year_built IS NOT NULL AND b.finished_area IS NOT NULL
        AND p.OwnDate >= '{comp_year_start}-01-01'
        AND p.OwnDate < '{comp_year_end_exclusive}-01-01'
        AND p.SalePrice >= {min_comp_sale_price}
    ),
    exact_candidates AS (
      SELECT c.ParID AS comp_parid, c.PropAddr AS comp_address, c.comp_assessment,
             c.sale_price, c.sale_date, c.year_built AS comp_year_built,
             c.finished_area AS comp_sqft, c.beds AS comp_beds, c.total_baths AS comp_baths,
             c.Acres AS comp_acres,
             ST_DISTANCE(ST_GEOGPOINT(s.Lon, s.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) / 1609.34 AS distance_miles,
             {sim_score} AS similarity_score
      FROM subject s JOIN recent_sales c ON
        s.LUDesc = c.LUDesc AND s.ParID != c.ParID
        AND ST_DISTANCE(ST_GEOGPOINT(s.Lon, s.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) <= {exact_max_distance_meters}
        AND c.finished_area BETWEEN s.finished_area * {exact_sqft_min_factor} AND s.finished_area * {exact_sqft_max_factor}
        AND c.year_built BETWEEN s.year_built - {EXACT_YEAR_RANGE} AND s.year_built + {EXACT_YEAR_RANGE}
        AND (s.Acres IS NULL OR s.Acres = 0 OR c.Acres IS NULL OR c.Acres = 0
             OR c.Acres BETWEEN s.Acres * {exact_acreage_min_factor} AND s.Acres * {exact_acreage_max_factor})
        AND (s.beds IS NULL OR c.beds IS NULL OR c.beds = s.beds)
        AND (s.total_baths IS NULL OR c.total_baths IS NULL OR c.total_baths = s.total_baths)
    ),
    fallback_candidates AS (
      SELECT c.ParID AS comp_parid, c.PropAddr AS comp_address, c.comp_assessment,
             c.sale_price, c.sale_date, c.year_built AS comp_year_built,
             c.finished_area AS comp_sqft, c.beds AS comp_beds, c.total_baths AS comp_baths,
             c.Acres AS comp_acres,
             ST_DISTANCE(ST_GEOGPOINT(s.Lon, s.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) / 1609.34 AS distance_miles,
             {sim_score} AS similarity_score
      FROM subject s JOIN recent_sales c ON
        s.LUDesc = c.LUDesc AND s.ParID != c.ParID
        AND ST_DISTANCE(ST_GEOGPOINT(s.Lon, s.Lat), ST_GEOGPOINT(c.Lon, c.Lat)) <= {max_distance_meters}
        AND c.finished_area BETWEEN s.finished_area * {sqft_min_factor} AND s.finished_area * {sqft_max_factor}
        AND c.year_built BETWEEN s.year_built - {year_range} AND s.year_built + {year_range}
        AND (s.Acres IS NULL OR s.Acres = 0 OR c.Acres IS NULL OR c.Acres = 0
             OR c.Acres BETWEEN s.Acres * {acreage_min_factor} AND s.Acres * {acreage_max_factor})
        AND (s.beds IS NULL OR c.beds IS NULL
             OR c.beds BETWEEN s.beds - {bed_range} AND s.beds + {bed_range})
        AND (s.total_baths IS NULL OR c.total_baths IS NULL
             OR c.total_baths BETWEEN s.total_baths - {bath_range} AND s.total_baths + {bath_range})
    ),
    exact_count AS (SELECT COUNT(*) AS n FROM exact_candidates),
    combined AS (
      SELECT ec.*, 'exact' AS match_type FROM exact_candidates ec
      CROSS JOIN exact_count cn WHERE cn.n >= {min_comparables}
      UNION ALL
      SELECT fc.*, 'fallback' AS match_type FROM fallback_candidates fc
      CROSS JOIN exact_count cn WHERE cn.n < {min_comparables}
    )
    SELECT * FROM combined ORDER BY similarity_score ASC LIMIT 20
    """


def run_debug_parid(
    client: bigquery.Client,
    parid: str,
    project: str,
    dataset: str,
    comp_year_start: int,
    comp_year_end: int,
    min_comp_sale_price: float,
    min_comparables: int,
    sqft_range: int,
    year_range: int,
    acreage_range: int,
    max_distance: float,
    bed_range: int,
    bath_range: int,
):
    """Print the exact comps used for a single property in generate_leads_v2."""

    # Fetch subject details
    subject_query = f"""
    SELECT p.ParID, p.PropAddr, p.PropZip, p.TotlAppr, p.Acres,
           p.SalePrice, FORMAT_DATE('%Y-%m-%d', p.OwnDate) AS last_sale_date,
           b.year_built, b.finished_area,
           bb.beds,
           COALESCE(bb.baths, 0) + COALESCE(bb.half_baths, 0) * 0.5 AS total_baths
    FROM `{project}.{dataset}.davidson_parcels` p
    LEFT JOIN `{project}.{dataset}.davidson_building_characteristics` b ON p.STANPAR = b.apn
    LEFT JOIN `{project}.{dataset}.davidson_bed_bath` bb ON p.ParID = bb.parcel_id
    WHERE p.ParID = '{parid}'
    LIMIT 1
    """
    subject_rows = list(client.query(subject_query).result())
    if not subject_rows:
        print(f"No property found with ParID {parid}", file=sys.stderr)
        return
    s = subject_rows[0]

    beds_str = str(int(s.beds)) if s.beds else "?"
    baths_str = f"{float(s.total_baths):.1f}" if s.total_baths else "?"
    sqft_str = f"{float(s.finished_area):,.0f}" if s.finished_area else "?"
    acres_str = f"{float(s.Acres):.2f}" if s.Acres else "?"
    last_sale_str = f"${float(s.SalePrice):,.0f} on {s.last_sale_date}" if s.SalePrice and s.last_sale_date else "N/A"

    print("")
    print("=" * 80)
    print("  COMPARABLE DEBUG — generate_leads_v2")
    print("=" * 80)
    print(f"  Subject:     {s.PropAddr}  ({s.PropZip})")
    print(f"  ParID:       {s.ParID}")
    print(f"  Assessment:  ${float(s.TotlAppr):,.0f}")
    print(f"  Last Sale:   {last_sale_str}")
    print(f"  Year Built:  {s.year_built or '?'}")
    print(f"  Sqft:        {sqft_str}")
    print(f"  Acres:       {acres_str}")
    print(f"  Beds/Baths:  {beds_str} bd / {baths_str} ba")
    print(f"  Comp years:  {comp_year_start}–{comp_year_end}  |  Min sale: ${min_comp_sale_price:,.0f}  |  Min comps: {min_comparables}")
    print(f"  Exact pass:  sqft ±{EXACT_SQFT_RANGE}%  |  year ±{EXACT_YEAR_RANGE}  |  dist ≤{EXACT_MAX_DISTANCE} mi  |  beds exact  |  baths exact")
    print(f"  Fallback:    sqft ±{sqft_range}%  |  year ±{year_range}  |  dist ≤{max_distance} mi  |  beds ±{bed_range}  |  baths ±{bath_range}")
    print("=" * 80)

    # Fetch comps
    debug_query = build_debug_query(
        parid=parid, project=project, dataset=dataset,
        comp_year_start=comp_year_start, comp_year_end=comp_year_end,
        min_comp_sale_price=min_comp_sale_price,
        min_comparables=min_comparables,
        sqft_range=sqft_range, year_range=year_range,
        acreage_range=acreage_range, max_distance=max_distance,
        bed_range=bed_range, bath_range=bath_range,
    )
    comps = list(client.query(debug_query).result())

    if not comps:
        print("  No comps found — this property would not appear as a lead.")
        print("=" * 80)
        return

    match_type = comps[0].match_type if comps else "unknown"
    match_label = "EXACT (strict criteria met min comps)" if match_type == "exact" else f"FALLBACK (exact pass had < {min_comparables} comps; loose criteria used)"

    sale_prices = [float(c.sale_price) for c in comps]
    median_sale = sorted(sale_prices)[len(sale_prices) // 2]
    over_assessment = float(s.TotlAppr) - median_sale
    est_savings = over_assessment * ASSESSMENT_RATIO * TAX_RATE

    print(f"  Match type:  {match_label}")
    print(f"  Comps found: {len(comps)}  |  Median sale price: ${median_sale:,.0f}")
    if over_assessment > 0:
        pct_over = over_assessment / median_sale * 100
        print(f"  Over-assessment: ${over_assessment:,.0f}  ({pct_over:.1f}% above comp median)")
        print(f"  Est. 1st-yr savings if reassessed to median: ${est_savings:,.2f}")
    else:
        print(f"  NOT over-assessed vs comp median (would not appear as lead)")
    print("")
    print(f"  {'#':<3} {'Address':<32} {'Assessment':>11}  {'Sale Price':>11}  {'Sale Date':<12} {'Sqft':>6}  {'Year':>5}  {'Bd/Ba':<6}  {'Dist':>8}  {'Sim':>6}  {'Match':<8}")
    print("  " + "-" * 122)
    for i, c in enumerate(comps, 1):
        addr = (c.comp_address[:30] if c.comp_address and len(c.comp_address) > 30 else (c.comp_address or "")).ljust(30)
        sqft = f"{float(c.comp_sqft):,.0f}" if c.comp_sqft else "N/A"
        beds = str(int(c.comp_beds)) if c.comp_beds else "?"
        baths = f"{float(c.comp_baths):.1f}" if c.comp_baths else "?"
        bed_bath = f"{beds}/{baths}"
        dist = f"{float(c.distance_miles):.2f} mi"
        sim = f"{float(c.similarity_score):.3f}"
        date = c.sale_date or "N/A"
        assessment = f"${float(c.comp_assessment):>10,.0f}" if c.comp_assessment else "        N/A"
        row_match = c.match_type or "?"
        print(f"  {i:<3} {addr}  {assessment}  ${float(c.sale_price):>10,.0f}  {date:<12} {sqft:>6}  {c.comp_year_built or '?':>5}  {bed_bath:<6}  {dist:>8}  {sim:>6}  {row_match:<8}")
    print("=" * 80)
    print("")


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
            pct_over_median=float(row.pct_over_median),
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
            match_type=str(row.match_type),
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
        "pct_over_median", "estimated_savings", "num_comparables", "confidence_score",
        "year_built", "sqft", "acreage", "beds", "baths", "land_use",
        "avg_similarity", "avg_comp_distance_miles", "in_flood_zone", "match_type"
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
            "pct_over_median": f"{lead.pct_over_median:.1f}",
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
            "match_type": lead.match_type,
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
        help=f"Bedroom fallback range +/- when exact match finds < min-comparables (default: {DEFAULT_BED_RANGE})"
    )
    parser.add_argument(
        "--bath-range",
        type=int,
        default=DEFAULT_BATH_RANGE,
        help=f"Bathroom fallback range +/- when exact match finds < min-comparables (default: {DEFAULT_BATH_RANGE})"
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
    parser.add_argument(
        "--debug-parid",
        type=str,
        default=None,
        help="Show the exact comps used for a single property (by ParID)"
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

    if args.debug_parid:
        run_debug_parid(
            client=client,
            parid=args.debug_parid,
            project=args.project,
            dataset=args.dataset,
            comp_year_start=args.comp_year_start,
            comp_year_end=args.comp_year_end,
            min_comp_sale_price=args.min_comp_sale_price,
            min_comparables=args.min_comparables,
            sqft_range=args.sqft_range,
            year_range=args.year_range,
            acreage_range=args.acreage_range,
            max_distance=args.max_distance,
            bed_range=args.bed_range,
            bath_range=args.bath_range,
        )
        return

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
