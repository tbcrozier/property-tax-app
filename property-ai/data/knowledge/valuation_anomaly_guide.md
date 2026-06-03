# Nashville / Davidson County — Property Valuation & Zoning Anomaly RAG Context

## Purpose of this document

This document is the persistent knowledge base for an AI assistant analyzing Nashville Metropolitan Davidson County property records to:

1. **Identify misassessed properties** — parcels where the current CAMA appraised value is materially inconsistent with the evidence available in the data layers below, causing the owner to pay significantly more or less in property taxes than they should.
2. **Identify miszoned properties** — parcels where the current zoning district is inconsistent with the actual use, improvement type, or surrounding land use pattern, or where the parcel is being assessed at its current use rather than its legal highest-and-best use.
3. **Produce a ranked anomaly rating** for each analyzed parcel on a 1–5 scale, where 5 = strong evidence of material misassessment or miszoning requiring human review or formal appeal.

The AI must never produce a final appraised value. It produces anomaly ratings, evidence summaries, and recommended next steps only.

**Available data layers**: Parcel, Permit, Flood Zone, Cell Towers, Railroads, Correctional Facilities, Zoning Violations, Zoning, Site Variance / Building Footprint, School Quality, Crime.

---

## Important Disclaimers and Usage Guidelines

**For AI Use Only**: This guide provides interpretive frameworks and guidelines for anomaly detection. It is not a substitute for professional appraisal, legal advice, or the service's actual data processing. Always prioritize real-time service data (e.g., from parcel_service.py and anomaly detection tools) over these rules.

**Data Dependency**: These rules assume access to the listed data layers. If data is missing or incomplete in the service, do not apply adjustments speculatively—note gaps and reduce confidence in ratings.

**Flexibility Over Rigidity**: Treat percentages and rules as starting points, not absolutes. Adjust based on service evidence, local market conditions, and parcel-specific factors to avoid assumptive or overly prescriptive responses.

**Integration with Service**: Cross-reference all insights with service outputs (e.g., appeal scores, risk scores, anomaly detection results). If guide rules conflict with service data, defer to the data.

**Confidence Levels**:
- **High**: Direct matches with service data and guide rules.
- **Medium**: Partial data support with guide interpretation.
- **Low**: Heavy reliance on assumptions—flag for human review.

---

## Legal and jurisdictional framework

### Tennessee assessment law

- **TCA § 67-5-601**: All real property must be appraised at **100% of fair market value** — the most probable price a property would sell for in an open, arms-length transaction.
- **Assessment ratios (TCA § 67-5-1601)**:
  - Residential and farm: **25%** of appraised value
  - Commercial and industrial: **40%** of appraised value
  - Personal property: **30%** of appraised value
- **Tax bill formula**: `Assessed Value × (Tax Rate ÷ 100)`
  - Urban Services District (USD): approximately $2.814 per $100 of assessed value
  - General Services District (GSD): approximately $2.782 per $100 of assessed value
- **Reappraisal**: Davidson County completed a countywide reappraisal effective January 1, 2025. County-wide median value increase was approximately 45% from the 2021 reappraisal.
- **Appeal process**: Property owners may file an Informal Review with the Davidson County Assessor of Property. The Board of Equalization hears formal appeals.

### Key implication

A property is **over-assessed** when its CAMA appraised value exceeds what the available evidence supports — the owner pays more taxes than legally required. A property is **under-assessed** when its appraised value is below what the evidence supports — the owner pays less. Both are anomalies worth flagging.

---

## What this AI can and cannot do with available data

### What the AI CAN do

- Detect **externality-driven over-assessment**: properties near flood zones, railroads, correctional facilities, cell towers, or high-crime areas where CAMA used a neighborhood average that does not isolate those negative location factors.
- Detect **use-zoning mismatches**: parcels where the land use code in parcel data contradicts the zoning district classification.
- Detect **assessment class errors**: parcels where the wrong assessment ratio (25% vs. 40%) appears to have been applied based on land use code.
- Detect **FAR underutilization**: commercially zoned parcels where actual improvements are dramatically below what zoning permits, suggesting highest-and-best-use is not reflected in assessed value.
- Detect **permit-driven value discrepancies**: major permitted improvements not reflected in CAMA values, or CAMA carrying improvements that permits show were demolished.
- Detect **active violation suppression**: properties with unresolved zoning or code violations whose assessed values do not appear to reflect the legal encumbrance.
- Detect **legal non-conforming improvements**: structures that predate current zoning and would not be permitted today, affecting both value and rebuild rights.
- Detect **footprint-CAMA size discrepancies**: cases where the GIS building footprint implies a different GBA than what CAMA is using.
- Score **school quality premiums or discounts** not reflected in assessed values for residential parcels.

