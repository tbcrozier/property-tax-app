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
- [ ] Neighborhood-based comparison analytics
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

## Davidson County Specifics
- Assessment appeals filed with Metropolitan Board of Equalization
- Appeals typically heard April-June
- Must demonstrate comparable properties are assessed lower
- Key evidence: recent sales, comparable assessments, property condition

## Open Questions
- How to handle properties without recent sales data?
- What radius/criteria defines "comparable" for different property types?
- How to incorporate building square footage (not currently in dataset)?
- Should we track appeal outcomes to improve the model?
