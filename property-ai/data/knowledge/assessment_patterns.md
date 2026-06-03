# Assessment Analysis — Pre-Built Views & Tables

The following views and tables are pre-built in PostgreSQL. The AI should query them
directly with simple SELECT statements rather than re-deriving the underlying logic.

Run `POST /admin/compute-enrichments` after loading data to create/refresh all of these.

---

## Appeal Score & Recommendation Reference

### Appeal Strength Score (0–100, stored in `parcel_signals.appeal_score`)

| Signal | Max Points | Condition |
|--------|-----------|-----------|
| Z-score vs land use peers | 30 pts | `z_score_zip * 20` |
| % above ZIP code median | 30 pts | `pct_above_zip_median * 30` |
| % above land use median | 20 pts | `pct_above_lu_median * 20` |
| Assessed above sale price | 15 pts | `assessed_above_sale = TRUE` |
| Zoning/LU mismatch | 15 pts | `zoning_lu_mismatch = TRUE` |

### Recommendation Values (`parcel_signals.recommendation`)

| Value | Threshold |
|-------|-----------|
| `STRONG_CANDIDATE` | z_score_zip ≥ 2.0 AND pct_above_zip_median ≥ 20% |
| `MODERATE_CANDIDATE` | z_score_zip ≥ 1.5 AND pct_above_zip_median ≥ 30% OR z_score_zip ≥ 1.5 OR pct_above_zip_median ≥ 15% |
| `REVIEW_ZONING` | zoning_lu_mismatch = TRUE |
| `NORMAL` | Does not meet above thresholds |

**For "which properties should appeal?" → always use `parcel_signals` ordered by `appeal_score DESC`**

---

## parcel_signals (pre-computed table)

The fastest path to appeal candidates. Covers every parcel.

```sql
-- Top 10 appeal candidates
SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_desc, p.totl_appr,
       ps.appeal_score, ps.recommendation,
       ROUND((ps.pct_above_zip_median * 100)::numeric, 1) AS pct_above_zip_pct,
       ps.assessment_to_sale_ratio, ps.zoning_lu_mismatch
FROM parcels p
JOIN parcel_signals ps ON ps.par_id = p.par_id
WHERE ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
ORDER BY ps.appeal_score DESC
LIMIT 10
```

---

## v_assessment_sale_ratio (view)

Use when the question involves: over-assessed, sale price, assessment ratio, recent transaction.
Only covers parcels with `sale_price > 10000`.

Key columns: `assessment_ratio`, `ratio_flag` (OVER_ASSESSED/UNDER_ASSESSED/FAIR), `potential_annual_savings`

```sql
-- Top over-assessed properties by sale ratio
SELECT par_id, prop_addr, prop_zip, lu_desc,
       totl_appr, sale_price, assessment_ratio,
       assessment_excess, potential_annual_savings
FROM v_assessment_sale_ratio
WHERE ratio_flag = 'OVER_ASSESSED'
ORDER BY assessment_ratio DESC
LIMIT 10
```

```sql
-- Combined: high appeal score AND over-assessed vs sale
SELECT p.par_id, p.prop_addr, p.totl_appr, p.sale_price,
       v.assessment_ratio, v.potential_annual_savings,
       ps.appeal_score, ps.recommendation
FROM parcels p
JOIN parcel_signals ps ON ps.par_id = p.par_id
JOIN v_assessment_sale_ratio v ON v.par_id = p.par_id
WHERE v.ratio_flag = 'OVER_ASSESSED'
  AND ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
ORDER BY v.assessment_ratio DESC
LIMIT 10
```

---

## v_condo_building_stats (view)

Use when the question involves: condos, condo comparison, within-building outlier, same building.
Only covers parcels where `lu_desc ILIKE '%condo%'`, buildings with 2+ units.

Key columns: `building_unit_count`, `building_median`, `building_z_score`, `building_assessment_flag`, `potential_annual_savings`

```sql
-- Condo units assessed much higher than building peers
SELECT par_id, prop_addr, prop_zip,
       totl_appr, building_unit_count,
       building_median, building_z_score,
       pct_from_building_median, building_assessment_flag,
       potential_annual_savings
FROM v_condo_building_stats
WHERE building_assessment_flag IN ('HIGH_OUTLIER', 'ABOVE_AVERAGE')
ORDER BY building_z_score DESC
LIMIT 20
```