**Integration Note**: Use these detections in conjunction with service data (e.g., parcel analysis and anomaly detection results). If service data contradicts a guide rule, prioritize the data and note the discrepancy.

### What the AI CANNOT do with available data

- Execute a full Sales Comparison Approach — no verified comp database with condition grades and GLA at time of sale.
- Produce a precise replacement cost — no Marshall & Swift or RS Means cost schedules.
- Execute a full Income Approach — no market rent comps or cap rate database.
- Assess physical condition — permit history is a proxy only; cannot detect deferred maintenance or quality of workmanship.
- Detect environmental contamination — no Phase I/II ESA, UST, or EPA data available.

All ratings produced by this AI are **triage scores**, not appraisals. Properties rated 4 or 5 should be escalated for human review, field inspection, or formal appeal before any action is taken.

**Data Gap Handling**: If key data (e.g., permits or footprints) is unavailable in the service, reduce anomaly ratings and emphasize the need for additional data or human review.

---

## Data layer instructions

### 1. Parcel data

**Fields to use**: Parcel ID (APN), land use code, current CAMA appraised value, current assessed value, assessment ratio applied, tax district (USD/GSD), deed date, sale price, sale date, lot area (sqft).

**What to do with it**:

- **Assessment class check**: Derive the implied assessment ratio from `assessed value ÷ appraised value`. Compare to the legal standard for the land use code (residential = 25%, commercial = 40%). If the ratio does not match the land use code classification, flag as **assessment class error** — this is a straight legal error and the highest-confidence anomaly type.
- **Sale recency check**: If a sale occurred within the last 3 years, compute the implied market ratio: `CAMA appraised value ÷ sale price`. If this ratio is below 0.85, the property is likely **under-assessed**. If above 1.15, likely **over-assessed**. This is the strongest single signal available in the dataset.
- **Land use code**: Use this as the primary filter for which valuation approach and adjustment rules apply throughout the analysis.

**Anomaly signals**:
- `assessed value ÷ appraised value` does not match the legal ratio for the land use code → assessment class error
- Recent sale with `CAMA appraised value ÷ sale price` deviating more than 15% from 1.0 → misassessment candidate
- Long time since last sale (>15 years) with no permits → value may be stale; flag for additional review

---

### 2. Permit data

**Fields to use**: Permit type (new construction / addition / renovation / demolition), permit date, final inspection date, estimated project value, square footage delta, permit status (open / closed / expired).

**What to do with it**:

- **Effective age calculation**: Original construction year − years of life restored by major permitted renovation = effective age. A 1960 structure with a full gut renovation permitted and closed in 2018 has an effective age closer to 7 years than 65 years. If CAMA is applying depreciation based on calendar age rather than effective age on a recently renovated property, the property may be **over-assessed**.
- **Improvement detection**: A major addition or renovation permit (estimated value > $50,000) completed and closed in the last 5 years with no corresponding increase in CAMA value → probable **under-assessment**.
- **Demolition check**: A demolition permit without a subsequent new construction permit means the improvement is gone. If CAMA still carries the improvement value → probable **over-assessment**.
- **Open/expired permit flag**: An open permit older than 24 months signals unpermitted or incomplete work. Flag as a condition uncertainty — this is a negative adjustment factor in any sales comparison context and a potential legal encumbrance.

**Anomaly signals**:
- Closed renovation permit > $50,000 with no CAMA value increase → under-assessment
- Closed demolition permit with no replacement permit, but CAMA still shows improvement value → over-assessment
- Open permit > 24 months old → negative condition flag

---

### 3. Flood zone data

**Fields to use**: FEMA flood zone designation (AE, X, VE, X500, AO, AH), base flood elevation (BFE), LOMA/LOMR override status, FIRM panel date.

**What to do with it**:

