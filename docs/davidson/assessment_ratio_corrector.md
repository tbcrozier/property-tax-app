# Detect Residences Taxed Like Commercial in Davidson County

## Update - pausing this exploration because the result set of properties with lu code = commercial with properties with  lu code = residential surrounding them is very small. 

## Objective

Build SQL and supporting logic to identify parcels in Davidson County that may be **classified/taxed like commercial property** but appear to be **used as residential property**.

This is the core opportunity:

* Tennessee property **classification is based on use**
* Zoning is useful context, but **zoning does not determine tax classification**
* We want to find parcels where the assessor-side signals may imply commercial treatment, while the actual property appears residential

Helpful Links:
https://www.nashville.gov/departments/planning/land-development/rezone-my-property/zoning-classifications
https://www.padctn.org/resources/tax-rates-and-calculator/


---

# Available Tables

## 1. Parcel table

```sql
`public-data-dev.property_tax.davidson_parcels`
```

Important fields:

* `ParID`
* `PropAddr`
* `LUCode`
* `LUDesc`
* `Zoning`
* `LandAppr`
* `ImprAppr`
* `TotlAppr`
* `Owner`
* `OwnAddr1`
* `OwnCity`
* `OwnState`
* `OwnZip`
* `PropCity`
* `PropState`
* `PropZip`
* `Lat`
* `Lon`

## 2. Zoning reference table

```sql
`public-data-dev.property_tax.ref_nashville_zoning`
```

Expected useful columns:

* `zoning_code`
* `zoning_desc`
* `zoning_category`
* `likely_tax_class`
* `inferred_assessment_ratio`

Use this as context only, not as the authoritative tax classification.

