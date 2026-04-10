# Davidson County Property Tax — Query Examples

These examples demonstrate common analysis patterns for finding over-assessed parcels.

---

## Example: Find top over-assessed residential parcels by ZIP

**Tags:** residential, zip comparison, value per acre

```sql
WITH peer_stats AS (
    SELECT
        par_id,
        prop_addr,
        prop_zip,
        lu_code,
        acres,
        totl_appr,
        totl_appr / NULLIF(acres, 0) AS vpa,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY totl_appr / NULLIF(acres, 0))
            OVER (PARTITION BY lu_code, prop_zip) AS zip_median_vpa,
        COUNT(*) OVER (PARTITION BY lu_code, prop_zip) AS peer_count
    FROM parcels
    WHERE acres > 0 AND totl_appr > 0 AND lu_code LIKE 'R%'
)
SELECT
    par_id,
    prop_addr,
    prop_zip,
    ROUND(vpa::numeric, 2) AS value_per_acre,
    ROUND(zip_median_vpa::numeric, 2) AS zip_median,
    ROUND(((vpa - zip_median_vpa) / NULLIF(zip_median_vpa, 0) * 100)::numeric, 1) AS pct_above_median,
    peer_count
FROM peer_stats
WHERE vpa > zip_median_vpa * 1.20
ORDER BY pct_above_median DESC
LIMIT 50
```

**Insight:** Parcels more than 20% above their ZIP+land-use median are prime appeal candidates.

---

## Example: Use pre-computed signals for fast hit list

**Tags:** parcel_signals, strong candidates, fast query

```sql
SELECT
    p.par_id,
    p.prop_addr,
    p.prop_zip,
    p.lu_code,
    p.totl_appr,
    ps.appeal_score,
    ps.recommendation,
    ps.z_score_zip,
    ROUND((ps.pct_above_zip_median * 100)::numeric, 1) AS pct_above_zip_pct
FROM parcels p
JOIN parcel_signals ps ON ps.par_id = p.par_id
WHERE ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
ORDER BY ps.appeal_score DESC
LIMIT 100
```

**Insight:** The parcel_signals table is pre-computed and indexed — always use it for large scans rather than recomputing window functions.

---

## Example: Find zoning/land-use mismatches

**Tags:** zoning, land use, mismatch, anomaly

```sql
SELECT
    par_id,
    prop_addr,
    prop_zip,
    lu_code,
    lu_desc,
    zoning,
    totl_appr
FROM parcels
WHERE
    (lu_code LIKE 'R%' AND zoning NOT LIKE 'R%')
    OR
    (lu_code LIKE 'C%' AND zoning NOT LIKE 'C%')
ORDER BY totl_appr DESC
LIMIT 50
```

**Insight:** Properties where the land use code and zoning district don't match may be mis-classified for assessment purposes, creating appeal opportunities.

---

## Example: Over-assessed vs recent sale price

**Tags:** sale price, assessment ratio, over-assessed

```sql
SELECT
    par_id,
    prop_addr,
    prop_zip,
    lu_code,
    totl_appr,
    sale_price,
    sale_date,
    ROUND((totl_appr / NULLIF(sale_price, 0))::numeric, 3) AS assessment_to_sale_ratio
FROM parcels
WHERE
    sale_price > 10000
    AND totl_appr > sale_price
    AND sale_date >= '2021-01-01'
ORDER BY assessment_to_sale_ratio DESC
LIMIT 50
```

**Insight:** An assessment-to-sale ratio above 1.0 means the county values the property higher than its actual market transaction — strong appeal evidence.

---

## Example: Improvement value anomalies

**Tags:** improvement value, building characteristics, anomaly

```sql
SELECT
    p.par_id,
    p.prop_addr,
    p.prop_zip,
    p.lu_code,
    p.impr_appr,
    p.bldg_sqft,
    ROUND((p.impr_appr / NULLIF(p.bldg_sqft, 0))::numeric, 2) AS impr_per_sqft,
    AVG(p.impr_appr / NULLIF(p.bldg_sqft, 0))
        OVER (PARTITION BY p.lu_code, p.prop_zip) AS avg_impr_per_sqft
FROM parcels p
WHERE p.bldg_sqft > 0 AND p.impr_appr > 0
HAVING p.impr_appr / NULLIF(p.bldg_sqft, 0) >
       AVG(p.impr_appr / NULLIF(p.bldg_sqft, 0)) OVER (PARTITION BY p.lu_code, p.prop_zip) * 1.30
ORDER BY impr_per_sqft DESC
LIMIT 50
```

**Insight:** Improvement value per square foot significantly above ZIP+lu peers suggests the county is over-valuing the structure itself.

