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
