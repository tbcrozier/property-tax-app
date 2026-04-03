# Property Tax App

## Overview
Comparative analysis tool for property tax assessments. Goal: identify parcels that are assessed too high or too low by comparing against similar properties. 

## Project Structure
```
infra/                # Terraform infrastructure
  main.tf             # BigQuery dataset, table, and views
  variables.tf        # Variable definitions
  outputs.tf          # Output values
  terraform.tfvars    # Variable values (gitignored)

parcels/
  davidson/           # Davidson County (Nashville, TN)
    extract_parcels.py  # Script to fetch parcel data from ArcGIS API
    data/
      features.csv      # Raw parcel data
```

## Data Sources

### Davidson County
- Source: Nashville Open Data ArcGIS Hub
- API: `services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Parcels_view/FeatureServer/0`
- Total records: ~286k parcels
- Key fields: `ParID`, `TotlAppr`, `LandAppr`, `ImprAppr`, `Acres`, `LUDesc`, `Zoning`, `Lat`, `Lon`

## Usage

### Extract Davidson County data
```bash
cd parcels/davidson

# Test with 100 parcels
python3 extract_parcels.py --count 100

# Fetch all parcels
python3 extract_parcels.py --count 300000

# Show available fields
python3 extract_parcels.py --show-fields

# Load CSV to BigQuery (append)
python3 extract_parcels.py --load-bq

# Load CSV to BigQuery (truncate/replace)
python3 extract_parcels.py --load-bq --truncate
```

### Deploy BigQuery Infrastructure
```bash
cd infra

# Initialize Terraform
terraform init

# Review changes
terraform plan

# Apply infrastructure
terraform apply
```

## BigQuery Resources
- **Dataset**: `property_tax`
- **Table**: `davidson_parcels` - Raw parcel data
- **Views**:
  - `v_assessment_by_land_use` - Summary stats by land use type
  - `v_assessment_outliers` - Parcels with z-score > 2 or < -2 (potential over/under assessed)