```
CREATE OR REPLACE TABLE `public-data-dev.property_tax.ref_nashville_zoning` AS

SELECT 'AG' AS zoning_code, 'Agricultural (5 acre min lots)' AS zoning_desc, 'Agricultural' AS zoning_category, 'Residential/Agricultural' AS likely_tax_class, 0.25 AS inferred_assessment_ratio UNION ALL
SELECT 'AR2A', 'Agricultural (2 acre min lots)', 'Agricultural', 'Residential/Agricultural', 0.25 UNION ALL

SELECT 'RS80', 'Single-family residential low density', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'RS40', 'Single-family residential low density', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'RS30', 'Single-family residential low density', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'RS20', 'Single-family residential low-medium density', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'RS15', 'Single-family residential low-medium density', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'RS10', 'Single-family residential low-medium density', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'RS7.5', 'Single-family residential medium density', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'RS5', 'Single-family residential medium density', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'RS3.75', 'Single-family residential medium density', 'Residential', 'Residential', 0.25 UNION ALL

SELECT 'R80', 'One- and two-family residential', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'R40', 'One- and two-family residential', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'R30', 'One- and two-family residential', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'R20', 'One- and two-family residential', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'R15', 'One- and two-family residential', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'R10', 'One- and two-family residential', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'R8', 'One- and two-family residential', 'Residential', 'Residential', 0.25 UNION ALL
SELECT 'R6', 'One- and two-family residential', 'Residential', 'Residential', 0.25 UNION ALL

SELECT 'RM2', 'Multifamily residential 2 units/acre', 'Multifamily', 'Residential', 0.25 UNION ALL
SELECT 'RM4', 'Multifamily residential 4 units/acre', 'Multifamily', 'Residential', 0.25 UNION ALL
SELECT 'RM6', 'Multifamily residential 6 units/acre', 'Multifamily', 'Residential', 0.25 UNION ALL
SELECT 'RM9', 'Multifamily residential 9 units/acre', 'Multifamily', 'Residential', 0.25 UNION ALL
SELECT 'RM15', 'Multifamily residential 15 units/acre', 'Multifamily', 'Residential', 0.25 UNION ALL
SELECT 'RM20', 'Multifamily residential 20 units/acre', 'Multifamily', 'Residential', 0.25 UNION ALL
SELECT 'RM40', 'High density multifamily', 'Multifamily', 'Residential', 0.25 UNION ALL
SELECT 'RM60', 'High density multifamily', 'Multifamily', 'Residential', 0.25 UNION ALL
SELECT 'RM80', 'High density multifamily', 'Multifamily', 'Residential', 0.25 UNION ALL
SELECT 'RM100', 'High density multifamily', 'Multifamily', 'Residential', 0.25 UNION ALL

SELECT 'MHP', 'Mobile Home Park', 'Residential', 'Residential', 0.25 UNION ALL

SELECT 'MUN', 'Mixed Use Neighborhood', 'Mixed Use', 'Mixed', 0.25 UNION ALL
SELECT 'MUL', 'Mixed Use Limited', 'Mixed Use', 'Mixed', 0.25 UNION ALL
SELECT 'MUG', 'Mixed Use General', 'Mixed Use', 'Mixed', 0.40 UNION ALL
SELECT 'MUI', 'Mixed Use Intensive', 'Mixed Use', 'Mixed', 0.40 UNION ALL

SELECT 'OR20', 'Office/Residential up to 20 du/ac', 'Office Residential', 'Mixed', 0.25 UNION ALL
SELECT 'OR40', 'Office/Residential up to 40 du/ac', 'Office Residential', 'Mixed', 0.25 UNION ALL
SELECT 'ORI', 'Office/Residential Intensive', 'Office Residential', 'Mixed', 0.40 UNION ALL

SELECT 'ON', 'Office Neighborhood', 'Office', 'Commercial', 0.40 UNION ALL
SELECT 'OL', 'Office Limited', 'Office', 'Commercial', 0.40 UNION ALL
SELECT 'OG', 'Office General', 'Office', 'Commercial', 0.40 UNION ALL

SELECT 'CN', 'Commercial Neighborhood', 'Commercial', 'Commercial', 0.40 UNION ALL
SELECT 'CL', 'Commercial Limited', 'Commercial', 'Commercial', 0.40 UNION ALL
SELECT 'CS', 'Commercial Service', 'Commercial', 'Commercial', 0.40 UNION ALL
SELECT 'CA', 'Commercial Arterial', 'Commercial', 'Commercial', 0.40 UNION ALL
SELECT 'CF', 'Commercial Core Frame', 'Commercial', 'Commercial', 0.40 UNION ALL

SELECT 'IR', 'Industrial Restrictive', 'Industrial', 'Commercial', 0.40 UNION ALL
SELECT 'IG', 'Industrial General', 'Industrial', 'Commercial', 0.40 UNION ALL

SELECT 'SP', 'Specific Plan District', 'Special', 'Depends', NULL UNION ALL
SELECT 'DTC', 'Downtown Code', 'Special', 'Depends', NULL;
```
---

# Key Business Rule

Tennessee tax classification is based on **use**, not zoning.

The target is:

* parcel appears residential in reality
* but parcel may be treated like commercial in assessor logic or commercial context

---

# Known LUCode Patterns

## Likely residential LU codes

Use these as strong residential-use indicators:

* `011` SINGLE FAMILY
* `012` DUPLEX
* `013` TRIPLEX
* `014` QUADPLEX
* `015` RESIDENTIAL CONDO
* `016` ZERO LOT LINE
* `018` MOBILE HOME
* `019` RESIDENTIAL COMBO/MISC
* `030` VACANT ZONED MULTI FAMILY
* `081` SINGLE FAMILY
* `082` DUPLEX
* `086` RESIDENTIAL CONDO
* `010` VACANT RESIDENTIAL LAND

## Likely commercial / non-residential LU codes

Examples:

* `020` VACANT COMMERCIAL LAND
* `022` STRIP SHOPPING CENTER
* `023` SHOPPING CENTER
* `024` SMALL SERVICE SHOP
* `025` GENERAL RETAIL
* `031` FINANCIAL INSTITUTION
* `032` OFFICE BLDG
* `033` OFFICE BLDG HIGH RISE
* `034` MEDICAL OFFICE
* `036` COMMERCIAL CONDO
* `041` AUTO DEALER
* `042` AUTO REPAIR
* `045` CONVENIENCE MARKET WITH GAS
* `051` RESTAURANT
* `052` FAST FOOD
* `059` HOTEL/MOTEL
* `063` MINI WAREHOUSE
* `064` SMALL WAREHOUSE
* `071` LIGHT MANUFACTURING
* `072` HEAVY MANUFACTURING
* `075` BUSINESS CENTER
* `077` TERMINAL / DISTRIBUTION WAREHOUSE
* `078` OPEN STORAGE

There are also exempt/government/nonprofit codes that should likely be excluded from this workflow.

---

# Problem To Solve

Create a query or view that ranks parcels that are **most likely residential in actual use** even when other signals suggest commercial context.

This is exploratory. We do **not** currently have an explicit field called `classification` or `assessment_ratio` in `davidson_parcels`. 

---

# Detection Strategy

## Step 1: Build parcel enrichment layer

Create a working view that adds:

### A. Owner occupancy proxy

Approximate owner occupancy by comparing owner mailing address fields to property address fields.

Example concept:

* `OwnAddr1 ~= PropAddr`
* and/or same city/state/zip

### B. Residential-use proxy

Use `LUCode` / `LUDesc` to classify likely residential vs likely commercial.

### C. Commercial-zoning context

Join parcel `Zoning` to `ref_nashville_zoning`.

Use zoning only as context.

### D. Neighborhood context

Use lat/lon with BigQuery GIS to calculate:

* nearby parcel count within a radius
* percent of nearby parcels whose `LUCode` is residential-like

This helps identify outliers.

---

# Desired Output Fields

Create a candidate output with fields like:

* `ParID`
* `PropAddr`
* `LUCode`
* `LUDesc`
* `Zoning`
* `zoning_desc`
* `zoning_category`
* `owner_occ_flag`
* `neighbor_count`
* `residential_neighbor_count`
* `pct_residential_neighbors`
* `looks_residential_flag`
* `commercial_context_flag`
* `confidence_score`
* `review_reason`

Optional:

* `annual_tax_if_commercial`
* `annual_tax_if_residential`
* `estimated_annual_tax_savings`

---

# Core Candidate Logic

The purpose of this logic is to find properties whose official records may not match likely real-world use.

We want to surface parcels with combinations like:

## Pattern A

* residential-looking parcel
* commercial zoning context
* mostly residential neighbors

## Pattern B

* ambiguous LU code like `019`
* residential appearance / owner occupancy
* mostly residential neighbors

---

# Suggested Confidence Score

Simple additive score is fine.

Example:

* owner occupied: +15
* commercial zoning category: +15
* > = 80% residential neighbors: +25
* LUCode = `019`: +10
* missing / ambiguous zoning match: 0
* clear industrial/commercial LU code: negative or exclude

No need to over-engineer the scoring yet.

---

# Suggested Deliverables

## 1. One reusable view

Example name:

```sql
`public-data-dev.property_tax.v_residential_use_candidates`
```

## 2. One “top candidates” query

Return top 100 most suspicious parcels for manual review.

## 3. One summary query

Show counts by:

* `LUCode`
* `zoning_category`
* score band

---

# Constraints / Notes

* Do not assume zoning determines tax class
* Use zoning as context only
* Prefer `LUCode` / `LUDesc` as assessor-use proxy
* Use lat/lon only; parcel geometry is not available in this table
* This is a **candidate detection system**, not proof
* Final output should support manual review in Google Maps / Street View

---

# What I Want You To Produce

Please produce:

1. A BigQuery SQL view for parcel enrichment
2. A BigQuery SQL query for top candidates
3. A short explanation of the logic
4. Any assumptions called out clearly

Do not overcomplicate the first iteration. Prioritize a usable shortlist for manual review.
