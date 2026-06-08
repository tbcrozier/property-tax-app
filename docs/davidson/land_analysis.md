# Land Assessment Analysis

## Overview

The `land_analysis.py` module identifies parcels where land is assessed higher (or lower) than expected based on measurable parcel characteristics. This approach isolates **land value** from total property value, which is useful because:

1. Land assessments are often less transparent than improvement assessments
2. Land value should correlate with physical characteristics (size, frontage, shape)
3. Outliers may indicate assessment errors or appeal opportunities

## Methodology

### Regression Model

We use **Ordinary Least Squares (OLS) regression** to predict expected land value:

```
LandAppr = β₀ + β₁(Acres) + β₂(Front) + β₃(IsRegular) + β₄(InFloodZone) + ε
```

Where:
- `β₀` = Intercept (base land value)
- `β₁-β₄` = Coefficients for each feature
- `ε` = Residual (unexplained variation)

### Why OLS?

OLS minimizes the sum of squared prediction errors:

```
Minimize: Σ(Actual - Predicted)²
```

The closed-form solution is:

```
β = (X'X)⁻¹ X'y
```

This gives us the coefficients that best fit the observed data in a least-squares sense.

### Current Model (Belle Meade Single Family)

```
LandAppr = $760,514
         + $94,286 × Acres
         + $3,514 × Front Footage
         - $45,592 × IsRegular (1 if regular shape)
         + $41,753 × InFloodZone (1 if in flood zone)

R² = 0.467 (model explains 46.7% of variance)
```

## Factors Affecting Land Value

### Factors Included in Model

| Factor | Coefficient | Interpretation |
|--------|-------------|----------------|
| **Acres** | +$94,286/acre | Larger lots are worth more, but with diminishing returns |
| **Front Footage** | +$3,514/ft | Street presence adds value; wider lots command premium |
| **Regular Shape** | -$45,592 | Coefficient is counterintuitive (see limitations below) |
| **Flood Zone** | +$41,753 | Coefficient is counterintuitive (see limitations below) |

### Factors NOT in Model (Part of the 53% Unexplained)

- **Location/Street desirability**: Premium streets (Lynnwood, Jackson Blvd) vs others
- **Corner lots**: More frontage, visibility
- **Topography**: Flat vs sloped, usable land
- **Views**: Skyline, golf course, etc.
- **Proximity**: To Belle Meade Country Club, parks, schools
- **Lot depth**: Front-to-depth ratio affects usability
- **Assessor judgment**: Subjective factors in valuation

## Interpreting Results

### Key Output Metrics

| Metric | Description |
|--------|-------------|
| `land_residual` | Actual - Predicted land value (positive = over-assessed) |
| `land_residual_pct` | Residual as % of predicted value |
| `size_band_median` | Median $/acre for similar-sized lots |
| `above_size_band_median` | How much higher this parcel's $/acre is vs median |
| `estimated_land_savings` | Potential annual tax savings if land reduced to predicted |

### How to Read Results

**Example**: 326 LYNNWOOD BLVD
```
Land Appraisal:    $2,568,000
Predicted:         $1,181,378
Residual:          $1,386,622 (+117%)
```

This parcel's land is assessed **$1.4M higher** than the model predicts for a 2.45-acre lot with 67 ft frontage. Either:
1. The assessor knows something the model doesn't (premium location, views)
2. The land is genuinely over-assessed relative to peers

### R² Interpretation

- **R² = 0.467** means 46.7% of land value variance is explained by the model
- The remaining 53% comes from unmeasured factors
- This is typical for real estate models with limited features
- A low R² doesn't invalidate the model for **ranking** purposes

## Model Limitations

### Counterintuitive Coefficients

The negative coefficient for `IsRegular` and positive for `InFloodZone` don't match intuition. This occurs because:

1. **Multicollinearity**: Regular lots correlate with smaller lot sizes. The Acres variable captures most of the size effect, leaving IsRegular to pick up residual correlations.

2. **Small samples**: Only 21 flood zone parcels exist in Belle Meade SF - insufficient for reliable coefficient estimation.

3. **Linear assumption**: True relationships may be non-linear (e.g., log-log for acres).

### Diminishing Returns to Acreage

A log-log regression shows:
```
log(LandAppr) = 14.15 + 0.58 × log(Acres)
R² = 0.74
```

The exponent 0.58 < 1 means **doubling acreage increases land value by only ~50%**, not 100%. The linear model approximates this but imperfectly.

