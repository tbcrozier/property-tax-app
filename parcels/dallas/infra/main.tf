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

# BigQuery Dataset - Dallas County
resource "google_bigquery_dataset" "dallas" {
  dataset_id  = var.dataset_id
  description = "Dallas County Appraisal District (DCAD) property tax assessment data"
  location    = var.region

  labels = {
    env    = "dev"
    county = "dallas"
  }
}

# =============================================================================
# TABLES
# =============================================================================

# ABATEMENT_EXEMPT - Tax abatement and exemption data
resource "google_bigquery_table" "abatement_exempt" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "abatement_exempt"
  description         = "Tax abatement and exemption data by jurisdiction"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "TOT_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Total value" },
    { name = "CITY_EFF_YR", type = "INTEGER", mode = "NULLABLE", description = "City effective year" },
    { name = "CITY_EXP_YR", type = "INTEGER", mode = "NULLABLE", description = "City expiration year" },
    { name = "CITY_EXEMPTION_PCT", type = "FLOAT64", mode = "NULLABLE", description = "City exemption percentage" },
    { name = "CITY_BASE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "City base value" },
    { name = "CITY_VAL_DIF", type = "FLOAT64", mode = "NULLABLE", description = "City value difference" },
    { name = "CITY_EXEMPTION_AMT", type = "FLOAT64", mode = "NULLABLE", description = "City exemption amount" },
    { name = "CNTY_EFF_YR", type = "INTEGER", mode = "NULLABLE", description = "County effective year" },
    { name = "CNTY_EXP_YR", type = "INTEGER", mode = "NULLABLE", description = "County expiration year" },
    { name = "CNTY_EXEMPTION_PCT", type = "FLOAT64", mode = "NULLABLE", description = "County exemption percentage" },
    { name = "CNTY_BASE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "County base value" },
    { name = "CNTY_VAL_DIF", type = "FLOAT64", mode = "NULLABLE", description = "County value difference" },
    { name = "CNTY_EXEMPTION_AMT", type = "FLOAT64", mode = "NULLABLE", description = "County exemption amount" },
    { name = "ISD_EFF_YR", type = "INTEGER", mode = "NULLABLE", description = "ISD effective year" },
    { name = "ISD_EXP_YR", type = "INTEGER", mode = "NULLABLE", description = "ISD expiration year" },
    { name = "ISD_EXEMPTION_PCT", type = "FLOAT64", mode = "NULLABLE", description = "ISD exemption percentage" },
    { name = "ISD_BASE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "ISD base value" },
    { name = "ISD_VAL_DIF", type = "FLOAT64", mode = "NULLABLE", description = "ISD value difference" },
    { name = "ISD_EXEMPTION_AMT", type = "FLOAT64", mode = "NULLABLE", description = "ISD exemption amount" },
    { name = "COLL_EFF_YR", type = "INTEGER", mode = "NULLABLE", description = "College effective year" },
    { name = "COLL_EXP_YR", type = "INTEGER", mode = "NULLABLE", description = "College expiration year" },
    { name = "COLL_EXEMPTION_PCT", type = "FLOAT64", mode = "NULLABLE", description = "College exemption percentage" },
    { name = "COLL_BASE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "College base value" },
    { name = "COLL_VAL_DIF", type = "FLOAT64", mode = "NULLABLE", description = "College value difference" },
    { name = "COLL_EXEMPTION_AMT", type = "FLOAT64", mode = "NULLABLE", description = "College exemption amount" },
    { name = "SPEC_EFF_YR", type = "INTEGER", mode = "NULLABLE", description = "Special district effective year" },
    { name = "SPEC_EXP_YR", type = "INTEGER", mode = "NULLABLE", description = "Special district expiration year" },
    { name = "SPEC_EXEMPTION_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Special district exemption percentage" },
    { name = "SPEC_BASE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Special district base value" },
    { name = "SPEC_VAL_DIF", type = "FLOAT64", mode = "NULLABLE", description = "Special district value difference" },
    { name = "SPEC_EXEMPTION_AMT", type = "FLOAT64", mode = "NULLABLE", description = "Special district exemption amount" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# ACCOUNT_APPRL_YEAR - Main appraisal year data with valuations
resource "google_bigquery_table" "account_apprl_year" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "account_apprl_year"
  description         = "Account appraisal year data with valuations and jurisdiction details"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "IMPR_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Improvement value" },
    { name = "LAND_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Land value" },
    { name = "LAND_AG_EXEMPT", type = "FLOAT64", mode = "NULLABLE", description = "Land agricultural exempt value" },
    { name = "AG_USE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Agricultural use value" },
    { name = "TOT_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Total value" },
    { name = "HMSTD_CAP_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Homestead cap value" },
    { name = "REVAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Revaluation year" },
    { name = "PREV_REVAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Previous revaluation year" },
    { name = "PREV_MKT_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Previous market value" },
    { name = "TOT_CONTRIB_AMT", type = "FLOAT64", mode = "NULLABLE", description = "Total contribution amount" },
    { name = "TAXPAYER_REP", type = "STRING", mode = "NULLABLE", description = "Taxpayer representative" },
    { name = "CITY_JURIS_DESC", type = "STRING", mode = "NULLABLE", description = "City jurisdiction description" },
    { name = "COUNTY_JURIS_DESC", type = "STRING", mode = "NULLABLE", description = "County jurisdiction description" },
    { name = "ISD_JURIS_DESC", type = "STRING", mode = "NULLABLE", description = "ISD jurisdiction description" },
    { name = "HOSPITAL_JURIS_DESC", type = "STRING", mode = "NULLABLE", description = "Hospital jurisdiction description" },
    { name = "COLLEGE_JURIS_DESC", type = "STRING", mode = "NULLABLE", description = "College jurisdiction description" },
    { name = "SPECIAL_DIST_JURIS_DESC", type = "STRING", mode = "NULLABLE", description = "Special district jurisdiction description" },
    { name = "CITY_SPLIT_PCT", type = "FLOAT64", mode = "NULLABLE", description = "City split percentage" },
    { name = "COUNTY_SPLIT_PCT", type = "FLOAT64", mode = "NULLABLE", description = "County split percentage" },
    { name = "ISD_SPLIT_PCT", type = "FLOAT64", mode = "NULLABLE", description = "ISD split percentage" },
    { name = "HOSPITAL_SPLIT_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Hospital split percentage" },
    { name = "COLLEGE_SPLIT_PCT", type = "FLOAT64", mode = "NULLABLE", description = "College split percentage" },
    { name = "SPECIAL_DIST_SPLIT_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Special district split percentage" },
    { name = "CITY_TAXABLE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "City taxable value" },
    { name = "COUNTY_TAXABLE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "County taxable value" },
    { name = "ISD_TAXABLE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "ISD taxable value" },
    { name = "HOSPITAL_TAXABLE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Hospital taxable value" },
    { name = "COLLEGE_TAXABLE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "College taxable value" },
    { name = "SPECIAL_DIST_TAXABLE_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Special district taxable value" },
    { name = "CITY_CEILING_VALUE", type = "FLOAT64", mode = "NULLABLE", description = "City ceiling value" },
    { name = "COUNTY_CEILING_VALUE", type = "FLOAT64", mode = "NULLABLE", description = "County ceiling value" },
    { name = "ISD_CEILING_VALUE", type = "FLOAT64", mode = "NULLABLE", description = "ISD ceiling value" },
    { name = "HOSPITAL_CEILING_VALUE", type = "FLOAT64", mode = "NULLABLE", description = "Hospital ceiling value" },
    { name = "COLLEGE_CEILING_VALUE", type = "FLOAT64", mode = "NULLABLE", description = "College ceiling value" },
    { name = "SPECIAL_DIST_CEILING_VALUE", type = "FLOAT64", mode = "NULLABLE", description = "Special district ceiling value" },
    { name = "VID_IND", type = "STRING", mode = "NULLABLE", description = "VID indicator" },
    { name = "GIS_PARCEL_ID", type = "STRING", mode = "NULLABLE", description = "GIS parcel ID" },
    { name = "APPRAISAL_METH_CD", type = "STRING", mode = "NULLABLE", description = "Appraisal method code" },
    { name = "RENDITION_PENALTY", type = "STRING", mode = "NULLABLE", description = "Rendition penalty indicator" },
    { name = "DIVISION_CD", type = "STRING", mode = "NULLABLE", description = "Division code" },
    { name = "EXTRNL_CNTY_ACCT", type = "STRING", mode = "NULLABLE", description = "External county account" },
    { name = "EXTRNL_CITY_ACCT", type = "STRING", mode = "NULLABLE", description = "External city account" },
    { name = "P_BUS_TYP_CD", type = "STRING", mode = "NULLABLE", description = "Property business type code" },
    { name = "BLDG_CLASS_CD", type = "STRING", mode = "NULLABLE", description = "Building class code" },
    { name = "SPTD_CODE", type = "STRING", mode = "NULLABLE", description = "SPTD code" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# ACCOUNT_INFO - Account/owner/property information
resource "google_bigquery_table" "account_info" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "account_info"
  description         = "Account, owner, and property information"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "DIVISION_CD", type = "STRING", mode = "NULLABLE", description = "Division code" },
    { name = "BIZ_NAME", type = "STRING", mode = "NULLABLE", description = "Business name" },
    { name = "OWNER_NAME1", type = "STRING", mode = "NULLABLE", description = "Owner name line 1" },
    { name = "OWNER_NAME2", type = "STRING", mode = "NULLABLE", description = "Owner name line 2" },
    { name = "EXCLUDE_OWNER", type = "STRING", mode = "NULLABLE", description = "Exclude owner indicator" },
    { name = "OWNER_ADDRESS_LINE1", type = "STRING", mode = "NULLABLE", description = "Owner address line 1" },
    { name = "OWNER_ADDRESS_LINE2", type = "STRING", mode = "NULLABLE", description = "Owner address line 2" },
    { name = "OWNER_ADDRESS_LINE3", type = "STRING", mode = "NULLABLE", description = "Owner address line 3" },
    { name = "OWNER_ADDRESS_LINE4", type = "STRING", mode = "NULLABLE", description = "Owner address line 4" },
    { name = "OWNER_CITY", type = "STRING", mode = "NULLABLE", description = "Owner city" },
    { name = "OWNER_STATE", type = "STRING", mode = "NULLABLE", description = "Owner state" },
    { name = "OWNER_ZIPCODE", type = "STRING", mode = "NULLABLE", description = "Owner zip code" },
    { name = "OWNER_COUNTRY", type = "STRING", mode = "NULLABLE", description = "Owner country" },
    { name = "STREET_NUM", type = "STRING", mode = "NULLABLE", description = "Street number" },
    { name = "STREET_HALF_NUM", type = "STRING", mode = "NULLABLE", description = "Street half number" },
    { name = "FULL_STREET_NAME", type = "STRING", mode = "NULLABLE", description = "Full street name" },
    { name = "BLDG_ID", type = "STRING", mode = "NULLABLE", description = "Building ID" },
    { name = "UNIT_ID", type = "STRING", mode = "NULLABLE", description = "Unit ID" },
    { name = "PROPERTY_CITY", type = "STRING", mode = "NULLABLE", description = "Property city" },
    { name = "PROPERTY_ZIPCODE", type = "STRING", mode = "NULLABLE", description = "Property zip code" },
    { name = "MAPSCO", type = "STRING", mode = "NULLABLE", description = "Mapsco reference" },
    { name = "NBHD_CD", type = "STRING", mode = "NULLABLE", description = "Neighborhood code" },
    { name = "LEGAL1", type = "STRING", mode = "NULLABLE", description = "Legal description line 1" },
    { name = "LEGAL2", type = "STRING", mode = "NULLABLE", description = "Legal description line 2" },
    { name = "LEGAL3", type = "STRING", mode = "NULLABLE", description = "Legal description line 3" },
    { name = "LEGAL4", type = "STRING", mode = "NULLABLE", description = "Legal description line 4" },
    { name = "LEGAL5", type = "STRING", mode = "NULLABLE", description = "Legal description line 5" },
    { name = "DEED_TXFR_DATE", type = "STRING", mode = "NULLABLE", description = "Deed transfer date" },
    { name = "GIS_PARCEL_ID", type = "STRING", mode = "NULLABLE", description = "GIS parcel ID" },
    { name = "PHONE_NUM", type = "STRING", mode = "NULLABLE", description = "Phone number" },
    { name = "LMA", type = "STRING", mode = "NULLABLE", description = "LMA code" },
    { name = "IMA", type = "STRING", mode = "NULLABLE", description = "IMA code" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# ACCOUNT_TIF - Tax Increment Financing data
resource "google_bigquery_table" "account_tif" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "account_tif"
  description         = "Tax Increment Financing (TIF) zone data"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "TIF_ZONE_DESC", type = "STRING", mode = "NULLABLE", description = "TIF zone description" },
    { name = "EFFECTIVE_YR", type = "INTEGER", mode = "NULLABLE", description = "Effective year" },
    { name = "EXPIRATION_YR", type = "INTEGER", mode = "NULLABLE", description = "Expiration year" },
    { name = "ACCT_MKT", type = "FLOAT64", mode = "NULLABLE", description = "Account market value" },
    { name = "CITY_PCT", type = "FLOAT64", mode = "NULLABLE", description = "City percentage" },
    { name = "CITY_BASE_MKT", type = "FLOAT64", mode = "NULLABLE", description = "City base market value" },
    { name = "CITY_BASE_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "City base taxable value" },
    { name = "CITY_ACCT_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "City account taxable value" },
    { name = "CNTY_PCT", type = "FLOAT64", mode = "NULLABLE", description = "County percentage" },
    { name = "CNTY_BASE_MKT", type = "FLOAT64", mode = "NULLABLE", description = "County base market value" },
    { name = "CNTY_BASE_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "County base taxable value" },
    { name = "CNTY_ACCT_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "County account taxable value" },
    { name = "ISD_PCT", type = "FLOAT64", mode = "NULLABLE", description = "ISD percentage" },
    { name = "ISD_BASE_MKT", type = "FLOAT64", mode = "NULLABLE", description = "ISD base market value" },
    { name = "ISD_BASE_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "ISD base taxable value" },
    { name = "ISD_ACCT_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "ISD account taxable value" },
    { name = "HOSP_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Hospital percentage" },
    { name = "HOSP_BASE_MKT", type = "FLOAT64", mode = "NULLABLE", description = "Hospital base market value" },
    { name = "HOSP_BASE_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "Hospital base taxable value" },
    { name = "HOSP_ACCT_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "Hospital account taxable value" },
    { name = "COLL_PCT", type = "FLOAT64", mode = "NULLABLE", description = "College percentage" },
    { name = "COLL_BASE_MKT", type = "FLOAT64", mode = "NULLABLE", description = "College base market value" },
    { name = "COLL_BASE_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "College base taxable value" },
    { name = "COLL_ACCT_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "College account taxable value" },
    { name = "SPEC_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Special district percentage" },
    { name = "SPEC_BASE_MKT", type = "FLOAT64", mode = "NULLABLE", description = "Special district base market value" },
    { name = "SPEC_BASE_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "Special district base taxable value" },
    { name = "SPEC_ACCT_TAXABLE", type = "FLOAT64", mode = "NULLABLE", description = "Special district account taxable value" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# ACCT_EXEMPT_VALUE - Exemption values by type
resource "google_bigquery_table" "acct_exempt_value" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "acct_exempt_value"
  description         = "Account exemption values by exemption type and jurisdiction"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "SORTORDER", type = "INTEGER", mode = "NULLABLE", description = "Sort order" },
    { name = "EXEMPTION_CD", type = "STRING", mode = "NULLABLE", description = "Exemption code" },
    { name = "EXEMPTION", type = "STRING", mode = "NULLABLE", description = "Exemption description" },
    { name = "CITY_APPLD_VAL", type = "FLOAT64", mode = "NULLABLE", description = "City applied value" },
    { name = "CNTY_APPLD_VAL", type = "FLOAT64", mode = "NULLABLE", description = "County applied value" },
    { name = "ISD_APPLD_VAL", type = "FLOAT64", mode = "NULLABLE", description = "ISD applied value" },
    { name = "HOSPITAL_APPLD_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Hospital applied value" },
    { name = "COLLEGE_APPLD_VAL", type = "FLOAT64", mode = "NULLABLE", description = "College applied value" },
    { name = "SPCL_APPLIED_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Special district applied value" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# APPLIED_STD_EXEMPT - Applied standard exemptions (homestead, over 65, etc.)
resource "google_bigquery_table" "applied_std_exempt" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "applied_std_exempt"
  description         = "Applied standard exemptions including homestead, over 65, disabled, and veteran"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "OWNER_SEQ_NUM", type = "INTEGER", mode = "NULLABLE", description = "Owner sequence number" },
    { name = "EXEMPT_STATUS_CD", type = "STRING", mode = "NULLABLE", description = "Exemption status code" },
    { name = "OWNERSHIP_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Ownership percentage" },
    { name = "APPLICANT_NAME", type = "STRING", mode = "NULLABLE", description = "Applicant name" },
    { name = "HOMESTEAD_EFF_DT", type = "STRING", mode = "NULLABLE", description = "Homestead effective date" },
    { name = "OVER65_DESC", type = "STRING", mode = "NULLABLE", description = "Over 65 description" },
    { name = "DISABLED_DESC", type = "STRING", mode = "NULLABLE", description = "Disabled description" },
    { name = "TAX_DEFERRED_DESC", type = "STRING", mode = "NULLABLE", description = "Tax deferred description" },
    { name = "CITY_CEIL_TAX_VAL", type = "FLOAT64", mode = "NULLABLE", description = "City ceiling tax value" },
    { name = "CITY_CEIL_DT", type = "STRING", mode = "NULLABLE", description = "City ceiling date" },
    { name = "CITY_CEIL_XFER_PCT", type = "FLOAT64", mode = "NULLABLE", description = "City ceiling transfer percentage" },
    { name = "CITY_CEIL_SET_IND", type = "STRING", mode = "NULLABLE", description = "City ceiling set indicator" },
    { name = "COUNTY_CEIL_TAX_VAL", type = "FLOAT64", mode = "NULLABLE", description = "County ceiling tax value" },
    { name = "COUNTY_CEIL_DT", type = "STRING", mode = "NULLABLE", description = "County ceiling date" },
    { name = "COUNTY_CEIL_XFER_PCT", type = "FLOAT64", mode = "NULLABLE", description = "County ceiling transfer percentage" },
    { name = "COUNTY_CEIL_SET_IND", type = "STRING", mode = "NULLABLE", description = "County ceiling set indicator" },
    { name = "ISD_CEIL_TAX_VAL", type = "FLOAT64", mode = "NULLABLE", description = "ISD ceiling tax value" },
    { name = "ISD_CEIL_DT", type = "STRING", mode = "NULLABLE", description = "ISD ceiling date" },
    { name = "ISD_CEIL_XFER_PCT", type = "FLOAT64", mode = "NULLABLE", description = "ISD ceiling transfer percentage" },
    { name = "ISD_CEIL_SET_IND", type = "STRING", mode = "NULLABLE", description = "ISD ceiling set indicator" },
    { name = "COLLEGE_CEIL_TAX_VAL", type = "FLOAT64", mode = "NULLABLE", description = "College ceiling tax value" },
    { name = "COLLEGE_CEIL_DT", type = "STRING", mode = "NULLABLE", description = "College ceiling date" },
    { name = "COLLEGE_CEIL_XFER_PCT", type = "FLOAT64", mode = "NULLABLE", description = "College ceiling transfer percentage" },
    { name = "COLLEGE_CEIL_SET_IND", type = "STRING", mode = "NULLABLE", description = "College ceiling set indicator" },
    { name = "DISABLE_EFF_DT", type = "STRING", mode = "NULLABLE", description = "Disabled effective date" },
    { name = "VET_EFF_YR", type = "INTEGER", mode = "NULLABLE", description = "Veteran effective year" },
    { name = "VET_DISABLE_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Veteran disability percentage" },
    { name = "VET_FLAT_AMT", type = "FLOAT64", mode = "NULLABLE", description = "Veteran flat amount" },
    { name = "VET2_EFF_YR", type = "INTEGER", mode = "NULLABLE", description = "Veteran 2 effective year" },
    { name = "VET2_DISABLE_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Veteran 2 disability percentage" },
    { name = "VET2_FLAT_AMT", type = "FLOAT64", mode = "NULLABLE", description = "Veteran 2 flat amount" },
    { name = "CAPPED_HS_AMT", type = "FLOAT64", mode = "NULLABLE", description = "Capped homestead amount" },
    { name = "HS_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Homestead percentage" },
    { name = "TOT_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Total value" },
    { name = "PRORATE_IND", type = "STRING", mode = "NULLABLE", description = "Prorate indicator" },
    { name = "DAYS_TAXABLE", type = "STRING", mode = "NULLABLE", description = "Days taxable" },
    { name = "PRORATE_EFF_DT", type = "STRING", mode = "NULLABLE", description = "Prorate effective date" },
    { name = "PRORATE_EXP_DT", type = "STRING", mode = "NULLABLE", description = "Prorate expiration date" },
    { name = "PRORATE_NAME", type = "STRING", mode = "NULLABLE", description = "Prorate name" },
    { name = "OVER65_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Over 65 percentage" },
    { name = "DISABLEDPCT", type = "FLOAT64", mode = "NULLABLE", description = "Disabled percentage" },
    { name = "XFER_IND", type = "STRING", mode = "NULLABLE", description = "Transfer indicator" },
    { name = "CIRCUIT_BK_FLG", type = "STRING", mode = "NULLABLE", description = "Circuit breaker flag" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# COM_DETAIL - Commercial building details
resource "google_bigquery_table" "com_detail" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "com_detail"
  description         = "Commercial building detail information"
  deletion_protection = false

  schema = jsonencode([
    { name = "TAX_OBJ_ID", type = "STRING", mode = "NULLABLE", description = "Tax object ID" },
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "BLDG_CLASS_DESC", type = "STRING", mode = "NULLABLE", description = "Building class description" },
    { name = "YEAR_BUILT", type = "INTEGER", mode = "NULLABLE", description = "Year built" },
    { name = "REMODEL_YR", type = "INTEGER", mode = "NULLABLE", description = "Remodel year" },
    { name = "GROSS_BLDG_AREA", type = "FLOAT64", mode = "NULLABLE", description = "Gross building area" },
    { name = "FOUNDATION_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Foundation type description" },
    { name = "FOUNDATION_AREA", type = "FLOAT64", mode = "NULLABLE", description = "Foundation area" },
    { name = "BASEMENT_DESC", type = "STRING", mode = "NULLABLE", description = "Basement description" },
    { name = "BASEMENT_AREA", type = "FLOAT64", mode = "NULLABLE", description = "Basement area" },
    { name = "NUM_STORIES", type = "INTEGER", mode = "NULLABLE", description = "Number of stories" },
    { name = "CONSTR_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Construction type description" },
    { name = "HEATING_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Heating type description" },
    { name = "AC_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "AC type description" },
    { name = "NUM_UNITS", type = "INTEGER", mode = "NULLABLE", description = "Number of units" },
    { name = "NET_LEASE_AREA", type = "FLOAT64", mode = "NULLABLE", description = "Net lease area" },
    { name = "PROPERTY_NAME", type = "STRING", mode = "NULLABLE", description = "Property name" },
    { name = "PROPERTY_QUAL_DESC", type = "STRING", mode = "NULLABLE", description = "Property quality description" },
    { name = "PROPERTY_COND_DESC", type = "STRING", mode = "NULLABLE", description = "Property condition description" },
    { name = "PHYS_DEPR_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Physical depreciation percentage" },
    { name = "FUNCT_DEPR_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Functional depreciation percentage" },
    { name = "EXTRNL_DEPR_PCT", type = "FLOAT64", mode = "NULLABLE", description = "External depreciation percentage" },
    { name = "TOT_DEPR_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Total depreciation percentage" },
    { name = "IMP_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Improvement value" },
    { name = "LAND_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Land value" },
    { name = "MKT_VAL", type = "FLOAT64", mode = "NULLABLE", description = "Market value" },
    { name = "APPR_METHOD_DESC", type = "STRING", mode = "NULLABLE", description = "Appraisal method description" },
    { name = "COMPARABILITY_CD", type = "STRING", mode = "NULLABLE", description = "Comparability code" },
    { name = "PCT_COMPLETE", type = "FLOAT64", mode = "NULLABLE", description = "Percent complete" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# FREEPORT_EXEMPTION - Freeport exemption flags
resource "google_bigquery_table" "freeport_exemption" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "freeport_exemption"
  description         = "Freeport exemption indicator flags"
  deletion_protection = false

  schema = jsonencode([
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "LATE_APP_IND", type = "STRING", mode = "NULLABLE", description = "Late application indicator" },
    { name = "LATE_DOC_IND", type = "STRING", mode = "NULLABLE", description = "Late documentation indicator" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# LAND - Land details (dimensions, zoning, values)
resource "google_bigquery_table" "land" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "land"
  description         = "Land parcel details including dimensions, zoning, and values"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "SECTION_NUM", type = "INTEGER", mode = "NULLABLE", description = "Section number" },
    { name = "SPTD_CD", type = "STRING", mode = "NULLABLE", description = "SPTD code" },
    { name = "SPTD_DESC", type = "STRING", mode = "NULLABLE", description = "SPTD description" },
    { name = "ZONING", type = "STRING", mode = "NULLABLE", description = "Zoning" },
    { name = "FRONT_DIM", type = "FLOAT64", mode = "NULLABLE", description = "Front dimension" },
    { name = "DEPTH_DIM", type = "FLOAT64", mode = "NULLABLE", description = "Depth dimension" },
    { name = "AREA_SIZE", type = "FLOAT64", mode = "NULLABLE", description = "Area size" },
    { name = "AREA_UOM_DESC", type = "STRING", mode = "NULLABLE", description = "Area unit of measure description" },
    { name = "PRICING_METH_DESC", type = "STRING", mode = "NULLABLE", description = "Pricing method description" },
    { name = "COST_PER_UOM", type = "FLOAT64", mode = "NULLABLE", description = "Cost per unit of measure" },
    { name = "MARKET_ADJ_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Market adjustment percentage" },
    { name = "VAL_AMT", type = "FLOAT64", mode = "NULLABLE", description = "Value amount" },
    { name = "AG_USE_IND", type = "STRING", mode = "NULLABLE", description = "Agricultural use indicator" },
    { name = "ACCT_AG_VAL_AMT", type = "FLOAT64", mode = "NULLABLE", description = "Account agricultural value amount" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# MULTI_OWNER - Multiple owners
resource "google_bigquery_table" "multi_owner" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "multi_owner"
  description         = "Multiple owner records for properties with shared ownership"
  deletion_protection = false

  schema = jsonencode([
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "OWNER_SEQ_NUM", type = "INTEGER", mode = "NULLABLE", description = "Owner sequence number" },
    { name = "OWNER_NAME", type = "STRING", mode = "NULLABLE", description = "Owner name" },
    { name = "OWNERSHIP_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Ownership percentage" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# RES_ADDL - Residential additional improvements
resource "google_bigquery_table" "res_addl" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "res_addl"
  description         = "Residential additional improvements (garages, pools, etc.)"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "TAX_OBJ_ID", type = "STRING", mode = "NULLABLE", description = "Tax object ID" },
    { name = "SEQ_NUM", type = "INTEGER", mode = "NULLABLE", description = "Sequence number" },
    { name = "IMPR_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Improvement type description" },
    { name = "IMPR_DESC", type = "STRING", mode = "NULLABLE", description = "Improvement description" },
    { name = "YR_BUILT", type = "INTEGER", mode = "NULLABLE", description = "Year built" },
    { name = "CONSTR_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Construction type description" },
    { name = "FLOOR_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Floor type description" },
    { name = "EXT_WALL_DESC", type = "STRING", mode = "NULLABLE", description = "Exterior wall description" },
    { name = "NUM_STORIES", type = "INTEGER", mode = "NULLABLE", description = "Number of stories" },
    { name = "AREA_SIZE", type = "FLOAT64", mode = "NULLABLE", description = "Area size" },
    { name = "VAL_AMT", type = "FLOAT64", mode = "NULLABLE", description = "Value amount" },
    { name = "DEPRECIATION_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Depreciation percentage" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# RES_DETAIL - Residential building details
resource "google_bigquery_table" "res_detail" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "res_detail"
  description         = "Residential building detail information"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "TAX_OBJ_ID", type = "STRING", mode = "NULLABLE", description = "Tax object ID" },
    { name = "BLDG_CLASS_DESC", type = "STRING", mode = "NULLABLE", description = "Building class description" },
    { name = "YR_BUILT", type = "INTEGER", mode = "NULLABLE", description = "Year built" },
    { name = "EFF_YR_BUILT", type = "INTEGER", mode = "NULLABLE", description = "Effective year built" },
    { name = "ACT_AGE", type = "INTEGER", mode = "NULLABLE", description = "Actual age" },
    { name = "CDU_RATING_DESC", type = "STRING", mode = "NULLABLE", description = "CDU rating description" },
    { name = "TOT_MAIN_SF", type = "FLOAT64", mode = "NULLABLE", description = "Total main square feet" },
    { name = "TOT_LIVING_AREA_SF", type = "FLOAT64", mode = "NULLABLE", description = "Total living area square feet" },
    { name = "PCT_COMPLETE", type = "FLOAT64", mode = "NULLABLE", description = "Percent complete" },
    { name = "NUM_STORIES_DESC", type = "STRING", mode = "NULLABLE", description = "Number of stories description" },
    { name = "CONSTR_FRAM_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Construction frame type description" },
    { name = "FOUNDATION_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Foundation type description" },
    { name = "HEATING_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Heating type description" },
    { name = "AC_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "AC type description" },
    { name = "FENCE_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Fence type description" },
    { name = "EXT_WALL_DESC", type = "STRING", mode = "NULLABLE", description = "Exterior wall description" },
    { name = "BASEMENT_DESC", type = "STRING", mode = "NULLABLE", description = "Basement description" },
    { name = "ROOF_TYP_DESC", type = "STRING", mode = "NULLABLE", description = "Roof type description" },
    { name = "ROOF_MAT_DESC", type = "STRING", mode = "NULLABLE", description = "Roof material description" },
    { name = "NUM_FIREPLACES", type = "INTEGER", mode = "NULLABLE", description = "Number of fireplaces" },
    { name = "NUM_KITCHENS", type = "INTEGER", mode = "NULLABLE", description = "Number of kitchens" },
    { name = "NUM_FULL_BATHS", type = "INTEGER", mode = "NULLABLE", description = "Number of full baths" },
    { name = "NUM_HALF_BATHS", type = "INTEGER", mode = "NULLABLE", description = "Number of half baths" },
    { name = "NUM_WET_BARS", type = "INTEGER", mode = "NULLABLE", description = "Number of wet bars" },
    { name = "NUM_BEDROOMS", type = "INTEGER", mode = "NULLABLE", description = "Number of bedrooms" },
    { name = "SPRINKLER_SYS_IND", type = "STRING", mode = "NULLABLE", description = "Sprinkler system indicator" },
    { name = "DECK_IND", type = "STRING", mode = "NULLABLE", description = "Deck indicator" },
    { name = "SPA_IND", type = "STRING", mode = "NULLABLE", description = "Spa indicator" },
    { name = "POOL_IND", type = "STRING", mode = "NULLABLE", description = "Pool indicator" },
    { name = "SAUNA_IND", type = "STRING", mode = "NULLABLE", description = "Sauna indicator" },
    { name = "MBL_HOME_SER_NUM", type = "STRING", mode = "NULLABLE", description = "Mobile home serial number" },
    { name = "MBL_HOME_MANUFCTR", type = "STRING", mode = "NULLABLE", description = "Mobile home manufacturer" },
    { name = "MBL_HOME_LENGTH", type = "INTEGER", mode = "NULLABLE", description = "Mobile home length" },
    { name = "MBL_HOME_WIDTH", type = "INTEGER", mode = "NULLABLE", description = "Mobile home width" },
    { name = "MBL_HOME_SPACE", type = "STRING", mode = "NULLABLE", description = "Mobile home space" },
    { name = "DEPRECIATION_PCT", type = "FLOAT64", mode = "NULLABLE", description = "Depreciation percentage" },
    { name = "NUM_UNITS", type = "INTEGER", mode = "NULLABLE", description = "Number of units" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# TAXABLE_OBJECT - Taxable object IDs
resource "google_bigquery_table" "taxable_object" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "taxable_object"
  description         = "Taxable object identifiers"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "TAX_OBJ_ID", type = "STRING", mode = "NULLABLE", description = "Tax object ID" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# TOTAL_EXEMPTION - Total exemption flag
resource "google_bigquery_table" "total_exemption" {
  dataset_id          = google_bigquery_dataset.dallas.dataset_id
  table_id            = "total_exemption"
  description         = "Accounts with total exemption"
  deletion_protection = false

  schema = jsonencode([
    { name = "ACCOUNT_NUM", type = "STRING", mode = "NULLABLE", description = "Account number" },
    { name = "APPRAISAL_YR", type = "INTEGER", mode = "NULLABLE", description = "Appraisal year" },
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}

# =============================================================================
# VIEWS
# =============================================================================

# View: Core Property - Joins account info, valuations, and land
resource "google_bigquery_table" "view_property_core" {
  dataset_id = google_bigquery_dataset.dallas.dataset_id
  table_id   = "v_property_core"

  view {
    query          = <<-SQL
      SELECT
        -- Account identifiers
        ai.ACCOUNT_NUM,
        ai.APPRAISAL_YR,
        ai.GIS_PARCEL_ID,
        ay.DIVISION_CD,

        -- Owner info
        ai.OWNER_NAME1,
        ai.OWNER_NAME2,
        ai.BIZ_NAME,
        ai.OWNER_CITY,
        ai.OWNER_STATE,
        ai.OWNER_ZIPCODE,

        -- Property address
        ai.STREET_NUM,
        ai.FULL_STREET_NAME,
        CONCAT(COALESCE(ai.STREET_NUM, ''), ' ', COALESCE(ai.FULL_STREET_NAME, '')) AS property_address,
        ai.UNIT_ID,
        ai.PROPERTY_CITY,
        ai.PROPERTY_ZIPCODE,
        ai.NBHD_CD,

        -- Legal description
        ai.LEGAL1,
        ai.LEGAL2,
        ai.DEED_TXFR_DATE,

        -- Valuations
        ay.LAND_VAL,
        ay.IMPR_VAL,
        ay.TOT_VAL,
        ay.HMSTD_CAP_VAL,
        ay.PREV_MKT_VAL,

        -- Taxable values by jurisdiction
        ay.CITY_TAXABLE_VAL,
        ay.COUNTY_TAXABLE_VAL,
        ay.ISD_TAXABLE_VAL,

        -- Jurisdictions
        ay.CITY_JURIS_DESC,
        ay.COUNTY_JURIS_DESC,
        ay.ISD_JURIS_DESC,

        -- Land details (first section)
        l.SPTD_CD,
        l.SPTD_DESC,
        l.ZONING,
        l.AREA_SIZE AS land_area_size,
        l.AREA_UOM_DESC AS land_area_uom,
        l.VAL_AMT AS land_val_amt,

        -- Metadata
        ai.load_timestamp

      FROM `${var.project_id}.${var.dataset_id}.account_info` ai
      JOIN `${var.project_id}.${var.dataset_id}.account_apprl_year` ay
        ON ai.ACCOUNT_NUM = ay.ACCOUNT_NUM
        AND ai.APPRAISAL_YR = ay.APPRAISAL_YR
      LEFT JOIN `${var.project_id}.${var.dataset_id}.land` l
        ON ai.ACCOUNT_NUM = l.ACCOUNT_NUM
        AND ai.APPRAISAL_YR = l.APPRAISAL_YR
        AND l.SECTION_NUM = 1  -- Primary land section only
    SQL
    use_legacy_sql = false
  }

  depends_on = [
    google_bigquery_table.account_info,
    google_bigquery_table.account_apprl_year,
    google_bigquery_table.land
  ]
}

# View: Residential Properties - Core + residential building details
resource "google_bigquery_table" "view_residential" {
  dataset_id = google_bigquery_dataset.dallas.dataset_id
  table_id   = "v_residential"

  view {
    query          = <<-SQL
      SELECT
        -- Core property fields
        p.ACCOUNT_NUM,
        p.APPRAISAL_YR,
        p.GIS_PARCEL_ID,
        p.OWNER_NAME1,
        p.property_address,
        p.UNIT_ID,
        p.PROPERTY_CITY,
        p.PROPERTY_ZIPCODE,
        p.NBHD_CD,

        -- Valuations
        p.LAND_VAL,
        p.IMPR_VAL,
        p.TOT_VAL,
        p.CITY_TAXABLE_VAL,
        p.COUNTY_TAXABLE_VAL,
        p.ISD_TAXABLE_VAL,

        -- Land
        p.SPTD_DESC,
        p.ZONING,
        p.land_area_size,
        p.land_area_uom,

        -- Building details
        rd.BLDG_CLASS_DESC,
        rd.YR_BUILT,
        rd.EFF_YR_BUILT,
        rd.ACT_AGE,
        rd.CDU_RATING_DESC,
        rd.TOT_LIVING_AREA_SF,
        rd.PCT_COMPLETE,
        rd.NUM_STORIES_DESC,
        rd.FOUNDATION_TYP_DESC,
        rd.EXT_WALL_DESC,
        rd.ROOF_TYP_DESC,
        rd.HEATING_TYP_DESC,
        rd.AC_TYP_DESC,
        rd.NUM_BEDROOMS,
        rd.NUM_FULL_BATHS,
        rd.NUM_HALF_BATHS,
        rd.NUM_FIREPLACES,
        rd.POOL_IND,
        rd.DEPRECIATION_PCT,
        rd.NUM_UNITS,

        -- Calculated fields
        SAFE_DIVIDE(p.TOT_VAL, NULLIF(rd.TOT_LIVING_AREA_SF, 0)) AS val_per_sqft,
        SAFE_DIVIDE(p.IMPR_VAL, NULLIF(rd.TOT_LIVING_AREA_SF, 0)) AS impr_val_per_sqft

      FROM `${var.project_id}.${var.dataset_id}.v_property_core` p
      JOIN `${var.project_id}.${var.dataset_id}.res_detail` rd
        ON p.ACCOUNT_NUM = rd.ACCOUNT_NUM
        AND p.APPRAISAL_YR = rd.APPRAISAL_YR
      WHERE p.DIVISION_CD = 'RES'
    SQL
    use_legacy_sql = false
  }

  depends_on = [
    google_bigquery_table.view_property_core,
    google_bigquery_table.res_detail
  ]
}

# View: Commercial Properties - Core + commercial building details
resource "google_bigquery_table" "view_commercial" {
  dataset_id = google_bigquery_dataset.dallas.dataset_id
  table_id   = "v_commercial"

  view {
    query          = <<-SQL
      SELECT
        -- Core property fields
        p.ACCOUNT_NUM,
        p.APPRAISAL_YR,
        p.GIS_PARCEL_ID,
        p.OWNER_NAME1,
        p.BIZ_NAME,
        p.property_address,
        p.PROPERTY_CITY,
        p.PROPERTY_ZIPCODE,
        p.NBHD_CD,

        -- Valuations
        p.LAND_VAL,
        p.IMPR_VAL,
        p.TOT_VAL,

        -- Land
        p.SPTD_DESC,
        p.ZONING,
        p.land_area_size,
        p.land_area_uom,

        -- Commercial building details
        cd.TAX_OBJ_ID,
        cd.BLDG_CLASS_DESC,
        cd.YEAR_BUILT,
        cd.REMODEL_YR,
        cd.GROSS_BLDG_AREA,
        cd.NET_LEASE_AREA,
        cd.NUM_STORIES,
        cd.NUM_UNITS,
        cd.FOUNDATION_TYP_DESC,
        cd.CONSTR_TYP_DESC,
        cd.HEATING_TYP_DESC,
        cd.AC_TYP_DESC,
        cd.PROPERTY_NAME,
        cd.PROPERTY_QUAL_DESC,
        cd.PROPERTY_COND_DESC,
        cd.PHYS_DEPR_PCT,
        cd.FUNCT_DEPR_PCT,
        cd.EXTRNL_DEPR_PCT,
        cd.TOT_DEPR_PCT,
        cd.APPR_METHOD_DESC,

        -- Calculated fields
        SAFE_DIVIDE(p.TOT_VAL, NULLIF(cd.GROSS_BLDG_AREA, 0)) AS val_per_sqft,
        SAFE_DIVIDE(p.TOT_VAL, NULLIF(cd.NET_LEASE_AREA, 0)) AS val_per_lease_sqft

      FROM `${var.project_id}.${var.dataset_id}.v_property_core` p
      JOIN `${var.project_id}.${var.dataset_id}.com_detail` cd
        ON p.ACCOUNT_NUM = cd.ACCOUNT_NUM
        AND p.APPRAISAL_YR = cd.APPRAISAL_YR
      WHERE p.DIVISION_CD = 'COM'
    SQL
    use_legacy_sql = false
  }

  depends_on = [
    google_bigquery_table.view_property_core,
    google_bigquery_table.com_detail
  ]
}

# View: Property with Exemptions - Shows homestead and other exemptions
resource "google_bigquery_table" "view_property_exemptions" {
  dataset_id = google_bigquery_dataset.dallas.dataset_id
  table_id   = "v_property_exemptions"

  view {
    query          = <<-SQL
      SELECT
        p.ACCOUNT_NUM,
        p.APPRAISAL_YR,
        p.OWNER_NAME1,
        p.property_address,
        p.PROPERTY_CITY,
        p.TOT_VAL,
        p.COUNTY_TAXABLE_VAL,
        p.ISD_TAXABLE_VAL,

        -- Exemption details
        ase.APPLICANT_NAME,
        ase.HOMESTEAD_EFF_DT,
        ase.OVER65_DESC,
        ase.DISABLED_DESC,
        ase.TAX_DEFERRED_DESC,
        ase.HS_PCT,
        ase.OVER65_PCT,
        ase.DISABLEDPCT AS DISABLED_PCT,
        ase.VET_DISABLE_PCT,
        ase.CAPPED_HS_AMT,

        -- Ceiling values (tax freeze)
        ase.COUNTY_CEIL_TAX_VAL,
        ase.ISD_CEIL_TAX_VAL,

        -- Flags
        CASE WHEN ase.HS_PCT > 0 THEN TRUE ELSE FALSE END AS has_homestead,
        CASE WHEN ase.OVER65_DESC NOT IN ('UNASSIGNED', '') THEN TRUE ELSE FALSE END AS has_over65,
        CASE WHEN ase.DISABLED_DESC NOT IN ('UNASSIGNED', '') THEN TRUE ELSE FALSE END AS has_disabled,
        CASE WHEN ase.VET_DISABLE_PCT > 0 THEN TRUE ELSE FALSE END AS has_veteran

      FROM `${var.project_id}.${var.dataset_id}.v_property_core` p
      JOIN `${var.project_id}.${var.dataset_id}.applied_std_exempt` ase
        ON p.ACCOUNT_NUM = ase.ACCOUNT_NUM
        AND p.APPRAISAL_YR = ase.APPRAISAL_YR
    SQL
    use_legacy_sql = false
  }

  depends_on = [
    google_bigquery_table.view_property_core,
    google_bigquery_table.applied_std_exempt
  ]
}
