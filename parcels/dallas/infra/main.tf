terraform {
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

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "public-data-dev"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "US"
}

variable "dataset_id" {
  description = "BigQuery dataset ID for Dallas data"
  type        = string
  default     = "dallas"
}

# Reference existing Dallas dataset
data "google_bigquery_dataset" "dallas" {
  dataset_id = var.dataset_id
  project    = var.project_id
}

# View: Dallas Condo Building Comparison
# Groups Dallas condo units by building and enables within-building comparisons to find outliers
# Similar to public-data-dev.property_tax.v_condo_comparison for Davidson County
resource "google_bigquery_table" "view_condo_comparison" {
  dataset_id          = data.google_bigquery_dataset.dallas.dataset_id
  table_id            = "v_condo_comparison"
  deletion_protection = false
  description         = "Dallas condo units grouped by building with within-building comparison metrics to identify assessment outliers"

  view {
    query          = <<-SQL
      WITH condos AS (
        -- Filter to condo units only by joining account info with appraisal data
        -- Condos identified by: SPTD codes A14/A15/A16 (townhouse/condo) or legal description containing CONDO
        SELECT
          ai.ACCOUNT_NUM,
          ai.STREET_NUM,
          ai.FULL_STREET_NAME,
          ai.UNIT_ID,
          ai.PROPERTY_ZIPCODE,
          ai.PROPERTY_CITY,
          ai.LEGAL1,
          ai.LEGAL2,
          ai.NBHD_CD,
          CONCAT(
            COALESCE(TRIM(ai.STREET_NUM), ''), ' ',
            COALESCE(TRIM(ai.FULL_STREET_NAME), ''),
            CASE WHEN ai.UNIT_ID IS NOT NULL AND TRIM(ai.UNIT_ID) != ''
                 THEN CONCAT(' #', TRIM(ai.UNIT_ID))
                 ELSE '' END,
            ', ', COALESCE(TRIM(ai.PROPERTY_CITY), ''),
            ' ', COALESCE(TRIM(ai.PROPERTY_ZIPCODE), '')
          ) AS full_address,
          aay.TOT_VAL AS tot_val,
          aay.LAND_VAL AS land_val,
          aay.IMPR_VAL AS impr_val,
          l.SPTD_CD,
          l.SPTD_DESC,
          l.AREA_SIZE AS lot_sqft,
          CAST(rd.TOT_LIVING_AREA_SF AS FLOAT64) AS living_area_sqft,
          rd.YR_BUILT,
          CAST(rd.NUM_BEDROOMS AS INT64) AS num_bedrooms,
          CAST(rd.NUM_FULL_BATHS AS INT64) AS num_full_baths,
          CAST(rd.NUM_HALF_BATHS AS INT64) AS num_half_baths,
          rd.CDU_RATING_DESC,
          SAFE_DIVIDE(aay.TOT_VAL, NULLIF(CAST(rd.TOT_LIVING_AREA_SF AS FLOAT64), 0)) AS value_per_sqft
        FROM `${var.project_id}.${var.dataset_id}.account_info` ai
        INNER JOIN `${var.project_id}.${var.dataset_id}.account_apprl_year` aay
          ON ai.ACCOUNT_NUM = aay.ACCOUNT_NUM
        LEFT JOIN `${var.project_id}.${var.dataset_id}.land` l
          ON ai.ACCOUNT_NUM = l.ACCOUNT_NUM
        LEFT JOIN `${var.project_id}.${var.dataset_id}.res_detail` rd
          ON ai.ACCOUNT_NUM = rd.ACCOUNT_NUM
        WHERE
          -- Condo identification: SPTD codes for condos/townhouses OR legal description contains CONDO
          (
            l.SPTD_CD IN ('A14', 'A15', 'A16')
            OR UPPER(ai.LEGAL1) LIKE '%CONDO%'
            OR UPPER(ai.LEGAL1) LIKE '%CONDOMINIUM%'
            OR UPPER(ai.LEGAL2) LIKE '%CONDO%'
          )
          AND aay.TOT_VAL > 0
          AND ai.UNIT_ID IS NOT NULL
          AND TRIM(ai.UNIT_ID) != ''
      ),
      buildings AS (
        -- Create building identifier from address components
        SELECT
          *,
          CONCAT(
            COALESCE(TRIM(STREET_NUM), ''), '|',
            COALESCE(TRIM(FULL_STREET_NAME), ''), '|',
            COALESCE(TRIM(PROPERTY_ZIPCODE), '')
          ) AS building_key,
          -- Extract complex name from LEGAL1 (often contains building/complex name)
          REGEXP_EXTRACT(UPPER(LEGAL1), r'^([A-Z0-9\s]+(?:CONDO|CONDOMINIUM|TOWER|PLACE|RESIDENCES|LOFTS|TOWNHOMES))') AS complex_name
        FROM condos
      ),
      building_stats AS (
        -- Calculate building-level statistics
        SELECT
          building_key,
          COUNT(*) AS unit_count,
          AVG(tot_val) AS building_avg_appraisal,
          STDDEV(tot_val) AS building_stddev_appraisal,
          APPROX_QUANTILES(tot_val, 100)[OFFSET(50)] AS building_median_appraisal,
          APPROX_QUANTILES(tot_val, 100)[OFFSET(25)] AS building_p25_appraisal,
          APPROX_QUANTILES(tot_val, 100)[OFFSET(75)] AS building_p75_appraisal,
          MIN(tot_val) AS building_min_appraisal,
          MAX(tot_val) AS building_max_appraisal,
          AVG(value_per_sqft) AS building_avg_value_per_sqft,
          AVG(living_area_sqft) AS building_avg_sqft
        FROM buildings
        GROUP BY building_key
        HAVING COUNT(*) >= 2  -- Only buildings with 2+ units for meaningful comparison
      ),
      neighborhood_stats AS (
        -- Calculate neighborhood-level statistics as secondary grouping
        SELECT
          NBHD_CD,
          COUNT(*) AS nbhd_unit_count,
          AVG(tot_val) AS nbhd_avg_appraisal,
          APPROX_QUANTILES(tot_val, 100)[OFFSET(50)] AS nbhd_median_appraisal,
          AVG(value_per_sqft) AS nbhd_avg_value_per_sqft
        FROM buildings
        GROUP BY NBHD_CD
        HAVING COUNT(*) >= 2
      )
      SELECT
        b.ACCOUNT_NUM,
        b.full_address,
        b.UNIT_ID,
        b.PROPERTY_ZIPCODE,
        b.PROPERTY_CITY,
        b.LEGAL1,
        b.SPTD_CD,
        b.SPTD_DESC,
        b.tot_val,
        b.land_val,
        b.impr_val,
        b.lot_sqft,
        CAST(b.living_area_sqft AS INT64) AS living_area_sqft,
        b.YR_BUILT,
        b.num_bedrooms,
        b.num_full_baths,
        b.num_half_baths,
        b.CDU_RATING_DESC,
        ROUND(b.value_per_sqft, 2) AS value_per_sqft,

        -- Building identification
        b.building_key,
        b.complex_name,
        b.NBHD_CD,

        -- Building statistics
        s.unit_count AS building_unit_count,
        ROUND(s.building_avg_appraisal, 2) AS building_avg_appraisal,
        ROUND(s.building_median_appraisal, 2) AS building_median_appraisal,
        ROUND(s.building_min_appraisal, 2) AS building_min_appraisal,
        ROUND(s.building_max_appraisal, 2) AS building_max_appraisal,
        ROUND(s.building_p25_appraisal, 2) AS building_p25_appraisal,
        ROUND(s.building_p75_appraisal, 2) AS building_p75_appraisal,
        ROUND(s.building_avg_value_per_sqft, 2) AS building_avg_value_per_sqft,
        ROUND(s.building_avg_sqft, 0) AS building_avg_sqft,

        -- Within-building comparison metrics
        ROUND((b.tot_val - s.building_avg_appraisal) / NULLIF(s.building_stddev_appraisal, 0), 2) AS building_z_score,
        ROUND((b.tot_val - s.building_median_appraisal) / NULLIF(s.building_median_appraisal, 0) * 100, 1) AS pct_from_building_median,
        ROUND(b.tot_val - s.building_median_appraisal, 2) AS diff_from_building_median,

        -- Neighborhood comparison (secondary validation)
        n.nbhd_unit_count,
        ROUND(n.nbhd_median_appraisal, 2) AS nbhd_median_appraisal,
        ROUND((b.tot_val - n.nbhd_median_appraisal) / NULLIF(n.nbhd_median_appraisal, 0) * 100, 1) AS pct_from_nbhd_median,

        -- Outlier classification based on z-score
        CASE
          WHEN s.building_stddev_appraisal IS NULL OR s.building_stddev_appraisal = 0 THEN 'UNIFORM'
          WHEN (b.tot_val - s.building_avg_appraisal) / s.building_stddev_appraisal > 2 THEN 'HIGH_OUTLIER'
          WHEN (b.tot_val - s.building_avg_appraisal) / s.building_stddev_appraisal > 1.5 THEN 'ABOVE_AVERAGE'
          WHEN (b.tot_val - s.building_avg_appraisal) / s.building_stddev_appraisal < -2 THEN 'LOW_OUTLIER'
          WHEN (b.tot_val - s.building_avg_appraisal) / s.building_stddev_appraisal < -1.5 THEN 'BELOW_AVERAGE'
          ELSE 'NORMAL'
        END AS building_assessment_flag,

        -- IQR-based outlier detection (more robust to non-normal distributions)
        CASE
          WHEN b.tot_val > s.building_p75_appraisal + 1.5 * (s.building_p75_appraisal - s.building_p25_appraisal) THEN 'IQR_HIGH_OUTLIER'
          WHEN b.tot_val < s.building_p25_appraisal - 1.5 * (s.building_p75_appraisal - s.building_p25_appraisal) THEN 'IQR_LOW_OUTLIER'
          ELSE 'WITHIN_IQR'
        END AS iqr_flag,

        -- Estimated annual tax savings if assessed at building median
        -- Using approximate Dallas combined tax rate of ~2.5%
        ROUND(
          GREATEST(0, (b.tot_val - s.building_median_appraisal) * 0.025)
        , 2) AS potential_annual_savings

      FROM buildings b
      JOIN building_stats s ON b.building_key = s.building_key
      LEFT JOIN neighborhood_stats n ON b.NBHD_CD = n.NBHD_CD
      ORDER BY building_z_score DESC NULLS LAST
    SQL
    use_legacy_sql = false
  }
}

output "condo_comparison_view_id" {
  description = "The ID of the condo comparison view"
  value       = google_bigquery_table.view_condo_comparison.table_id
}

