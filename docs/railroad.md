

# Handoff Document for Claude Code

## Project: Rail Line Proximity Enrichment for Davidson County Parcels (BigQuery)

## Objective

I already have **property assessor data in BigQuery** for Davidson County. I want to enrich it with **railroad / train track location data** so I can determine how close each property is to the nearest rail line.

The goal is to create a workflow that:

1. loads rail line data covering **Davidson County, TN**
2. stores it in BigQuery as `GEOGRAPHY`
3. creates a **view** that calculates parcel-level proximity to the nearest rail line
4. optionally adds boolean thresholds like “within 100m / 250m / 500m of rail”

A strong candidate public source is the **Bureau of Transportation Statistics National Transportation Atlas Database / North American Rail Network (NARN) Rail Lines** dataset. BTS states NTAD data is publicly downloadable in formats including Shapefile and GeoJSON, and the NARN Rail Lines dataset includes ownership and geographic reference information. ([Bureau of Transportation Statistics][1])

---

## What I want built

I want a simple, practical implementation that:

* uses a public rail line dataset
* narrows it to Davidson County or the Nashville area
* loads the rail geometry into BigQuery
* computes parcel-to-rail distance using BigQuery GIS
* produces a final view for downstream analysis

---

## Desired Output

### View: `parcel_rail_enrichment`

Fields should include at least:

* `parcel_id`
* `latitude`
* `longitude`
* `parcel_point` (`GEOGRAPHY`)
* `distance_to_rail_m`
* `within_100m_rail`
* `within_250m_rail`
* `within_500m_rail`
* optional nearest rail attributes, if available:

  * `nearest_rail_owner`
  * `nearest_rail_type`
  * `nearest_rail_id`

If my parcel table already has a point or centroid field, use it. Otherwise, create one from lat/long.

---

## Current Context

* Property assessor data is already in **BigQuery**
* I want to start with **point-based parcel location** using lat/long
* This is for a **property tax analysis application**
* The analytical idea is that proximity to rail may be a negative externality that could later be used in comp analysis or appeal narratives

---

## Specific Tasks for Claude Code

### 1. Identify and recommend the rail dataset

Please confirm and recommend a practical public dataset for rail lines, ideally starting with:

* **BTS / NTAD / NARN Rail Lines**

BTS publishes NTAD as a public geospatial transportation database, and recent BTS notices say NTAD data is available in formats such as Shapefile and GeoJSON. ([Bureau of Transportation Statistics][2])

Please determine:

* the exact dataset to use
* how to download it
* whether to clip/filter to Tennessee or Davidson County before loading
* what attributes are useful to preserve

---

### 2. Data ingestion plan

Design a minimal-friction ingestion approach. Consider:

* Python with GeoPandas
* `ogr2ogr`
* loading GeoJSON into BigQuery
* filtering rail lines to Davidson County before load vs after load

I want a workflow I can realistically run locally and later automate.

---

### 3. BigQuery table design

Please design a raw or staged table, such as:

`rail_lines_raw`

Suggested fields:

* `rail_id`
* `geom` (`GEOGRAPHY`)
* `owner`
* `rail_type`
* any other useful source fields

Please advise whether geometry simplification is recommended.

---

### 4. Parcel point creation

Assume my parcel table looks something like:

`parcels`

Fields:

* `parcel_id`
* `latitude`
* `longitude`

Please generate SQL to create the parcel point with:

```sql
ST_GEOGPOINT(longitude, latitude)
```

---

### 5. Core spatial logic

I want actual BigQuery SQL for:

#### A. Nearest rail distance

Use `ST_DISTANCE(parcel_point, rail_geom)` and calculate the minimum distance per parcel.

#### B. Threshold flags

Add booleans such as:

* within 100 meters
* within 250 meters
* within 500 meters

#### C. Optional nearest-feature attribution

If practical, return the nearest rail segment’s attributes too.

---

### 6. Final view

Create a final view:

`parcel_rail_enrichment`

Requirements:

* every parcel should appear
* parcels with no close rail line should still return distance if possible
* SQL should be readable and production-friendly

---

### 7. Suggested SQL

Please generate runnable SQL for:

1. rail line staging table logic if needed
2. parcel point creation
3. nearest-rail calculation
4. final view creation

Avoid pseudocode.

---

### 8. Suggested repo structure

Keep it simple:

```text
project-root/
  sql/
    rail_line_tables.sql
    parcel_rail_view.sql
  scripts/
    load_rail_lines.py
  data_sources/
    rail_dataset_notes.md
  docs/
    architecture.md
```

---

## MVP Definition

This is the MVP:

* load rail line data covering Davidson County
* store rail geometry in BigQuery
* create parcel points from lat/long
* calculate nearest rail distance in meters
* create boolean proximity flags

That’s all I need for now.

---

## Important Notes

* Use **lat/long point proximity**, not parcel polygons, for now
* Do not overengineer
* Prefer practical implementation over GIS perfection
* If the source is nationwide, it is fine to subset to Tennessee or Davidson County before the final view
* If a county boundary clip is useful, note that as an optional improvement

---

## What I want back from Claude Code

Please provide:

1. recommended public rail dataset
2. step-by-step ingestion approach
3. Python or CLI scaffolding to prepare/load the data
4. BigQuery table design
5. working BigQuery SQL for distance and threshold flags
6. performance considerations
7. any source-data gotchas

---

## Final Instruction to Claude Code

Act like a pragmatic data engineer helping me stand up a first working version of a rail proximity enrichment pipeline in BigQuery for Davidson County assessor parcels. Prioritize clarity, runnable code, and simple implementation.

---
