terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# BigQuery Dataset
resource "google_bigquery_dataset" "property_tax" {
  dataset_id  = var.dataset_id
  description = "Property tax assessment data for comparative analysis"
  location    = var.region

  labels = {
    env = "dev"
  }
}

# BigQuery Table - Davidson County Parcels
resource "google_bigquery_table" "davidson_parcels" {
  dataset_id          = google_bigquery_dataset.property_tax.dataset_id
  table_id            = "davidson_parcels"
  description         = "Davidson County (Nashville, TN) parcel assessment data"
  deletion_protection = false

  schema = jsonencode([
    { name = "OBJECTID", type = "INTEGER", mode = "NULLABLE", description = "ArcGIS object ID" },
    { name = "STANPAR", type = "STRING", mode = "NULLABLE", description = "Standard parcel ID" },
    { name = "FEATURETYPE", type = "STRING", mode = "NULLABLE", description = "Feature type" },
    { name = "FLOORNUMBER", type = "STRING", mode = "NULLABLE", description = "Floor number" },
    { name = "ParID", type = "STRING", mode = "NULLABLE", description = "Parcel ID" },
    { name = "Tract", type = "STRING", mode = "NULLABLE", description = "Tract" },
    { name = "Council", type = "STRING", mode = "NULLABLE", description = "Council district" },
    { name = "TaxDist", type = "STRING", mode = "NULLABLE", description = "Tax district" },
    { name = "Owner", type = "STRING", mode = "NULLABLE", description = "Owner name" },
    { name = "OwnDate", type = "DATE", mode = "NULLABLE", description = "Ownership date" },
    { name = "SalePrice", type = "FLOAT64", mode = "NULLABLE", description = "Sale price" },
    { name = "OwnInstr", type = "STRING", mode = "NULLABLE", description = "Ownership instrument" },
    { name = "OwnAddr1", type = "STRING", mode = "NULLABLE", description = "Owner address line 1" },
    { name = "OwnAddr2", type = "STRING", mode = "NULLABLE", description = "Owner address line 2" },
    { name = "OwnAddr3", type = "STRING", mode = "NULLABLE", description = "Owner address line 3" },
    { name = "OwnCity", type = "STRING", mode = "NULLABLE", description = "Owner city" },
    { name = "OwnState", type = "STRING", mode = "NULLABLE", description = "Owner state" },
    { name = "OwnCountry", type = "STRING", mode = "NULLABLE", description = "Owner country" },
    { name = "OwnZip", type = "STRING", mode = "NULLABLE", description = "Owner zip code" },
    { name = "PropAddr", type = "STRING", mode = "NULLABLE", description = "Property address" },
    { name = "PropHouse", type = "STRING", mode = "NULLABLE", description = "Property house number" },
    { name = "PropFraction", type = "STRING", mode = "NULLABLE", description = "Property fraction" },
    { name = "PropStreet", type = "STRING", mode = "NULLABLE", description = "Property street" },
    { name = "PropSuite", type = "STRING", mode = "NULLABLE", description = "Property suite" },
    { name = "PropCity", type = "STRING", mode = "NULLABLE", description = "Property city" },
    { name = "PropState", type = "STRING", mode = "NULLABLE", description = "Property state" },
    { name = "PropZip", type = "STRING", mode = "NULLABLE", description = "Property zip code" },
    { name = "LegalDesc", type = "STRING", mode = "NULLABLE", description = "Legal description" },
    { name = "PropInstr", type = "STRING", mode = "NULLABLE", description = "Property instrument" },
    { name = "PropDate", type = "DATE", mode = "NULLABLE", description = "Property date" },
    { name = "Acres", type = "FLOAT64", mode = "NULLABLE", description = "Parcel acreage" },
    { name = "Front", type = "FLOAT64", mode = "NULLABLE", description = "Front footage" },
    { name = "Side", type = "FLOAT64", mode = "NULLABLE", description = "Side footage" },
    { name = "IsRegular", type = "STRING", mode = "NULLABLE", description = "Is regular shape" },
    { name = "LUCode", type = "STRING", mode = "NULLABLE", description = "Land use code" },
    { name = "LUDesc", type = "STRING", mode = "NULLABLE", description = "Land use description" },
    { name = "LandAppr", type = "FLOAT64", mode = "NULLABLE", description = "Land appraised value" },
    { name = "ImprAppr", type = "FLOAT64", mode = "NULLABLE", description = "Improvement appraised value" },
    { name = "TotlAppr", type = "FLOAT64", mode = "NULLABLE", description = "Total appraised value" },
    { name = "Zoning", type = "STRING", mode = "NULLABLE", description = "Zoning classification" },
    { name = "Shape__Area", type = "FLOAT64", mode = "NULLABLE", description = "Shape area" },
    { name = "Lat", type = "FLOAT64", mode = "NULLABLE", description = "Latitude" },
    { name = "Lon", type = "FLOAT64", mode = "NULLABLE", description = "Longitude" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# View: Assessment summary by land use
resource "google_bigquery_table" "view_assessment_by_land_use" {
  dataset_id = google_bigquery_dataset.property_tax.dataset_id
  table_id   = "v_assessment_by_land_use"

  view {
    query          = <<-SQL
      SELECT
        LUDesc AS land_use,
        COUNT(*) AS parcel_count,
        ROUND(AVG(TotlAppr), 2) AS avg_total_appraisal,
        ROUND(AVG(LandAppr), 2) AS avg_land_appraisal,
        ROUND(AVG(ImprAppr), 2) AS avg_improvement_appraisal,
        ROUND(AVG(Acres), 3) AS avg_acres,
        ROUND(AVG(SAFE_DIVIDE(TotlAppr, NULLIF(Acres, 0))), 2) AS avg_value_per_acre
      FROM `${var.project_id}.${var.dataset_id}.davidson_parcels`
      WHERE LUDesc IS NOT NULL
      GROUP BY LUDesc
      ORDER BY parcel_count DESC
    SQL
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_table.davidson_parcels]
}

# View: Potential over/under assessed parcels (outliers within land use)
resource "google_bigquery_table" "view_assessment_outliers" {
  dataset_id = google_bigquery_dataset.property_tax.dataset_id
  table_id   = "v_assessment_outliers"

  view {
    query          = <<-SQL
      WITH land_use_stats AS (
        SELECT
          LUDesc,
          AVG(SAFE_DIVIDE(TotlAppr, NULLIF(Acres, 0))) AS avg_value_per_acre,
          STDDEV(SAFE_DIVIDE(TotlAppr, NULLIF(Acres, 0))) AS stddev_value_per_acre
        FROM `${var.project_id}.${var.dataset_id}.davidson_parcels`
        WHERE LUDesc IS NOT NULL AND Acres > 0 AND TotlAppr > 0
        GROUP BY LUDesc
        HAVING COUNT(*) >= 10
      )
      SELECT
        p.ParID,
        p.PropAddr,
        p.LUDesc,
        p.TotlAppr,
        p.Acres,
        ROUND(SAFE_DIVIDE(p.TotlAppr, p.Acres), 2) AS value_per_acre,
        ROUND(s.avg_value_per_acre, 2) AS avg_value_per_acre,
        ROUND((SAFE_DIVIDE(p.TotlAppr, p.Acres) - s.avg_value_per_acre) / NULLIF(s.stddev_value_per_acre, 0), 2) AS z_score,
        CASE
          WHEN (SAFE_DIVIDE(p.TotlAppr, p.Acres) - s.avg_value_per_acre) / NULLIF(s.stddev_value_per_acre, 0) > 2 THEN 'POTENTIALLY_OVER'
          WHEN (SAFE_DIVIDE(p.TotlAppr, p.Acres) - s.avg_value_per_acre) / NULLIF(s.stddev_value_per_acre, 0) < -2 THEN 'POTENTIALLY_UNDER'
          ELSE 'NORMAL'
        END AS assessment_flag
      FROM `${var.project_id}.${var.dataset_id}.davidson_parcels` p
      JOIN land_use_stats s ON p.LUDesc = s.LUDesc
      WHERE p.Acres > 0 AND p.TotlAppr > 0
    SQL
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_table.davidson_parcels]
}

# View: Assessment-to-Sale Ratio Analysis
# Identifies properties where assessment exceeds or significantly differs from sale price
resource "google_bigquery_table" "view_assessment_sale_ratio" {
  dataset_id = google_bigquery_dataset.property_tax.dataset_id
  table_id   = "v_assessment_sale_ratio"

  view {
    query          = <<-SQL
      SELECT
        ParID,
        PropAddr,
        LUDesc,
        TotlAppr,
        SalePrice,
        OwnDate AS sale_date,
        ROUND(SAFE_DIVIDE(TotlAppr, NULLIF(SalePrice, 0)), 3) AS assessment_ratio,
        ROUND(TotlAppr - SalePrice, 2) AS assessment_difference,
        CASE
          WHEN SAFE_DIVIDE(TotlAppr, NULLIF(SalePrice, 0)) > 1.15 THEN 'OVER_ASSESSED'
          WHEN SAFE_DIVIDE(TotlAppr, NULLIF(SalePrice, 0)) < 0.85 THEN 'UNDER_ASSESSED'
          ELSE 'FAIR'
        END AS ratio_flag,
        -- Estimate potential tax savings (assuming 25% assessment ratio and ~3% tax rate)
        ROUND(GREATEST(0, (TotlAppr - SalePrice) * 0.25 * 0.03), 2) AS potential_annual_savings
      FROM `${var.project_id}.${var.dataset_id}.davidson_parcels`
      WHERE SalePrice > 0
        AND TotlAppr > 0
        AND OwnDate >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 YEAR)
      ORDER BY assessment_ratio DESC
    SQL
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_table.davidson_parcels]
}

# View: Neighborhood Peer Comparison
# Compares each property to nearby properties with same land use
resource "google_bigquery_table" "view_neighborhood_comparison" {
  dataset_id = google_bigquery_dataset.property_tax.dataset_id
  table_id   = "v_neighborhood_comparison"

  view {
    query          = <<-SQL
      WITH property_metrics AS (
        SELECT
          ParID,
          PropAddr,
          LUDesc,
          TotlAppr,
          LandAppr,
          ImprAppr,
          Acres,
          Lat,
          Lon,
          PropZip,
          SAFE_DIVIDE(TotlAppr, NULLIF(Acres, 0)) AS value_per_acre,
          SAFE_DIVIDE(ImprAppr, NULLIF(TotlAppr, 0)) AS improvement_ratio
        FROM `${var.project_id}.${var.dataset_id}.davidson_parcels`
        WHERE TotlAppr > 0 AND Acres > 0 AND Lat IS NOT NULL AND Lon IS NOT NULL
      ),
      zip_stats AS (
        SELECT
          PropZip,
          LUDesc,
          AVG(value_per_acre) AS zip_avg_value_per_acre,
          APPROX_QUANTILES(value_per_acre, 100)[OFFSET(50)] AS zip_median_value_per_acre,
          STDDEV(value_per_acre) AS zip_stddev_value_per_acre,
          COUNT(*) AS zip_peer_count
        FROM property_metrics
        WHERE PropZip IS NOT NULL
        GROUP BY PropZip, LUDesc
        HAVING COUNT(*) >= 5
      )
      SELECT
        p.ParID,
        p.PropAddr,
        p.LUDesc,
        p.PropZip,
        p.TotlAppr,
        p.Acres,
        ROUND(p.value_per_acre, 2) AS value_per_acre,
        ROUND(z.zip_median_value_per_acre, 2) AS zip_median_value_per_acre,
        ROUND(z.zip_avg_value_per_acre, 2) AS zip_avg_value_per_acre,
        z.zip_peer_count,
        ROUND((p.value_per_acre - z.zip_median_value_per_acre) / NULLIF(z.zip_median_value_per_acre, 0) * 100, 1) AS pct_above_median,
        ROUND((p.value_per_acre - z.zip_avg_value_per_acre) / NULLIF(z.zip_stddev_value_per_acre, 0), 2) AS neighborhood_z_score,
        -- Estimate savings if assessed at median
        ROUND(GREATEST(0, (p.value_per_acre - z.zip_median_value_per_acre) * p.Acres * 0.25 * 0.03), 2) AS potential_annual_savings
      FROM property_metrics p
      JOIN zip_stats z ON p.PropZip = z.PropZip AND p.LUDesc = z.LUDesc
    SQL
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_table.davidson_parcels]
}

# View: Appeal Candidates with Composite Score
# Combines multiple signals into a single appeal strength score
resource "google_bigquery_table" "view_appeal_candidates" {
  dataset_id = google_bigquery_dataset.property_tax.dataset_id
  table_id   = "v_appeal_candidates"

  view {
    query          = <<-SQL
      WITH base_metrics AS (
        SELECT
          p.ParID,
          p.PropAddr,
          p.LUDesc,
          p.PropZip,
          p.TotlAppr,
          p.LandAppr,
          p.ImprAppr,
          p.Acres,
          p.SalePrice,
          p.OwnDate,
          p.Lat,
          p.Lon,
          SAFE_DIVIDE(p.TotlAppr, NULLIF(p.Acres, 0)) AS value_per_acre
        FROM `${var.project_id}.${var.dataset_id}.davidson_parcels` p
        WHERE p.TotlAppr > 0 AND p.Acres > 0
      ),
      land_use_stats AS (
        SELECT
          LUDesc,
          AVG(value_per_acre) AS lu_avg_vpa,
          STDDEV(value_per_acre) AS lu_stddev_vpa,
          APPROX_QUANTILES(value_per_acre, 100)[OFFSET(50)] AS lu_median_vpa,
          APPROX_QUANTILES(value_per_acre, 100)[OFFSET(75)] AS lu_p75_vpa
        FROM base_metrics
        GROUP BY LUDesc
        HAVING COUNT(*) >= 10
      ),
      zip_stats AS (
        SELECT
          PropZip,
          LUDesc,
          AVG(value_per_acre) AS zip_avg_vpa,
          APPROX_QUANTILES(value_per_acre, 100)[OFFSET(50)] AS zip_median_vpa
        FROM base_metrics
        WHERE PropZip IS NOT NULL
        GROUP BY PropZip, LUDesc
        HAVING COUNT(*) >= 5
      ),
      scored AS (
        SELECT
          b.*,

          -- Signal 1: Land use z-score (how far above average for this land use type)
          ROUND((b.value_per_acre - lu.lu_avg_vpa) / NULLIF(lu.lu_stddev_vpa, 0), 2) AS land_use_z_score,

          -- Signal 2: Percentage above land use median
          ROUND((b.value_per_acre - lu.lu_median_vpa) / NULLIF(lu.lu_median_vpa, 0) * 100, 1) AS pct_above_lu_median,

          -- Signal 3: Percentage above zip code median
          ROUND((b.value_per_acre - z.zip_median_vpa) / NULLIF(z.zip_median_vpa, 0) * 100, 1) AS pct_above_zip_median,

          -- Signal 4: Assessment-to-sale ratio (if recent sale exists)
          CASE
            WHEN b.SalePrice > 0 AND b.OwnDate >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 YEAR)
            THEN ROUND(SAFE_DIVIDE(b.TotlAppr, b.SalePrice), 3)
            ELSE NULL
          END AS assessment_sale_ratio,

          -- Signal 5: Is in top 25% of land use category
          CASE WHEN b.value_per_acre > lu.lu_p75_vpa THEN 1 ELSE 0 END AS in_top_quartile,

          lu.lu_median_vpa,
          z.zip_median_vpa

        FROM base_metrics b
        LEFT JOIN land_use_stats lu ON b.LUDesc = lu.LUDesc
        LEFT JOIN zip_stats z ON b.PropZip = z.PropZip AND b.LUDesc = z.LUDesc
      )
      SELECT
        ParID,
        PropAddr,
        LUDesc,
        PropZip,
        TotlAppr,
        Acres,
        ROUND(value_per_acre, 2) AS value_per_acre,
        ROUND(lu_median_vpa, 2) AS land_use_median_vpa,
        ROUND(zip_median_vpa, 2) AS zip_median_vpa,
        land_use_z_score,
        pct_above_lu_median,
        pct_above_zip_median,
        assessment_sale_ratio,

        -- Composite Appeal Strength Score (0-100 scale)
        -- Higher score = stronger case for appeal
        ROUND(
          GREATEST(0, LEAST(100,
            -- Z-score contribution (max 30 points)
            LEAST(30, GREATEST(0, land_use_z_score * 15)) +
            -- Pct above zip median contribution (max 30 points)
            LEAST(30, GREATEST(0, pct_above_zip_median * 0.75)) +
            -- Pct above land use median contribution (max 20 points)
            LEAST(20, GREATEST(0, pct_above_lu_median * 0.5)) +
            -- Assessment > sale price contribution (max 20 points)
            CASE
              WHEN assessment_sale_ratio > 1.0 THEN LEAST(20, (assessment_sale_ratio - 1) * 100)
              ELSE 0
            END
          ))
        , 0) AS appeal_strength_score,

        -- Estimated annual tax savings if assessed at zip median
        ROUND(
          GREATEST(0, (value_per_acre - COALESCE(zip_median_vpa, lu_median_vpa)) * Acres * 0.25 * 0.03)
        , 2) AS estimated_annual_savings,

        -- Appeal recommendation
        CASE
          WHEN land_use_z_score > 2 AND pct_above_zip_median > 20 THEN 'STRONG_CANDIDATE'
          WHEN land_use_z_score > 1.5 OR pct_above_zip_median > 30 THEN 'MODERATE_CANDIDATE'
          WHEN land_use_z_score > 1 OR pct_above_zip_median > 15 THEN 'WORTH_REVIEWING'
          ELSE 'LIKELY_FAIR'
        END AS appeal_recommendation

      FROM scored
      WHERE land_use_z_score IS NOT NULL
      ORDER BY appeal_strength_score DESC
    SQL
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_table.davidson_parcels]
}

# View: Residential Single Family Focus
# Filtered view specifically for single family homeowners
resource "google_bigquery_table" "view_single_family_appeals" {
  dataset_id = google_bigquery_dataset.property_tax.dataset_id
  table_id   = "v_single_family_appeals"

  view {
    query          = <<-SQL
      SELECT *
      FROM `${var.project_id}.${var.dataset_id}.v_appeal_candidates`
      WHERE LUDesc = 'SINGLE FAMILY'
        AND appeal_strength_score > 20
      ORDER BY appeal_strength_score DESC
    SQL
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_table.view_appeal_candidates]
}

# BigQuery Table - Rail Lines (NARN)
# Stores BTS NTAD North American Rail Network line geometry for proximity analysis
resource "google_bigquery_table" "rail_lines" {
  dataset_id          = google_bigquery_dataset.property_tax.dataset_id
  table_id            = "rail_lines"
  description         = "North American Rail Network (NARN) rail lines for Davidson County area"
  deletion_protection = false

  schema = jsonencode([
    { name = "rail_id", type = "INTEGER", mode = "NULLABLE", description = "OBJECTID from NARN dataset" },
    { name = "fra_arc_id", type = "INTEGER", mode = "NULLABLE", description = "FRA Arc ID" },
    { name = "state_fips", type = "STRING", mode = "NULLABLE", description = "State FIPS code" },
    { name = "county_fips", type = "STRING", mode = "NULLABLE", description = "County FIPS code" },
    { name = "state_county_fips", type = "STRING", mode = "NULLABLE", description = "Combined state+county FIPS" },
    { name = "state_abbrev", type = "STRING", mode = "NULLABLE", description = "State abbreviation" },
    { name = "owner", type = "STRING", mode = "NULLABLE", description = "Primary railroad owner" },
    { name = "owner2", type = "STRING", mode = "NULLABLE", description = "Secondary railroad owner" },
    { name = "owner3", type = "STRING", mode = "NULLABLE", description = "Tertiary railroad owner" },
    { name = "passenger_rail", type = "STRING", mode = "NULLABLE", description = "Passenger rail indicator (A=Amtrak, C=Commuter, etc.)" },
    { name = "stracnet", type = "STRING", mode = "NULLABLE", description = "Strategic Rail Corridor Network indicator" },
    { name = "tracks", type = "INTEGER", mode = "NULLABLE", description = "Number of tracks" },
    { name = "miles", type = "FLOAT64", mode = "NULLABLE", description = "Segment length in miles" },
    { name = "subdivision", type = "STRING", mode = "NULLABLE", description = "Railroad subdivision name" },
    { name = "division", type = "STRING", mode = "NULLABLE", description = "Railroad division name" },
    { name = "geom", type = "GEOGRAPHY", mode = "NULLABLE", description = "Rail line geometry (LineString)" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# View: Parcel Rail Enrichment
# Calculates distance from each parcel to nearest rail line with proximity flags
resource "google_bigquery_table" "view_parcel_rail_enrichment" {
  dataset_id = google_bigquery_dataset.property_tax.dataset_id
  table_id   = "v_parcel_rail_enrichment"

  view {
    query          = <<-SQL
      WITH parcel_points AS (
        -- Create point geometry for each parcel from lat/lon
        SELECT
          ParID AS parcel_id,
          PropAddr AS property_address,
          LUDesc AS land_use,
          TotlAppr AS total_appraisal,
          Lat AS latitude,
          Lon AS longitude,
          ST_GEOGPOINT(Lon, Lat) AS parcel_point
        FROM `${var.project_id}.${var.dataset_id}.davidson_parcels`
        WHERE Lat IS NOT NULL AND Lon IS NOT NULL
      ),
      nearest_rail AS (
        -- Find nearest rail line for each parcel
        SELECT
          p.parcel_id,
          p.property_address,
          p.land_use,
          p.total_appraisal,
          p.latitude,
          p.longitude,
          p.parcel_point,
          r.rail_id AS nearest_rail_id,
          r.owner AS nearest_rail_owner,
          r.passenger_rail AS nearest_rail_type,
          r.tracks AS nearest_rail_tracks,
          ST_DISTANCE(p.parcel_point, r.geom) AS distance_to_rail_m
        FROM parcel_points p
        CROSS JOIN `${var.project_id}.${var.dataset_id}.rail_lines` r
        QUALIFY ROW_NUMBER() OVER (PARTITION BY p.parcel_id ORDER BY ST_DISTANCE(p.parcel_point, r.geom)) = 1
      )
      SELECT
        parcel_id,
        property_address,
        land_use,
        total_appraisal,
        latitude,
        longitude,
        parcel_point,
        nearest_rail_id,
        nearest_rail_owner,
        nearest_rail_type,
        nearest_rail_tracks,
        ROUND(distance_to_rail_m, 2) AS distance_to_rail_m,
        ROUND(distance_to_rail_m * 3.28084, 2) AS distance_to_rail_ft,
        distance_to_rail_m <= 100 AS within_100m_rail,
        distance_to_rail_m <= 250 AS within_250m_rail,
        distance_to_rail_m <= 500 AS within_500m_rail,
        distance_to_rail_m <= 1000 AS within_1000m_rail
      FROM nearest_rail
    SQL
    use_legacy_sql = false
  }

  depends_on = [
    google_bigquery_table.davidson_parcels,
    google_bigquery_table.rail_lines
  ]
}
