# Rail Line Proximity — Davidson County Property Analysis

## Overview

Rail line proximity is a **negative externality** for residential and some commercial properties.
Properties within 100–500m of active rail lines may be under-assessed relative to peers farther away,
or may have legitimate appeal arguments based on noise/vibration impacts on market value.

Rail line data is available in the `rail_lines` table (PostGIS geometry).

---

## Database Table: rail_lines

| Column         | Type    | Description |
|---------------|---------|-------------|
| owner         | TEXT    | Railroad company name (e.g. CSX, NS, Tennessee Central) |
| passenger_rail | BOOL   | TRUE if used for passenger service (Amtrak, commuter) |
| tracks        | INT     | Number of tracks |
| miles         | FLOAT   | Segment length in miles |
| geom          | GEOMETRY(MULTILINESTRING, 4326) | Rail line geometry |

---

## How Rail Proximity Affects Property Values

- Within **100m**: Significant noise/vibration impact — may suppress residential values 5–15%
- Within **250m**: Moderate impact — relevant for quiet residential neighborhoods
- Within **500m**: Mild impact — primarily relevant for high-sensitivity uses
- Within **1000m**: Minimal direct impact; mainly relevant if freight rail is very active

---

## Querying Rail Proximity (PostgreSQL + PostGIS)

### Find parcels within 500m of any rail line:
```sql
SELECT
    p.par_id,
    p.prop_addr,
    p.prop_zip,
    p.lu_code,
    p.totl_appr,
    MIN(ST_Distance(
        ST_Transform(p.location, 3857),
        ST_Transform(r.geom, 3857)
    )) AS distance_to_rail_m
FROM parcels p
CROSS JOIN rail_lines r
WHERE p.location IS NOT NULL
GROUP BY p.par_id, p.prop_addr, p.prop_zip, p.lu_code, p.totl_appr
HAVING MIN(ST_Distance(
    ST_Transform(p.location, 3857),
    ST_Transform(r.geom, 3857)
)) <= 500
ORDER BY distance_to_rail_m
LIMIT 50
```

### Find nearest rail line for a specific parcel:
```sql
SELECT
    p.par_id,
    p.prop_addr,
    r.owner AS rail_owner,
    r.passenger_rail,
    r.tracks,
    ST_Distance(
        ST_Transform(p.location, 3857),
        ST_Transform(r.geom, 3857)
    ) AS distance_m
FROM parcels p
CROSS JOIN rail_lines r
WHERE p.par_id = '<parcel_id>'
ORDER BY distance_m
LIMIT 1
```

### Rail proximity + appeal score (combined enrichment):
```sql
SELECT
    p.par_id,
    p.prop_addr,
    p.prop_zip,
    p.lu_code,
    p.totl_appr,
    ps.appeal_score,
    ps.recommendation,
    ROUND(MIN(ST_Distance(
        ST_Transform(p.location, 3857),
        ST_Transform(r.geom, 3857)
    ))::numeric, 0) AS distance_to_rail_m,
    MIN(ST_Distance(
        ST_Transform(p.location, 3857),
        ST_Transform(r.geom, 3857)
    )) <= 250 AS within_250m_rail
FROM parcels p
JOIN parcel_signals ps ON ps.par_id = p.par_id
CROSS JOIN rail_lines r
WHERE p.location IS NOT NULL
  AND ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
GROUP BY p.par_id, p.prop_addr, p.prop_zip, p.lu_code, p.totl_appr,
         ps.appeal_score, ps.recommendation
HAVING MIN(ST_Distance(
    ST_Transform(p.location, 3857),
    ST_Transform(r.geom, 3857)
)) <= 500
ORDER BY ps.appeal_score DESC
LIMIT 25
```

---

## Appeal Narrative: Using Rail Proximity

When a residential parcel is within 250m of an active freight rail line AND has a high appeal score,
the argument is:
1. The rail line depresses market value (noise, vibration, air quality)
2. Comparable properties without rail proximity will have sold for higher prices
3. The assessor may not have adequately discounted for rail proximity
4. The `assessment_to_sale_ratio` from `parcel_signals` is the strongest evidence

---

## Notes

- ST_Transform to EPSG:3857 converts to meters for accurate distance calculation
- Davidson County has primarily CSX and Norfolk Southern freight lines
- The WeGo Music City Star commuter rail runs along the Cumberland River corridor
- Freight rail runs 24/7; passenger rail only a few times per day (less impact)
