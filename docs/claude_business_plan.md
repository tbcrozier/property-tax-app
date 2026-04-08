# Property Tax Appeal Analyzer - Business Plan

## Vision
Empower homeowners to identify and successfully appeal unfair property tax assessments by providing data-driven insights that reveal assessment inequities.

## Problem Statement
Property tax assessments are often inconsistent and opaque. Many homeowners pay more than they should because:
- They don't know their property is over-assessed relative to comparable properties
- They lack the data to build a compelling appeal case
- The process seems complex and intimidating

## Target Users
- **Primary**: Homeowners in Davidson County (Nashville, TN) who suspect they are over-assessed
- **Secondary**: Real estate professionals, tax consultants, and attorneys who assist with appeals

## Goals

### Phase 1: MVP Analytics (Current)
- [x] Extract and store Davidson County parcel data (~286k parcels)
- [x] Basic outlier detection using z-scores within land use categories
- [ ] Assessment-to-sale-price ratio analysis
- [ ] Appeal strength scoring system

### Phase 2: Enhanced Analytics
- [ ] Geographic clustering for true "comparable" identification
- [ ] Historical assessment trend analysis
- [ ] Improvement value anomaly detection
- [ ] Tax savings calculator

### Phase 3: User-Facing Product
- [ ] Web interface for homeowners to look up their property
- [ ] Comparable property reports
- [ ] Appeal letter templates with supporting data
- [ ] Success probability estimates

## Key Requirements

### Data Requirements
1. **Parcel assessment data** - Total, land, and improvement values
2. **Sale price history** - For assessment ratio analysis
3. **Property characteristics** - Acreage, land use, zoning
4. **Geographic coordinates** - For neighborhood clustering

### Analytics Requirements
1. **Assessment Ratio Analysis**
   - Compare assessed value to recent sale price
   - Flag properties where assessment exceeds sale price

2. **Uniformity Analysis**
   - Identify properties assessed higher than peers
   - Calculate percentile rankings within peer groups

3. **Geographic Peer Comparison**
   - Find N nearest properties with similar characteristics
   - Compare assessment per acre/sqft

4. **Appeal Strength Score**
   - Composite score combining multiple signals
   - Higher score = stronger case for appeal

### Success Metrics
- Number of properties identified as potentially over-assessed
- Estimated total tax savings potential in dataset
- (Future) User conversion and appeal success rates

## Revenue Model (Future Considerations)
- Freemium: Basic lookup free, detailed reports paid
- Per-report pricing for comprehensive appeal packages
- Subscription for real estate professionals

## Competitive Landscape
- Manual assessment lookup via county websites (free but no analysis)
- Tax appeal attorneys (expensive, typically 40-50% of savings)
- Limited DIY tools exist for Tennessee

## Technical Architecture
- **Data Pipeline**: Python scripts → BigQuery
- **Analytics**: BigQuery SQL views
- **Infrastructure**: Terraform-managed GCP resources
- **Future Frontend**: TBD (likely React/Next.js)

---

## Conceptual Model: Over-Taxation Predictor

### Core Principle

A property is **over-taxed** when its assessed value is higher than it should be relative to:
1. **Market value** - What it would actually sell for
2. **Peer properties** - Similar properties assessed lower = unfair/non-uniform

Tennessee law requires both accuracy *and* uniformity. A property owner can appeal on either ground.

### Available Fields for Profiling

| Field | Role in Model |
|-------|---------------|
| **LUCode/LUDesc** | Primary peer grouping (single family vs condo vs commercial) |
| **Zoning** | Secondary peer grouping (RS10 vs RM40 = different land values) |
| **TaxDist** | Tax jurisdiction grouping (different rates, different comps) |
| **PropZip** | Neighborhood proxy |
| **Council** | Alternate neighborhood proxy |
| **Acres** | Size normalization (value-per-acre) |
| **TotlAppr/LandAppr/ImprAppr** | Assessment values to compare |
| **SalePrice/OwnDate** | Market value evidence (if recent) |
| **Lat/Lon** | Proximity-based peer finding |

### Peer Group Definition (Comparability Profile)

Tiered approach - tightest match first, relax if insufficient peers:

| Tier | Criteria | Min Peers |
|------|----------|-----------|
| **Tier 1 (Ideal)** | LUCode + PropZip + Zoning (base) + Acres (±25%) | 10+ |
| **Tier 2 (Good)** | LUCode + PropZip + Acres (±50%) | 10+ |
| **Tier 3 (Acceptable)** | LUCode + TaxDist + Acres (±50%) | 20+ |
| **Tier 4 (Fallback)** | LUCode (county-wide) | 50+ |

**Example Tier 1 profile:**
> Single Family (011), Zip 37209, RS10 zoning, 0.15-0.25 acres

### Signals of Over-Taxation

