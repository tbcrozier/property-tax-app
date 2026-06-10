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
| `public-data-dev.property_tax.v_parcel_floodzone_enrichment` | FEMA flood zone data |

---

## Lead Qualification Criteria

### Property Type Filter
- **Include**: Single Family only (`LUDesc = 'SINGLE FAMILY'`)
- **Exclude**: All other property types (condos, duplexes, commercial, etc.)

### Recent Sale Exclusion
- **Exclude**: Properties sold within last 2 years (730 days)
- **Rationale**: Recent sales likely have accurate market-based assessments

### Sale Validation Filter
- **Exclude**: Properties where a valid recent sale validates the assessment
- **Valid sale**: Sale price >= $10,000, sale date between 2020-01-01 and 2025-01-01
- **Validation rule**: If assessment is within 110% of sale price, exclude the property
- **Rationale**: If someone paid $500k and the property is assessed at $480k, the sale proves the assessment is reasonable. Only properties assessed >110% of a valid sale are potential leads.

### Minimum Savings Threshold
- **Default**: $1,500 first-year tax savings
- **Rationale**: Must provide meaningful value to justify appeal effort

---

## Lead Qualification Formula

```
Tax Savings = (Current Assessment - Median Comparable Assessment) × 25% × 3.254%

Where:
- 25% = Tennessee residential assessment ratio
- 3.254% = Davidson County tax rate (per $100 of assessed value)

Minimum Lead Threshold: Savings ≥ $1,500
Required Over-Assessment: ≥ ~$185,000
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

## Comparable Selection Methodology

The lead generator uses a **percentage-based, distance-weighted comparable selection** approach (similar to `compare_property.py`).

### Comparable Criteria

Each subject property finds its own custom comparable set based on:

| Dimension | Matching Logic | Default |
|-----------|----------------|---------|
| **Distance** | Within X miles of subject (geographic) | 2 miles |
| **Square Footage** | Within ±X% of subject sqft | ±15% |
| **Year Built** | Within ±X years of subject | ±7 years |
| **Acreage** | Within ±X% of subject acreage | ±10% |
| **Bedrooms** | Within ±X beds of subject | Exact match (0) |
| **Bathrooms** | Within ±X baths of subject | Exact match (0) |
| **Land Use** | Same LUDesc (SINGLE FAMILY) | Required |

**Note:** Bed/bath data comes from the `davidson_bed_bath` table (scraped from padctn.org). Half baths count as 0.5 baths. Properties without bed/bath data skip those filters but receive a confidence penalty.

### Similarity Scoring

Each comparable is assigned a similarity score (lower = more similar):

| Factor | Weight | Calculation |
|--------|--------|-------------|
| Square Footage | 25% | `|subject_sqft - comp_sqft| / subject_sqft` |
| Year Built | 20% | `|subject_year - comp_year| / year_range` |
| Acreage | 15% | `|subject_acres - comp_acres| / subject_acres` |
| Distance | 20% | `distance_meters / max_distance_meters` |
| Bedrooms | 10% | `|subject_beds - comp_beds| / subject_beds` |
| Bathrooms | 10% | `|subject_baths - comp_baths| / subject_baths` |

### Quality-Based Selection

1. All properties meeting the criteria are ranked by similarity score
2. Top 20 most similar comparables are selected
3. Median assessment is calculated from these top comps
4. Properties with NULL/zero acreage skip the acreage filter (treated as "any acreage")
5. Properties without bed/bath data skip those filters but receive a -10 point confidence penalty

### Confidence Scoring

Each lead receives a confidence score (0-100) based on:

| Comp Count | Base Score |
|------------|------------|
| 1-2 comps | 10-20 (very low confidence) |
| 3-4 comps | 30-50 (low confidence) |
| 5-9 comps | 50-70 (moderate confidence) |
| 10+ comps | 70 (good base) |

**Similarity bonus** (0-30 points):
- Excellent similarity (avg < 0.15): +30
- Good similarity (avg < 0.25): +20
- Moderate similarity (avg < 0.40): +10
- Poor similarity: +0

---

## Output Schema

| Column | Type | Description |
|--------|------|-------------|
| `parid` | STRING | Parcel ID |
| `address` | STRING | Property street address |
| `owner_name` | STRING | Owner name |
| `owner_address` | STRING | Mailing address (for outreach) |
| `current_assessment` | FLOAT | Current TotlAppr |
| `median_comparable` | FLOAT | Median assessment of top 20 comps |
| `over_assessment` | FLOAT | Current - Median |
| `estimated_savings` | FLOAT | First-year tax savings |
| `num_comparables` | INT | Number of comps used (max 20) |
| `confidence_score` | FLOAT | Quality score 0-100 |
| `year_built` | INT | Year property was built |
| `sqft` | FLOAT | Finished square footage |
| `acreage` | FLOAT | Property acreage |
| `beds` | INT | Number of bedrooms |
| `baths` | FLOAT | Total bathrooms (half baths = 0.5) |
| `land_use` | STRING | Land use description |
| `avg_similarity` | FLOAT | Average similarity score of comps |
| `avg_comp_distance_miles` | FLOAT | Average distance to comps |
| `in_flood_zone` | STRING | "Yes" or "No" - FEMA flood zone status |

---

## Runbook

### Basic Usage

```bash
cd /path/to/property-tax-app

