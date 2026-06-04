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

# BigQuery Dataset for St. Louis County
resource "google_bigquery_dataset" "st_louis" {
  dataset_id  = var.dataset_id
  description = "St. Louis County property tax assessment data"
  location    = var.region

  labels = {
    env = "dev"
  }
}

# BigQuery Table - St. Louis County Parcels
resource "google_bigquery_table" "parcels" {
  dataset_id          = google_bigquery_dataset.st_louis.dataset_id
  table_id            = "parcels"
  description         = "St. Louis County (MO) parcel assessment data"
  deletion_protection = false

  schema = jsonencode([
    { name = "OBJECTID", type = "INTEGER", mode = "NULLABLE", description = "ArcGIS object ID" },
    { name = "LOCATOR", type = "STRING", mode = "NULLABLE", description = "Parcel locator ID" },
    { name = "PARENT_LOC", type = "STRING", mode = "NULLABLE", description = "Parent locator" },

    # Property Address
    { name = "PROP_ADRNUM", type = "STRING", mode = "NULLABLE", description = "Property address number" },
    { name = "PROP_ADD", type = "STRING", mode = "NULLABLE", description = "Property address" },
    { name = "PROP_ZIP", type = "STRING", mode = "NULLABLE", description = "Property zip code" },

    # Owner Information
    { name = "OWNER_NAME", type = "STRING", mode = "NULLABLE", description = "Owner name" },
    { name = "CAREOF", type = "STRING", mode = "NULLABLE", description = "Care of" },
    { name = "OWN_ADD", type = "STRING", mode = "NULLABLE", description = "Owner address" },
    { name = "OWN_CITY", type = "STRING", mode = "NULLABLE", description = "Owner city" },
    { name = "OWN_STATE", type = "STRING", mode = "NULLABLE", description = "Owner state" },
    { name = "OWN_ZIP", type = "STRING", mode = "NULLABLE", description = "Owner zip code" },

    # Valuation Data
    { name = "APPLANDVAL", type = "FLOAT64", mode = "NULLABLE", description = "Appraised land value" },
    { name = "APPIMPVAL", type = "FLOAT64", mode = "NULLABLE", description = "Appraised improvements value" },
    { name = "TOTAPVAL", type = "FLOAT64", mode = "NULLABLE", description = "Total appraised value" },
    { name = "ASSTLANDVAL", type = "FLOAT64", mode = "NULLABLE", description = "Assessed land value" },
    { name = "ASSTIMPVAL", type = "FLOAT64", mode = "NULLABLE", description = "Assessed improvements value" },
    { name = "TOTASSMT", type = "FLOAT64", mode = "NULLABLE", description = "Total assessed value" },

    # Property Characteristics
    { name = "ACRES", type = "FLOAT64", mode = "NULLABLE", description = "Parcel acreage" },
    { name = "RESQFT", type = "FLOAT64", mode = "NULLABLE", description = "Residential square footage" },
    { name = "COMSTRUC", type = "FLOAT64", mode = "NULLABLE", description = "Commercial structure square footage" },
    { name = "YEARBLT", type = "INTEGER", mode = "NULLABLE", description = "Year built" },
    { name = "LIVUNIT", type = "INTEGER", mode = "NULLABLE", description = "Living units" },
    { name = "BLDGNAME", type = "STRING", mode = "NULLABLE", description = "Building name" },
    { name = "TENURE", type = "STRING", mode = "NULLABLE", description = "Tenure type" },

    # Land Use
    { name = "PROPCLASS", type = "STRING", mode = "NULLABLE", description = "Property class" },
    { name = "LANDUSE2", type = "STRING", mode = "NULLABLE", description = "Land use description" },
    { name = "LANDUSE3", type = "INTEGER", mode = "NULLABLE", description = "Additional land use code" },
    { name = "LUC", type = "STRING", mode = "NULLABLE", description = "Land use code" },
    { name = "LUCODE", type = "STRING", mode = "NULLABLE", description = "Land use category" },

    # Legal Description
    { name = "LEGAL", type = "STRING", mode = "NULLABLE", description = "Legal description" },
    { name = "SUBDIVISION", type = "STRING", mode = "NULLABLE", description = "Subdivision name" },
    { name = "BLOCKNUM", type = "STRING", mode = "NULLABLE", description = "Block number" },
    { name = "LOTNUM", type = "STRING", mode = "NULLABLE", description = "Lot number" },
    { name = "LOTFRONT", type = "STRING", mode = "NULLABLE", description = "Lot frontage" },
    { name = "LOTDEPTH", type = "STRING", mode = "NULLABLE", description = "Lot depth" },
    { name = "LOTDIM", type = "STRING", mode = "NULLABLE", description = "Lot dimensions" },

    # Deed Information
    { name = "DEEDBKPG", type = "STRING", mode = "NULLABLE", description = "Deed book and page" },
    { name = "DEEDTYPE", type = "STRING", mode = "NULLABLE", description = "Deed type" },
    { name = "RECDATEDAILY", type = "STRING", mode = "NULLABLE", description = "Recording date" },

    # Jurisdictional
    { name = "MUNICIPALITY", type = "STRING", mode = "NULLABLE", description = "Municipality" },
    { name = "MUNYCODE", type = "STRING", mode = "NULLABLE", description = "Municipality code" },
    { name = "MUNI_WARD", type = "STRING", mode = "NULLABLE", description = "Municipal ward" },
    { name = "MUNI_ZONING", type = "STRING", mode = "NULLABLE", description = "Municipal zoning" },
    { name = "ZONING", type = "STRING", mode = "NULLABLE", description = "Zoning" },
    { name = "TWP", type = "STRING", mode = "NULLABLE", description = "Township code" },
    { name = "TWPNAME", type = "STRING", mode = "NULLABLE", description = "Township name" },
    { name = "NBHD", type = "STRING", mode = "NULLABLE", description = "Neighborhood" },

    # Districts
    { name = "COUNTY_COUNCIL", type = "INTEGER", mode = "NULLABLE", description = "County council district" },
    { name = "SCHOOL_DISTRICT", type = "STRING", mode = "NULLABLE", description = "School district" },
    { name = "SCHOOLCODE", type = "INTEGER", mode = "NULLABLE", description = "School code" },
    { name = "SCHSUB", type = "STRING", mode = "NULLABLE", description = "School subdistrict" },
    { name = "SPECIAL_SCHOOL", type = "INTEGER", mode = "NULLABLE", description = "Special school district" },
    { name = "JR_COLLEGE", type = "INTEGER", mode = "NULLABLE", description = "Junior college district" },
    { name = "FIRE_DISTRICT", type = "STRING", mode = "NULLABLE", description = "Fire district" },
    { name = "LIBRARY_DISTRICT", type = "STRING", mode = "NULLABLE", description = "Library district" },
    { name = "LIGHT_DISTRICT", type = "STRING", mode = "NULLABLE", description = "Light district" },
    { name = "TRASH_DISTRICT", type = "INTEGER", mode = "NULLABLE", description = "Trash district" },
    { name = "TRASH_OPTOUT", type = "STRING", mode = "NULLABLE", description = "Trash opt-out" },
    { name = "CODE_ENFORCEMENT_DISTRICT", type = "INTEGER", mode = "NULLABLE", description = "Code enforcement district" },

    # Political
    { name = "STATE_REP", type = "INTEGER", mode = "NULLABLE", description = "State representative district" },
    { name = "STATE_SENATE", type = "INTEGER", mode = "NULLABLE", description = "State senate district" },
    { name = "US_CONGRESS", type = "INTEGER", mode = "NULLABLE", description = "US Congress district" },

    # Census
    { name = "CENSUS_TRACT", type = "STRING", mode = "NULLABLE", description = "Census tract" },
    { name = "CENSUS_BLOCKGROUP", type = "STRING", mode = "NULLABLE", description = "Census block group" },

    # Tax
    { name = "TAXCODE", type = "STRING", mode = "NULLABLE", description = "Tax code" },
    { name = "TAXYR", type = "INTEGER", mode = "NULLABLE", description = "Tax year" },

    # Other
    { name = "ASRBKPG", type = "STRING", mode = "NULLABLE", description = "Assessor book and page" },
    { name = "COGIS", type = "STRING", mode = "NULLABLE", description = "COGIS identifier" },
    { name = "FIRM_PANEL", type = "STRING", mode = "NULLABLE", description = "FEMA FIRM panel" },
    { name = "PMZ_NEIGHBORHOOD", type = "INTEGER", mode = "NULLABLE", description = "PMZ neighborhood" },

    # Metadata
    { name = "load_timestamp", type = "TIMESTAMP", mode = "NULLABLE", description = "When the record was loaded" }
  ])
}