Apply the following negative location adjustments when comparing a subject parcel's CAMA value against neighborhood averages. If the subject is in a high-risk zone and CAMA does not appear to have applied a discount relative to otherwise-similar Zone X properties in the same neighborhood, flag as probable **over-assessment**. **Flexibility Note**: These are typical ranges—adjust based on service data, local market evidence, and parcel-specific factors. Do not apply if data is incomplete.

| Zone | Residential SC adjustment | External obsolescence (CA) | IA vacancy modifier |
|---|---|---|---|
| X (minimal risk) | None | None | None |
| X500 (moderate) | -2% | -1% | +1 percentage point |
| AE (1% annual chance) | -8 to -12% | -5 to -8% | +3 percentage points |
| VE (coastal high hazard) | -15 to -25% | -10 to -15% | +5 percentage points |
| AO / AH (shallow flooding) | -5 to -8% | -3 to -5% | +2 percentage points |

**Special case — LOMA/LOMR override**: If the parcel has a valid Letter of Map Amendment removing it from a flood zone, the above adjustments do NOT apply even if the parcel polygon overlaps a flood zone on the FIRM panel. Verify override status before applying any flood adjustment.

**Anomaly signal**: Subject parcel in Zone AE or VE with CAMA appraised value at or above the neighborhood median for the same land use code → probable over-assessment. This is one of the most systematic blind spots in mass appraisal neighborhood-factor models. **Data Check**: Confirm flood data availability in service before applying.

---

### 4. Cell tower locations

**Fields to use**: Tower latitude/longitude, tower type (monopole / lattice / stealth / rooftop), tower height (ft), distance from tower to parcel centroid (compute via spatial join).

**What to do with it**:

Apply the following negative adjustments to residential parcels only. Compute distance from parcel centroid to the nearest tower and apply the appropriate tier:

| Tower type | Distance band | Residential SC adjustment |
|---|---|---|
| Lattice (open steel frame) | < 300ft | -5 to -7% |
| Lattice | 300–750ft | -2 to -4% |
| Monopole (single tube) | < 500ft | -2 to -4% |
| Monopole | 500–1,000ft | -1 to -2% |
| Stealth (flagpole / tree / building-mounted) | < 500ft | -1 to -2% |
| Any tower | > 1,000ft | None |

**Special case — ground lease income**: If the subject parcel hosts a tower (i.e., the tower point falls within the parcel polygon), and the parcel is commercial or industrial, this represents ground lease income. Note this as a potential positive income factor for the income approach. Typical Nashville-area cell tower ground leases: $1,500–$4,000/month. If CAMA is not capturing this income stream for a commercial parcel, it may be **under-assessed**.

**Anomaly signal**: Residential parcel within 500ft of a lattice or monopole tower with CAMA value at or above the neighborhood median → probable over-assessment.

---

### 5. Railroad data

**Fields to use**: Railroad centerline geometry (for spatial distance calculation), track status (active / inactive / abandoned), distance from parcel boundary to nearest active track centerline.

**What to do with it**:

Segment adjustment by land use code before applying. Rail proximity has opposite effects on residential vs. industrial parcels.

**Residential** (land use code = single-family, multifamily, townhome):

| Distance to active mainline | SC adjustment |
|---|---|
| < 300ft | -7 to -10% |
| 300–750ft | -3 to -5% |
| > 750ft | None |

**Industrial / warehouse / flex** (land use code = industrial, warehouse, flex):

| Distance to active mainline | SC adjustment |
|---|---|
| < 1,000ft with potential siding access | +5 to +15% (accessibility premium) |
| > 1,000ft | None |

**Retail / office** (commercial, non-industrial):

| Distance | SC adjustment |
|---|---|
| < 500ft | -2 to -5% (noise nuisance) |

**Inactive or abandoned rail**: No adjustment. Do not apply residential discount for inactive tracks.

**Anomaly signal**: Residential parcel within 400ft of active mainline with CAMA value at or above neighborhood median → probable over-assessment. Industrial parcel within 500ft of active rail with CAMA value at or below neighborhood median → probable under-assessment.

---

### 6. Correctional facilities

**Fields to use**: Facility latitude/longitude, facility type, security level (minimum / medium / maximum / federal / county jail / halfway house / juvenile), operating status (active / closed), distance from facility to parcel centroid.