# Test on a single zip code first (fast, cheap)
python analysis/generate_leads.py --zipcode 37205 --limit 50 --output test_leads.csv

# Generate leads with default settings
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

#### Test on Single Zip Code (Cost-Controlled)

```bash
python analysis/generate_leads.py \
  --zipcode 37205 \
  --limit 50 \
  --output test_leads.csv
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

#### Wider Comparable Criteria (More Comps)

```bash
python analysis/generate_leads.py \
  --sqft-range 25 \
  --year-range 10 \
  --acreage-range 15 \
  --max-distance 3.0 \
  --output wider_leads.csv
```

### CLI Options Reference

| Option | Default | Description |
|--------|---------|-------------|
| `--min-savings` | 1500 | Minimum first-year tax savings to qualify |
| `--year-range` | 7 | Year built range (+/- years) for comparables |
| `--sqft-range` | 15 | Square footage % range (+/-) for comparables |
| `--acreage-range` | 10 | Acreage % range (+/-) for comparables |
| `--max-distance` | 2.0 | Maximum distance in miles for comparables |
| `--bed-range` | 0 | Bedroom range (+/-) for comparables (0 = exact match) |
| `--bath-range` | 0 | Bathroom range (+/-) for comparables (0 = exact match) |
| `--min-comparables` | 3 | Minimum comps required for inclusion |
| `--exclude-recent-sales` | 730 | Exclude sales within N days |
| `--zipcode` | (none) | Restrict to single zip code (for testing) |
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
# or
python analysis/compare_property.py --address "123 MAIN ST"
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

### 3. Check Confidence Scores

Review the `confidence_score` column:
- **70-100**: High confidence - solid comparable basis
- **50-70**: Moderate confidence - reasonable estimate
- **30-50**: Low confidence - use with caution
- **0-30**: Very low confidence - may not be reliable

### 4. Validate Comp Quality

Check `avg_similarity` and `avg_comp_distance_miles`:
- Lower similarity scores (< 0.25) indicate better matches
- Closer average distance indicates tighter geographic clustering

---

## Known Limitations

### Data Quality Issues

1. **Misclassified Properties**: Some non-residential properties may be coded as SINGLE FAMILY (e.g., public housing, institutional properties)

2. **Missing Building Data**: Properties without year_built or finished_area are excluded

3. **Missing Location Data**: Properties without Lat/Lon coordinates are excluded

### Methodology Limitations

1. **Self-Join Performance**: The distance-based comparable search uses a self-join which is more expensive than fixed cohorts. Full county runs may take several minutes.

2. **No Location Quality**: Properties in the same distance radius may be in very different neighborhoods or across major boundaries (highways, rivers).

3. **Assessment Timing**: Data reflects point-in-time assessments; may not reflect recent appeals or corrections.

---

## BigQuery Cost Estimation

The query performs a self-join on ~180,000 parcels with geographic distance calculations.

**Estimated cost per run:**
- Single zip code: < $0.05
- Full county: $0.10 - $0.50 (depends on result set size)

**Tip:** Use `--zipcode` for development/testing to minimize costs.

---

## Troubleshooting

### "No leads found"

1. Check `--min-savings` threshold - try lowering it
2. Check `--min-comparables` - try lowering to 2 or 3
3. Verify BigQuery connectivity: `bq ls public-data-dev:property_tax`
4. Check if tables exist and have data

### "Permission denied"

1. Ensure `GOOGLE_APPLICATION_CREDENTIALS` is set
2. Verify access to `public-data-dev` project
3. Run `gcloud auth application-default login`

### Query takes too long

1. Use `--zipcode` to restrict to a single zip code
2. Use `--limit` to cap results
3. Consider reducing `--max-distance` to narrow the comparable search radius

---

## Comparison with compare_property.py

Both scripts use similar methodology for finding comparables:

| Feature | generate_leads.py | compare_property.py |
|---------|-------------------|---------------------|
| **Purpose** | Batch lead generation | Single property analysis |
| **Comp Selection** | Percentage-based + distance | Percentage-based + zip code |
| **Geographic Filter** | Distance (miles) | Zip code |
| **Similarity Scoring** | Yes (weighted) | Yes (weighted) |
| **Top N Comps** | 20 | Configurable |
| **Sales Analysis** | No | Yes (COMPER-style) |
| **Confidence Score** | Yes | No (uses recommendation) |

Use `compare_property.py` to validate individual leads from `generate_leads.py`.