### Omitted Variable Bias

Street/location effects are significant but unmeasured. Properties on Jackson Blvd or Lynnwood Blvd may appear "over-assessed" simply because these streets command premiums the model doesn't capture.

## Usage

### Basic Usage

```bash
# Belle Meade Single Family, $100K+ over-assessment
python land_analysis.py --output leads.csv

# Lower threshold to capture more properties
python land_analysis.py --min-overassessment 50000 --output all_leads.csv

# All land use types
python land_analysis.py --land-use all --output all_types.csv

# Different tax district (e.g., Nashville USD)
python land_analysis.py --tax-district USD --output nashville.csv

# JSON output with model details
python land_analysis.py --format json --output analysis.json

# Preview SQL query
python land_analysis.py --show-query
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--tax-district` | BM | Tax district code (BM=Belle Meade, USD=Nashville) |
| `--land-use` | SINGLE FAMILY | Land use filter, or "all" for no filter |
| `--min-overassessment` | 100000 | Minimum $ over-assessment to include |
| `--output` | stdout | Output file path |
| `--format` | csv | Output format (csv or json) |
| `--limit` | unlimited | Max records to return |
| `--project` | public-data-dev | GCP project ID |
| `--dataset` | property_tax | BigQuery dataset |

## Integration with Other Modules

### Potential Integration with `generate_leads.py`

The land analysis could enhance the main lead generator by:

1. **Adding land-specific flags**: Properties over-assessed on land vs improvements
2. **Separate land/improvement analysis**: Some appeals focus on land, others on improvements
3. **Composite scoring**: Weight total over-assessment by confidence (land vs improvement)

```python
# Potential integration approach
from land_analysis import fit_land_model, predict_land_value

# In generate_leads.py, after fetching parcels:
land_model = fit_land_model(parcels)
for parcel in parcels:
    parcel['predicted_land'] = predict_land_value(parcel, land_model)
    parcel['land_over_assessment'] = parcel['LandAppr'] - parcel['predicted_land']
```

### Potential Integration with `compare_property.py`

For individual property comparisons:

1. **Show land vs improvement breakdown**: How much of over-assessment is land vs building?
2. **Find land-comparable properties**: Same size band, similar frontage
3. **Visualize land value distribution**: Where does subject fall?

## Future Enhancements

### Additional Features to Consider

1. **Street/neighborhood indicators**: Dummy variables for premium streets
2. **Corner lot flag**: From GIS data or address parsing
3. **Lot depth**: Side footage or computed from acres/front
4. **Distance to amenities**: Country club, parks (requires geocoding)
5. **Historical sales**: Land allocation from recent sales

### Model Improvements

1. **Log-log transformation**: Better captures diminishing returns
2. **Quantile regression**: Predict median instead of mean (robust to outliers)
3. **Spatial regression**: Account for neighborhood clustering
4. **Separate models by size band**: Different dynamics for small vs estate lots

### Data Quality

1. **Validate flood zone data**: Current positive coefficient suggests data issues
2. **Review IsRegular coding**: Verify definition matches assessor usage
3. **Cross-reference with sales**: Do residuals correlate with sale price residuals?

## Appendix: Mathematical Details

### OLS Derivation

Given:
- `X` = n × (k+1) matrix of features (including intercept column of 1s)
- `y` = n × 1 vector of land appraisals
- `β` = (k+1) × 1 vector of coefficients

The OLS estimator minimizes:
```
L(β) = (y - Xβ)'(y - Xβ) = y'y - 2β'X'y + β'X'Xβ
```

Taking derivative and setting to zero:
```
∂L/∂β = -2X'y + 2X'Xβ = 0
β = (X'X)⁻¹X'y
```

### R² Calculation

```
R² = 1 - SS_res / SS_tot
   = 1 - Σ(yᵢ - ŷᵢ)² / Σ(yᵢ - ȳ)²
```

Where:
- `SS_res` = Sum of squared residuals
- `SS_tot` = Total sum of squares
- `ŷᵢ` = Predicted value
- `ȳ` = Mean of actual values

### Tax Savings Calculation

```
Estimated Savings = Land_Residual × Assessment_Ratio × Tax_Rate
                  = Land_Residual × 0.25 × 0.03254
```

For Davidson County:
- Assessment ratio: 25% (residential)
- Tax rate: $3.254 per $100 assessed value