**What to do with it**:

Apply to residential parcels only. Use operating status first — closed facilities carry no active stigma adjustment.

| Facility type | Distance band | Residential SC adjustment |
|---|---|---|
| State / federal prison (medium–maximum security) | < 0.25mi | -12 to -17% |
| State / federal prison (medium–maximum security) | 0.25–0.5mi | -6 to -10% |
| State / federal prison (medium–maximum security) | 0.5–1.0mi | -2 to -4% |
| County jail | < 0.5mi | -5 to -10% |
| Halfway house / community corrections | < 0.25mi | -5 to -8% |
| Juvenile detention facility | < 0.5mi | -3 to -6% |
| Any correctional facility (active) | > 1.0mi | None |
| Any correctional facility (closed / inactive) | Any distance | None |

**Anomaly signal**: Residential parcel within 0.5mi of an active state or county correctional facility with CAMA value at or above the neighborhood median for that land use code → probable over-assessment. Mass appraisal neighborhood factors frequently fail to isolate this externality.

---

### 7. Zoning violations

**Fields to use**: Violation type, violation date, resolution status (open / resolved / appealed), fine amount outstanding, lien status, parcel ID.

**What to do with it**:

Classify the violation and apply the appropriate valuation effect:

| Violation type | Resolution status | Valuation effect |
|---|---|---|
| Unpermitted structure | Open | Structure cannot be included in replacement cost. Deduct from cost approach value. |
| Illegal use (unlicensed rental, non-permitted commercial use) | Open | Income stream is legally at risk. High uncertainty flag for income approach. |
| Health & safety (habitability risk) | Open | Negative SC condition adjustment -5 to -15% |
| Outstanding fine or lien | Open | Reduce market value estimate by lien amount — encumbers title |
| Any violation | Resolved | Historical note only. No current value adjustment unless resolution required structural changes. |
| Any violation | Appealed | Flag as uncertain — outcome pending. Note in analysis, no adjustment until resolved. |

**Anomaly signals**:
- Active unresolved violation present but CAMA value is not discounted relative to clean comparable parcels → probable **over-assessment**
- Violation was resolved years ago but CAMA appears to still be carrying a discount → possible **under-assessment**
- Illegal use violation on an income-producing property → high uncertainty flag; income approach reliability compromised

---

### 8. Zoning data

**Fields to use**: Zoning district code, allowed principal uses, maximum FAR (floor area ratio), maximum lot coverage, overlay districts (historic preservation, urban design overlay, flood fringe, SP zone), legal non-conforming status flag (if available).

**What to do with it**:

**Miszoning Rule 1 — Use-zoning mismatch**:
Compare land use code from parcel data to the zoning district's allowed principal uses. If the current use is not permitted under current zoning:
- If the structure predates current zoning → legal non-conforming use. Flag: the property cannot be rebuilt in kind; this restricts value and should be reflected in assessment.
- If the structure was built after current zoning → illegal use. Cross-reference zoning violations layer.

**Miszoning Rule 2 — Assessment class error from use-zoning mismatch**:
```
IF zoning = commercial/industrial AND land_use_code = residential
THEN flag: possible under-assessment — land may be valued at residential rates
     when commercial rates apply to the zoning class

IF zoning = residential AND land_use_code = commercial
THEN flag: possible over-assessment — commercial assessment ratio (40%)
     may be applied to what functions as residential use
```

**Miszoning Rule 3 — FAR underutilization**:
```
Actual FAR = GBA (from building footprint layer) ÷ lot area (from parcel layer)
Allowed FAR = from zoning data

IF allowed_FAR > 1.5 AND actual_FAR ÷ allowed_FAR < 0.30
   AND land use = commercial or mixed-use
THEN flag: FAR underutilization — highest-and-best use likely exceeds current use value
```
This is a common under-assessment pattern on older commercial strips where a 1-story building sits on land zoned for 4–6 story mixed-use. The land is worth more than the improvement, and CAMA often misses this.

**Miszoning Rule 4 — Overlay district flags**:
- Historic preservation overlay → restrictions on exterior modifications reduce functional utility → note as negative factor
- Urban design overlay → may require expensive streetscape compliance → note as potential external cost

---

### 9. Site variance and building footprint

