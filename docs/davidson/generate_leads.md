# Davidson County Appeal Lead Generator

## Objective

Generate a list of Single Family properties in Davidson County where the property assessment exceeds the median of comparable properties by enough to justify the $200 customer acquisition cost through first-year tax savings.

This tool enables scalable lead generation for property tax appeal services by identifying homeowners most likely to benefit from an appeal.

---

## Requirements

### System Requirements

- Python 3.10+
- Google Cloud SDK with BigQuery access
- Authentication to `public-data-dev` GCP project

### Python Dependencies

```bash
pip install google-cloud-bigquery
```

### Data Requirements

The following BigQuery tables must be available:

| Table | Description |
|-------|-------------|
| `public-data-dev.property_tax.davidson_parcels` | Davidson County parcel data with assessments |
| `public-data-dev.property_tax.davidson_building_characteristics` | Building details (year built, sqft) |

---

## Lead Qualification Criteria

### Property Type Filter
- **Include**: Single Family only (`LUDesc = 'SINGLE FAMILY'`)
- **Exclude**: All other property types (condos, duplexes, commercial, etc.)

### Recent Sale Exclusion
- **Exclude**: Properties sold within last 2 years (730 days)
- **Rationale**: Recent sales likely have accurate market-based assessments

### Minimum Savings Threshold
- **Default**: $200 first-year tax savings
- **Rationale**: Must cover customer acquisition cost

---

## Lead Qualification Formula

```
Tax Savings = (Current Assessment - Median Comparable Assessment) × 25% × 3.254%

Where:
- 25% = Tennessee residential assessment ratio
- 3.254% = Davidson County tax rate (per $100 of assessed value)

Minimum Lead Threshold: Savings ≥ $200
Required Over-Assessment: ≥ $24,585 (~$25,000)
```

### Example Calculation

| Field | Value |
|-------|-------|
| Current Assessment | $500,000 |
| Median Comparable | $450,000 |
| Over-Assessment | $50,000 |
| Assessed Value Reduction | $50,000 × 25% = $12,500 |
| Tax Savings | $12,500 × 3.254% = $406.75 |

---

## Comparable Cohort Definition

Properties are grouped into cohorts based on:

| Dimension | Grouping Logic |
|-----------|----------------|
| Location | Same zip code |
| Land Use | Same LUDesc (SINGLE FAMILY) |
| Age | Same decade (e.g., 1980-1989) |
| Size | Same 500 sqft band (e.g., 1500-1999) |

### Cohort Size Requirement
- Minimum 5 properties per cohort
- Cohorts with fewer properties are excluded (unreliable median)

---

## Output Schema

| Column | Type | Description |
|--------|------|-------------|
| `parid` | STRING | Parcel ID |
| `address` | STRING | Property street address |
| `owner_name` | STRING | Owner name |
| `owner_address` | STRING | Mailing address (for outreach) |
| `current_assessment` | FLOAT | Current TotlAppr |
| `median_comparable` | FLOAT | Median assessment of cohort |
| `over_assessment` | FLOAT | Current - Median |
| `estimated_savings` | FLOAT | First-year tax savings |
| `num_comparables` | INT | Size of comparable cohort |
| `year_built` | INT | Year property was built |
| `sqft` | FLOAT | Finished square footage |
| `land_use` | STRING | Land use description |
| `in_flood_zone` | STRING | "Yes" or "No" - FEMA flood zone status |

---

## Runbook

### Basic Usage

```bash
cd /path/to/property-tax-app

# Generate leads with default $200 minimum savings
python analysis/generate_leads.py --output leads.csv

# Preview the SQL query without executing
python analysis/generate_leads.py --show-query
```

### Common Scenarios

#### Generate Premium Leads ($500+ savings)

```bash
python analysis/generate_leads.py \
  --min-savings 500 \
  --output premium_leads.csv
```

#### Generate Limited Sample for Testing

```bash
python analysis/generate_leads.py \
  --limit 100 \
  --output sample_leads.csv
```

#### Export as JSON

```bash
python analysis/generate_leads.py \
  --format json \
  --output leads.json
```

#### Adjust Comparable Criteria

```bash
python analysis/generate_leads.py \
  --min-comparables 10 \
  --exclude-recent-sales 365 \
  --output conservative_leads.csv
```

### CLI Options Reference

