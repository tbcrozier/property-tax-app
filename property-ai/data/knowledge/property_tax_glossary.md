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

### Land Use Code (`LUCode`) and Description (`LUDesc`)
The classification system describing how a property is used. LUCode is a 3-character identifier; LUDesc is the human-readable label. Properties with the same LUCode are typically valued using similar assessment methods, making this field essential for building peer comparison groups.

#### Davidson County Land Use Codes

| Range | Category | Examples |
|-------|----------|----------|
| 001-008 | Government/Public | Parks, fire stations, libraries, police stations |
| 010-019 | Residential | Single family (011), duplex (012), condo (015), mobile home (018) |
| 020-029 | Commercial Retail | Shopping centers, stores, day care, convenience markets |
| 030-039 | Commercial Office/Multi-family | Banks (031), offices (032-035), apartments (037-039) |
| 041-049 | Auto-related | Dealers (041), gas stations (043-045), car wash (047), parking (048-049) |
| 051-059 | Entertainment/Hospitality | Restaurants (051-052), hotels (059), theaters (054) |
| 061-069 | Other Commercial | Warehouses (063-064), marinas (067), mobile home parks (062) |
| 070-078 | Industrial | Manufacturing (071-072), distribution (077), open storage (078) |
| 080-089 | Rural | Same as residential but rural zoning (081=single family, 086=condo) |
| 090-099 | Exempt | Churches (091), schools (093), hospitals (094), non-profits (097) |

#### Using LUCode for Property Comparisons

LUCode is valuable for building comparison profiles because it enables granular peer groups. Instead of comparing all "residential" properties, you can compare single family (011) only to other single family homes.

**Building a comparison profile:** Combine LUCode with other attributes for tighter peer groups:
- `LUCode` - Same property type
- `TaxDist` - Same tax jurisdiction
- `Zip` or `Council` - Same neighborhood
- `Acres` range - Similar lot size
- `YearBuilt` range - Similar age

**Example profile for an appeal:**
> "Single family homes (011) in USD tax district, zip 37209, 0.1-0.3 acres, built 1950-1970"

This approach identifies whether a specific property's value-per-acre or value-per-sqft is an outlier compared to true peers.

#### Data Quality Notes
Some LUCodes have duplicate entries with typos (e.g., "VACANT RESIDENTIAL" vs "VACANT RESIENTIAL" for code 010). Consider using `TRIM()` and standardizing descriptions in queries.

### Zoning
The municipal classification governing what can be built on a property. Zoning significantly affects land value - properties with higher-intensity zoning (e.g., RM40 vs RS10) typically have higher land values. For property comparisons, match properties with similar zoning intensity.

**Official Resource:** [Metro Nashville Zoning Code (Title 17)](https://library.municode.com/tn/metro_government_of_nashville_and_davidson_county/codes/code_of_ordinances?nodeId=CD_TIT17ZO)

#### Davidson County Zoning Codes

**Residential - Single Family (R, RS):**
| Code | Meaning |
|------|---------|
| R6, R8, R10, R15, R20, R40, R80 | Residential (number = min lot size in 1000s sq ft) |
| RS3.75, RS5, RS7.5, RS10, RS15, RS20, RS40, RS80 | Residential Single-family |

**Residential - Multi-family (RM):**
| Code | Meaning |
|------|---------|
| RM2, RM4, RM6, RM9, RM15, RM20, RM40, RM60 | Residential Multi-family (number = units per acre) |

**Commercial (C):**
| Code | Meaning |
|------|---------|
| CN | Commercial Neighborhood |
| CL | Commercial Limited |
| CS | Commercial Service |
| CA | Commercial Attracting |
| CF | Civic Facility |

**Office (O):**
| Code | Meaning |
|------|---------|
| ON | Office Neighborhood |
| OL | Office Limited |
| OG | Office General |
| OR20, OR40 | Office/Residential |
| ORI | Office/Residential Intensive |

**Industrial (I):**
| Code | Meaning |
|------|---------|
| IR | Industrial Restrictive |
| IG | Industrial General |
| IWD | Industrial Warehouse/Distribution |

**Mixed Use (MU):**
| Code | Meaning |
|------|---------|
| MUL | Mixed Use Limited |
| MUN | Mixed Use Neighborhood |
| MUG | Mixed Use General |
| MUI | Mixed Use Intensive |

**Special Districts:**
| Code | Meaning |
|------|---------|
| SP | Specific Plan (custom overlay) |
| DTC | Downtown Code |
| AR2A | Agricultural/Residential 2-Acre |
| SCC | Shopping Center Community |
| SCN | Shopping Center Neighborhood |
| SCR | Shopping Center Regional |
| #ZZ (3ZZ, 4ZZ, etc.) | Legacy/grandfathered zoning |

**Suffixes:**
- `-A` = Alternative (more flexibility in development standards)
- `-NS` = No Short-term rentals (STR restricted)

**Split Zoning:**
Comma-separated values (e.g., `R10,CS`) indicate a parcel spans multiple zoning districts.

### Parcel ID (`ParID`)
The unique identifier assigned to each property parcel by the county assessor.

---

## Geographic Terms

### Tax District (`TaxDist`)
The specific taxing jurisdiction for a property. Determines which tax rates apply (city, county, special districts).

#### Davidson County Tax District Codes

**Incorporated Cities:**
- `BH` - Berry Hill
- `BM` - Belle Meade
- `FH` - Forest Hills
- `GO` - Goodlettsville (portion in Davidson County)
- `OH` - Oak Hill
- `RT` - Ridgetop (portion in Davidson County)

**Metro Nashville Service Districts:**
- `GSD` - General Services District (lower tax rate, fewer urban services)
- `USD` - Urban Services District (higher tax rate, full urban services like trash, streetlights)

**Business Improvement Districts (BIDs):**
- `CBID` - Capitol Mall Business Improvement District
- `GBID` - Gulch Business Improvement District
- `SIP` - SoBro Improvement District (South of Broadway)

**Other:**
- `SNDG` / `SNDU` - Special Nashville district designations
- `UNASSIGNED` - Properties not yet assigned to a district
- `null` - Missing data

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
