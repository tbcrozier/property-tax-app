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

railroad/             # Rail line proximity data
  load_rail_lines.py  # Script to download NARN rail data and load to BigQuery
  data/
    rail_lines.json   # Downloaded rail line data (newline-delimited JSON)

floodzone/            # FEMA flood zone data
  load_floodzone.py   # Script to download FEMA NFHL data and load to BigQuery
  data/
    flood_zones.json  # Downloaded flood zone data (newline-delimited JSON)
```

## Data Sources

### Davidson County Parcels
- Source: Nashville Open Data ArcGIS Hub
- API: `services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Parcels_view/FeatureServer/0`
- Total records: ~286k parcels
- Key fields: `ParID`, `TotlAppr`, `LandAppr`, `ImprAppr`, `Acres`, `LUDesc`, `Zoning`, `Lat`, `Lon`

### Railroad / Rail Lines (NARN)
- Source: BTS NTAD North American Rail Network (NARN) via ArcGIS FeatureServer
- API: `services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_North_American_Rail_Network_Lines/FeatureServer/0`
- Coverage: Filtered to Davidson County (FIPS 47037) by default, can fetch entire state
- Key fields: `RROWNER1` (owner), `PASSNGR` (passenger rail), `STRACNET` (strategic corridor), `TRACKS`, `MILES`
- Geometry: LineString (GEOGRAPHY type in BigQuery)

### FEMA Flood Zones (NFHL)
- Source: FEMA National Flood Hazard Layer (NFHL) via ArcGIS MapServer
- API: `hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28` (Flood Hazard Zones layer)
- Coverage: Filtered by DFIRM_ID (county FIPS code), Davidson County (47037) by default
- Key fields: `FLD_ZONE` (zone code), `ZONE_SUBTY` (subtype), `SFHA_TF` (Special Flood Hazard Area)
- Geometry: Polygon/MultiPolygon (GEOGRAPHY type in BigQuery)
- Flood Zone Codes:
  - `A`, `AE`, `AH`, `AO`, `AR`, `A99`: High-risk areas (1% annual flood chance / 100-year floodplain)
  - `V`, `VE`: High-risk coastal areas with wave action
  - `X` (with subtype): Moderate-risk areas (500-year floodplain)
  - `X` (minimal): Minimal flood hazard
  - `D`: Undetermined risk

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

### Load Rail Line Data
```bash
cd railroad

# Download Davidson County rail lines
python3 load_rail_lines.py

# Download entire Tennessee
python3 load_rail_lines.py --state 47

# Show available fields
python3 load_rail_lines.py --show-fields

# Load JSON to BigQuery (handles GEOGRAPHY conversion automatically)
python3 load_rail_lines.py --load-bq --truncate
```

### Load Flood Zone Data
```bash
cd floodzone

# Download Davidson County flood zones
python3 load_floodzone.py

# Download flood zones for a different county (by FIPS code)
python3 load_floodzone.py --county 47157  # Shelby County (Memphis)

# Show available fields
python3 load_floodzone.py --show-fields

# Load JSON to BigQuery (handles GEOGRAPHY conversion automatically)
python3 load_floodzone.py --load-bq --truncate
```

## BigQuery Resources
- **Dataset**: `property_tax`
- **Tables**:
  - `davidson_parcels` - Raw parcel data from Nashville assessor
  - `rail_lines` - NARN rail line geometry for proximity analysis
  - `fema_floodplain` - FEMA NFHL flood zone polygons for flood risk analysis
- **Views**:
  - `v_assessment_by_land_use` - Summary stats by land use type
  - `v_assessment_outliers` - Parcels with z-score > 2 or < -2 (potential over/under assessed)
  - `v_assessment_sale_ratio` - Compares assessment to sale price for recent sales
  - `v_neighborhood_comparison` - Compares properties to zip code peers
  - `v_appeal_candidates` - Composite appeal strength score (0-100) with savings estimate
  - `v_single_family_appeals` - Filtered view for single family homes with score > 20
  - `v_parcel_rail_enrichment` - Distance to nearest rail line with proximity flags (100m/250m/500m/1000m)
  - `v_parcel_floodzone_enrichment` - Flood zone status for each parcel with risk classification


Table public-data-dev:property_tax.davidson_parcels

   Last modified               Schema              Total Rows   Total Bytes   Expiration   Time Partitioning   Clustered Fields   Total Logical Bytes   Total Physical Bytes   Labels
 ----------------- ------------------------------ ------------ ------------- ------------ ------------------- ------------------ --------------------- ---------------------- --------
  02 Apr 22:02:38   |- OBJECTID: integer           286176       117236010                                                         117236010             22069656
                    |- STANPAR: string
                    |- FEATURETYPE: string
                    |- FLOORNUMBER: string
                    |- ParID: string
                    |- Tract: string
                    |- Council: string
                    |- TaxDist: string
                    |- Owner: string
                    |- OwnDate: date
                    |- SalePrice: float
                    |- OwnInstr: string
                    |- OwnAddr1: string
                    |- OwnAddr2: string
                    |- OwnAddr3: string
                    |- OwnCity: string
                    |- OwnState: string
                    |- OwnCountry: string
                    |- OwnZip: string
                    |- PropAddr: string
                    |- PropHouse: string
                    |- PropFraction: string
                    |- PropStreet: string
                    |- PropSuite: string
                    |- PropCity: string
                    |- PropState: string
                    |- PropZip: string
                    |- LegalDesc: string
                    |- PropInstr: string
                    |- PropDate: date
                    |- Acres: float
                    |- Front: float
                    |- Side: float
                    |- IsRegular: string
                    |- LUCode: string
                    |- LUDesc: string
                    |- LandAppr: float
                    |- ImprAppr: float
                    |- TotlAppr: float
                    |- Zoning: string
                    |- Shape__Area: float
                    |- Lat: float
                    |- Lon: float
                    |- load_timestamp: timestamp




## Appeal Analytics

### Appeal Strength Score (0-100)
Properties are scored based on multiple signals:
- **Z-score vs land use peers** (max 30 pts) - How many std devs above average
- **% above zip code median** (max 30 pts) - Local neighborhood comparison
- **% above land use median** (max 20 pts) - County-wide comparison
- **Assessment > sale price** (max 20 pts) - If assessed higher than recent sale

### Appeal Recommendations
- `STRONG_CANDIDATE` - z-score > 2 AND >20% above zip median
- `MODERATE_CANDIDATE` - z-score > 1.5 OR >30% above zip median
- `WORTH_REVIEWING` - z-score > 1 OR >15% above zip median
- `LIKELY_FAIR` - Assessment appears reasonable