| Option | Default | Description |
|--------|---------|-------------|
| `--min-savings` | 200 | Minimum first-year tax savings to qualify |
| `--year-range` | 10 | Year built range for cohort grouping |
| `--sqft-range` | 25 | Square footage % range for cohorts |
| `--min-comparables` | 5 | Minimum cohort size for reliable median |
| `--exclude-recent-sales` | 730 | Exclude sales within N days |
| `--output` | stdout | Output file path |
| `--format` | csv | Output format (csv or json) |
| `--limit` | unlimited | Maximum leads to return |
| `--project` | public-data-dev | GCP project ID |
| `--dataset` | property_tax | BigQuery dataset |
| `--show-query` | false | Print SQL without executing |

---

## Verification Steps

### 1. Spot-Check Individual Leads

Use `compare_property.py` to verify a lead's assessment vs comparables:

```bash
python analysis/compare_property.py --parid "181782.0"
```

### 2. Verify Savings Calculation

For a lead with:
- `current_assessment`: $500,000
- `median_comparable`: $450,000

Manual calculation:
```
Over-assessment: $500,000 - $450,000 = $50,000
Savings: $50,000 × 0.25 × 0.03254 = $406.75
```

### 3. Check Cohort Reasonableness

Review that the `num_comparables` count is reasonable (5-100 properties). Very large cohorts may indicate overly broad grouping.

---

## Known Limitations

### Data Quality Issues

1. **Misclassified Properties**: Some non-residential properties may be coded as SINGLE FAMILY (e.g., public housing, institutional properties)

2. **Duplicate Leads**: A property may appear multiple times if it falls into different cohorts based on building characteristics data

3. **Missing Building Data**: Properties without year_built or finished_area are excluded

### Methodology Limitations

1. **Cohort Boundaries**: Using fixed bands (decades, 500 sqft) may split similar properties into different cohorts

2. **No Location Quality**: Properties in the same zip code may be in very different neighborhoods

3. **Assessment Timing**: Data reflects point-in-time assessments; may not reflect recent appeals or corrections

---

## BigQuery Cost Estimation

The query scans approximately:
- `davidson_parcels`: ~180,000 rows
- `davidson_building_characteristics`: ~150,000 rows

Estimated cost per run: < $0.10 (depends on current BigQuery pricing)

---

## Troubleshooting

### "No leads found"

1. Check `--min-savings` threshold - try lowering it
2. Verify BigQuery connectivity: `bq ls public-data-dev:property_tax`
3. Check if tables exist and have data

### "Permission denied"

1. Ensure `GOOGLE_APPLICATION_CREDENTIALS` is set
2. Verify access to `public-data-dev` project
3. Run `gcloud auth application-default login`

### Duplicate ParIDs in output

This is expected behavior - a property may match multiple cohorts. Filter duplicates in post-processing if needed:

```bash
# Keep only highest savings per parcel
sort -t',' -k8 -rn leads.csv | awk -F',' '!seen[$1]++' > deduped_leads.csv
```

---

## Ideas for Improvement

### Cohort Refinement

- **Lot size as cohort dimension**: Add parcel acreage or lot square footage as a comparison criteria. This would limit outliers where land value is significantly higher than peers due to larger lots. Currently, a 0.25 acre lot and a 2 acre lot in the same zip/decade/sqft band are compared equally, which can skew the median unfairly.

- **Geographic clustering**: Use neighborhood-level grouping instead of zip code. Properties in the same zip can be in vastly different micro-markets.

### Data Quality Filters

- **Institutional/exempt property filter**: Exclude properties owned by housing authorities (MDHA), churches, government entities by owner name patterns. These are often misclassified as SINGLE FAMILY.

- **Maximum appraisal cap**: Filter out properties above a threshold (e.g., $3M) to avoid ultra-high-value homes where comps are harder to defend.

### Appeal Success Indicators

- **Property condition signals**: Incorporate building permit data to identify homes with/without recent renovations.

- **Appeal success probability score**: Historical appeal outcomes by cohort to estimate win likelihood.

- **Flood zone leverage**: Properties in flood zones may have stronger arguments for land value reduction.

### Expanded Scope

- **Support additional land use types**: Condos, duplexes, townhomes.

- **Multi-county support**: Extend to Shelby (Memphis), Knox (Knoxville), etc.
