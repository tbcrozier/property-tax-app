# US Property Zoning Knowledge Base
> **Purpose:** This document is intended as a structured knowledge base for an AI system to (1) explain zoning concepts and categories, and (2) evaluate whether a property appears to be correctly or incorrectly zoned under US municipal zoning law.

---

## Table of Contents
1. [Foundational Concepts: Zoning vs. Land Use](#1-foundational-concepts-zoning-vs-land-use)
2. [The Planning Hierarchy](#2-the-planning-hierarchy)
3. [Zoning Categories and Definitions](#3-zoning-categories-and-definitions)
4. [How Zoning Designations Are Determined](#4-how-zoning-designations-are-determined)
5. [Key Zoning Metrics and Calculations](#5-key-zoning-metrics-and-calculations)
6. [Overlay Districts and Special Zones](#6-overlay-districts-and-special-zones)
7. [Assessing Correct vs. Incorrect Zoning](#7-assessing-correct-vs-incorrect-zoning)
8. [Legal Nonconforming Uses](#8-legal-nonconforming-uses)
9. [Variances, Conditional Use Permits, and Rezoning](#9-variances-conditional-use-permits-and-rezoning)
10. [Common Zoning Violations and Red Flags](#10-common-zoning-violations-and-red-flags)
11. [AI Compliance Evaluation Framework](#11-ai-compliance-evaluation-framework)

---

## 1. Foundational Concepts: Zoning vs. Land Use

**Land use** is the broad, descriptive concept of how land is actually utilized — residential, commercial, industrial, agricultural, etc. It describes what is physically happening on a parcel, regardless of legal permissions.

**Zoning** is the legal mechanism that regulates land use. It is codified in enforceable municipal ordinances that specify:
- Which uses are **permitted by right**, **conditionally permitted**, or **prohibited** in a defined geographic district
- **Dimensional standards** controlling how structures may be built (height, setbacks, coverage, density, floor area ratio)
- **Procedures** for variances, special permits, appeals, and rezoning

**Key distinction for compliance analysis:** A property may have an actual land use that differs from its legally assigned zoning district. This discrepancy is the core signal of a potential zoning issue.

---

## 2. The Planning Hierarchy

US land regulation follows a three-tier hierarchy. Understanding this is critical to assessing whether a property is legally compliant.

### Tier 1 — Comprehensive Plan (Master Plan)
- A **policy document** expressing a municipality's long-term vision, goals, and development intent
- Designates general land-use patterns (where future residential, commercial, and industrial growth is desired)
- **Not directly enforceable law** — it guides decisions but does not itself create violations
- Zoning decisions are expected to be **consistent with the comprehensive plan**

### Tier 2 — Zoning Ordinance
- The **legally enforceable code** implementing the comprehensive plan
- Defines each zoning district (R-1, C-2, I-1, A-1, etc.), what uses are permitted, and all dimensional standards
- Violations of the zoning ordinance carry legal consequences: fines, stop-work orders, cease-and-desist orders, and forced remediation

### Tier 3 — Zoning Map
- A geographic document showing **which zoning district applies to each parcel**
- The zoning map and the zoning ordinance together determine what a specific property may legally do
- When evaluating a property, the zoning map identifies the applicable district, and the ordinance defines what is allowed in that district

> **AI Instruction:** To evaluate a property, identify its zoning designation from the local zoning map, then apply the rules in the local zoning ordinance for that district. If specific local rules are unavailable, use the general US standards outlined in this document.

---

## 3. Zoning Categories and Definitions

The United States uses five primary zoning categories. Districts within each category are typically numbered to indicate intensity (lower numbers = lower density/intensity).

---

### 3.1 Residential Zones (R)

Residential zoning designates areas for housing. Density and building type are the primary variables.

| District | Common Name | Typical Uses | Typical Density |
|---|---|---|---|
| R-1 | Single-Family Residential | Detached single-family homes only | 1–4 units/acre |
| R-2 | Two-Family / Duplex | Single-family + duplexes | 4–8 units/acre |
| R-3 | Small-Scale Multifamily | Triplexes, fourplexes, small apartments | 8–16 units/acre |
| R-4 | Medium-Density Multifamily | Apartments, townhouses, low-rise residential | 16–25 units/acre |
| R-5 | High-Density Multifamily | High-rise apartments, condominiums | 25–100+ units/acre |

**Permitted uses by right in residential zones typically include:**
- Primary dwelling unit(s) consistent with density classification
- Accessory dwelling units (ADUs) — increasingly permitted in R-1/R-2 zones
- Home-based occupations with restrictions (no external signage, limited employees, no customer traffic)
- Small residential accessory structures (garages, sheds)

**Uses commonly prohibited in residential zones:**
- Commercial retail or service businesses
- Industrial or manufacturing operations
- Large-scale agricultural operations
- Boarding houses or rooming houses above unit limits
- Short-term rentals (in some jurisdictions — highly variable)

---

### 3.2 Commercial Zones (C)

Commercial zoning permits business and retail activities. Intensity increases with the district number.

| District | Common Name | Typical Uses |
|---|---|---|
| C-1 | Neighborhood Commercial | Corner stores, small restaurants, professional offices, personal services |
| C-2 | Community Commercial | Shopping centers, supermarkets, banks, medical offices |
| C-3 | Regional / Highway Commercial | Big-box retail, auto dealerships, large shopping malls, drive-throughs |

**Additional commercial subcategories that may appear in local ordinances:**
- **Office (O or OB):** Professional and medical offices; limited retail
- **Mixed-Use (MU):** Combines residential (upper floors) with ground-floor commercial; common in urban corridors
- **Downtown Commercial (CBD):** High-density, pedestrian-oriented; reduced parking requirements

**Uses commonly prohibited in commercial zones:**
- Heavy manufacturing or industrial processing
- Residential uses (except in mixed-use designations)
- Outdoor storage of materials or equipment (except in specific commercial districts)
- Uses generating significant noise, odor, or hazardous materials

---

### 3.3 Industrial Zones (I)

Industrial zoning accommodates manufacturing, warehousing, and related uses. Intensity and environmental impact are the distinguishing factors.

| District | Common Name | Typical Uses |
|---|---|---|
| I-1 / IL | Light Industrial | Light assembly, R&D facilities, warehousing, distribution, small fabrication |
| I-2 / IH | Heavy Industrial | Chemical processing, large-scale manufacturing, scrap yards, bulk fuel storage |
| IM / IW | Manufacturing / Warehouse | Production facilities, logistics hubs, cold storage |

**Key characteristics of industrial zones:**
- Typically located at municipal peripheries, near rail lines, or along major freight corridors
- Large minimum lot sizes (commonly 1–5 acres)
- High impervious surface limits (80–95%)
- Uses generating noise, vibration, odor, or hazardous materials are regulated by performance standards

**Uses commonly prohibited in industrial zones:**
- Residential uses (primary dwellings)
- Sensitive uses such as schools, daycare centers, or hospitals
- Retail unless serving on-site industrial workforce

---

### 3.4 Agricultural Zones (A)

Agricultural zoning protects farmland and rural character from premature or incompatible development.

| District | Common Name | Typical Uses |
|---|---|---|
| A-1 | Agricultural | Active farming, ranching, orchards, vineyards, farm buildings |
| A-2 | Agricultural-Residential | Farming + limited residential (hobby farms, rural estates) |
| A-3 / RR | Rural Residential | Low-density rural housing with some agricultural activities |

**Typical lot size minimums in agricultural zones:** 1 to 40+ acres per parcel (varies widely by jurisdiction and state).

**Uses commonly permitted in agricultural zones:**
- Crop production, livestock operations, aquaculture
- Farm worker housing (on active farms)
- Agritourism (farm stands, u-pick, wine tasting — often conditionally permitted)
- Farm-based processing of on-site products

**Uses commonly prohibited in agricultural zones:**
- Dense residential subdivisions
- Commercial retail unrelated to agriculture
- Industrial operations (unless farm-related, such as grain elevators)

---

## 4. How Zoning Designations Are Determined

When a municipality assigns or changes a zoning designation for a parcel, the following criteria are typically considered:

**Physical parcel characteristics:**
- Parcel size, topography, and shape
- Existing infrastructure (roads, water, sewer)
- Natural constraints (wetlands, floodplains, steep slopes)

**Contextual factors:**
- Zoning and actual uses of adjacent and nearby parcels
- Established neighborhood character
- Proximity to transportation corridors, transit, or freight infrastructure

**Policy alignment:**
- Consistency with the comprehensive/master plan land-use designations
- Alignment with housing, economic development, or environmental goals
- Infrastructure capacity (can utilities and roads support the proposed intensity?)

**Public benefit analysis:**
- Impact on surrounding property values and uses
- Community need for the proposed use type
- Environmental and traffic impacts

> **AI Instruction:** If a property's zoning designation appears inconsistent with its surroundings (e.g., a single R-1 parcel surrounded by C-2 zoning), this may indicate an error, a historical anomaly, or a pending rezoning. Flag for human review.

---

## 5. Key Zoning Metrics and Calculations

These are the quantitative standards that determine whether structures and uses comply with zoning requirements.

---

### 5.1 Floor Area Ratio (FAR)

FAR controls the total bulk of a building relative to the lot.

**Formula:**
```
FAR = Total Gross Floor Area of All Buildings ÷ Total Lot Area
```

**Example:** A 10,000 sq ft lot with FAR = 2.0 permits a maximum of 20,000 sq ft of total floor area.

**Typical FAR ranges by zone:**

| Zone Type | Typical FAR |
|---|---|
| R-1 (Single-Family) | 0.3 – 0.6 |
| R-3/R-4 (Multifamily) | 0.8 – 2.5 |
| C-1/C-2 (Commercial) | 1.0 – 3.0 |
| C-3 / Downtown | 3.0 – 10.0+ |
| I-1 (Light Industrial) | 0.5 – 1.5 |
| I-2 (Heavy Industrial) | 0.5 – 1.0 |
| A-1 (Agricultural) | 0.01 – 0.1 |

**Compliance check:** Calculate total built square footage across all floors of all structures on the parcel. Divide by lot area. If result exceeds the zone's maximum FAR, the property is potentially over-built and non-compliant.

---

### 5.2 Lot Coverage

Lot coverage measures what percentage of the lot is covered by building footprints (not total floor area).

**Formula:**
```
Lot Coverage % = Total Building Footprint Area ÷ Total Lot Area × 100
```

**Typical maximum lot coverage by zone:**

| Zone Type | Typical Maximum Coverage |
|---|---|
| R-1 (Single-Family) | 30% – 50% |
| R-3/R-4 (Multifamily) | 50% – 75% |
| C-1/C-2 (Commercial) | 60% – 85% |
| I-1/I-2 (Industrial) | 80% – 95% |
| A-1 (Agricultural) | 5% – 15% |

---

### 5.3 Setbacks

Setbacks are the minimum distances structures must maintain from property lines.

| Setback Type | Definition | Typical Residential Range | Typical Commercial Range |
|---|---|---|---|
| Front setback | Distance from front lot line / street right-of-way | 15 – 30 ft | 10 – 25 ft |
| Rear setback | Distance from back property line | 20 – 50 ft | 10 – 30 ft |
| Side setback (each) | Distance from side lot lines | 5 – 15 ft | 10 – 25 ft |

**Important notes:**
- Some ordinances specify a minimum **total side yard** (sum of both sides) rather than per-side minimums
- Corner lots typically have two front setbacks (one per street frontage)
- Accessory structures (garages, sheds) usually have reduced setback requirements
- Decks, porches, steps, and eaves may be permitted to encroach a limited distance (typically 2–5 ft) into required setbacks

**Compliance check:** Measure from the exterior wall of any structure to each property line. Any dimension shorter than the zone's required setback is a potential violation.

---

### 5.4 Height Limits

Height is typically measured from average finished grade at the base of the structure to the highest point of the roof.

**Typical maximum heights by zone:**

| Zone Type | Typical Height Limit |
|---|---|
| R-1 (Single-Family) | 30 – 45 ft |
| R-2/R-3 (Multifamily — low-rise) | 35 – 65 ft |
| R-4/R-5 (Multifamily — mid/high-rise) | 65 – 150 ft |
| C-1 (Neighborhood Commercial) | 35 – 50 ft |
| C-2/C-3 (Regional Commercial) | 50 – 200 ft |
| I-1 (Light Industrial) | 45 – 65 ft |
| A-1 (Agricultural) | 35 – 60 ft (farm structures often exempt) |

---

### 5.5 Residential Density

Density controls how many dwelling units may exist on a parcel or within a project.

**Formula:**
```
Gross Density = Total Dwelling Units ÷ Total Lot Area (in acres)
Net Density = Total Dwelling Units ÷ Net Developable Area (excluding roads, dedications)
```

**Compliance check:** Count all dwelling units on the parcel (including ADUs, converted units, basement apartments). Divide by lot area in acres. Compare to the zone's maximum units-per-acre standard.

---

### 5.6 Impervious Surface Coverage

Impervious surfaces (roofs, pavement, concrete, asphalt) are regulated to control stormwater runoff.

**Formula:**
```
Impervious Surface % = Total Impervious Surface Area ÷ Total Lot Area × 100
```

**Typical limits:**

| Zone Type | Typical Maximum Impervious Coverage |
|---|---|
| R-1 (low density) | 30% – 50% |
| R-3/R-4 (medium density) | 50% – 70% |
| R-5 / High-Density | 70% – 85% |
| Commercial | 75% – 90% |
| Industrial | 80% – 95% |
| Agricultural | 5% – 20% |

---

### 5.7 Parking Requirements

Most zones require a minimum number of off-street parking spaces based on use type and size.

**Common parking minimums:**

| Use | Typical Minimum Parking |
|---|---|
| Single-family residential | 2 spaces per unit |
| Multifamily (1-bedroom) | 1 – 1.5 spaces per unit |
| Multifamily (2+ bedrooms) | 1.5 – 2 spaces per unit |
| Retail / Commercial | 4 – 5 spaces per 1,000 sq ft |
| Office | 3 – 4 spaces per 1,000 sq ft |
| Restaurant | 8 – 15 spaces per 1,000 sq ft |
| Industrial / Warehouse | 1 – 2 spaces per 1,000 sq ft |

---

## 6. Overlay Districts and Special Zones

Overlay districts are applied **on top of** base zoning districts to add supplemental regulations. A property may have both a base zone (e.g., R-2) and one or more overlays (e.g., Flood Zone + Historic District).

---

### 6.1 Flood Hazard Overlay (Floodplain Overlay)

- Based on **FEMA Flood Insurance Rate Maps (FIRMs)**
- Special Flood Hazard Areas (SFHAs) = areas with 1% annual chance of flooding (100-year flood)
- Communities participating in the **National Flood Insurance Program (NFIP)** must adopt floodplain regulations

**Key requirements in flood overlay zones:**
- New structures and substantial improvements must be elevated above the **Base Flood Elevation (BFE)**
- Fill and grading within the floodplain is restricted
- Floodway areas (innermost channel + adjacent land needed to convey the flood) are typically off-limits for development
- Development permits required for any construction within the SFHA

**Compliance signal:** A structure located within a FEMA-mapped SFHA with a finished floor below the BFE is likely non-compliant with the flood overlay unless it was built before the community joined NFIP.

---

### 6.2 Historic District and Landmark Overlay

- Protects architecturally or historically significant buildings, districts, and sites
- May be federally designated (National Register of Historic Places), state-designated, or locally designated
- Only **locally designated** historic districts carry enforceable design review requirements

**Key requirements:**
- Exterior alterations, demolitions, new construction, and signage require a **Certificate of Appropriateness (COA)** from a Historic Preservation Commission
- Design standards ensure changes are compatible with historic character
- Interior modifications are generally not regulated
- Tax incentives (Federal Historic Tax Credit — 20% credit for income-producing properties) may apply

**Compliance signal:** Exterior alterations or new construction within a historic district that lack a COA are likely violations regardless of base zone compliance.

---

### 6.3 Transit-Oriented Development (TOD) Overlay

Applied near transit stations and major transit corridors to encourage walkable, mixed-use development.

**Typical modifications applied:**
- Reduced or eliminated minimum parking requirements
- Increased permitted density and FAR
- Ground-floor retail/active uses required or incentivized
- Reduced front setbacks to create walkable streetscapes
- Expedited permitting or density bonuses for affordable housing inclusion

---

### 6.4 Planned Unit Development (PUD)

A PUD is a site-specific development agreement that replaces or supplements standard zoning with a custom set of regulations negotiated between the developer and the municipality.

**Key characteristics:**
- Approved via a master plan and binding development agreement
- May permit uses, densities, and configurations not otherwise allowed in the base zone
- Developer provides public benefits in exchange for flexibility (open space, affordable housing, transit improvements)
- PUD approval is recorded and runs with the land — subsequent owners are bound by its terms

**Compliance signal:** A property with a PUD approval must be evaluated against the PUD master plan, not standard zoning tables.

---

### 6.5 Agricultural Preservation Overlay

- Restricts development on farmland through **Purchase of Development Rights (PDR)** programs or agricultural conservation easements
- Easements are permanent and recorded against the deed
- Permits limited residential development (often one dwelling per easement parcel)
- Prohibits subdivision and non-agricultural commercial development

---

### 6.6 Environmental and Resource Protection Overlays

| Overlay Type | What It Protects | Common Requirements |
|---|---|---|
| Wetland Overlay | Jurisdictional wetlands (Section 404 of Clean Water Act) | Development setbacks (25–100 ft), fill prohibitions, permits |
| Stream/Riparian Buffer | Water quality in streams and rivers | 50–300 ft no-build buffer from stream banks |
| Steep Slope | Hillside stability and erosion | Development restrictions on slopes >20–25%; grading limits |
| Forest / Tree Canopy | Urban tree cover | Tree preservation requirements; replanting mandates |
| Wellhead Protection | Groundwater recharge areas | Restrictions on impervious surface and hazardous materials storage |

---

## 7. Assessing Correct vs. Incorrect Zoning

This section provides a structured framework for determining whether a property appears to be correctly zoned.

---

### Step 1: Identify the Zoning Designation

- Obtain the property's zoning district from the local zoning map
- Note any overlay districts that apply
- If a PUD is present, obtain the PUD master plan

---

### Step 2: Identify the Actual Land Use

Assess what the property is actually being used for:
- Primary use (residential, commercial retail, office, industrial, agricultural)
- Secondary or accessory uses (home-based business, ADU, storage facility)
- Number and type of dwelling units (for residential)
- Type of commercial activity (for commercial/mixed-use)

---

### Step 3: Compare Use to Permitted Use Table

Using the local zoning ordinance (or the general standards in this document), determine whether the actual land use falls within one of three categories:

| Classification | Meaning |
|---|---|
| **Permitted by right (P)** | Allowed without discretionary review |
| **Conditionally permitted (C)** | Allowed only with a Conditional Use Permit (CUP) or Special Use Permit (SUP) |
| **Prohibited (X)** | Not allowed in this zone under any circumstances |

**If the actual use is Prohibited or Conditionally Permitted without the required permit → potential zoning violation.**

---

### Step 4: Evaluate Dimensional Compliance

For each of the following metrics, compare the actual measured value to the zone's standard:

- [ ] **FAR:** Actual FAR ≤ Maximum allowed FAR?
- [ ] **Lot Coverage:** Actual coverage % ≤ Maximum allowed %?
- [ ] **Front Setback:** Measured distance ≥ Required minimum?
- [ ] **Rear Setback:** Measured distance ≥ Required minimum?
- [ ] **Side Setbacks:** Measured distance(s) ≥ Required minimum(s)?
- [ ] **Height:** Actual structure height ≤ Maximum allowed height?
- [ ] **Density:** Actual units per acre ≤ Maximum allowed density?
- [ ] **Impervious Coverage:** Actual % ≤ Maximum allowed %?
- [ ] **Parking:** Actual spaces ≥ Minimum required for use type?

**Any "No" answer → potential dimensional zoning violation.**

---

### Step 5: Check for Overlay Compliance

If any overlays apply:
- [ ] Is the property in a FEMA flood zone? If so, is the structure elevated to or above BFE?
- [ ] Is the property in a historic district? Were exterior alterations done with a COA?
- [ ] Does the property have a PUD agreement? Is development consistent with the PUD master plan?
- [ ] Are environmental overlays present? Are required buffers and restrictions respected?

---

### Step 6: Determine Zoning Status

Based on findings from Steps 1–5, classify the property:

| Status | Description |
|---|---|
| **Compliant** | All uses and dimensional standards meet current zoning requirements |
| **Legally Nonconforming** | Uses or structures are noncompliant but were lawfully established before current zoning took effect |
| **Conditionally Compliant** | Use requires a CUP/SUP; confirm whether permit has been obtained |
| **Violation** | Use or structure does not comply with current zoning and is not legally protected |
| **Unclear — Needs Review** | Insufficient information; flag for human review |

---

## 8. Legal Nonconforming Uses

A **legal nonconforming use** (also called a "grandfathered" use) is a property use or structure that:
1. Was **lawfully established** before the current zoning regulation took effect, AND
2. Does not comply with the **current** zoning requirements

**Key rules governing legal nonconforming uses:**

- The nonconforming use may **continue indefinitely** as long as it is not discontinued
- Discontinuation (typically defined as **6–12 months of inactivity**, depending on jurisdiction) results in loss of nonconforming status; the property must then comply with current zoning
- The nonconforming use **cannot be expanded** significantly or changed to a different nonconforming use
- If a nonconforming structure is **substantially damaged** (typically >50% of assessed value), it may not be rebuilt to its prior nonconforming state
- Some jurisdictions apply **amortization clauses** requiring nonconforming uses to cease within a defined period

**Nonconforming use vs. zoning violation:**

| | Legal Nonconforming | Zoning Violation |
|---|---|---|
| Established before current zoning? | Yes | No (or cannot be proven) |
| Enforcement action possible? | No (while protected) | Yes |
| Can expand? | No / Very limited | N/A — must remediate |
| Can change to another use? | Only to conforming uses | Must become conforming |

> **AI Instruction:** If a property's use appears inconsistent with its zoning but the property is older or has historical records suggesting the use predates current zoning, classify as "Possibly Nonconforming — Needs Verification" rather than "Violation" without further documentation.

---

## 9. Variances, Conditional Use Permits, and Rezoning

These are the primary legal mechanisms through which a property may legally deviate from standard zoning requirements.

---

### 9.1 Variance

A variance is a **discretionary waiver** of a specific zoning standard granted to a property owner when strict compliance would cause **undue hardship** due to unique property characteristics.

**Types:**
- **Area Variance (Dimensional Variance):** Modification of a numerical standard (setback, height, lot size, FAR). Requires showing practical difficulty.
- **Use Variance:** Permission for a use not permitted in the zone. Rare and requires showing that denial amounts to confiscation of property value.

**Standards for granting:**
1. Hardship is due to unique physical characteristics of the parcel (not general area conditions)
2. Hardship was not self-created
3. Variance is the minimum necessary relief
4. Granting does not harm the public interest or neighboring properties

**Compliance implication:** A property with an approved variance may legally deviate from a standard dimensional requirement. The variance approval (typically a recorded document) defines the permitted deviation.

---

### 9.2 Conditional Use Permit (CUP) / Special Use Permit (SUP)

A CUP authorizes a use that is **expressly anticipated** in the zoning ordinance as potentially compatible with the zone, subject to conditions.

**How it works:**
- The use must be listed in the zoning ordinance as "conditional" or "special" for that district
- Approval is granted by the zoning board or planning commission following a public hearing
- Conditions may address: hours of operation, traffic, signage, landscaping, noise, outdoor storage, lighting

**Compliance implication:** A conditionally permitted use without an approved CUP/SUP is a violation. Confirm whether the permit was obtained and whether the property is operating within the conditions set.

---

### 9.3 Rezoning

Rezoning changes a parcel's zoning district classification. It requires:
- Formal application to the planning department
- Staff report and planning commission recommendation
- Public hearing
- City council or county board approval
- Demonstration of consistency with the comprehensive plan

**Compliance implication:** A recent rezoning changes the applicable standards. Always confirm the current, effective zoning designation rather than relying on outdated records.

---

## 10. Common Zoning Violations and Red Flags

### 10.1 Use Violations

| Violation | Description |
|---|---|
| Commercial use in residential zone | Business operating from home beyond home occupation limits (customer traffic, signage, employees on-site) |
| Industrial use in commercial zone | Manufacturing, heavy equipment storage, or processing in a C-zone |
| Residential use in industrial zone | People living in warehouses, factories, or lofts without residential zoning |
| Unpermitted short-term rentals | Operating Airbnb/VRBO without required local permits in zones that restrict STRs |
| Agricultural operations in non-agricultural zones | Livestock or crop production in residential or commercial zones |

---

### 10.2 Structural / Dimensional Violations

| Violation | Description |
|---|---|
| Setback encroachment | Structure (wall, deck, shed, garage) built within the required setback distance |
| Height violation | Building exceeds zone's maximum height limit |
| FAR exceedance | Total floor area of all buildings exceeds the maximum FAR for the lot |
| Lot coverage violation | Building footprints cover more of the lot than the zone allows |
| Impervious surface violation | Total paved/covered area exceeds allowable impervious coverage |

---

### 10.3 Density and Unit Violations

| Violation | Description |
|---|---|
| Illegal unit conversion | Single-family home converted to multiple units without rezoning or approval |
| Excess units per acre | Number of dwelling units exceeds the zone's maximum density |
| Unpermitted ADU | Accessory dwelling unit added without permits (basement apartment, garage conversion) |
| Boarding house operation | Property rented to multiple unrelated individuals, effectively operating as a rooming house |

---

### 10.4 Parking Violations

| Violation | Description |
|---|---|
| Insufficient parking | Property does not provide the minimum required off-street parking for its use type |
| Converted garage | Required garage spaces converted to living area, reducing parking below minimum |
| Parking in setbacks | Parking areas located within required front or side setbacks |

---

### 10.5 Signage Violations

| Violation | Description |
|---|---|
| Oversized signage | Sign dimensions exceed zone maximums for area, height, or illumination |
| Prohibited sign type | Animated, electronic, or billboard-type signs in zones where prohibited |
| Unpermitted sign placement | Signs in rights-of-way, visibility triangles, or required setbacks |

---

### 10.6 Overlay / Environmental Violations

| Violation | Description |
|---|---|
| Construction below BFE | Structure in FEMA flood zone with floor elevation below Base Flood Elevation |
| Unpermitted wetland fill | Fill, grading, or construction within jurisdictional wetlands or required buffers |
| Historic alteration without COA | Exterior changes to a locally designated historic structure without required approval |
| Buffer encroachment | Impervious surface or structures within required stream, wetland, or slope buffers |

---

## 11. AI Compliance Evaluation Framework

Use this step-by-step decision logic when evaluating a specific property for zoning compliance.

---

### Input Data Required

To perform a complete evaluation, the following data should be provided or retrieved:

- [ ] Parcel address or APN (Assessor Parcel Number)
- [ ] Zoning district designation (from local zoning map)
- [ ] Any overlay districts applicable to the parcel
- [ ] Actual current land use(s) on the property
- [ ] Lot area (square feet or acres)
- [ ] Total gross floor area of all structures (square feet, by floor)
- [ ] Building footprint area (square feet)
- [ ] Structure height (feet)
- [ ] Number of dwelling units (if residential)
- [ ] Number of off-street parking spaces
- [ ] Setback measurements (front, rear, both sides)
- [ ] Any recorded variances, CUPs, PUD agreements, or special permits
- [ ] Year property was built / year current use was established

---

### Evaluation Decision Tree

```
1. Is the actual land use PERMITTED in the zoning district?
   ├── YES (by right) → Proceed to Step 2
   ├── YES (conditionally) → Is a valid CUP/SUP on record?
   │     ├── YES → Proceed to Step 2
   │     └── NO → FLAG: Conditional use without permit → VIOLATION
   └── NO (prohibited) → Is use legally nonconforming?
         ├── YES (established before zoning, continuously operated) → LEGALLY NONCONFORMING
         └── NO → FLAG: Prohibited use → VIOLATION

2. Do ALL dimensional metrics comply?
   ├── FAR ≤ maximum? 
   ├── Lot coverage ≤ maximum?
   ├── All setbacks ≥ minimum?
   ├── Height ≤ maximum?
   ├── Density ≤ maximum?
   ├── Impervious surface ≤ maximum?
   └── Parking spaces ≥ minimum?
   If ALL YES → Proceed to Step 3
   If ANY NO → Are any violations covered by an approved variance?
         ├── YES → CONDITIONALLY COMPLIANT (document variance scope)
         └── NO → FLAG: Dimensional violation → VIOLATION

3. Do overlay requirements comply?
   ├── All flood zone requirements met (if applicable)?
   ├── Historic alterations have COA (if applicable)?
   ├── PUD master plan conditions met (if applicable)?
   └── Environmental buffer requirements met (if applicable)?
   If ALL YES → COMPLIANT
   If ANY NO → FLAG: Overlay violation → VIOLATION
```

---

### Output Classification

After completing evaluation, classify the property as one of the following:

| Classification | Meaning | Recommended Action |
|---|---|---|
| **COMPLIANT** | All use and dimensional standards are met; all overlay requirements satisfied | No action required |
| **LIKELY COMPLIANT** | All indicators are compliant but some data is missing or unverifiable | Request missing data or verify with local planning department |
| **LEGALLY NONCONFORMING** | Noncompliant use or structure predates current zoning; lawfully protected | Document nonconforming status; monitor for changes in use |
| **CONDITIONALLY COMPLIANT** | Compliant only if applicable CUP/SUP/Variance is confirmed on record | Verify recorded permits with local planning or building department |
| **POTENTIAL VIOLATION** | One or more metrics indicate noncompliance; further investigation needed | Flag for human review; do not make final determination without verification |
| **VIOLATION — HIGH CONFIDENCE** | Clear, documented noncompliance with no apparent legal protection | Recommend remediation, variance application, or rezoning |
| **INSUFFICIENT DATA** | Too little information to evaluate | Request additional property data |

---

### Caveats and Limitations

> **Important:** This knowledge base provides general US zoning standards and principles. Actual zoning regulations vary significantly by municipality, county, and state. The specific numerical standards in this document (setbacks, FAR, density, etc.) are representative ranges only. For a legally authoritative determination, always consult:
> - The **local zoning ordinance** for the specific municipality
> - The **local zoning map** for the parcel's district designation
> - **Recorded documents** for any variances, CUPs, PUDs, or easements
> - A **licensed land use attorney or professional planner** for high-stakes decisions

This knowledge base is intended to support AI-assisted preliminary analysis only and does not constitute legal advice.

---

*Last updated: April 2026 | Jurisdiction: United States (General) | Covers: Residential, Commercial, Industrial, Agricultural, and Special Use zones*