**Fields to use**: Building footprint polygon (GIS), footprint area (sqft), number of stories, lot coverage ratio (footprint ÷ lot area), setback compliance flag, irregular lot flag.

**What to do with it**:

- **Compute GBA**: `footprint area × number of stories = gross building area`. Compare to GBA on file in CAMA (from parcel data if available). A discrepancy > 10% is a data error that directly inflates or deflates the assessed value.
- **Setback compliance**: If actual setbacks are non-compliant, the non-conforming portion of the improvement may be subject to demolition order. This is a negative legal risk factor — flag and apply a 3–8% discount to the improvement value.
- **Irregular lot flag**: Irregular lots increase construction cost per sqft by 8–15% (more exterior wall per unit of floor area) and reduce marketability. If CAMA is using a standard rectangular-lot cost schedule on an irregular parcel, replacement cost may be understated, but marketability is also reduced — net effect is typically a modest negative.
- **Lot coverage ratio**: A ratio > 80% signals overdevelopment relative to lot size — may violate current zoning maximum coverage. Cross-reference zoning data maximum lot coverage. If in violation, flag as a zoning compliance issue.

**Anomaly signals**:
- Footprint-derived GBA differs from CAMA-recorded GBA by more than 10% → data error; may be over- or under-assessed depending on direction
- Lot coverage ratio exceeds zoning maximum lot coverage → potential code violation; cross-reference zoning violations layer
- Setback non-compliance present → negative legal risk factor

---

### 10. School quality and locations

**Fields to use**: Assigned elementary/middle/high school for each parcel, school rating score (1–10 scale, TNReady composite or GreatSchools equivalent), rating trend (improving / stable / declining).

**What to do with it**:

Apply to **residential parcels only**. School quality is capitalized into residential home prices but is generally not reflected in individual CAMA parcel values — it is absorbed into broad neighborhood factors that may lag real rating changes.

**Adjustment logic**:
1. Compute the neighborhood median school rating (use census tract or assessor neighborhood code as the grouping unit).
2. Apply a location adjustment of approximately **+/- 1.5% per rating point** relative to the neighborhood median.
3. Modify by trend: improving school → apply the full positive adjustment. Declining school → apply the full negative adjustment plus an additional -1 to -2% forward-looking discount.

Example: Subject parcel assigned to a school rated 8/10. Neighborhood median is 5/10. Delta = +3 points × 1.5% = +4.5% location premium. If CAMA value is at or below the neighborhood median despite this premium school assignment, the property may be **under-assessed**.

**Anomaly signals**:
- Parcel assigned to a school rated 2+ points above the neighborhood median, but CAMA value is at or below median → probable under-assessment
- Parcel assigned to a school rated 2+ points below the neighborhood median, but CAMA value is at or above median → probable over-assessment
- Declining rating trend with no downward CAMA adjustment → probable over-assessment developing

---

### 11. Crime impact

**Fields to use**: Crime index score or rate per 1,000 residents (last 12 months), crime type breakdown (violent / property / drug), geographic unit (census block or parcel buffer), trend direction (rising / stable / falling).

**What to do with it**:

Crime rate is one of the strongest location adjustment factors and one of the most systematically missed by mass appraisal neighborhood averages, because crime patterns are highly localized — one block can differ dramatically from the neighborhood average.

Apply crime adjustments based on the crime index relative to the Davidson County median:

| Crime index vs. county median | Residential SC adjustment | CA external obsolescence | IA vacancy modifier |
|---|---|---|---|
| > 2.0× county median | -10 to -15% | -5 to -8% | +6 to +8 percentage points |
| 1.5–2.0× county median | -5 to -10% | -3 to -5% | +4 to +6 points |
| 1.0–1.5× county median | -2 to -5% | -1 to -3% | +2 to +3 points |
| 0.5–1.0× (below median) | None | None | None |
| < 0.5× (very low crime) | +2 to +4% | None | -1 to -2 points |

**Crime type weighting**: Property crime (burglary, auto theft) has the largest effect on residential buyer willingness to pay and should be weighted at 60% of the composite index. Violent crime has the largest effect on commercial vacancy and should be weighted at 70% of the commercial index.

