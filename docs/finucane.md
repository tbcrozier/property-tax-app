# Property Tax Assessment Analysis - Handoff Document

## Project Overview

**Repository**: `/Users/tbcjr/repos/github/tbcrozier/property-tax-app`
**Branch**: `feature/finucane`
**GCP Project**: `public-data-dev`
**BigQuery Dataset**: `property_tax`

---

## What We Built This Session

### 1. Property Comparison Analysis Tool

Created `analysis/compare_property.py` - a CLI tool that:
- Looks up a property by address or ParID
- Finds comparable properties based on defined criteria
- Calculates statistics (mean, median, z-score, percentile)
- Generates text or JSON reports with appeal recommendations

**Usage:**
```bash
python analysis/compare_property.py --address "1045 LYNNWOOD BLVD"
python analysis/compare_property.py --parid "237054.0" --format json
```

**Comparison Criteria Defaults:**
- Same zip code
- Same land use type (e.g., SINGLE FAMILY)
- Year built: +/- 10 years
- Square footage: +/- 25%

---

## Available BigQuery Tables & Views

### Core Tables
| Table | Description | Key Fields |
|-------|-------------|------------|
| `davidson_parcels` | Property assessment data | ParID, STANPAR, PropAddr, TotlAppr, LandAppr, ImprAppr, Acres, LUDesc, PropZip |
| `davidson_building_characteristics` | Building details | apn (joins to STANPAR), finished_area, year_built, structure_type, exterior |
| `building_permits_nashville` | Building permits | Address, Permit_Type_Description, Purpose, Construction_Cost, Date_Issued |
| `fema_floodzone` | FEMA flood data | Flood zone polygons |
| `rail_lines` | Railroad proximity | Rail line geometries |

### Pre-built Views
| View | Purpose |
|------|---------|
| `v_appeal_candidates` | Composite appeal score (0-100) with savings estimates |
| `v_neighborhood_comparison` | Zip-code peer analysis |
| `v_parcel_building_enrichment` | Parcels joined with building characteristics |
| `v_parcel_floodzone_enrichment` | Parcels with flood zone risk assessment |
| `v_parcel_rail_enrichment` | Parcels with distance to nearest rail line |
| `v_assessment_outliers` | Properties with z-score > 2 or < -2 |

---

## Case Study: 1045 Lynnwood Blvd (Finucane Property)

### Property Details
- **ParID**: 237054.0
- **STANPAR**: 14402001300
- **Owner**: FINUCANE, SHANNON LEE MCCUTCHIN, TRUSTEE
- **Assessment**: $3,066,100 (Land: $910K, Improvements: $2.16M)
- **Specs**: 6,440 sqft, built 1959, brick, 2.18 acres
- **Zoning**: 5ZZ (Belle Meade area - no Metro Nashville zoning)
- **Price/SqFt**: $476.10

### Analysis Results
- **Z-score**: -0.02 (essentially at the mean for comparables)
- **Percentile**: ~60th (slightly above median)
- **Flood Zone**: NOT_IN_FLOOD_ZONE
- **Rail Proximity**: 8,256 ft (1.56 miles) - not a factor
- **Initial Recommendation**: LIKELY_FAIR - no strong appeal case

### Key Finding: Invalid Comparables
When we checked Zillow for beds/baths on the comps, we found:

**Subject**: 5 beds, 7 baths, 6,440 sqft

**Invalid comps identified:**
- **6113 Chickering Ct**: Only 3 beds, 2-3 baths, 2,612 sqft - 60% smaller!
- **6224 Hillsboro Pike**: Only 4 beds, 3 baths - half the bathrooms

**Valid comps:**
- 4401 Tyne Blvd: 5 beds, 6.5-8 baths, 6,914 sqft
- 4504 Shys Hill Rd: 5 beds, 6 baths, 6,002 sqft
- 4411 Tyne Blvd: 6 beds, 7-8 baths, 6,359 sqft

**Potential Appeal Argument**: If assessor used non-comparable properties (wrong bed/bath count), methodology is flawed.

---

## What Needs to Be Built Next

### Goal: Multi-Property Analysis Pipeline

Input: List of property addresses or ParIDs
Output: In-depth analysis report for each property with appeal recommendations

### Suggested Analysis Components

1. **Core Assessment Analysis** (already built)
   - Find comparable properties (same zip, land use, year, sqft)
   - Calculate z-score, percentile, % above median
   - Generate appeal strength score

2. **Environmental Risk Factors** (data exists)
   - Flood zone check via `v_parcel_floodzone_enrichment`
   - Rail proximity via `v_parcel_rail_enrichment`
   - These factors could LOWER assessments if present

3. **Building Permits Check** (data exists)
   - Query `building_permits_nashville` for recent renovations
   - Comps with major renovations shouldn't be compared to un-renovated homes
   - Note: Belle Meade properties may not appear (separate permit system)

4. **Zillow/Web Enrichment** (to explore)
   - Get actual beds/baths to validate comparability
   - Get recent sale prices (Zestimate) to compare to assessment
   - Identify renovations not captured in permits

### Suggested Output Format

For each property, generate:
```
PROPERTY APPEAL ANALYSIS: [ADDRESS]
=====================================

PROPERTY SUMMARY
- Assessment: $X
- Specs: X beds, X baths, X sqft
- Year Built: XXXX

ENVIRONMENTAL FACTORS
- Flood Zone: [RISK LEVEL or NOT IN FLOOD ZONE]
- Rail Proximity: [X feet - IMPACT/NO IMPACT]

COMPARABLE ANALYSIS
- Comparables Found: X
- Price/SqFt: $XXX (Subject) vs $XXX (Median)
- Z-Score: X.XX
- Percentile: XXth

COMPARABLES VALIDATION (from Zillow)
- [Address]: X bed/X bath - [VALID/INVALID COMP]

APPEAL RECOMMENDATION
- Strength Score: XX/100
- Recommendation: [STRONG_CANDIDATE / MODERATE / LIKELY_FAIR]
- Key Arguments:
  1. [...]
  2. [...]

ESTIMATED SAVINGS: $XXX/year
```

---

## Key SQL Patterns

### Join Building Characteristics
```sql
SELECT p.*, b.year_built, b.finished_area, b.structure_type
FROM davidson_parcels p
LEFT JOIN davidson_building_characteristics b ON p.STANPAR = b.apn
WHERE p.PropAddr LIKE '%LYNNWOOD%'
```

### Check Flood Zone
```sql
SELECT * FROM v_parcel_floodzone_enrichment
WHERE parcel_id = '237054.0'
```

### Check Rail Proximity
```sql
SELECT * FROM v_parcel_rail_enrichment
WHERE parcel_id = '237054.0'
```

### Search Building Permits
```sql
SELECT Address, Permit_Type_Description, Purpose, Construction_Cost
FROM building_permits_nashville
WHERE UPPER(Address) LIKE '%LYNNWOOD%'
```

---

## Files Created/Modified

- `analysis/compare_property.py` - Main comparison tool (created)
- `analysis/data/` - Output directory for reports (created)

---

## Notes

- **Belle Meade (5ZZ zoning)**: Independent city within Davidson County. Properties may not appear in Nashville permit database.
- **Building characteristics join**: Use `STANPAR` from parcels to `apn` in building_characteristics
- **Zillow access**: Direct URL fetch blocked (403). Use WebSearch to find property details on Redfin/Zillow/Trulia.
