# Dallas County Appraisal District (DCAD) Data

## Overview

Property tax assessment data from Dallas County Appraisal District for tax year 2026.

**Data Source:** DCAD2026_CURRENT (certified appraisal data export)

## Directory Structure

```
dallas/
├── dallas.md              # This file
├── load_dcad.py           # Python script to load CSVs to BigQuery
├── DCAD2026_CURRENT/      # Raw CSV data files (not committed)
│   ├── ACCOUNT_INFO.CSV
│   ├── ACCOUNT_APPRL_YEAR.CSV
│   ├── RES_DETAIL.CSV
│   └── ... (14 CSV files total)
└── infra/                 # Terraform configuration
    ├── main.tf            # Dataset + table definitions
    ├── variables.tf       # Project, region, dataset variables
    └── outputs.tf         # Output values
```

## BigQuery

**Dataset:** `dallas`
**Project:** `public-data-dev`

### Tables

| Table | Description | Key Fields |
|-------|-------------|------------|
| `account_info` | Owner/property information | ACCOUNT_NUM, OWNER_NAME1, property address, legal description |
| `account_apprl_year` | Valuations and jurisdictions | ACCOUNT_NUM, IMPR_VAL, LAND_VAL, TOT_VAL, taxable values by jurisdiction |
| `res_detail` | Residential building details | TAX_OBJ_ID, YR_BUILT, TOT_LIVING_AREA_SF, bedrooms, baths |
| `com_detail` | Commercial building details | TAX_OBJ_ID, YEAR_BUILT, GROSS_BLDG_AREA, depreciation |
| `land` | Land parcel details | ACCOUNT_NUM, SPTD_CD, ZONING, AREA_SIZE, VAL_AMT |
| `abatement_exempt` | Tax abatements by jurisdiction | ACCOUNT_NUM, exemption amounts by city/county/ISD/college/special |
| `applied_std_exempt` | Standard exemptions | ACCOUNT_NUM, homestead, over65, disabled, veteran info |
| `acct_exempt_value` | Exemption values by type | ACCOUNT_NUM, EXEMPTION_CD, applied values by jurisdiction |
| `account_tif` | Tax Increment Financing | ACCOUNT_NUM, TIF_ZONE_DESC, base values by jurisdiction |
| `res_addl` | Residential additional improvements | TAX_OBJ_ID, IMPR_TYP_DESC (garage, pool, etc.) |
| `multi_owner` | Multiple owner records | ACCOUNT_NUM, OWNER_NAME, OWNERSHIP_PCT |
| `freeport_exemption` | Freeport exemption flags | ACCOUNT_NUM, LATE_APP_IND, LATE_DOC_IND |
| `taxable_object` | Taxable object identifiers | ACCOUNT_NUM, TAX_OBJ_ID |
| `total_exemption` | Total exemption flags | ACCOUNT_NUM, APPRAISAL_YR |

### Views

| View | Description |
|------|-------------|
| `v_property_core` | Joins account_info + account_apprl_year + land. Core property data with valuations. |
| `v_residential` | Core + res_detail. Residential properties with building details and $/sqft. |
| `v_commercial` | Core + com_detail. Commercial properties with building details and $/sqft. |
| `v_property_exemptions` | Core + applied_std_exempt. Properties with homestead, over65, disabled, veteran flags. |

### Key Relationships

- `ACCOUNT_NUM` - Primary identifier linking most tables
- `TAX_OBJ_ID` - Links improvement tables (res_detail, com_detail, res_addl) to accounts
- `GIS_PARCEL_ID` - Links to GIS/spatial data (in account_info and account_apprl_year)
- `DIVISION_CD` - Property type: RES (residential), COM (commercial), BPP (business personal property)

## Usage

### Deploy Infrastructure

```bash
cd parcels/dallas/infra
terraform init
terraform apply
```

### Load Data

```bash
cd parcels/dallas

# Load all tables (replace existing data)
python load_dcad.py --truncate

# Load all tables (append)
python load_dcad.py

# Load specific tables
python load_dcad.py --tables account_info res_detail land

# Preview without loading
python load_dcad.py --dry-run
```

### Example Queries

```sql
-- Using v_property_core view (simplest)
SELECT *
FROM `public-data-dev.dallas.v_property_core`
WHERE APPRAISAL_YR = 2026
  AND PROPERTY_CITY = 'DALLAS'
LIMIT 100;

-- Residential properties with value per sqft
SELECT
  ACCOUNT_NUM,
  property_address,
  PROPERTY_CITY,
  TOT_VAL,
  TOT_LIVING_AREA_SF,
  val_per_sqft,
  YR_BUILT,
  NUM_BEDROOMS,
  NUM_FULL_BATHS
FROM `public-data-dev.dallas.v_residential`
WHERE APPRAISAL_YR = 2026
ORDER BY val_per_sqft DESC
LIMIT 100;

-- Properties with homestead exemption
SELECT
  ACCOUNT_NUM,
  property_address,
  TOT_VAL,
  COUNTY_TAXABLE_VAL,
  has_homestead,
  has_over65,
  COUNTY_CEIL_TAX_VAL AS tax_freeze_value
FROM `public-data-dev.dallas.v_property_exemptions`
WHERE APPRAISAL_YR = 2026
  AND has_homestead = TRUE;

-- Raw table join (if you need more control)
SELECT
  ai.ACCOUNT_NUM,
  ai.OWNER_NAME1,
  ai.STREET_NUM || ' ' || ai.FULL_STREET_NAME AS property_address,
  ay.LAND_VAL,
  ay.IMPR_VAL,
  ay.TOT_VAL
FROM `public-data-dev.dallas.account_info` ai
JOIN `public-data-dev.dallas.account_apprl_year` ay
  ON ai.ACCOUNT_NUM = ay.ACCOUNT_NUM
  AND ai.APPRAISAL_YR = ay.APPRAISAL_YR
WHERE ai.APPRAISAL_YR = 2026;
```

## Notes

- All tables include `load_timestamp` column added during data load
- DCAD data uses `ACCOUNT_NUM` as the primary key (17-character string)
- `APPRAISAL_YR` should be included in joins for multi-year data
- Dates in source data are stored as strings (MM/DD/YYYY format)

## TODO

- [x] Add views for common analysis patterns (v_property_core, v_residential, v_commercial, v_property_exemptions)
- [ ] Add spatial/GIS integration if parcel geometry available
- [ ] Create appeal candidate analysis views (similar to Davidson)
- [ ] Add neighborhood comparison views
- [ ] Add assessment ratio analysis views