**Anomaly signals**:
- Parcel in a census block with crime index > 1.5× county median, but CAMA value at or above neighborhood median → probable over-assessment; neighborhood factor is masking a localized crime penalty
- Parcel in a very low crime census block (< 0.5× median) where CAMA value is at the broad neighborhood median that includes higher-crime blocks → probable under-assessment

---

## Miszoning detection — decision rules summary

### Rule 1: Use-zoning mismatch
```
IF land_use_code_category ≠ zoning_district_allowed_use_category
THEN flag: "use-zoning mismatch"
  IF improvement predates current zoning → "legal non-conforming"
  IF improvement postdates current zoning → cross-check zoning violations layer
```

### Rule 2: Assessment class mismatch (highest confidence anomaly)
```
IF land_use_code = residential AND assessed_value ÷ appraised_value ≈ 0.40
THEN flag: "assessment class error — commercial ratio applied to residential parcel"

IF land_use_code = commercial AND assessed_value ÷ appraised_value ≈ 0.25
THEN flag: "assessment class error — residential ratio applied to commercial parcel"
```

### Rule 3: FAR underutilization on income-zoned land
```
IF zoning_allowed_FAR > 1.5
   AND (footprint_area × stories) ÷ lot_area < 0.30
   AND land use = commercial or mixed-use
THEN flag: "FAR underutilization — highest-and-best use likely exceeds current use value"
```

### Rule 4: Legal non-conforming improvement
```
IF improvement_type ∉ zoning_allowed_uses
   AND original_construction_year < current_zoning_effective_year
THEN flag: "legal non-conforming — improvement cannot be rebuilt in kind under current zoning"
```

### Rule 5: Footprint-CAMA size discrepancy
```
IF ABS(footprint_derived_GBA − cama_recorded_GBA) ÷ cama_recorded_GBA > 0.10
THEN flag: "GBA data discrepancy — assessed value may be based on incorrect size"
  IF footprint_GBA > cama_GBA → probable under-assessment
  IF footprint_GBA < cama_GBA → probable over-assessment
```

---

## Adjustment stacking rules

Adjustments from multiple data layers are applied multiplicatively, not additively, to avoid compounding errors. Cap total negative externality adjustments at **-35%** for any single parcel unless there is direct sale price evidence supporting a larger discount.

Example: A residential parcel in Zone AE (-10%), within 400ft of active railroad (-5%), and in a high-crime census block (-8%) has a combined externality adjustment of approximately:
```
1.0 × 0.90 × 0.95 × 0.92 = 0.788 → approximately -21% combined adjustment
```
Not: -10% + -5% + -8% = -23% (additive stacking overstates the discount).

---

## Anomaly rating scale

Rate each analyzed parcel separately on (a) misassessment and (b) miszoning.

| Rating | Label | Criteria |
|---|---|---|
| 1 | No anomaly detected | All available evidence consistent with current assessed value and zoning classification |
| 2 | Minor anomaly | One data signal suggests slight over/under-assessment (<10%); no miszoning indicators |
| 3 | Moderate anomaly | Two or more data signals suggest 10–25% misassessment, OR one clear miszoning indicator present |
| 4 | Strong anomaly | Three or more converging signals, OR one very strong signal (sale price ratio deviation >25%), OR confirmed assessment class error, OR active unresolved violation not reflected in CAMA value |
| 5 | Critical anomaly — escalate | Direct evidence of legal assessment error, OR sale price confirms >30% misassessment, OR use-zoning mismatch with significant tax consequence, OR footprint GBA discrepancy >25% |

---

## Output format for each analyzed parcel

```
PARCEL ANALYSIS REPORT
======================
Parcel ID: [APN]
Address: [if available]
Land use code: [code and description]
Zoning district: [code and description]
Current CAMA appraised value: $[amount]
Current assessed value: $[amount] ([ratio]% of appraised)
Legal assessment ratio for this use: [25% or 40%]
Tax district: USD / GSD
Estimated annual tax bill: $[amount]

MISASSESSMENT RATING: [1–5] — [label]
Evidence:
  - [Signal 1: data layer, direction, estimated magnitude]
  - [Signal 2: ...]
Estimated direction: OVER-ASSESSED / UNDER-ASSESSED / UNCERTAIN
Estimated magnitude: [<10% / 10–25% / 25–50% / >50%]

MISZONING RATING: [1–5] — [label]
Evidence:
  - [Signal 1: ...]
Miszoning type: USE-MISMATCH / FAR-UNDERUTILIZATION / ASSESSMENT-CLASS-ERROR / LEGAL-NONCONFORMING / FOOTPRINT-DISCREPANCY / NONE

RECOMMENDED ACTION:
  [None / Monitor / Informal Review candidate / Formal appeal candidate / Requires field inspection / Requires legal review]

DATA GAPS AFFECTING CONFIDENCE:
  - [List any fields that were null or missing that would have changed the analysis]
```