---

## parcel_rail_proximity (pre-computed table)

Use when the question involves: rail, railroad, train, proximity, nearby tracks.

Key columns: `distance_m`, `within_100m/250m/500m/1000m`, `nearest_rail_owner`, `passenger_rail`

```sql
-- Appeal candidates near active freight rail (negative externality)
SELECT p.par_id, p.prop_addr, p.prop_zip, p.totl_appr,
       rp.distance_m, rp.nearest_rail_owner, rp.passenger_rail,
       ps.appeal_score, ps.recommendation
FROM parcels p
JOIN parcel_signals ps ON ps.par_id = p.par_id
JOIN parcel_rail_proximity rp ON rp.par_id = p.par_id
WHERE rp.within_500m = TRUE
  AND ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
ORDER BY ps.appeal_score DESC
LIMIT 20
```

```sql
-- All parcels within 250m of rail, ordered by distance
SELECT p.par_id, p.prop_addr, p.lu_desc, p.totl_appr,
       rp.distance_m, rp.nearest_rail_owner
FROM parcels p
JOIN parcel_rail_proximity rp ON rp.par_id = p.par_id
WHERE rp.within_250m = TRUE
ORDER BY rp.distance_m
LIMIT 50
```

---

## parcel_flood_zone (pre-computed table)

Use when the question involves: flood, flood zone, SFHA, FEMA, flood risk.

Key columns: `flood_zone`, `sfha_tf`, `flood_risk_category`, `in_flood_zone`

Risk categories: `HIGH_RISK_COASTAL`, `HIGH_RISK`, `MODERATE_RISK`, `MINIMAL_RISK`, `UNDETERMINED`, `NOT_IN_FLOOD_ZONE`

```sql
-- Properties in high-risk flood zones that are also over-assessed
SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_desc, p.totl_appr,
       pfz.flood_zone, pfz.flood_risk_category, pfz.sfha_tf,
       ps.appeal_score, ps.recommendation
FROM parcels p
JOIN parcel_signals ps ON ps.par_id = p.par_id
JOIN parcel_flood_zone pfz ON pfz.par_id = p.par_id
WHERE pfz.sfha_tf = TRUE
  AND ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
ORDER BY ps.appeal_score DESC
LIMIT 20
```

```sql
-- Count parcels by flood risk category
SELECT flood_risk_category, COUNT(*) AS parcel_count
FROM parcel_flood_zone
GROUP BY flood_risk_category
ORDER BY parcel_count DESC
```

---

## Multi-signal queries (combining tables)

```sql
-- Strongest cases: high appeal score + over-assessed + in flood zone
SELECT p.par_id, p.prop_addr, p.prop_zip, p.totl_appr,
       ps.appeal_score, ps.recommendation,
       v.assessment_ratio, v.potential_annual_savings,
       pfz.flood_risk_category,
       rp.distance_m AS distance_to_rail_m
FROM parcels p
JOIN parcel_signals ps      ON ps.par_id  = p.par_id
LEFT JOIN v_assessment_sale_ratio v   ON v.par_id   = p.par_id
LEFT JOIN parcel_flood_zone pfz       ON pfz.par_id  = p.par_id
LEFT JOIN parcel_rail_proximity rp    ON rp.par_id   = p.par_id
WHERE ps.recommendation = 'STRONG_CANDIDATE'
ORDER BY ps.appeal_score DESC
LIMIT 20
```

---

## Key Tax Calculation Facts (Davidson County)

- **Residential assessment ratio**: 25% of appraised value
- **Commercial assessment ratio**: 40% of appraised value
- **USD tax rate**: ~$2.814 per $100 assessed value (~2.814%)
- **GSD tax rate**: ~$2.782 per $100 assessed value (~2.782%)
- **Estimated annual savings**: `(totl_appr - fair_value) × 0.25 × 0.028`
- **2025 reappraisal**: County-wide median values increased ~45% from 2021 baseline
