# Property Tax Glossary

This glossary defines key terms used in property tax assessment and appeals.

---

## Assessment Terms

### Appraised Value (Appraisal)
The total estimated market value of a property as determined by the county assessor. In Tennessee, this is meant to reflect what the property would sell for in an open market transaction.

### Total Appraised Value (`TotlAppr`)
The sum of land value and improvement value. This is the full market value estimate before any assessment ratios are applied.

### Land Appraised Value (`LandAppr`)
The assessed value of the land itself, excluding any buildings or improvements. Based on factors like location, size, zoning, and comparable land sales.

### Improvement Appraised Value (`ImprAppr`)
The assessed value of all structures and improvements on the land, including buildings, garages, pools, and other permanent fixtures. Does not include personal property.

### Assessed Value
The value used to calculate property taxes. In Tennessee:
- Residential property: 25% of appraised value
- Commercial/Industrial: 40% of appraised value
- Farm property: 25% of appraised value

### Assessment Ratio
The percentage of appraised value used to calculate the assessed value. Tennessee uses:
- 25% for residential and farm
- 40% for commercial and industrial

---

## Comparison Metrics

### Value Per Acre
Total appraised value divided by acreage (`TotlAppr / Acres`). Useful for comparing properties of different sizes within the same land use category.

### Assessment-to-Sale Ratio
The ratio of assessed value to actual sale price (`TotlAppr / SalePrice`). A ratio significantly above 1.0 may indicate over-assessment. Also called "assessment ratio" or "level of assessment."

### Z-Score
A statistical measure indicating how many standard deviations a property's value-per-acre is from the mean for its land use category. A z-score > 2 suggests the property may be over-assessed relative to peers.

### Coefficient of Dispersion (COD)
A measure of assessment uniformity. Lower COD indicates more uniform assessments. COD > 15% for residential properties often indicates poor uniformity.

---

## Property Classification

### Land Use (`LUDesc`)
The classification describing how a property is used. Common Davidson County categories:
- SINGLE FAMILY
- RESIDENTIAL CONDO
- VACANT RESIDENTIAL
- COMMERCIAL
- INDUSTRIAL
- EXEMPT (government, religious, etc.)

### Zoning
The municipal classification governing what can be built on a property (e.g., R10 for residential, CS for commercial services). Affects land value.

### Parcel ID (`ParID`)
The unique identifier assigned to each property parcel by the county assessor.

---

## Geographic Terms

### Tax District (`TaxDist`)
The specific taxing jurisdiction for a property. Determines which tax rates apply (city, county, special districts).

### Council District (`Council`)
The Metro Nashville council district where the property is located.

---

## Sales & Ownership

### Sale Price (`SalePrice`)
The actual transaction price when a property was last sold. Critical for determining if current assessment is fair relative to market value.

### Arms-Length Transaction
A sale between unrelated parties where both buyer and seller act in their own self-interest. Non-arms-length sales (between family, foreclosures, etc.) may not reflect true market value.

### Ownership Date (`OwnDate`)
The date when current ownership was recorded.

---

## Appeal Process

### Informal Review
The first step in challenging an assessment, typically involving a meeting with the assessor's office to discuss the valuation.

### Board of Equalization
The formal body that hears property tax appeals. In Davidson County, this is the Metropolitan Board of Equalization.

### Comparable Sales (Comps)
Recent sales of similar properties used to support an argument that a property's assessment is too high. Strong comps are similar in:
- Location (ideally within 0.5-1 mile)
- Size (acreage and/or square footage)
- Land use and zoning
- Age and condition

### Uniformity
The legal principle that similar properties should be assessed similarly. If your property is assessed higher than comparable neighbors, this may be grounds for appeal.

### Burden of Proof
In Tennessee property tax appeals, the taxpayer has the burden of proving the assessment is incorrect.

---

## Tax Calculation

### Mill Rate / Tax Rate
The amount of tax per dollar of assessed value, typically expressed as mills (1 mill = $0.001). Davidson County's rate varies by tax district.

### Property Tax
Calculated as: `Assessed Value × Tax Rate`. For example, a home with $300,000 appraised value in Tennessee:
- Assessed value: $300,000 × 25% = $75,000
- Tax (at 3% rate): $75,000 × 0.03 = $2,250/year

---

## Data Quality Terms

### Outlier
A property whose assessment metrics (like value per acre) differ significantly from similar properties. May indicate over-assessment, under-assessment, or data errors.

### Peer Group
Properties with similar characteristics used for comparison. Typically defined by land use, zoning, location, and size.