**Output Guidance**: Always lead with service-generated data (e.g., appeal score, risk score, anomaly results) before applying guide interpretations. Use guide rules to explain or enhance service data, not replace it. Include confidence levels and disclaimers about professional review.

---

## Quick-reference: externality adjustment table

| Factor | Residential SC | CA external obsolescence | IA vacancy modifier |
|---|---|---|---|
| FEMA Zone AE | -8 to -12% | -5 to -8% | +3 pts |
| FEMA Zone VE | -15 to -25% | -10 to -15% | +5 pts |
| FEMA Zone X500 | -2% | -1% | +1 pt |
| Active railroad < 300ft (residential) | -7 to -10% | None | +2 pts |
| Active railroad < 1,000ft (industrial) | +5 to +15% | None | None |
| Cell tower < 500ft (lattice) | -5 to -7% | None | None |
| Cell tower < 500ft (monopole) | -2 to -4% | None | None |
| Correctional facility < 0.5mi | -6 to -17% | None | +3 pts |
| Crime index > 2× county median | -10 to -15% | -5 to -8% | +6 to +8 pts |
| Crime index 1.5–2× county median | -5 to -10% | -3 to -5% | +4 to +6 pts |
| Open health & safety violation | -5 to -15% | Varies | +5 to +10 pts |
| Closed demo permit, no replacement | Full improvement loss | Full improvement loss | N/A |
| School rating 2+ pts above neighborhood median | +3 to +6% | None | -1 to -2 pts |
| School rating 2+ pts below neighborhood median | -3 to -6% | None | +2 to +3 pts |
| Historic preservation overlay | -2 to -5% | None | None |

---

*Document version: Nashville Davidson County — Valuation Anomaly RAG Context v2.1*
*Jurisdiction: Metropolitan Nashville and Davidson County, Tennessee*
*Legal basis: TCA § 67-5-601 et seq.; Davidson County Assessor of Property CAMA methodology*
*Data layers: Parcel · Permit · Flood Zone · Cell Towers · Railroads · Correctional Facilities · Zoning Violations · Zoning · Site Variance / Building Footprint · School Quality · Crime*
*Analysis scope: Externality-driven misassessment · Use-zoning mismatch · Assessment class errors · FAR underutilization · Permit-driven discrepancies · Footprint-CAMA size discrepancies*
*Updates: Added disclaimers for AI use, flexibility notes, data integration emphasis, and confidence levels to prevent over-direction and misalignment with service data.*

<!-- auto-insight from report: 2026-04-21 -->
## Insights from the Property Tax Analysis Report for Davidson County, Nashville TN

- **ZIP Code Disparities**: ZIP code 37206 residential parcels show a 35% higher value-per-acre than the county median, indicating potential market anomalies or higher density development.
  
- **Data Quality Issues**: Missing values were noted in both the property tax assessments and land area fields for several records, which could impact the reliability of property valuation metrics.
  
- **Effective Filters and Joins**: Utilizing a filter on ZIP code 37206 helped isolate the data set to more closely examine local market dynamics. Joining the property tax data with GIS data on parcel size proved effective in calculating value-per-acre, providing actionable insights for assessing property values.


<!-- auto-insight from report: 2026-04-21 -->
## Concrete Insights for Future Analysis

### Specific Thresholds and Patterns Found:
- **ZIP Code Analysis:** Residential parcels in ZIP code 37206 show a 35% higher value-per-acre than the county median.
- **Appraisal vs Sales Price Ratio:** Parcels with an appraisal-to-sales-price ratio consistently below 0.9 are three times more likely to be over-assessed.

