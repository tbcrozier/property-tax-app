"""
Enrichment service — pre-computes spatial relationships and creates SQL views
for assessment analysis.

Spatial tables (parcel_rail_proximity, parcel_flood_zone) follow the same
INSERT...ON CONFLICT pattern as signals_service.py so they can be refreshed
idempotently after data loads.

SQL views (v_assessment_sale_ratio, v_condo_building_stats) are lightweight
PostgreSQL views — the AI queries them directly with simple SELECT statements
instead of generating complex CTEs every time.

Trigger via POST /admin/compute-enrichments after loading parcel data.
Do NOT run at startup — spatial joins are expensive.
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_enrichments_computed = False


# ── SQL Views (non-spatial, fast) ─────────────────────────────────────────────

_VIEW_ASSESSMENT_SALE_RATIO = """
CREATE OR REPLACE VIEW v_assessment_sale_ratio AS
SELECT
    par_id,
    prop_addr,
    prop_zip,
    lu_code,
    lu_desc,
    totl_appr,
    sale_price,
    sale_date,
    ROUND((totl_appr / NULLIF(sale_price, 0))::numeric, 3)     AS assessment_ratio,
    ROUND((totl_appr - sale_price)::numeric, 0)                 AS assessment_excess,
    CASE
        WHEN totl_appr / NULLIF(sale_price, 0) > 1.15 THEN 'OVER_ASSESSED'
        WHEN totl_appr / NULLIF(sale_price, 0) < 0.85 THEN 'UNDER_ASSESSED'
        ELSE 'FAIR'
    END                                                          AS ratio_flag,
    ROUND(GREATEST(0, (totl_appr - sale_price) * 0.25 * 0.028)::numeric, 2)
                                                                 AS potential_annual_savings
FROM parcels
WHERE sale_price > 10000
  AND totl_appr   > 0
"""

_VIEW_CONDO_BUILDING_STATS = """
CREATE OR REPLACE VIEW v_condo_building_stats AS
WITH condos AS (
    SELECT
        par_id,
        prop_addr,
        prop_zip,
        lu_desc,
        totl_appr,
        -- Building key: strip unit/# suffix so all units in same building share a key
        REGEXP_REPLACE(
            UPPER(COALESCE(TRIM(prop_addr), '')),
            '\\s*(#|UNIT|APT|SUITE|STE)\\s+.*$', ''
        ) || '|' || COALESCE(TRIM(prop_zip), '') AS building_key
    FROM parcels
    WHERE lu_desc ILIKE '%condo%'
      AND totl_appr > 0
),
building_stats AS (
    SELECT
        building_key,
        COUNT(*)                                                   AS unit_count,
        AVG(totl_appr)                                             AS building_avg,
        STDDEV(totl_appr)                                          AS building_stddev,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY totl_appr)    AS building_median,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY totl_appr)   AS building_p25,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY totl_appr)   AS building_p75
    FROM condos
    GROUP BY building_key
    HAVING COUNT(*) >= 2
)
SELECT
    c.par_id,
    c.prop_addr,
    c.prop_zip,
    c.lu_desc,
    c.totl_appr,
    c.building_key,
    s.unit_count                                                   AS building_unit_count,
    ROUND(s.building_median::numeric, 2)                           AS building_median,
    ROUND(s.building_avg::numeric, 2)                              AS building_avg,
    ROUND(s.building_p25::numeric, 2)                              AS building_p25,
    ROUND(s.building_p75::numeric, 2)                              AS building_p75,
    ROUND(((c.totl_appr - s.building_avg)
           / NULLIF(s.building_stddev, 0))::numeric, 2)            AS building_z_score,
    ROUND(((c.totl_appr - s.building_median)
           / NULLIF(s.building_median, 0) * 100)::numeric, 1)      AS pct_from_building_median,
    CASE
        WHEN (c.totl_appr - s.building_avg) / NULLIF(s.building_stddev, 0) >  2   THEN 'HIGH_OUTLIER'
        WHEN (c.totl_appr - s.building_avg) / NULLIF(s.building_stddev, 0) >  1.5 THEN 'ABOVE_AVERAGE'
        WHEN (c.totl_appr - s.building_avg) / NULLIF(s.building_stddev, 0) < -2   THEN 'LOW_OUTLIER'
        WHEN (c.totl_appr - s.building_avg) / NULLIF(s.building_stddev, 0) < -1.5 THEN 'BELOW_AVERAGE'
        ELSE 'NORMAL'
    END                                                            AS building_assessment_flag,
    ROUND(GREATEST(0, (c.totl_appr - s.building_median)
                      * 0.25 * 0.028)::numeric, 2)                 AS potential_annual_savings
FROM condos c
JOIN building_stats s ON c.building_key = s.building_key
"""


async def create_views(db: AsyncSession) -> None:
    """Create or replace the assessment analysis SQL views."""
    for sql in (_VIEW_ASSESSMENT_SALE_RATIO, _VIEW_CONDO_BUILDING_STATS):
        await db.execute(text(sql))
    await db.commit()
    logger.info("[ENRICH] Views created: v_assessment_sale_ratio, v_condo_building_stats")


# ── Rail proximity (spatial, pre-computed) ────────────────────────────────────

_RAIL_PROXIMITY_SQL = text("""
INSERT INTO parcel_rail_proximity (
    par_id, nearest_rail_owner, passenger_rail, rail_tracks,
    distance_m, within_100m, within_250m, within_500m, within_1000m, computed_at
)
SELECT
    p.par_id,
    nr.owner,
    nr.passenger_rail,
    nr.tracks,
    nr.distance_m,
    nr.distance_m <= 100                                           AS within_100m,
    nr.distance_m <= 250                                           AS within_250m,
    nr.distance_m <= 500                                           AS within_500m,
    nr.distance_m <= 1000                                          AS within_1000m,
    NOW()