| Signal | What It Measures | Weight | Notes |
|--------|------------------|--------|-------|
| **Z-score vs peers** | How many std devs above peer mean | High | Statistical outlier detection |
| **% above peer median** | Simpler, more robust than mean | High | Less affected by outliers |
| **Assessment > Sale Price** | Direct market evidence | Very High | Only valid if sale is recent (3 years) |
| **% above zip median** | Local neighborhood fairness | Medium | Coarser than true peer group |
| **Land/Improvement ratio anomaly** | Unusual split may indicate error | Low | Compare to peers with similar age |
| **Value-per-acre percentile** | Rank within peer group | Medium | Top 10% = red flag |

### Scoring Model

```
Appeal Score (0-100) =
  + min(30, z_score * 12)                    -- Statistical outlier
  + min(25, pct_above_peer_median * 0.5)     -- Above local peers
  + min(25, pct_above_zip_median * 0.5)      -- Above neighborhood
  + (assessment > sale_price ? min(20, (ratio-1)*50) : 0)  -- Market evidence
```

**Score Interpretation:**
| Score | Recommendation |
|-------|----------------|
| **70+** | Strong appeal case |
| **50-69** | Moderate case, worth pursuing |
| **30-49** | Marginal, needs additional evidence |
| **<30** | Probably fairly assessed |

### Current Model Gaps

| Gap | Impact | Status |
|-----|--------|--------|
| No zoning in peer groups | RS10 compared to RM40 = unfair comparison | Future improvement |
| No acreage banding | 0.1 acre vs 5 acre lots compared | Future improvement |
| Single LUCode only | Misses 081 (rural single family) which is same as 011 | Future improvement |
| No proximity peers | Zip code is coarse for neighborhoods | Future improvement |
| No improvement age | New build vs 1950 house not distinguished | Missing field (YearBuilt) |
| No square footage | Value per sqft better for improved properties | Missing field (SqFt) |

---

## Davidson County Specifics
- Assessment appeals filed with Metropolitan Board of Equalization
- Appeals typically heard April-June
- Must demonstrate comparable properties are assessed lower
- Key evidence: recent sales, comparable assessments, property condition

## Open Questions

### Market Value Determination
- **How will we determine market value for properties without recent sales?**
  - Use comparable sales from peer properties?
  - Apply price-per-acre or price-per-sqft from recent sales in the area?
  - Use third-party valuation APIs (Zillow, Redfin estimates)?
  - Rely solely on uniformity argument (peer comparison) rather than market value?

### Peer Group Definition
- What radius/criteria defines "comparable" for different property types?
- Should zoning be exact match or category match (all RS* vs RS10 specifically)?
- How to handle properties at the edge of zip code boundaries?
- Should we weight closer properties more heavily than distant ones?

### Missing Data
- How to incorporate building square footage (not currently in dataset)?
- Is YearBuilt available from the ArcGIS API or another source?
- How to handle properties with null/missing zoning or LUCode?

### Model Validation
- Should we track appeal outcomes to improve the model?
- How do we validate that high-scoring properties actually win appeals?
- What's the false positive rate (properties flagged but actually fair)?

### Business/Legal
- Are there restrictions on using/displaying property owner information?
- How to handle commercial vs residential differently (different assessment ratios)?
- What disclaimers are needed for tax advice?

---

## Future Ideas

### Enhanced Peer Matching
1. **Add base zoning to peer matching** - Extract first zoning code before comma using `SPLIT(Zoning, ',')[OFFSET(0)]`
2. **Add acreage bands** - Group similar lot sizes (0-0.25, 0.25-0.5, 0.5-1, 1-5, 5+ acres)
3. **Create LUCode groups** - Combine similar codes (011 + 081 = single family, 015 + 086 = condo)
4. **Proximity-based peers** - Use Lat/Lon to find nearest N similar properties instead of zip code

### Additional Data Fields
5. **Check ArcGIS API for missing fields** - YearBuilt, SqFt, Bedrooms, Bathrooms would significantly improve model
6. **Building permit data** - Could indicate recent improvements not yet assessed
7. **Historical assessment data** - Track year-over-year changes, flag unusual jumps

### Advanced Analytics
8. **Machine learning model** - Train on appeal outcomes to predict success probability
9. **Automated comparable selection** - Algorithm to find best N comps for any property
10. **Assessment trend analysis** - Identify neighborhoods with systematic over-assessment
11. **Improvement value anomaly detection** - Flag when improvement value seems wrong for property type/age

### User Features
12. **Property lookup by address** - User enters their address, gets appeal score
13. **Comparable property report** - PDF with maps showing peer properties
14. **Appeal letter generator** - Template with property-specific data filled in
15. **Email alerts** - Notify users when new data suggests appeal opportunity

### Data Pipeline
16. **Incremental updates** - Detect changed parcels rather than full reload
17. **Multi-county support** - Expand beyond Davidson County
18. **Historical snapshots** - Track assessments over time for trend analysis
