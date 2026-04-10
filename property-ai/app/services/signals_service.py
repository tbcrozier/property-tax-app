from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_signals_computed = False


async def compute_parcel_signals(db: AsyncSession) -> int:
    global _signals_computed

    sql = text(
        """
        WITH base AS (
            SELECT
                par_id,
                prop_addr,
                prop_zip,
                lu_code,
                zoning,
                acres,
                totl_appr,
                sale_price,
                sale_date,
                totl_appr / NULLIF(acres, 0) AS vpa
            FROM parcels
            WHERE acres > 0
              AND totl_appr > 0
        ),
        peer_stats AS (
            SELECT
                *,
                AVG(vpa) OVER (PARTITION BY lu_code, prop_zip)           AS zip_avg,
                STDDEV(vpa) OVER (PARTITION BY lu_code, prop_zip)        AS zip_std,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY vpa)
                    OVER (PARTITION BY lu_code, prop_zip)                AS zip_median,
                COUNT(*) OVER (PARTITION BY lu_code, prop_zip)           AS zip_peer_count,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY vpa)
                    OVER (PARTITION BY lu_code)                          AS lu_median
            FROM base
        ),
        scored AS (
            SELECT
                par_id,
                prop_zip,
                lu_code,
                zoning,
                totl_appr,
                sale_price,
                vpa,
                zip_median,
                lu_median,
                zip_peer_count,
                (vpa - zip_avg) / NULLIF(zip_std, 0)                    AS z_score_zip,
                (vpa - zip_median) / NULLIF(zip_median, 0)              AS pct_above_zip_median,
                (vpa - lu_median) / NULLIF(lu_median, 0)                AS pct_above_lu_median,
                CASE
                    WHEN sale_price > 0
                    THEN totl_appr / NULLIF(sale_price, 0)
                    ELSE NULL
                END                                                      AS assessment_to_sale_ratio,
                CASE
                    WHEN sale_price > 0 AND totl_appr > sale_price
                    THEN TRUE ELSE FALSE
                END                                                      AS assessed_above_sale,
                -- Flag zoning/lu mismatch: residential lu but commercial zoning or vice versa
                CASE
                    WHEN lu_code LIKE 'R%' AND zoning NOT LIKE 'R%' THEN TRUE
                    WHEN lu_code LIKE 'C%' AND zoning NOT LIKE 'C%' THEN TRUE
                    ELSE FALSE
                END                                                      AS zoning_lu_mismatch
            FROM peer_stats
        )
        INSERT INTO parcel_signals (
            par_id, z_score_zip, pct_above_zip_median, pct_above_lu_median,
            zip_peer_count, assessment_to_sale_ratio, assessed_above_sale,
            zoning_lu_mismatch, appeal_score, recommendation, computed_at
        )
        SELECT
            par_id,
            z_score_zip,
            pct_above_zip_median,
            pct_above_lu_median,
            zip_peer_count::int,
            assessment_to_sale_ratio,
            assessed_above_sale,
            zoning_lu_mismatch,
            -- appeal_score: weighted composite 0-100
            LEAST(100, GREATEST(0,
                COALESCE(z_score_zip, 0) * 20
                + COALESCE(pct_above_zip_median, 0) * 30
                + COALESCE(pct_above_lu_median, 0) * 20
                + CASE WHEN assessed_above_sale THEN 15 ELSE 0 END
                + CASE WHEN zoning_lu_mismatch THEN 15 ELSE 0 END
            ))                                                           AS appeal_score,
            CASE
                WHEN z_score_zip >= 2.0 AND pct_above_zip_median >= 0.20
                    THEN 'STRONG_CANDIDATE'
                WHEN z_score_zip >= 1.5 AND pct_above_zip_median >= 0.30
                    THEN 'STRONG_CANDIDATE'
                WHEN z_score_zip >= 1.5 OR pct_above_zip_median >= 0.15
                    THEN 'MODERATE_CANDIDATE'
                WHEN zoning_lu_mismatch = TRUE
                    THEN 'REVIEW_ZONING'
                ELSE 'NORMAL'
            END                                                         AS recommendation,
            NOW()                                                       AS computed_at
        FROM scored
        ON CONFLICT (par_id) DO UPDATE SET
            z_score_zip             = EXCLUDED.z_score_zip,
            pct_above_zip_median    = EXCLUDED.pct_above_zip_median,
            pct_above_lu_median     = EXCLUDED.pct_above_lu_median,
            zip_peer_count          = EXCLUDED.zip_peer_count,
            assessment_to_sale_ratio = EXCLUDED.assessment_to_sale_ratio,
            assessed_above_sale     = EXCLUDED.assessed_above_sale,
            zoning_lu_mismatch      = EXCLUDED.zoning_lu_mismatch,
            appeal_score            = EXCLUDED.appeal_score,
            recommendation          = EXCLUDED.recommendation,
            computed_at             = EXCLUDED.computed_at
        """
    )

    await db.execute(sql)
    await db.commit()

    count_result = await db.execute(text("SELECT COUNT(*) FROM parcel_signals"))
    count = count_result.scalar_one()
    _signals_computed = True
    return count


async def signals_are_stale(db: AsyncSession) -> bool:
    if not _signals_computed:
        result = await db.execute(text("SELECT COUNT(*) FROM parcel_signals"))
        count = result.scalar_one()
        return count == 0
    return False


def reset_signals_flag() -> None:
    global _signals_computed
    _signals_computed = False