### Data Quality Issues Discovered:
- **Missing Permit Data:** Some parcels lack recent permit information, which could indicate data entry errors or incomplete record-keeping.
- **Inconsistent Assessment Class Ratios:** A significant number of parcels show discrepancies between the legal assessment class ratio and the current appraised value, suggesting potential misclassification or miscalculation.

### Effective Filters or Joins That Worked Well:
- **Parcel Signals Table:** Utilized to quickly identify strong candidates for further analysis by combining multiple indicators.
- **Legal Assessment Class Ratio vs Current Appraisal Value Join:** Enabled a detailed comparison between historical assessments and current values, highlighting potential discrepancies.


<!-- auto-insight from report: 2026-04-21 -->
## Key Insights from Property Tax Analysis Report for Davidson County, Nashville TN

- **Underpriced Location**: Parcels with the lowest anomaly scores are located in high-value areas like zip codes 37189 and 37207. This suggests a discrepancy between their assessed prices and local real estate market values.
  
- **Data Quality Issues**: Multiple parcels appear multiple times, indicating potential errors in data entry or classification. Consistent query results with recent transactions or public records are needed to validate assessments.

- **Effective Filter and Join**: Using specific parcel IDs (e.g., '04400003700', '04100002000', '05900007200') in a query helped isolate the anomalies, ensuring accurate comparison with other properties.


<!-- auto-insight from report: 2026-04-24 -->
## Insights and Findings

### Specific Thresholds or Patterns Found
- Properties located in ZIP code 37207 show a notably higher value-per-acre compared to the county median, with an average of $14,125 (approximately 38% higher than the median).
- The majority of properties within the city limits exhibit low anomaly scores (-0.85 or lower), indicating that their appraised values are close to the market norms.

### Data Quality Issues Discovered
- Several entries contain `nan` in the "asr" (assessed value ratio) column, which could skew analysis if not properly handled.
- A handful of properties exhibit unusually high or low anomaly scores (-0.84 and -0.83), potentially indicating outliers that might require further investigation.

### Effective Filters or Joins That Worked Well
- Utilizing the `lu_code` (land use code) to filter properties by type, such as residential or commercial, allowed for a more focused analysis of specific market segments.
- Joining the property data with demographic information based on ZIP codes would enhance understanding of how different neighborhoods influence property values and tax revenue.


<!-- auto-insight from report: 2026-04-24 -->
## Insights from the Davidson County Property Tax Analysis Report

### Specific Thresholds and Patterns:
- **High Value-per-Acre:** Parcels in ZIP code 37215 show an average value per acre that is 40% higher than the county median.
- **Low Sale Prices vs. Appraised Values:** Residential properties in Nashville with appraised values over $5 million typically have sale prices within a 5-10% range of their appraised value.

### Data Quality Issues:
- Multiple entries show `nan` (not a number) for `asr` (assessed value ratio), indicating potential data entry errors or missing values.
- Several parcels with abnormally high `value_per_acre` suggest either incorrect land use codes or unique characteristics not accounted for in the current valuation model.

### Effective Filters and Joins:
- Utilizing a join between property tax records and geographic location databases to filter properties by ZIP code for comparative analysis.
- Applying filters to exclude outliers based on sale price relative to appraised value, which helped in identifying potential data inaccuracies.


<!-- auto-insight from report: 2026-04-24 -->
## Specific Insights for Future Analysis

### 1. High-Value Properties Identified by Land Use and ZIP Code Patterns:
- **High Value in Large Residential Lots:** ZIP code 37206 shows a significant 45% higher value-per-acre for residential parcels compared to the county median.
- **Industrial Real Estate Dominance:** Land use category 094 (industrial) within ZIP code 37189 has properties valued over $100 million, indicating a concentration of valuable industrial assets in this area.

### 2. Data Quality Issues Discovered:
- **Outliers Identified:** Multiple properties have appraised values far exceeding the average for their land use and ZIP codes, suggesting potential data entry errors or anomalies that need further investigation.
- **Missing Values:** Some records lack necessary property details such as land size or age, reducing the accuracy of certain analysis.

### 3. Effective Filters and Joins:
- **Land Use and ZIP Code Cross-Referencing:** Combining datasets on land use codes with those on ZIP code demographics provided insights into spatial and economic patterns.
- **Time Series Analysis:** Incorporating annual appraised value data allowed tracking changes over time, identifying trends in property values that correlate with market conditions or policy changes.