FROM parcels p
CROSS JOIN LATERAL (
    SELECT
        r.owner,
        r.passenger_rail,
        r.tracks,
        ST_Distance(
            ST_Transform(p.location::geometry, 3857),
            ST_Transform(r.geom::geometry, 3857)
        )                                                          AS distance_m
    FROM rail_lines r
    ORDER BY p.location::geometry <-> r.geom::geometry
    LIMIT 1
) nr
WHERE p.location IS NOT NULL
ON CONFLICT (par_id) DO UPDATE SET
    nearest_rail_owner = EXCLUDED.nearest_rail_owner,
    passenger_rail     = EXCLUDED.passenger_rail,
    rail_tracks        = EXCLUDED.rail_tracks,
    distance_m         = EXCLUDED.distance_m,
    within_100m        = EXCLUDED.within_100m,
    within_250m        = EXCLUDED.within_250m,
    within_500m        = EXCLUDED.within_500m,
    within_1000m       = EXCLUDED.within_1000m,
    computed_at        = EXCLUDED.computed_at
""")

async def compute_rail_proximity(db: AsyncSession) -> int:
    """Pre-compute nearest rail line distance for every parcel with a location."""
    logger.info("[ENRICH] Computing rail proximity (LATERAL KNN — fast index lookup)...")
    await db.execute(_RAIL_PROXIMITY_SQL)
    await db.commit()
    result = await db.execute(text("SELECT COUNT(*) FROM parcel_rail_proximity"))
    count = result.scalar_one()
    logger.info("[ENRICH] Rail proximity computed: %d parcels", count)
    return count


# ── Flood zone (spatial, pre-computed) ───────────────────────────────────────

_FLOOD_ZONE_SQL = text("""
INSERT INTO parcel_flood_zone (
    par_id, flood_zone, sfha_tf, zone_description,
    flood_risk_category, in_flood_zone, computed_at
)
SELECT
    p.par_id,
    rz.flood_zone,
    rz.sfha_tf,
    rz.zone_description,
    CASE
        WHEN rz.flood_zone IN ('V', 'VE')                              THEN 'HIGH_RISK_COASTAL'
        WHEN rz.flood_zone IN ('A', 'AE', 'AH', 'AO', 'AR', 'A99')   THEN 'HIGH_RISK'
        WHEN rz.flood_zone = 'X' AND rz.zone_description IS NOT NULL  THEN 'MODERATE_RISK'
        WHEN rz.flood_zone = 'D'                                       THEN 'UNDETERMINED'
        WHEN rz.flood_zone = 'X'                                       THEN 'MINIMAL_RISK'
        ELSE                                                            'NOT_IN_FLOOD_ZONE'
    END                                                                 AS flood_risk_category,
    rz.flood_zone IS NOT NULL                                           AS in_flood_zone,
    NOW()
FROM parcels p
LEFT JOIN LATERAL (
    SELECT fz.flood_zone, fz.sfha_tf, fz.zone_description
    FROM flood_zones fz
    WHERE ST_Within(p.location::geometry, fz.geom::geometry)
    ORDER BY
        fz.sfha_tf DESC NULLS LAST,
        CASE fz.flood_zone
            WHEN 'V'   THEN 1  WHEN 'VE'  THEN 2
            WHEN 'A'   THEN 3  WHEN 'AE'  THEN 4
            WHEN 'AH'  THEN 5  WHEN 'AO'  THEN 6
            WHEN 'AR'  THEN 7  WHEN 'A99' THEN 8
            WHEN 'D'   THEN 9  WHEN 'X'   THEN 10
            ELSE 11
        END
    LIMIT 1
) rz ON true
WHERE p.location IS NOT NULL
ON CONFLICT (par_id) DO UPDATE SET
    flood_zone          = EXCLUDED.flood_zone,
    sfha_tf             = EXCLUDED.sfha_tf,
    zone_description    = EXCLUDED.zone_description,
    flood_risk_category = EXCLUDED.flood_risk_category,
    in_flood_zone       = EXCLUDED.in_flood_zone,
    computed_at         = EXCLUDED.computed_at
""")

async def compute_flood_zones(db: AsyncSession) -> int:
    """Pre-compute flood zone membership for every parcel with a location."""
    logger.info("[ENRICH] Computing flood zone membership (LATERAL spatial join)...")
    await db.execute(_FLOOD_ZONE_SQL)
    await db.commit()
    result = await db.execute(text("SELECT COUNT(*) FROM parcel_flood_zone"))
    count = result.scalar_one()
    logger.info("[ENRICH] Flood zone enrichment computed: %d parcels", count)
    return count


# ── Public entry point ────────────────────────────────────────────────────────

async def compute_all_enrichments(db: AsyncSession) -> dict:
    """Run all enrichments: views + rail proximity + flood zones."""
    global _enrichments_computed
    await create_views(db)
    rail_count  = await compute_rail_proximity(db)
    flood_count = await compute_flood_zones(db)
    _enrichments_computed = True
    return {
        "views_created": ["v_assessment_sale_ratio", "v_condo_building_stats"],
        "rail_proximity": rail_count,
        "flood_zones": flood_count,
    }


def reset_enrichments_flag() -> None:
    global _enrichments_computed
    _enrichments_computed = False
