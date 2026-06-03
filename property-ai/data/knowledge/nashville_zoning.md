# Nashville / Metro Davidson County Zoning Knowledge Base
> **Jurisdiction:** Metropolitan Nashville and Davidson County, Tennessee — Title 17 of the Metro Code of Ordinances  
> **Governing Authority:** Metro Planning Department | Metro Codes Department  
> **Purpose:** Structured knowledge base for an AI system to (1) explain Nashville zoning concepts and (2) evaluate whether a property is correctly or incorrectly zoned under local law.  
> **Expansion Note:** This document is designed for Nashville first. Additional city-specific sections can be appended over time using the same structural framework.

---

## Table of Contents
1. [Nashville Zoning Framework Overview](#1-nashville-zoning-framework-overview)
2. [How to Find a Property's Zoning in Nashville](#2-how-to-find-a-propertys-zoning-in-nashville)
3. [The Planning Hierarchy in Nashville](#3-the-planning-hierarchy-in-nashville)
4. [Nashville Zoning Districts](#4-nashville-zoning-districts)
5. [Land Use Permissions — The District Land Use Table](#5-land-use-permissions--the-district-land-use-table)
6. [Nashville Bulk Standards — Dimensional Requirements](#6-nashville-bulk-standards--dimensional-requirements)
7. [Nashville Street Setbacks](#7-nashville-street-setbacks)
8. [Nashville Overlay Districts and Special Zones](#8-nashville-overlay-districts-and-special-zones)
9. [Downtown Code (DTC — Chapter 17.37)](#9-downtown-code-dtc--chapter-1737)
10. [MDHA Redevelopment Districts](#10-mdha-redevelopment-districts)
11. [Nonconforming Uses and Structures](#11-nonconforming-uses-and-structures)
12. [Variances, Special Exceptions, and Rezoning](#12-variances-special-exceptions-and-rezoning)
13. [Common Zoning Violations and Red Flags](#13-common-zoning-violations-and-red-flags)
14. [Land Use Code Crosswalk — Davidson County Assessor Data](#14-land-use-code-crosswalk--davidson-county-assessor-data)
15. [Detecting Legally Nonconforming Uses](#15-detecting-legally-nonconforming-uses)
16. [Variance and CUP Documentation](#16-variance-and-cup-documentation)
17. [Split Zoning and Complex Designations](#17-split-zoning-and-complex-designations)
18. [Assessment Data Quality Notes](#18-assessment-data-quality-notes)
19. [Using Building Permits to Confirm Zoning Compliance](#19-using-building-permits-to-confirm-zoning-compliance)
20. [Common Zoning Violation Patterns in Davidson County](#20-common-zoning-violation-patterns-in-davidson-county)
21. [How Zoning Affects Assessment Ratios](#21-how-zoning-affects-assessment-ratios)
22. [AI Compliance Evaluation Framework — Nashville](#22-ai-compliance-evaluation-framework--nashville)

---

## 1. Nashville Zoning Framework Overview

Nashville's land use is governed by **Title 17 of the Metro Code of Ordinances**, known as "the Zoning Code for Metropolitan Nashville and Davidson County." It applies to all land within Metro's jurisdiction, exclusive of incorporated municipalities.

**Zoning Code vs. Building Code:**
- **Title 17 (Zoning Code):** Controls *what* can be built and operated on a property — use types, density, height, setbacks, lot coverage.
- **Title 16 (Metro Building and Construction Ordinance):** Controls *how* it can be built — construction standards, structural safety.

> **AI Instruction:** Zoning compliance is evaluated under Title 17. Building code compliance (structural safety, electrical, plumbing) is a separate determination under Title 16 and is not assessed by this knowledge base.

**A property's zoning status is determined by two documents used together:**
1. The **official zoning map** — which district is assigned to the parcel
2. The **zoning ordinance (Title 17)** — what that district permits

A parcel may carry a **"Current"** zoning code and one or more **"Inactive"** codes. Inactive codes may still be relevant for understanding grandfathering (nonconforming) rights. For new construction, only the Current code governs.

---

## 2. How to Find a Property's Zoning in Nashville

**Step 1 — Metro Parcel Viewer**  
The primary tool is the **Metro Planning Department's Parcel Viewer** (available at Nashville.gov). Search by address, parcel number, or owner name. The Parcel Viewer aggregates data from the Property Assessor, Register of Deeds, Planning Department, Metro Codes, and other agencies.

**Step 2 — Identify Zoning Code(s)**  
In the Parcel Viewer, find the zoning code with status "Current." Note all overlay districts that appear (e.g., UZO, NCZO, HPZO, UDO). A property may have multiple current codes — for new construction, use the most current applicable base zone.

**Step 3 — Look Up Permitted Uses**  
Reference the **District Land Use Table (Metro Code 17.08.030)**. This table lists every land use category and indicates for each district whether it is: Permitted (P), Permitted with Conditions (PC), a Special Exception (SE), Accessory (A), Overlay only (O), or Not Permitted.

**Step 4 — Look Up Dimensional Standards**  
Reference the **District Bulk Tables (Metro Code 17.12.020)** for FAR, density, coverage, height, and setbacks. Reference **Street Setbacks (Metro Code 17.12.030)** for minimum street setback distances.

**Step 5 — Check for Overlays**  
If any overlay district is present (UZO, NCZO, HPZO, UDO, SP), apply those additional standards on top of base zone requirements.

**Step 6 — Check for Specific Plans (SP)**  
If the parcel is zoned SP, locate and read the specific ordinance that established the plan (findable via the Parcel Viewer link to the adopting ordinance). SP standards override the general tables.

---

## 3. The Planning Hierarchy in Nashville

Nashville uses a three-tier planning hierarchy:

**Tier 1 — Concept 2010 (General Plan)**  
Nashville's comprehensive plan, adopted by the Metropolitan Planning Commission. This is a policy document — not enforceable law — expressing long-term land use goals. The Zoning Code is designed to implement the General Plan's goals and objectives.

**Tier 2 — Zoning Ordinance (Title 17)**  
The legally enforceable code. Violations carry legal consequences including fines, stop-work orders, cease-and-desist orders, and required remediation. The Zoning Administrator enforces this code; the Board of Zoning Appeals (BZA) hears appeals and special exceptions.

**Tier 3 — Official Zoning Map**  
Shows the district designation for each parcel. A parcel's zoning is determined by reading the map and then applying the ordinance's standards for that district.

---

## 4. Nashville Zoning Districts

Nashville uses a detailed, named district system — not the generic R-1/C-2 codes common elsewhere. Below is the complete district list established by Metro Code 17.08.010.

---

### 4.1 Agricultural Districts

| Code | Name | Minimum Lot Area | Primary Purpose |
|---|---|---|---|
| AG | Agricultural | 5 acres | Rural farming, ranching; low-density residential on unsubdivided tracts |
| AR2a | Agricultural-Residential | 2 acres | Transitional zone; farming with limited rural residential |

Agricultural districts implement "natural conservation" or "interim non-urban" policies — areas unsuitable for urban development or not intended to urbanize within the planning period.

---

### 4.2 Residential Districts

#### Single-Family Districts (RS and RS-A)
The number in the district name equals the **minimum lot size in square feet divided by 1,000** (e.g., RS5 = 5,000 sq ft minimum lot).

| Code | Min. Lot (sq ft) | Intended Density | Notes |
|---|---|---|---|
| RS80 | 80,000 | Very low | Rural residential |
| RS40 | 40,000 | Low | Rural/semi-rural |
| RS30 | 30,000 | Low | Low density |
| RS20 | 20,000 | Low-medium | |
| RS15 | 15,000 | Low-medium | |
| RS10 | 10,000 | Low-medium | |
| RS7.5 / RS7.5-A | 7,500 | Medium | -A variant has special garage/access rules |
| RS5 / RS5-A | 5,000 | Medium | Common Nashville neighborhood district |
| RS3.75 / RS3.75-A | 3,750 | Medium-high | Near transit corridors |

**RS-A districts** (alternative) add specific standards: alley-required access where available, garage doors must face side/rear, minimum raised foundation of 18–36 inches.

#### One- and Two-Family Districts (R and R-A)
These districts allow both single-family and duplex development.

| Code | Min. Lot (sq ft) | Notes |
|---|---|---|
| R80 | 80,000 | |
| R40 | 40,000 | |
| R30 | 30,000 | |
| R20 | 20,000 | |
| R15 | 15,000 | |
| R10 | 10,000 | |
| R8 / R8-A | 8,000 | |
| R6 / R6-A | 6,000 | Near arterials; preference for transit access |

#### Multifamily Districts (RM)
The number indicates **maximum units per acre**. Many districts have "-NS" (No STRP) and "-A" (alternative walkable design) variants.

| Code | Max Density (units/acre) | Min. Lot (sq ft) | Building Type |
|---|---|---|---|
| RM2 / RM2-NS | 2 | 66,000 | Low-intensity multifamily, 1–3 stories |
| RM4 / RM4-NS | 4 | 33,000 | Low-intensity multifamily |
| RM6 / RM6-NS | 6 | 22,000 | Low-medium multifamily |
| RM9 / RM9-NS / RM9-A / RM9-A-NS | 9 | 15,000 | 2–3 story multifamily |
| RM15 / RM15-NS / RM15-A / RM15-A-NS | 15 | 10,000 | Moderate multifamily |
| RM20 / RM20-NS / RM20-A / RM20-A-NS | 20 | 7,500 | Moderately high multifamily |
| RM40 / RM40-NS / RM40-A / RM40-A-NS | 40 | 6,000 | High-density; mid-rise possible |
| RM60 / RM60-NS / RM60-A / RM60-A-NS | 60 | 6,000 | High-density; mid/high-rise |
| RM80-A / RM80-A-NS | 80 | 6,000 | High-rise; near high-accessibility areas |
| RM100-A / RM100-A-NS | 100 | 6,000 | Maximum residential density |

**MHP — Mobile Home Park District:** Designed for mobile home parks; collector street access preferred.

---

### 4.3 Specific Plan District (SP)

**SP** is not a standard district — it is a site-specific plan adopted by Metro Council and the Planning Commission for a specific parcel or area. SP districts may deviate from any standard zoning requirement.

To evaluate an SP-zoned parcel, you must locate and read the specific ordinance (ordinance number found in Parcel Viewer). The SP ordinance defines all permitted uses and development standards. Default standards from the zoning tables do NOT apply unless explicitly incorporated in the SP.

**Example:** A parcel at 1219 Stockell Street is zoned SP under Ordinance BL2014-896. That SP permits Detached Accessory Dwelling Units (DADUs) with RS5 standards applying to all other structures. Without reading that ordinance, you cannot determine compliance.

---

### 4.4 Mixed-Use Districts (MU)

Mixed-use districts encourage a combination of residential, office, personal services, and retail in compact, walkable areas.

| Code | Name | Intensity | Notes |
|---|---|---|---|
| MUN / MUN-A / MUN-NS / MUN-A-NS | Mixed-Use Neighborhood | Low | Residential scale; good for adaptive reuse |
| MUL / MUL-A / MUL-NS / MUL-A-NS | Mixed-Use Limited | Moderate | Near major intersections; arterial access |
| MUG / MUG-A / MUG-NS / MUG-A-NS | Mixed-Use General | Moderately high | Near employment centers; transit served |
| MUI / MUI-A / MUI-NS / MUI-A-NS | Mixed-Use Intensive | High | Near downtown; large-scale buildings |

**-A (Alternative) variants** require build-to-zone placement, minimum glazing standards, alley-first parking access, and step-back regulations — they are more walkability-oriented than their standard counterparts.

**-NS (No STRP) variants** prohibit both Owner-Occupied and Not-Owner-Occupied Short-Term Rental Properties.

---

### 4.5 Office Districts (O)

| Code | Name | Intensity |
|---|---|---|
| OR20 / OR20-A / OR20-NS / OR20-A-NS | Office/Residential 20 | Medium-high (20 units/acre residential permitted) |
| OR40 / OR40-A / OR40-NS / OR40-A-NS | Office/Residential 40 | High (40 units/acre residential permitted) |
| ON | Office Neighborhood | Low; abuts residential areas |
| OL | Office Limited | Moderate |
| OG / OG-NS | Office General | Moderately high; arterial streets |
| ORI / ORI-A / ORI-NS / ORI-A-NS | Office/Residential Intensive | High; compatible with high-density residential |

---

### 4.6 Commercial Districts (C)

| Code | Name | Market Served |
|---|---|---|
| CN / CN-A / CN-NS / CN-A-NS | Commercial Neighborhood | Local/frequent needs of nearby residences |
| CL / CL-A / CL-NS / CL-A-NS | Commercial Limited | Community-wide retail and consumer services |
| CS / CS-A / CS-NS / CS-A-NS | Commercial Service | Wide market area; auto-oriented; diverse uses |
| CA / CA-NS | Commercial Attraction | Tourist, amusement, overnight accommodations |
| CF / CF-NS | Commercial Core Frame | Downtown-support services near CBD |

---

### 4.7 Shopping Center Districts (SC)

| Code | Name | Market Scale |
|---|---|---|
| SCN / SCN-NS | Shopping Center Neighborhood | Local (recurring neighborhood shopping) |
| SCC / SCC-NS | Shopping Center Community | 35,000–100,000 person market |
| SCR / SCR-NS | Shopping Center Regional | Regional market; malls, large anchors |

---

### 4.8 Industrial Districts (I)

| Code | Name | Primary Uses |
|---|---|---|
| IWD | Industrial Warehousing/Distribution | Wholesale, warehousing, bulk distribution; large tracts; heavy truck traffic |
| IR | Industrial Restrictive | Light industrial; enclosed buildings; limited outdoor storage |
| IG | Industrial General | Intensive manufacturing; access to highway, river, or rail required |

---

## 5. Land Use Permissions — The District Land Use Table

The District Land Use Table (**Metro Code 17.08.030**) governs whether a specific use is allowed in a specific district. It uses the following notations:

| Code | Meaning |
|---|---|
| **P** | Permitted by right — no discretionary review needed |
| **PC** | Permitted with Conditions — must comply with specific conditions in Chapter 17.16, Article II |
| **SE** | Special Exception — requires Board of Zoning Appeals approval under Chapter 17.16, Article III |
| **A** | Accessory — permitted only as secondary to a principal use |
| **O** | Overlay only — permitted only within a designated special overlay district |
| *(blank)* | **Not permitted** in this district |

> **AI Instruction:** If a use is blank for a given district, it is not permitted. If it is PC, the specific conditions must also be satisfied. If it is SE, an approved special exception must be on record. Always check whether any applicable conditions have been met before concluding a use is compliant.

### Selected Key Use Permissions by Category

**Single-Family Residential:**  
Permitted (P) in all RS and R districts; conditionally permitted (PC) in most mixed-use and office districts; not permitted in IWD, IR, IG industrial districts.

**Multi-Family Residential:**  
Not permitted in RS or R (single/two-family) districts. Permitted in RM districts and most MU, office, and higher commercial districts. SE in agricultural districts.

**Short-Term Rental Property (STRP) — Owner Occupied:**  
Permitted as Accessory (A) in most residential and mixed-use districts. **Prohibited in all -NS districts** (e.g., MUN-NS, RM9-NS).

**Short-Term Rental Property (STRP) — Not Owner Occupied:**  
Conditionally permitted (PC) in most districts where residential is allowed. **Prohibited in all -NS districts.**

**Retail:**  
PC in most commercial and shopping center districts; not permitted in pure industrial or agricultural districts.

**Restaurant (Full-Service):**  
PC in residential districts (with conditions); permitted in commercial and mixed-use districts.

**Industrial Manufacturing (Heavy):**  
Permitted (P) only in the IG district.

**Home Occupation:**  
Permitted as Accessory (A) in residential districts; permitted by right in some commercial and mixed-use districts. Home occupations must remain incidental to the residential use — no external signage, no on-site employees, no customer traffic beyond that normally associated with residential use.

**Detached Accessory Dwelling Unit (DADU):**  
PC (conditionally permitted) in RS and R districts only when: (a) within a historic overlay, (b) within a UDO with DADU standards, (c) on a lot with an improved alley at the rear or side, or (d) on a lot over 15,000 sq ft.

---

## 6. Nashville Bulk Standards — Dimensional Requirements

Bulk standards are established by the District Bulk Tables in **Metro Code 17.12.020**. Four tables apply depending on use and district type.

---

### 6.1 Table 17.12.020A — Single-Family and Two-Family Dwellings

| Zoning District | Min. Lot Area | Max. Building Coverage | Min. Rear Setback | Min. Side Setback | Max. Height |
|---|---|---|---|---|---|
| AG | 5 acres | 0.20 (20%) | 20 ft | 20 ft | 3 stories |
| AR2a | 2 acres | 0.20 | 20 ft | 20 ft | 3 stories |
| RS80 / R80 | 80,000 sq ft | 0.20 | 20 ft | 20 ft | 3 stories |
| RS40 / R40 | 40,000 sq ft | 0.25 | 20 ft | 15 ft | 3 stories |
| RS30 / R30 | 30,000 sq ft | 0.30 | 20 ft | 15 ft | 3 stories |
| RS20 / R20 | 20,000 sq ft | 0.35 | 20 ft | 10 ft | 3 stories |
| RS15 / R15 | 15,000 sq ft | 0.35 | 20 ft | 10 ft | 3 stories |
| RS10 / R10 | 10,000 sq ft | 0.40 | 20 ft | 5 ft | 3 stories |
| R8 / R8-A | 8,000 sq ft | 0.45 | 20 ft | 5 ft | 3 stories |
| RS7.5 / RS7.5-A | 7,500 sq ft | 0.45 | 20 ft | 5 ft | 3 stories |
| R6 / R6-A | 6,000 sq ft | 0.50 | 20 ft | 5 ft | 3 stories |
| RS5 / RS5-A | 5,000 sq ft | 0.50 | 20 ft | 5 ft | 3 stories |
| RS3.75 / RS3.75-A | 3,750 sq ft | 0.60 | 20 ft | 3 ft | 3 stories |

**Important notes:**
- In the **Urban Zoning Overlay (UZO)**, single and two-family dwellings are capped at **3 stories to a maximum of 45 feet** (Section 17.12.060C). Height is measured from finished grade (or ceiling of exposed basement ≤7 ft above grade) to eave/roof deck.
- Accessory structures on lots <40,000 sq ft: maximum 1 story or 16 ft.
- Accessory structures on lots ≥40,000 sq ft: may be 2 stories or 24 ft if full district setbacks are maintained.
- The top elevation of an accessory structure cannot exceed the top elevation of the principal dwelling.
- **Building Coverage** = footprint area ÷ lot area. This is distinct from FAR (which counts all floor area).

---

### 6.2 Table 17.12.020B — Multifamily and Nonresidential Uses in Residential Districts

This table applies to multifamily structures and nonresidential uses in residential districts. Key columns: minimum lot, maximum density, maximum FAR, maximum ISR (Impervious Surface Ratio), rear/side setbacks, and maximum height at the setback line.

| Zoning District | Max. Density (units/ac) | Max. FAR | Max. ISR | Min. Rear Setback | Min. Side Setback | Max. Height at Setback |
|---|---|---|---|---|---|---|
| RM2 | 2 | 0.40 | 0.60 | 20 ft | 20 ft | 20 ft |
| RM4 | 4 | 0.40 | 0.60 | 20 ft | 10 ft | 20 ft |
| RM6 | 6 | 0.60 | 0.70 | 20 ft | 10 ft | 20 ft |
| RM9 / RM9-NS | 9 | 0.60 | 0.70 | 20 ft | 10 ft | 20 ft |
| RM15 / RM15-NS | 15 | 0.75* | 0.70 | 20 ft | 10 ft | 20 ft |
| RM20 / RM20-NS / OR20 / OR20-NS | 20 | 0.80* | 0.70 | 20 ft | 5 ft | 30 ft |
| RM40 / RM40-NS / OR40 / OR40-NS | 40 | 1.00* | 0.75 | 20 ft | 5 ft | 45 ft |
| RM60 / RM60-NS | 60 | 1.25* | 0.80 | 20 ft | 5 ft | 65 ft |
| MHP | 9 | See Ch. 17.16 | See Ch. 17.16 | See Ch. 17.16 | See Ch. 17.16 | See Ch. 17.16 |

*No maximum FAR applies to multifamily developments in RM15, RM20, RM40, RM60, OR20, OR40 districts (Note 2).

**ISR (Impervious Surface Ratio)** = total impervious area ÷ lot area. Impervious surfaces include roofs, streets, driveways, parking lots, sidewalks paved with asphalt, concrete, compacted sand, gravel, or clay.

**Height control plane:** Height is further controlled by a sloped height control plane measured from the setback line (slope varies by district, typically 2:1 vertical to horizontal). No structure may penetrate the height control plane.

**Attached housing (townhomes/rowhouses):** Covered by Table 17.12.020B.1 — minimum lot areas are reduced (e.g., 2,800 sq ft in RM2–RM9-NS; 1,500 sq ft in RM20 and above), with zero side setback on common walls.

---

### 6.3 Table 17.12.020C — Mixed-Use and Nonresidential Districts

| Zoning District | Max. FAR | Max. ISR | Min. Rear Setback | Min. Side Setback | Max. Height at Setback |
|---|---|---|---|---|---|
| MUN / MUN-NS | 0.60* | 0.80 | 20 ft | None req. | 3 stories / 45 ft max |
| MUL / MUL-NS | 1.00* | 0.90 | 20 ft | None req. | 3 stories / 45 ft max |
| MUG / MUG-NS | 3.00* | 0.90 | 20 ft | None req. | 5 stories / 75 ft max |
| MUI / MUI-NS | 5.00* | 1.00 | None req. | None req. | 7 stories / 105 ft max |
| ON | 0.40 | 0.60 | 20 ft | 5 ft | 20 ft |
| OL | 0.75 | 0.70 | 20 ft | 5 ft | 30 ft |
| OG / OG-NS | 1.50 | 0.80 | 20 ft | 5 ft | 30 ft |
| ORI / ORI-NS | 3.00 | 0.90 | 20 ft | None req. | 65 ft |
| CN / CN-NS | 0.25 | 0.80 | 20 ft | None req. | 20 ft |
| CL / CL-NS | 0.60 | 0.90 | 20 ft | None req. | 30 ft |
| CS / CS-NS | 0.60 | 0.90 | 20 ft | None req. | 30 ft |
| CA / CA-NS | 0.60 | 0.90 | 20 ft | None req. | 30 ft |
| CF / CF-NS | 5.00 | 1.00 | None req. | None req. | 65 ft |
| SCN / SCN-NS | 0.25 | 0.80 | 20 ft | None req. | 20 ft |
| SCC / SCC-NS | 0.50 | 0.80 | 20 ft | None req. | 30 ft |
| SCR / SCR-NS | 1.00 | 0.80 | 20 ft | None req. | 30 ft |
| IWD | 0.80 | 0.90 | 20 ft | None req. | 30 ft |
| IR | 0.60 | 0.90 | 20 ft | None req. | 45 ft |
| IG | 0.60 | 0.90 | 20 ft | None req. | 60 ft |
| SP | As specified in SP ordinance |
| DTC | See Chapter 17.37 |

*FAR bonuses available in MUI/MUI-NS and within the UZO for all mixed-use districts (Section 17.12.060).

**FAR Definition (Nashville):**
```
FAR = Total Floor Area of All Structures ÷ Total Horizontal Lot Area
```
Parking floor area used to satisfy required parking is excluded from FAR calculations. In MUI districts, street-level leasable retail/restaurant space (min. 20 ft depth) with individual street access and ≥50% glazing is also excluded.

---

### 6.4 Table 17.12.020D — Alternative Zoning Districts (-A variants)

Alternative districts add build-to-zone (BTZ) requirements, step-back regulations, and glazing standards that standard districts do not. These districts require:
- Building to be located within the build-to zone measured from the right-of-way
- A primary entrance along the street-facing façade
- Minimum glazing (40% first-floor non-residential; 25% first-floor residential; 25% upper floors)
- Step-backs on upper stories above the BTZ height
- Alley-first parking access where alleys exist (in the UZO)

Key examples from Table 17.12.020D:

| District | Max. FAR | Max. ISR | Build-to Zone | Max. Height in BTZ | Step-back | Max. Height Overall |
|---|---|---|---|---|---|---|
| MUN-A | 0.60 | 0.80 | 0–15 ft (UZO) / 0–80 ft (outside UZO) | 3 stories / 45 ft | 15 ft | 4 stories / 60 ft |
| MUL-A | 1.00 | 0.90 | 0–15 ft (UZO) / 0–80 ft (outside UZO) | 3 stories / 45 ft | 15 ft | 4 stories / 60 ft |
| MUG-A | 3.00 | 0.90 | 0–15 ft | 5 stories / 75 ft | 15 ft | 7 stories / 105 ft |
| MUI-A | 5.00 | 1.00 | 0–15 ft | 7 stories / 105 ft | 15 ft | 15 stories / 150 ft |
| RM9-A | 0.60 | 0.70 | 0–15 ft (UZO) / 0–80 ft (outside UZO) | 30 ft | 15 ft | 35 ft |
| RM20-A | 0.80 | 0.70 | 0–15 ft (UZO) / 0–80 ft (outside UZO) | 30 ft | 15 ft | 45 ft |
| RM40-A | 1.00 | 0.75 | 0–15 ft | 45 ft | 15 ft | 60 ft |
| RM60-A | No FAR max | 0.80 | 0–15 ft | 65 ft | 15 ft | 90 ft |

---

## 7. Nashville Street Setbacks

Street setbacks are the minimum distances buildings must maintain from the street right-of-way line. They are separate from the rear and side setbacks in the bulk tables.

**For single and two-family lots:** Measured from the street right-of-way line.  
**For multifamily and non-residential:** Measured from the Standard Right-of-Way line in the Major and Collector Street Plan.

---

### 7.1 Table 17.12.030A — Street Setbacks for Single- and Two-Family Structures

| Zoning Districts | Minor-Local & Local Streets | All Other Streets |
|---|---|---|
| AG, AR2a, RS80/R80, RS40/R40 | 40 ft | 40 ft |
| RS30/R30, RS20/R20, RS15/R15, RM2/RM2-NS | 30 ft | 40 ft |
| RS10/R10, R8/R8-A, RS7.5/RS7.5-A, R6/R6-A, RS5/RS5-A, RS3.75/RS3.75-A, MHP, RM4–RM60 (non-A variants), MUN, MUL, MUG, MUI, ON, OR20, OR40, ORI (non-A variants) | 20 ft¹ | 40 ft |
| Alternative districts (RM9-A through RM100-A, MUN-A, MUL-A, MUG-A, MUI-A, OR20-A, OR40-A, ORI-A) | 5 ft | 5 ft |
| SP | As specified in the site-specific SP ordinance | |
| DTC | See Chapter 17.37 | |

¹ Two-family dwellings with parking between street line and front of structure: minimum 30 ft setback.

---

### 7.2 Table 17.12.030B — Street Setbacks for Multi-Family and Non-Residential Districts

| District Group | Street Setback |
|---|---|
| AG through RM15 / RM15-NS | 40 ft |
| RM20, RM20-NS, RM40, RM40-NS | 30 ft |
| ON, OL, OG, OG-NS, OR20, OR20-NS, OR40, OR40-NS | 30 ft |
| RM60, RM60-NS, MUN, MUN-NS, MUL, MUL-NS, MUG, MUG-NS, ORI, ORI-NS | 20 ft |
| CN, CN-NS, CN-A, CN-A-NS, SCN, SCN-NS, SCC, SCC-NS, SCR, SCR-NS | 20 ft |
| CL, CL-NS, CL-A, CL-A-NS, CS, CS-NS, CS-A, CS-A-NS, CA, CA-NS | 15 ft |
| IWD, IR, IG | 50 ft |
| CF, CF-NS, MUI, MUI-NS | 5 ft |
| DTC | See Chapter 17.37 |

> **Note:** These setback standards do NOT apply in alternative (-A) zoning districts, which use build-to zone requirements instead (Table 17.12.020D).

---

### 7.3 Contextual Street Setbacks in the UZO

Within the **Urban Zoning Overlay District (UZO)**, Section 17.12.035 establishes contextual street setbacks for mixed-use, office, industrial, and higher-density residential districts. When surrounding buildings don't meet standard setback requirements, the contextual standard applies based on the predominant pattern of pre-1950 buildings within three lot widths along the same block face. Buildings must still occupy the front of the lot with the primary entrance at the setback line.

---

### 7.4 Permitted Setback Encroachments

The following may encroach into required setbacks (Section 17.12.040):
- Accessory buildings ≤700 sq ft footprint: 1/2 required side setback (min. 3 ft), 3 ft rear setback (10 ft if garage door faces alley)
- Awnings, patio covers, canopies: up to 6 ft from building wall
- Chimneys: up to 3 ft (min. 3 ft from property line)
- Eaves, gutters, downspouts: up to 24 inches
- Open uncovered stoops and steps: up to 6 ft into setback
- Covered front porches (residential): up to 6 ft into street setback (must not be enclosed; min. 10 ft from right-of-way)
- Fences/screening walls: max 2.5 ft within 10 ft of right-of-way (open fences: 6 ft); max 6 ft in remainder of front setback; max 8 ft in side/rear setbacks

---

## 8. Nashville Overlay Districts and Special Zones

Overlay districts are applied on top of base zone districts and may add restrictions or grant additional permissions. A property may have multiple overlays simultaneously.

---

### 8.1 Urban Zoning Overlay (UZO)

Created in 2000 to protect the character of Nashville's urban core neighborhoods developed prior to the 1950s. Mapped area covers portions of the city west of the river and inner-ring neighborhoods.

**Key UZO rules:**
- **Residential height cap:** Single- and two-family dwellings: 3 stories, maximum 45 ft (stricter than non-UZO areas where stories alone apply)
- **Contextual setbacks:** New development must be consistent with the predominant setback pattern of pre-1950 buildings within three lot widths (Section 17.12.035)
- **Parking placement:** In commercial and mixed-use districts, parking must be at sides and rears of buildings — not between building and street
- **Building coverage:** In alternative districts, building must extend across ≥60% of lot frontage (lots ≥60 ft wide) or full width (lots <60 ft wide) in mixed-use/commercial districts
- **Alley access:** Where an improved alley exists, primary vehicular access must come from the alley
- **Special height exceptions:** In non-residential districts, structures exceeding the height control plane for up to 30% of street-facing façade may be approved by BZA special exception

---

### 8.2 Neighborhood Conservation Zoning Overlay (NCZO)

Protects the character, scale, and architectural consistency of established Nashville neighborhoods. Properties with NCZO designations may have different height, setback, or design requirements than the base zone.

To determine NCZO requirements: Review guidelines for that specific neighborhood at the **Historical Commission** (615-862-7970). NCZO restrictions vary by neighborhood — there is no single universal standard.

---

### 8.3 Historic Preservation Zoning Overlay (HPZO)

Protects historically or architecturally significant properties and districts. Stronger than NCZO — exterior changes require a **Preservation Permit** (Certificate of Appropriateness) from the Metro Historic Zoning Commission.

**Key HPZO rules:**
- All exterior modifications, additions, demolition, new construction, and signage require a Preservation Permit
- Interior modifications are generally not regulated
- Height regulations within an HPZO are established by the Zoning Administrator based on recommendation of the Historic Zoning Commission — not automatically derived from the bulk tables
- Alternative flood protection measures may substitute for standard elevation requirements if they preserve historic character

**Contact:** Historic Zoning Administrator: 615-862-7970

> **AI Instruction:** If a property is within an HPZO, any exterior alteration, addition, or new construction without a recorded Preservation Permit is a potential overlay violation regardless of base zone compliance.

---

### 8.4 Urban Design Overlay (UDO)

Urban Design Overlays require specific design standards for development in designated areas (e.g., signage, façade materials, building placement, open space). These vary by overlay area.

To evaluate UDO requirements: Visit the Planning Department website or contact planningstaff@nashville.gov / 615-862-7190 for the specific design standards applicable to that overlay area.

---

### 8.5 Specific Plan (SP) District

Specific Plans are site-specific development frameworks adopted by Metro Council and the Planning Commission. They may permit uses, densities, and configurations not otherwise available in standard zoning.

**How to evaluate SP compliance:**
1. Locate the adopting ordinance number (found in Parcel Viewer)
2. Read the full ordinance — it defines all permitted uses, development standards, and conditions
3. SP standards supersede standard district tables
4. If the SP references a base district (e.g., "all standards of RS5 apply except as noted"), both the SP and base district standards apply concurrently
5. Contact the Metro Planning Department for questions about SP zoning (615-862-7190)

---

### 8.6 Flood Hazard Areas

Nashville properties in FEMA-mapped Special Flood Hazard Areas (SFHAs / 100-year floodplain) are subject to floodplain overlay regulations. Properties within floodplains must meet Metro Stormwater and NFIP requirements:
- New structures and substantial improvements must be elevated above Base Flood Elevation (BFE)
- Fill in floodways is restricted
- Development within SFHAs requires permits
- Properties with finished floors below BFE are potentially non-compliant unless pre-NFIP

**Compliance signal:** A structure in a FEMA-mapped SFHA with a finished floor below BFE is likely non-compliant with flood overlay regulations unless legally established before community participation in NFIP.

---

## 9. Downtown Code (DTC — Chapter 17.37)

The Downtown Code is a **form-based zoning code** that applies to downtown Nashville (generally the area west of the river within the Downtown Community Plan boundary). It is entirely separate from the standard zoning code and uses different tools and standards.

**Key characteristics:**
- Emphasizes regulating the **height, bulk, and location** of buildings and their relationship to surroundings rather than use alone
- Designed to encourage live/work/shop mixed-use within downtown neighborhoods
- Applies DTC subdistrict rules rather than standard district bulk tables (Tables 17.12.020A–C do not apply)
- Street setbacks, FAR, height, and parking standards are all DTC-specific (see Chapter 17.37)
- Parking is managed differently — less parking is often required due to transit access and walkability
- A separate DTC Design Review Committee process applies for certain developments

**For any property showing "DTC" as its zoning designation:** All standards must be evaluated under Chapter 17.37, not the general tables in this document. The DTC subdistrict designation (North, South, East, West, Central) determines the applicable standards.

**Contact:** Eric Hammer, Metro Planning Department — designstudio@nashville.gov / 615-862-7165

> **AI Instruction:** Do not apply standard bulk table values to DTC-zoned properties. Flag all DTC properties as requiring DTC-specific analysis.

---

## 10. MDHA Redevelopment Districts

The **Metropolitan Development and Housing Agency (MDHA)** has established multiple redevelopment districts throughout Nashville aimed at eliminating blight and improving neighborhood quality. Properties within MDHA redevelopment districts have additional restrictions and rights beyond standard zoning.

If a property's Parcel Viewer entry shows an MDHA designation: The applicable plan must be reviewed at **MDHA's website** (mdha.org). Contact MDHA's Development Office at 615-252-3750 for property rights and restrictions within these districts.

**Note:** Redevelopment district plans may establish alternative height standards different from the base zone (Section 17.12.020C, Note 4).

---

## 11. Nonconforming Uses and Structures

Nonconforming provisions are governed by **Chapter 17.40 (Article XIV)** of the Metro Code.

### Legal Nonconforming Use
A use that was **lawfully established** before current zoning took effect and does not comply with current use regulations.

**Rules under Nashville zoning:**
- May continue as long as the use is not discontinued
- A **change of occupancy or ownership alone** does not constitute a change of use — nonconforming protection continues
- A **change of use** (to another use group or major class) terminates nonconforming status — property must then comply with current zoning
- Nonconforming uses may not be changed to another nonconforming use (except as provided in Section 17.40.650C)

**Permits previously issued (Section 17.04.030):**
- Permits issued before zoning changes remain effective if construction begins within **6 months of permit issuance**
- "Construction" means physical improvements — footings, foundations, water/sewer lines. Clearing, grading, material storage, or temporary structures do not constitute construction.

### Nonconforming Structures
A structure that was legally constructed but does not currently meet dimensional standards (setbacks, height, coverage, etc.) for the district. The structure may remain but cannot be expanded into greater noncompliance.

**Substantial damage rule:** If a nonconforming structure is substantially damaged, it may not be rebuilt to its prior nonconforming dimensions unless the structure and use meet current code.

### Temporary Structures After Natural Disaster
The Zoning Administrator may permit a temporary mobile home on a lot where a permanent dwelling was destroyed by natural causes and is being rebuilt. Permits are issued for 3-month periods (maximum two periods). This is an emergency exception, not a permanent use authorization.

---

## 12. Variances, Special Exceptions, and Rezoning

### Board of Zoning Appeals (BZA)
The BZA administers variances and special exceptions under Chapter 17.16.

### Special Exception (SE)
Uses designated SE in the District Land Use Table require BZA approval before a zoning permit is issued. The BZA evaluates the use against specific standards in Chapter 17.16, Article III. An approved SE is site-specific and runs with the land.

> **Compliance signal:** A use designated SE in a district is a violation if no BZA approval is on record.

### Variance
A waiver of a specific dimensional standard (setback, height, coverage, FAR) where strict application creates practical difficulty or unnecessary hardship unique to the property. Approved variances are recorded and run with the land.

**Area variance:** Modification of numerical standards. Applicant must show hardship from unique property characteristics, not self-created.

> **Compliance signal:** A structure that violates a dimensional standard may be legally compliant if a recorded variance covers that specific deviation.

### Permitted with Conditions (PC)
PC uses require compliance with specific conditions listed in Chapter 17.16, Article II. No separate BZA approval is needed, but the conditions must be met. The conditions vary by use type and district.

### Rezoning
Changing a parcel's district designation requires Metro Council approval following planning commission review and public hearing. Rezonings must be consistent with the General Plan.

---

## 13. Common Zoning Violations and Red Flags

### 13.1 Use Violations

| Violation | Description |
|---|---|
| Commercial use in residential zone | Business activity from a home exceeding home occupation standards (employees on-site, external signage, customer traffic beyond normal residential levels) |
| Unpermitted STRP | Short-term rental operating without the required PC approval or operating in an NS district |
| Residential use in industrial zone | People living in IWD, IR, or IG districts |
| Agricultural activity in urban zone | Livestock or crop operations outside permitted agricultural or overlay zones |
| Missing SE approval | Uses designated SE in the district land use table operating without BZA approval |
| Missing PC conditions | Uses designated PC operating without meeting the required conditions |

### 13.2 Structural / Dimensional Violations

| Violation | Description |
|---|---|
| Exceeds maximum building coverage | Footprint of all structures exceeds the coverage ratio for the district (e.g., >50% coverage on RS5 lot) |
| Exceeds maximum FAR | Total floor area of all structures divided by lot area exceeds district maximum |
| Exceeds ISR limit | Total impervious surface exceeds district ISR limit (common in infill development) |
| Setback encroachment | Structure (wall, addition, deck, garage) built closer to property line than required setback |
| Height violation | Building exceeds the district's maximum story count or height limit; in UZO, exceeds the 45-ft residential cap |
| Height control plane penetration | Building exceeds the sloped height control plane measured from the setback line |

### 13.3 Density and Unit Violations

| Violation | Description |
|---|---|
| Excess units per acre | Number of dwelling units exceeds zone's maximum density (e.g., 3 units on RM2 land area that allows only 2/acre) |
| Illegal unit conversion | Single-family home converted to multifamily without rezoning |
| Unpermitted DADU | Detached accessory dwelling unit added without PC approval and without meeting the qualifying conditions (improved alley, lot >15,000 sq ft, or historic/UDO overlay) |
| Exceeds two-family limits | More than 2 units in an R or RS district |

### 13.4 Short-Term Rental (STRP) Violations

Nashville has a specific STRP regulatory framework. Key violations:

| Violation | Description |
|---|---|
| STRP in NS district | Operating any STR in a district with the -NS suffix |
| Not-Owner-Occupied STRP without PC | Operating a non-owner-occupied STR without the required conditional use permit |
| STRP exceeding 4 sleeping rooms | Any STRP exceeding 4 sleeping rooms |
| Transient occupancy beyond 30 days | "Transient" is defined as occupancy of less than 30 continuous days — using residential property for such occupancy without proper permitting |

### 13.5 Overlay Violations

| Violation | Description |
|---|---|
| Historic alteration without Preservation Permit | Any exterior modification to an HPZO property without Metro Historic Zoning Commission approval |
| UZO height exceedance | Residential structure in the UZO exceeding 3 stories or 45 feet |
| UZO parking in front of building | In commercial/mixed-use districts within the UZO, parking located between building and street |
| UZO building setback non-compliance | Building not placed at contextual setback consistent with surrounding pre-1950 buildings |
| Flood zone development without elevation | Structure in SFHA not elevated to BFE |

### 13.6 Accessory Structure Violations

| Violation | Description |
|---|---|
| Accessory structure used as dwelling | Accessory building used as a residential unit without base zoning, overlay, or use permit authorization |
| Oversized accessory structure | Accessory structure footprint exceeds 700 sq ft and does not meet full district setbacks; or exceeds 2,500 sq ft or 50% of principal building coverage |
| Accessory structure height violation | Structure on lot <40,000 sq ft exceeds 1 story/16 ft; or exceeds the top elevation of the principal building |

---


## 14. Land Use Code Crosswalk — Davidson County Assessor Data

### Overview
The Davidson County Tax Assessor assigns Land Use (LU) codes to each parcel based on the property's actual current use. These codes are **independent of zoning** — a property may be zoned RS5 but have an LU code of "010" (Single-family residential vacant land) or "030" (Mobile Home).

Understanding the relationship between LU codes and expected zoning is essential for identifying zoning violations and nonconforming uses. This section maps common assessor LU codes to their expected zoning matches and flags potential violations.

### Land Use Code Categories

**Residential (010–103)**

| LU Code | Description | Expected Zoning | Notes |
|---------|-------------|-----------------|-------|
| 010 | Single-family residential (improved) | RS 3.75 – RS80, R 6 – R80 | Most common residential code |
| 011 | Single-family residential (vacant) | RS 3.75 – RS80, R 6 – R80 | Land held for future development; nonconforming detection harder (no structure to measure) |
| 012 | Single-family residential (unoccupied) | RS 3.75 – RS80, R 6 – R80 | Structure present but boarded/abandoned |
| 013 | Mobile Home | RM2–RM4, MHP, or RS if allowed | Check if MHP designation is mapped |
| 014 | Mobile Home (vacant) | RM2–RM4, MHP, or RS | Flag if occupied informally in non-MHP zones |
| 015 | Duplex / Two-family | R 6 – R80 | **NOT permitted in RS zones** — potential violation |
| 019 | Other residential | Varies | Review deed/permit history |
| 030 | Multi-family residential (2–9 units) | RM2–RM20, MU, OR zones | Check if unit count matches density limits |
| 031 | Multi-family residential (10+ units) | RM40–RM100-A, MUI | High-density — verify against lot size and FAR |
| 032 | Manufactured housing (mobile home park) | MHP | Verify MHP zone mapped |

**Vacant Land & Agriculture (101–103)**

| LU Code | Description | Expected Zoning | Red Flags |
|---------|-------------|-----------------|-----------|
| 101 | Vacant land | Any zone | Cannot evaluate dimensional compliance without structure |
| 102 | Agricultural land (improved) | AG, AR2a | Outside city limits; verify if recently annexed |
| 103 | Agricultural land (vacant) | AG, AR2a | Monitor for rezoning/development intent |

**Commercial (200–299)**

| LU Code | Description | Expected Zoning | Red Flags |
|---------|-------------|-----------------|-----------|
| 200 | Retail sales (general) | CN–SCC, CF, CL, CS, CA, SC | Verify against use table for specific district |
| 201 | Shopping center | SCC, SCR | May be zoned SC or CS; verify permitted |
| 202 | Professional office | ON, OL, OG, OR20–ORI, CN–CF | Not permitted in residential zones |
| 203 | Financial institution | CN–SCC, CF | Check if in residential (violation) |
| 204 | Restaurant / bar | CN–CA, CF, MU | Verify use permitted in zone; check if full-service (PC in residential) |
| 205 | Lodging / hotel | CA (hotel/motel), OR/ORI (bed & breakfast), may be PC in residential | **High violation risk** if in single-family zone |
| 206 | Service station / fuel | CS, CA | Rarely permitted in residential or office zones |
| 208 | Vehicle sales | CS, CA | Not permitted in office or residential |
| 210 | Auto repair / service | CS (may be IR for heavy service) | If IR, verify site plan/industrial zoning |
| 213 | Heavy equipment / vehicle storage | IWD, IR, IG, CS | Not permitted in residential or office zones |
| 220 | Grocery / supermarket | SCC, CA | Verify against district use table |
| 230 | Warehouse / storage | IWD, IR, OP, CS | Large footprint — verify FAR compliance |
| 240 | Solid waste facility | IG | Heavy industrial; verify zoning |
| 250 | Amusement / entertainment | CA, MUG, MUI | Often CA zoning; check if in residential |
| 260 | Parking lot / deck | Any zone (as accessory) | If principal use, may violate zoning |
| 270 | Truck terminal / fleet | IWD, IG | Heavy industrial; not in residential |
| 290 | Other commercial | Varies | Check specific use against District Land Use Table |

**Office / Institutional (300–399)**

| LU Code | Description | Expected Zoning | Red Flags |
|---------|-------------|-----------------|-----------|
| 300 | Medical / dental office | ON, OL, OG, OR, CN (PC) | If large facility in residential, may need rezoning |
| 301 | Hospital | OG, ORI, MUI, CF | Major institutional use; often rezoned from residential |
| 302 | Office building (general) | ON, OL, OG, OR20–ORI | Not in pure residential; some PC in MU/residential |
| 303 | Government office | CN–CF, OG, ORI, SP | Often has SP zoning due to institutional nature |
| 305 | Educational institution | ON, OG, ORI, often SP | Schools/universities often zoned SP for stability |
| 310 | Religious institution | CN–CF, ON, OL, OG, ORI, permitted in all residential | Permitted in most zones; verify no covenant violations |
| 320 | Library / public building | OG, ORI, CF, allowed in most residential as PC | Verify use is administratively approved |
| 330 | Funeral home | CN–CF, OL, OG (check individual district) | Check District Land Use Table; often PC |
| 340 | Museum / cultural | OG, ORI, CF, MU | May be CA (attraction) depending on size |
| 390 | Other office / institutional | Varies | Review specific use with Nashville Planning Department |

**Industrial (400–499)**

| LU Code | Description | Expected Zoning | Red Flags |
|---------|-------------|-----------------|-----------|
| 410 | Light manufacturing | IR (restricted industrial) | Fully enclosed; no outdoor storage |
| 420 | Heavy manufacturing | IG (general industrial) | Access to highway/rail required; outdoor storage permitted |
| 430 | Petroleum storage | IG (only) | Heavy industrial; permitted in IG only; requires SE in IG |
| 440 | Chemical manufacturing | IG (only) | Heavy industrial regulatory requirements |
| 450 | Mineral extraction / mining | IG (outside city); may be SP | Monitor for environmental compliance |
| 460 | Utilities (water, wastewater, electrical) | IG, IWD, or non-zoned utility easement | Often operates under separate franchise authority |
| 490 | Other industrial | IR, IG, IWD | Verify specific use against industrial use table |

**Utilities & Special (500–599)**

| LU Code | Description | Zoning Notes | Compliance Path |
|---------|-------------|-------------|-----------------|
| 510 | Electrical transmission | Often non-zoned utility corridor | Not subject to local zoning; state utility authority applies |
| 520 | Water / wastewater | Often public utility zone (non-zoned) | Review utility easement document |
| 530 | Waste disposal | IG (only) | Environmental permit required in addition to zoning |
| 540 | Communications tower | May be SP or permitted in all zones as AC | Verify conditional use permit |
| 590 | Other utilities | Non-zoned or SP | Check Metro Public Works for jurisdiction |

**Vacant / Other (600+)**

| LU Code | Description | Approach |
|---------|-------------|-----------|
| 600+ | Various special categories | Consult assessor's codebook or Metro Planning |

### Using This Crosswalk for Violation Detection

**Pattern 1: Residential property, non-residential LU code, residential zoning**
- Example: LU 204 (Restaurant) on RS5-zoned land
- **Action:** Verify if restaurant has PC approval; if not, flag as violation
- **Data source:** Check Board of Zoning Appeals records for SE/PC approval

**Pattern 2: Multi-family LU code (030, 031) on single-family zone (RS, R)**
- Example: LU 031 (10+ unit building) on RS10-zoned lot
- **Action:** Check if lot is large enough for multifamily under overlay or SP; if not, rezoning was required but may not have occurred
- **Data source:** Metro Parcel Viewer historical zoning; Metro Planning Department records

**Pattern 3: Commercial LU code in residential zone with no recorded variance/PC**
- Example: LU 205 (Hotel) on RM9 land with no SE approval
- **Action:** Flag as likely violation; recommend property owner contact Planning Department
- **Data source:** Board of Zoning Appeals approvals; Metro Planning parcel history

**Pattern 4: Industrial LU code (410–430) in mixed-use or office zone**
- Example: LU 420 (Heavy manufacturing) on OG (Office General) zone
- **Action:** This is a zoning violation; heavy manufacturing is not permitted in OG
- **Data source:** Land Use Table 17.08.030

**Pattern 5: Single-family residential (010) on lot too small for zoned district**
- Example: LU 010 (S-F residential) with 3,500 sq ft lot, zoned RS5 (5,000 min)
- **Action:** Lot is nonconforming or property line was adjusted; flag for further review
- **Data source:** Assessor lot area; Metro Parcel Viewer

> **AI Instruction:** Use this crosswalk to flag inconsistencies between declared LU codes and zoning. LU codes reflect *actual current use* — zoning reflects *permitted use*. When the two clash, investigate whether the property has required approvals (variances, special exceptions, conditional use permits) or is operating outside the law.

---

## 15. Detecting Legally Nonconforming Uses

### Definition and Legal Framework
A **legally nonconforming use** is a land use that was lawfully established before the zoning that currently restricts it took effect. The use is protected from being forced to cease, even though it no longer complies with current zoning — **provided the use has not been abandoned, changed, or materially expanded**.

From Metro Code **Chapter 17.40 (Article XIV)** — Nonconforming Uses and Structures:

- A nonconforming use may continue **as long as it is not discontinued for a period exceeding 6 months**
- A **change in ownership or occupancy alone does not terminate nonconforming status** — the use may pass to a new owner and remain protected
- A **change of use** — from one use group/major class to another — *terminates* nonconforming protection; the property must then comply with current zoning
- A nonconforming use may not be changed to *another* nonconforming use (with rare exceptions under Section 17.40.650C)
- **Rebuilding after substantial damage:** If a nonconforming structure is substantially damaged (>50% of fair market value), it may be rebuilt only if the new structure and use comply with current zoning
- **Structural alterations:** Expanding a nonconforming structure into greater noncompliance is prohibited

### Key Indicators of Nonconforming Use Status

To assess whether a property likely has nonconforming use protection:

| Indicator | Implies Nonconforming Status? | Verification Steps |
|-----------|-------------------------------|-------------------|
| Current land use does NOT match district permits | **YES** — likely nonconforming | Check: (1) Year use was established; (2) Historical zoning records to see if zoning changed after use began |
| Deed or previous owner records show different use | **YES** — nonconforming status likely carries forward | Review historical Parcel Viewer entries; request deed research |
| Building appears aged / predates current zoning | **YES** — construction year often correlates with use start | Compare building construction date to zoning effective date of current district |
| No variance or special exception on record | **LIKELY YES** — if use has continued without formal approval | Check Board of Zoning Appeals records; if no approval, nonconforming may be the legal basis |
| Property transferred recently but same use continues | **YES** — nonconforming status survives ownership change | Verify use at parcel viewer before and after transfer |
| Use has been continuous (no closure >6 months) | **YES** — nonconforming protection likely intact | Interview property owner about operational history |

### Nonconforming Use Detection Checklist



### Common Nonconforming Use Scenarios in Nashville

| Scenario | Zoning | Current Use | Status | Notes |
|----------|--------|-------------|--------|-------|
| Small antique shop, family-run since 1965 | RS5 (Single-family residential) | Retail antiques | Likely NONCONFORMING | Use predates 1974 large-scale rezoning; continuous operation; no expansion |
| Three-story apartment building | RS10 (Single-family only) | Multifamily (6 units) | Likely NONCONFORMING | Building footprint suggests pre-1970s construction; no unit count increase in recent years |
| Church building | RS7.5 (Single-family) | Religious institution | **PERMITTED** (not nonconforming) | Churches permitted as accessory/principal use in most residential zones |
| Automotive repair shop | RM9 (Low-density multifamily) | Vehicle service | Likely NONCONFORMING | Commercial use; appears to predate zone; no variance on record |
| Metal fabrication facility | CS (Commercial Service) | Light manufacturing | **CHECK** | If IG or IR is required, may be violation or require SE approval; if established before CS zoning, may be nonconforming |
| Historic mansion converted to law offices | RS20 (Single-family) | Legal offices (10+ employees) | Status depends on conversion timing | If converted pre-1990, likely nonconforming; if post-2010, should have PC/SE approval |
| Single-unit dwelling in mixed-use building | MUG (Mixed-Use General) | Single dwelling unit | **PERMITTED** | Residential permitted in MU zones; not nonconforming |

### Red Flags Requiring Legal Review

A property flagged as potentially nonconforming should be escalated for attorney review if:

- The use is relatively recent (< 10 years) but does not match zoning → likely violation, not nonconforming
- Property was recently sold and current owner unaware of nonconforming status → risk of forced compliance
- Nonconforming structure substantially damaged (fire, water, etc.) → rebuilding may require compliance with current zoning
- Property owner applying for major renovation/expansion → may trigger compliance order from Metro Codes
- Property financing declined due to nonconforming risk → attorney review recommended
- Intent is to expand use beyond current scope → nonconforming protection may not extend to expansion

---

## 16. Variance and CUP Documentation

### Variance Authority and Process
The **Board of Zoning Appeals (BZA)** approves variances, which are authorized under **Metro Code Chapter 17.16, Article II**. A variance is a waiver of a specific dimensional standard (height, setback, coverage, FAR, density) granted when strict application creates practical difficulty or unnecessary hardship unique to the property.

**Types of Variances:**
- **Area variance:** Modification of numerical standards (setback, height, FAR, coverage, etc.)
- **Use variance:** Waiver of use restrictions (rare; generally not granted; setback variances much more common)
- **Density variance:** Waiver of density limits (units per acre)

### How to Verify Variance Status

| Method | Data Source | Reliability |
|--------|-------------|------------|
| **Metro Parcel Viewer — Variance Tab** | Official Metro Planning database | HIGH — official record |
| **Board of Zoning Appeals Records** | BZA approval documents filed with Metro Codes | HIGH — official approval |
| **Deed / Title Search** | Private title company or Register of Deeds | MEDIUM — might not record variance details |
| **Property Survey** | Surveyor or property owner | LOW — may be outdated |
| **Metro Planning Department** | Direct inquiry; 615-862-7190 | HIGH — official confirmation |

**Best Practice:** When evaluating dimensional compliance, always check **both** the bulk table standards AND the Parcel Viewer variance history. A structure that appears to exceed standards may be legally compliant if an approved variance covers the deviation.

### Recording and Duration of Variances

- Variances are typically **recorded in the Register of Deeds** (Property Records) under the property deed or as a separate filing
- Once approved and recorded, a variance **runs with the land** — it survives transfers of ownership
- Variances are **site-specific and non-transferable** — they apply to that parcel and cannot be moved to another property
- A variance may include an **expiration date** (commonly 2–5 years); the applicant must renew if work is not completed within the specified period

### Conditional Use Permits (CUP) and Permitted with Conditions (PC) Approvals

**Distinction:**
- **Permitted with Conditions (PC):** A use that the District Land Use Table allows, but only if specific conditions listed in the Metro Code are met. No separate permit or BZA approval required — conditions are automatically applicable.
- **Conditional Use Permit (CUP):** A discretionary approval for a use that is not automatically permitted in a zone but may be approved on a case-by-case basis. Unlike SE (special exception), a CUP involves Planning Commission and/or BZA discretion.

**Nashville's approach:** Nashville's code primarily uses the PC framework in the Land Use Table. However, some uses are labeled SE (Special Exception), which functionally operates similarly to a CUP — requiring Board of Zoning Appeals approval.

### Special Exception (SE) vs. Permitted with Conditions (PC)

| Framework | Defined Where? | Process | Approval Authority | Notes |
|-----------|---|---------|---------|-------------|
| **SE** | Land Use Table, Chapter 17.08.030 | Formal application to BZA with public hearing | Board of Zoning Appeals | Formal approval required; approval is site-specific |
| **PC** | Each specific use section, Chapter 17.16 Article II | Must comply with listed conditions; no separate permit | Self-administered | Conditions are deemed incorporated; non-compliance = violation |

### Common Conditions Attached to PC Uses

#### Single-Family Residential in Non-Residential Zones
If a parcel is zoned commercial/office but a single-family dwelling is PC, typical conditions include:
- Dwelling must be owner-occupied (or primary residence if rental)
- Lot may not be subdivided further
- External accessory uses (workshops, rentals) are prohibited
- Dwelling must conform to all bulk standards applicable to residential use in that zone

#### Multifamily in Mixed-Use / Office Zones
If multifamily is PC in a mixed-use district, conditions may include:
- Public parking provided for commercial ground floor
- Minimum percentage of first-floor retail/commercial use (e.g., 30%)
- Loading/service area at rear or alley
- Dedicated ground-floor entry for residential units

#### Short-Term Rental Property (STRP) — Not Owner-Occupied
If Not-Owner-Occupied STRP is PC, conditions typically include:
- Maximum number of sleeping rooms (commonly 4)
- Proof of property management on-site or on-call
- Annual registration and renewal
- Renewal of PC approval every 2–5 years
- Prohibition on modifications to primary structure
- Neighbor notification and complaint procedures

#### Home Occupation
If home occupation is PC in a residential zone, conditions include:
- Use is incidental to the residential use
- No external business signage
- No on-site employees beyond the resident owner (or owner + 1 employee)
- No customer traffic beyond normal residential levels
- No equipment/storage visible from street
- Parking for customers on-site only

### Verifying PC Compliance

To evaluate whether a property with a PC use is compliant:

1. **Locate the specific use** in Chapter 17.16, Article II (or the District Land Use Table, 17.08.030)
2. **Read all conditions** for that use in that district
3. **Inspect the property** against each condition:
   - Is signage present? (Violates "no external signage")
   - Are employees visible? (Violates "no on-site employees")
   - Is ground-floor retail activated? (Satisfies "minimum retail" condition)
   - Etc.
4. **If any condition is not met** → PC use is non-compliant → **VIOLATION**

### Examples: Variance vs. SE vs. PC

| Property | Zoning | Use | Regulatory Status | Approval Required? |
|----------|--------|-----|------|---------|
| Single-family on corner lot, 15-ft side setback, zone requires 20 ft, but structure predates zone | RS10 | Residential | **NONCONFORMING STRUCTURE** (not a variance) | None; protected by nonconformance |
| Single-family on corner, 15-ft side setback, structure just built, needs approval for 5-ft reduction | RS10 | Residential | **AREA VARIANCE** | Yes; Board of Zoning Appeals variance approval required |
| Home-based consulting business; owner working from home, no on-site employees, no signage | RS5 | Home Occupation | **PC (Permitted with Conditions)** | None if all conditions met; no separate permit |
| Restaurant in zone where PC permits full-service restaurants with conditions on hours (8am–11pm) | CN (Commercial Neighborhood) | Full-service restaurant | **PC (Permitted with Conditions)** | None if hours are followed; self-administered |
| Multifamily apartment building proposed on office-zoned lot where multifamily is SE | OL (Office Limited) | Multifamily residential | **SPECIAL EXCEPTION** | Yes; Board of Zoning Appeals approval required |
| Bed & breakfast inn in residential zone without SE approval or variance | RS5 | Transient lodging (bed & breakfast) | **Likely VIOLATION** unless SE is on record or property is nonconforming | Yes if newly established; check BZA records |

> **AI Instruction for Chat:** When evaluating a property with a potentially problematic use or dimension:
> 1. **First, check Parcel Viewer** for variance history and overlay approvals
> 2. **If variance found:** Property compliant for that deviation
> 3. **If no variance but use is PC:** Verify all conditions are met
> 4. **If no variance and use is SE:** Check Board of Zoning Appeals records for approval
> 5. **If neither variance nor approval found:** Flag as potential violation and recommend Legal/Planning review

---

## 17. Split Zoning and Complex Designations

### What is Split Zoning?

**Split zoning** (also called **co-zoning** or **dual zoning**) occurs when a single parcel is assigned two or more zoning districts simultaneously. This typically happens when:

- Parcel straddles district boundary line (e.g., half in RS5, half in RS10)
- Historical zoning layering has resulted in multiple zones being mapped to the same parcel
- Specific Plan (SP) applies across a parcel that also has a base zone
- Overlay district and base district both apply (e.g., MUL + UZO)

### How to Identify Split Zoning

In the **Metro Parcel Viewer:**
- Property will show more than one "Current" zoning code
- Example: A parcel may show "RS5" and "RS7.5" both marked as Current
- Each zone will cover a portion of the parcel (percentage or description may be listed)

### Evaluating Compliance Under Split Zoning

**Rule:** When a parcel is split-zoned, development must comply with the standards of the zone in which that specific use or structure is located.

**Example:**
- A parcel is 60% RS5 (5,000 sq ft minimum lot) and 40% RS10 (10,000 sq ft minimum lot)
- A single-family home with 7,500 sq ft footprint positioned entirely on the RS5 portion → Compliant
- Same home positioned to occupy portions of both RS5 and RS10 → Must meet the more restrictive standard (RS10) for the portion it occupies

**Complex Scenario — Mixed-Use + Overlay:**
- Parcel zoned MUL (Mixed-Use Limited) with UZO (Urban Zoning Overlay)
- Both zoning codes apply simultaneously to the same parcel
- Development must satisfy **both** MUL use/dimensional standards AND UZO requirements (height cap, contextual setback, parking placement)
- This is not ambiguous — it is **additive regulation**

### Registry of Split-Zoned Parcels

Nashville does not maintain a consolidated list of split-zoned properties. To identify split zoning:

1. **Metro Parcel Viewer** — Check the "Zoning" tab; if more than one "Current" code is listed, the parcel is split-zoned
2. **Metro Planning Department** — Call 615-862-7190 if unclear from Parcel Viewer
3. **Plat / Survey** — Professional surveyor can determine district boundaries relative to parcel boundaries

### Complex Designations (Overlapping Regulatory Frameworks)

**Scenario 1: Base zone + Special Plan (SP)**
- Parcel zoned "SP20-567" (specific plan ordinance 20-567) with an underlying zone of "MUL"
- Both SP and MUL standards apply in tandem where they don't conflict; SP prevails in conflicts
- Example: SP may permit density of 50 units/acre on a lot where MUL permits only 20 units/acre → SP permits 50

**Scenario 2: Base zone + HPZO**
- Parcel zoned "RS7.5" within "HPZO" (Historic Preservation Zoning Overlay)
- RS7.5 bulk standards apply (setbacks, height, coverage)
- HPZO standards apply to design/materials (requires Preservation Permit for exterior alterations)
- A structure that is dimensionally compliant with RS7.5 but lacks required Preservation Permit = **VIOLATION**

**Scenario 3: Base zone + Flood Overlay**
- Parcel zoned "CN" (Commercial Neighborhood) within FEMA Special Flood Hazard Area
- CN bulk standards apply normally
- Flood fringe standards apply (structures must be elevated per Base Flood Elevation)
- A structure that meets CN standards but has finished floor below BFE = **VIOLATION**

### Tier Hierarchy for Overlapping Designations

When multiple frameworks apply to the same parcel, the hierarchy is:

1. **Most restrictive standard wins** (in general)
2. **Specific Plan (SP)** overrides base district (SP is site-specific; base zone is general)
3. **Historic preservation requirements** cannot be waived (HPZO applies even if SP says otherwise)
4. **Flood overlay** applies regardless of zone (flood safety is non-waivable)
5. **Conditional approvals** are specifically recorded — only those recorded approvals apply

### Example Decision Tree — Split Zoning


> **AI Instruction:** For split-zoned parcels, evaluate each geographic portion separately against the zone that applies to that portion. Overlays apply to the entire parcel additively. When in doubt, contact Metro Planning Department (615-862-7190) — split-zoned parcels frequently require clarification.

---

## 18. Assessment Data Quality Notes

### Common Data Integrity Issues

The Tax Assessor's database is the source of truth for property characteristics (lot area, building dimensions, land use code), but it contains inconsistencies. When flagging a property for zoning analysis, be aware of:

| Issue | Impact | Detection | Remediation |
|-------|--------|-----------|-----------|
| **Lot area mismatch** | Property shown as non-compliant due to too-small lot, but actual lot was subdivided/consolidated | Compare assessor lot area to recorded plat; Metro GIS may differ | Request updated survey to confirm true lot boundaries |
| **Obsolete building dimensions** | Structure dimensions in assessor DB reflect original construction, not recent additions | Visual inspection or permit records will show addition; DB shows original footprint only | Review building permits for additions; update assessment via supplemental appraisal request |
| **Missing recent additions** | New structures or major renovations not yet reflected in assessor data | Compare photo records (Google Earth timeline) to assessment data date | New addition = reassessment trigger; verify if reassessment completed |
| **Incorrect structure count** | Assessor shows 1 structure; property has 2 or more buildings | Parcel Viewer photo; physical inspection | Contact assessor to request correction / supplemental appraisal |
| **Land use code misalignment** | LU code does not match site condition (e.g., shows "residential" but property operates as mini storage) | Compare LU code description to actual property use | Report to assessor; may trigger SE violation investigation by Metro Codes |
| **Height recorded incorrectly** | Assessor shows 1-story; structure appears to be 2-3 stories | Google Earth, Street View, or property visit | Contact assessor; building permits may show true height/addition |
| **Parcel boundary errors** | Assessor GIS boundary does not match recorded deed description | Compare deed legal description to Parcel Viewer GIS map | Request correction via assessor department; may require new survey |
| **Split parcel records** | Parcel subdivided years ago but assessor DB still shows as single parcel | Compare property address to plat map; check Register of Deeds | File correction request with assessor; ensure deeds properly recorded |

### Data Governance and Timing

**When is assessment data updated?**
- **New construction:** Reassessment typically triggered within 1 calendar year of completion
- **Renovations / additions:** Supplemental appraisal may lag 6–18 months behind permit issuance
- **Change of use:** Assessor may not update LU code for months or years after use change unless reported
- **Ownership transfer:** Property reassessed at next tax cycle (January 1 following transfer), but data lags by months

**Implication:** A property flagged as a violation based on assessor data may have recently been remedied (addition built to code, use changed to compliant use). Always cross-reference assessment date with property records and recent permits.

### Red Flags in Assessment Data

When evaluating a property, investigate further if:

| Red Flag | Questions to Ask |
|----------|-----------------|
| **LU code does not match parcel zoning** | Is use nonconforming? Has property changed use recently? Is variance/SE on record? |
| **Lot area reported is below minimum for zone** | Was parcel recently subdivided? Is split zoning involved? Has plat been corrected? |
| **Building dimensions seem inconsistent with photos** | Are recent permits showing additions/renovations not yet in assessment? |
| **Multiple structures on lot but only 1 shown in DB** | Are accessory structures recorded separately? Is one a legal accessory dwelling? |
| **Assessment data is >5 years old (stale)** | Request updated appraisal; may reflect outdated conditions |
| **Square footage values are suspiciously low** | Lot area OK, but building footprint too small? May indicate demolished additions or data entry error |

### Requesting Assessment Corrections

**Nashville Tax Assessor:** 
- Phone: 615-862-6390
- Online: Supplement Appraisal form available on Davidson County Assessor website
- Process: Assessor will review; may schedule inspection; supplemental appraisal will update DB
- Timeline: 4–12 weeks typical

**For zoning-related questions (not assessment):**
- Metro Planning Department: 615-862-7190
- Parcel Viewer online: Nashville.gov

---

## 19. Using Building Permits to Confirm Zoning Compliance

### Building Permits as Evidence of Zoning Authority

Before a structure is built (or substantially modified), Nashville requires both:
1. **Zoning Permit** — confirms land use is permitted in the zone and spatial standards (setbacks, height) are met
2. **Building Permit** — confirms structural and safety standards will be followed

The issuance of a **permit is evidence that compliance was assessed and approved at the time of permitting.** However, permits can be issued with conditions or can be issued in error, so permit records are an important **but not conclusive** indicator of compliance.

### Accessing Building Permit Records

**Nashville Metro Codes Department:**
- Online database: CoDesign.com (Nashville Permits portal — searchable by address, permit #, or applicant)
- Phone: 615-862-6350
- In-person: 1801 Dickerson Pike, Nashville, TN 37207

**Key permit metadata to note:**
- **Permit issue date** (when zoning/building permits were issued)
- **Zoning code in effect at time of permitting** (zoning may have changed since)
- **Specific conditions attached** to the permit (e.g., "offset parking entrance to east side")
- **Inspector sign-offs** (indicates which elements were inspected/approved)
- **Certificate of Occupancy** date (when structure was declared ready for use)

### Using Permits to Validate Dimensional Compliance

| Permit Type | What It Shows | Zoning Relevance |
|---|---|---|
| **Zoning Permit** | Lot coverage, setbacks, height, bulk standards reviewed at approval | If permitted at that time, setbacks/height approved as compliant |
| **Footing/Foundation Permit** | Footprint and footing location | Confirms building footprint matches approved zoning plan |
| **General Building Permit** | Dimensions, stories, materials, use classification | Use code must match zoning Land Use Table permission |
| **Electrical, Mechanical, Plumbing** | Confirms structure is being built to plans | Indirect evidence that structure is being built as permitted |
| **Certificate of Occupancy** | Structure is complete and approved for use by specified use category | Use confirmed as compliant as of COO date |

### Permits and Changes-of-Use

A critical timeline issue: **zoning enforcement looks at the zoning in effect at the time a structure is built, not at the time of later use changes.**

**Example:**
- 1985: Building erected under RS10 zoning; warehouse use not permitted in RS10, but property owner obtains SE approval for warehouse
- 2015: Zoning changed; RS10 still does not permit warehouse, but SE still valid
- 2024: Building still operating as warehouse under original 1985 SE approval
- **Assessment:** Property is legally compliant (SE is on record), even though current zoning does not permit warehouse; nonconforming or grandfathered use

**Implication:** Permit records reveal the original zoning authority for a structure. Use that as the reference point, then check whether subsequent zoning changes affected compliance.

### Red Flags in Permit Records

| Red Flag | Investigation |
|---|---|
| **No permit on record for major structure** | Structure may predate permit requirements (pre-1960s) or was built without permit (code violation). May have nonconforming status if use is older than current zoning. |
| **Permit issued, but COO never issued** | Structure was permitted but never completed/occupied. Property may be abandoned or in limbo. |
| **Multiple conflicting permits** | E.g., 1990 permit shows 3-story height; 2005 permit shows 5-story height. Check which was actually built (site inspection or photo progression). |
| **Permit issued for "other" use category** | Use classification vague or nonspecific. May indicate assessor/permit office was uncertain of the use; requires clarification. |
| **Conditions on permit appear unmet** | E.g., permit required "parking offset to rear alley"; photos show parking at street. Likely violation of permit conditions (and underlying zoning). |
| **Permit date predates zoning change by <2 years** | Zoning may have changed after permit issued; use may have become nonconforming. Verify effective date of zone change. |

### Demonstration: Using Permits to Trace Compliance History

**Scenario:** Evaluate a 6-unit apartment building on RS10-zoned land (single/two-family only).

1. **Check zoning:** Current zone is RS10 (multifamily not permitted)
2. **Red flag:** 6 units on single-family land
3. **Check permits:**
   - 1978: Zoning Permit (original construction) — shows zone was RM4 (multifamily, 4 units/acre) at time of build
   - 1978: Building Permit issued; foundation/footing at approx. 12,000 sq ft (meets RM4 requirement for 6-unit building)
   - 1978: Certificate of Occupancy issued for "multifamily residential, 6 units"
   - 1995: Zoning changed; RS10 adopted (multifamily no longer permitted in this district)
4. **Conclusion:** Building was legally permitted under RM4 zoning, which has since been changed. Building is now **LEGALLY NONCONFORMING** — structure and use are protected by nonconformance, even though current zoning does not permit it.

---

## 20. Common Zoning Violation Patterns in Davidson County

### Pattern 1: Undocumented Use Changes

**Description:**  
Property has zoning that permits Use A, but current operation is Use B (not permitted). No variance, SE, or PC approval is on record.

**Red flag indicators:**
- Land Use code changed in recent assessor records but no zoning zoning change
- Building signage / operations suggest commercial use but lot is zoned residential
- Parcel Viewer shows old address/use but site visit reveals different business
- No current business license on file

**Example:** Single-family house (RS5) now operating as 3-unit short-term rental without STRP PC approval (and in an -NS district prohibiting STR)

**Remediation:**  
- Owner must apply for variance, SE, or rezoning
- If no approval is obtained, property is in violation; Metro Codes can require cessation
- New owner should demand legal verification before purchase

### Pattern 2: Dimensional Violations Without Recorded Variance

**Description:**  
Structure does not meet setback, height, or coverage standards, and no variance is recorded. Appears to have been constructed in violation of then-current code.

**Red flags:**
- Building clearly encroaches on side/rear setback line
- Structure taller than district maximum (e.g., 4+ stories in area capped at 3 stories)
- Footprint is 60%+ of lot (exceeding coverage max of 50%)
- No variance in Parcel Viewer records

**Example:** A 45-foot tall building on RS5 lot in a UZO district (capped at 45 ft for residential; building shows 50+ feet)

**Remediation:**
- If structure predates current zoning: Likely nonconforming structure; protect from being forced to demolish, but cannot expand further
- If structure was recently built: Illegal construction; Metro Codes may demand remediation or demolition
- New owner should hire architect/attorney to assess remediation cost before purchase

### Pattern 3: Lot Size Non-Compliance

**Description:**  
Parcel is smaller than minimum lot area required for its zoning district.

**Red flags:**
- Lot area in Parcel Viewer: 3,000 sq ft; zone requires RS5 (5,000 sq ft minimum)
- Property has only 1 street frontage; zone requires frontage on 2 streets
- Lot is landlocked or has irregular shape that prevents building per standards

**Cause:**
- Often results from historical subdivisions before lot-size minimums were enforced
- May reflect tax value preservation by previous owner (kept as nonconforming)

**Status:**
- If lot and use predate current zoning: Legally nonconforming lot (nonconforming structure may be rebuilt but not expanded)
- If lot was recently created by subdivision: Likely violation (non-compliant lot cannot be built on)

**Example:** 3,000-sq-ft residential lot was subdivided in 1920; grandfathered as nonconforming. Cannot add square footage but existing structure is protected.

### Pattern 4: Unpermitted Additions

**Description:**  
New structure or significant expansion built without zoning and/or building permits.

**Red flags:**
- Permit records show original footprint and height; site inspection shows larger building
- Google Earth timeline shows structure appeared in recent years with no permit record
- Owner claims "just a minor deck" but building footprint increased 20%+ from deed survey

**Example:** Single-story house expanded to 2 stories and footprint doubled; no zoning permit issued for height change

**Risk:**
- Metropolitan Codes can issue orders to demolish unpermitted work
- Title clouds develop (lender/buyer won't finance till resolved)
- Unpermitted expansion may push property into violation of coverage, FAR, or density limits

**Remediation:**
- Retroactive permitting (rare, if construction can demonstrate code compliance)
- Demolition of non-compliant portion
- Variance application to legalize existing non-compliant condition (difficult; must show hardship)

### Pattern 5: Overcrowding / Density Violations

**Description:**  
Property zoned for single- or two-family, but evidence suggests more units or occupants living there.

**Red flags:**
- Multiple mailboxes for single-family address
- Street presence: many cars, multiple trash/recycling bins, laundry lines suggest multifamily
- Land Use code changed to "multifamily" but zone still shows "RS5"
- Parcel Viewer photos show building divided into apartments or floor divisions

**Common cause:** Property owner illegally subdivides single-family home into rental units to increase income.

**Example:** RS5 house (1 unit permitted) subdivided into 3 apartments without rezoning

**Legal risk:**
- Metro Codes can issue violation notice; units must be recombined or property rezoned
- Leases for occupied units may be rendered voidable (tenants have diminished possession, potentially)
- Property title becomes cloud until resolved

### Pattern 6: Nonmotorized Vehicle Storage as Principal Use

**Description:**  
Property primarily operates as a vehicle storage facility (boats, RVs, motorcycles, cars) with minimal or no principal use.

**Red flags:**
- Lot is fenced/secured with vehicle inventory visible
- No building structure; only outdoor storage
- Assessor LU code shows "vacant" or "industrial" despite clear vehicle/equipment presence

**Zoning issue:**
- Vehicle storage (unless accessory to a principal permitted use) is typically only permitted in CS, IG, or IWD
- On residential or office zones, vehicle storage is typically not permitted as principal use

**Example:** RS10-zoned lot used for used-car sales / outdoor storage; no showroom or commercial office

**Remediation:** Rezoning to CS or IWD, or cessation of vehicle storage use

### Pattern 7: STRP Violations in -NS Districts

**Description:**  
Short-term rental property operating in a "-NS" (No STRP) zoning district.

**Red flags:**
- Zone shows "-NS" suffix (e.g., MUN-NS, RM9-NS, CL-NS)
- Property appears in online STR rental platforms (Airbnb, VRBO, etc.)
- Neighbors report frequent turnover / transient occupants

**Legal issue:**  
All -NS districts explicitly prohibit both owner-occupied and not-owner-occupied STR. Operating an STR in -NS = clear violation.

**Example:** Duplex zoned RM9-NS; owner rents one unit as monthly residential (permitted) but other unit as 2-week nightly rental (not permitted in -NS)

**Enforcement risk:** Metro Codes actively investigates STRP violations. Fines and cease-and-desist orders are common.

### Pattern 8: Zoning Overlay Non-Compliance

**Description:**  
Property violates overlay district (HPZO, UZO, NCZO) standards even though base zone use is permitted.

**Red flags:**
- **HPZO:** Exterior alteration or addition without visible Preservation Permit (HZC approval)
- **UZO:** Residential structure exceeding 45 ft or 3 stories; parking between building and street; building setback inconsistent with adjacent pre-1950 buildings
- **NCZO:** Structure architectural style/mass violates neighborhood-conservation guidelines
- **Floodplain:** Building finished floor below Base Flood Elevation (BFE)

**Example:** Historic building zoned HPZO; new windows and exterior paint applied without HZC approval = HPZO violation

**Remediation:** Requires after-fact approval or remediation under overlay authority (Historic Commission, NCZO administrator, etc.)

### Pattern 9: Home Occupation Expansion Beyond Scope

**Description:**  
Home-based business (home occupation = PC use in residential zones) operated in violation of conditions.

**Red flags:**
- Customer traffic clearly visible (signs on property, multiple vehicles, drive-through behavior)
- On-site employees beyond owner (cars parked at property during business hours)
- External business signage (violates "no external signage" condition)
- Deliveries/commercial trucks arriving regularly

**Example:** Consulting practice (legitimate home occupation with PC) expanded to 5 employees working in converted garage with commercial signage

**Violation:** Home occupation conditions prohibit employees and signage. This expansion terminates PC compliance.

---

## 21. How Zoning Affects Assessment Ratios

### Assessment Fundamentals

A property's **assessed value** is a percentage of its estimated **market value.** In Tennessee:

- **Assessment ratio target:** 25% of fair market value (per Tennessee State Board of Equalization)
- **How it works:** Assessed value = (Market value estimate) × (0.25) = (Assessed value for tax purposes)
- **Tax owed:** Annually = (Assessed value) × (tax rate in mills)

Example: A house appraised at $400,000 market value → Assessed at $100,000 (25% ratio) → Taxed annually at metro rate (e.g., 8.41 mills = $841/year on that assessed value)

### Zoning Impact on Market Value and Assessment

**Property value is HEAVILY influenced by what zoning permits.** The same physical structure on two adjacent lots may have different market values purely because of zoning differences.

| Zone | Same 10,000 sq ft lot | Typical Market Value Impact | How Zoning Contributes |
|------|---|---|---|
| **RS80 (Rural)** | Single home, no commercial | **$350K – $600K** | Strict residential; limits future development; rural supply constraints |
| **RS10** | Single home, possible duplex | **$450K – $700K** | Slightly denser; adds some strategic value (could become duplex) |
| **RS5** | Single home, suburban density | **$550K – $850K** | Standard suburban; strong residential market; active development |
| **RM9** | Multifamily permitted (9 units/acre) | **$650K – $900K** | Allows denser residential; development potential adds value |
| **MUL** | Mixed-use (shops + residential) | **$800K – $1.2M** | Commercial ground floor; higher density; walkability premium |
| **CS** (Commercial) | Retail/commercial use permitted | **$1.2M – $2M+** | Commercial zoning = high value; development potential |
| **IG** (Industrial) | Heavy manufacturing | **$400K – $700K** | Industrial zoning = specialized buyer pool; lower residential demand |

**Principle:** More permissive zoning = higher market value (generally).

### Zoning and Assessment Ratio Anomalies

**Scenario 1: Undervalued Due to Outdated Zoning**

A parcel zoned RS20 (rural, large lot minimum) but property is surrounded by RM20 (multifamily) development. Assessed value may lag behind market because assessor hasn't updated zoning impact in valuation model.

- **Market signals:** Neighboring multifamily worth $1M+; comparable RS20 lot in similar condition worth $600K
- **Assessment issue:** If assessed at $150K (10% of market), this is below target 25% ratio
- **Remedy:** Appeal assessment; compare to recently sold RM20 properties nearby; assessor may be undervaluing due to stale comp selections

**Scenario 2: Nonconforming Use Discount**

A 10-unit apartment building on RS10-zoned land (single/two-family only). Building is nonconforming and protected, but assessed value may be discounted to account for future loss of use.

- **Market impact:** Building worth $2.5M if permanent (stable commercial asset); worth $1.8M if nonconforming (risk of forced closure if zoning enforced)
- **Assessment:** Assessor may value at $1.8M (reflecting nonconforming risk)
- **Appeal option:** If building predates zoning by 50+ years with zero enforcement activity, argue that nonconforming status is fully stable; seek higher assessed value (closer to $2.5M)

**Scenario 3: Zoning Overlay Premium**

A property in a HPZO (Historic Preservation zoning) or NCZO (Neighborhood Conservation) often carries a **premium** over similar unprotected properties because:
- Historic designation makes property eligible for historic tax credits and grants
- NCZO stability = lower future redevelopment risk
- Buyers may pay premium for character preservation guarantee

**Assessment approach:** Assessor should apply HPZO/NCZO premium comparables when valuing similar historic-overlaid properties.

### Development Potential and Assessed vs. Market Value

**Key insight:** Zoning creates **development potential** that may not be immediately reflected in assessed value if property is currently underdeveloped.

**Example:**
- 2-acre parcel zoned MUI (Mixed-Use Intensive); current use = single-family house
- Market value reflects *potential* for dense mixed-use development (e.g., $5M for development site)
- Current assessed value may reflect only current house value ($500K) if assessor hasn't re-valued for development potential
- **Opportunity for owner:** Appeal assessment, present comparable sales of development-ready MUI parcels; argue assessed value should reflect development potential, not just current use

### Appeal Strategy: Zoning-Based Arguments

When appealing property assessment in Davidson County (Tax Assessor, 615-862-6390), provide:

1. **Zoning comparison:** "My RS5 lot should be compared to similar RS5 lots sold in past 12 months, not to RM9 multifamily properties"
2. **Density/development potential:** "My lot's zoning permits X density; sold comparables are zoned for Y density — this affects value"
3. **Overlay impact:** "My property is in HPZO, which adds historic premium; comparables I was compared to are not in HPZO — not comparable"
4. **Nonconforming discount:** "My use is nonconforming; assessor should apply stability discount / comparables should be other nonconforming properties, not standard-zone properties"
5. **Zoning change pending:** "District is being rezoned from RS10 to RS5; this affects development potential; assess at current zoning until change is effective"

**Documentation to support appeal:**
- Recent sales of similarly zoned/overlaid parcels (appraisal company databases or real estate websites)
- Market analysis showing zoning impact on value
- Any recorded variance/SE approvals affecting development potential
- Professional appraisal from real estate appraiser (costly, but persuasive in appeal)

> **AI Instruction for Chat:** When analyzing a potential appeal candidate, always consider zoning as a value factor:
> - If assessed value is significantly below market for the zoning, zoning-based appeal may succeed
> - If assessed value ignores development potential zoning permits, market/assessment gap suggests successful appeal
> - If overlay status (HPZO, NCZO) affects value, check whether comparables accounted for that premium

---


## 22. AI Compliance Evaluation Framework — Nashville

### Input Data Required

To evaluate a Nashville property:

- [ ] Property address or Parcel ID (APN)
- [ ] Current zoning designation from Metro Parcel Viewer
- [ ] All overlay districts shown as Current (UZO, NCZO, HPZO, UDO, SP)
- [ ] If SP: adopting ordinance number and its terms
- [ ] Actual current land use(s) on the property
- [ ] Lot area (square feet)
- [ ] Total gross floor area of all structures (all floors)
- [ ] Building footprint area (square feet)
- [ ] Total impervious surface area (roofs + all paved/hardscaped areas)
- [ ] Structure height (stories and/or feet)
- [ ] Number and type of dwelling units
- [ ] Number of parking spaces
- [ ] All setback measurements (street/front, rear, both sides)
- [ ] Year built / when current use was established
- [ ] Any recorded BZA approvals (variances, special exceptions)

---

### Evaluation Decision Tree

```
1. IDENTIFY ZONING
   ├── Is the base zone SP? → Read the specific plan ordinance; apply its standards
   ├── Is the base zone DTC? → Apply Chapter 17.37 Downtown Code (flag for DTC-specific review)
   └── Otherwise → Apply relevant bulk table (17.12.020A, B, C, or D)

2. CHECK OVERLAYS
   ├── UZO present? → Apply UZO height cap (45 ft residential), contextual setbacks, parking placement, alley access rules
   ├── HPZO present? → Verify Preservation Permit for any exterior alterations
   ├── NCZO present? → Verify compliance with neighborhood-specific conservation guidelines
   ├── UDO present? → Apply UDO-specific design standards
   └── MDHA present? → Review MDHA redevelopment plan standards

3. EVALUATE LAND USE
   ├── Find the use in the District Land Use Table (17.08.030) for the district
   ├── P (Permitted) → Proceed to Step 4
   ├── PC (Permitted with Conditions) → Are conditions met? YES → Proceed; NO → VIOLATION
   ├── SE (Special Exception) → Is BZA approval on record? YES → Proceed; NO → VIOLATION
   ├── A (Accessory) → Is there a valid principal use? YES → Proceed; NO → VIOLATION
   ├── O (Overlay) → Is the required overlay present and activated? YES → Proceed; NO → VIOLATION
   └── Blank / Not Listed → Is use legally nonconforming (predates current zoning)?
         ├── YES → LEGALLY NONCONFORMING
         └── NO → VIOLATION

4. EVALUATE DIMENSIONAL COMPLIANCE
   Using the applicable bulk table (17.12.020A, B, C, or D):
   
   For Single/Two-Family (Table 17.12.020A):
   - [ ] Lot area ≥ minimum for district?
   - [ ] Building coverage (footprint ÷ lot) ≤ maximum?
   - [ ] Rear setback ≥ minimum?
   - [ ] Side setback(s) ≥ minimum?
   - [ ] Height ≤ 3 stories? (in UZO: also ≤ 45 ft?)
   - [ ] Accessory structure(s) within height and coverage limits?
   
   For Multifamily / Non-residential in residential districts (Table 17.12.020B):
   - [ ] FAR ≤ maximum?
   - [ ] ISR ≤ maximum?
   - [ ] Density (units/acre) ≤ maximum?
   - [ ] Rear setback ≥ minimum?
   - [ ] Side setback(s) ≥ minimum?
   - [ ] Height ≤ maximum at setback line?
   - [ ] Does not penetrate height control plane?
   
   For commercial / mixed-use / office / industrial (Table 17.12.020C):
   - [ ] FAR ≤ maximum?
   - [ ] ISR ≤ maximum?
   - [ ] Rear setback ≥ minimum?
   - [ ] Height ≤ maximum?
   
   For alternative (-A) districts (Table 17.12.020D):
   - [ ] Building located within build-to zone?
   - [ ] Primary entrance on street-facing façade?
   - [ ] Glazing meets minimum percentages?
   - [ ] Step-back applied at specified height?
   - [ ] Parking at side/rear only?

5. EVALUATE STREET SETBACKS (17.12.030)
   - [ ] Identify street classification (minor-local, local, arterial, etc.)
   - [ ] Is the street setback ≥ the required distance from Table 17.12.030A or B?
   - [ ] If in UZO and standard setback not met → does contextual setback analysis apply?
   - [ ] Are any encroachments within permitted categories (Section 17.12.040)?

6. EVALUATE STRP STATUS (if applicable)
   - [ ] Is the district an -NS district? If YES and STR operates → VIOLATION
   - [ ] Is STRP-Owner-Occupied? → Verify Accessory status
   - [ ] Is STRP-Not-Owner-Occupied? → Verify PC approval on record
   - [ ] Does STRP have ≤ 4 sleeping rooms?

7. DETERMINE FINAL STATUS
```

---

### Output Classification

| Status | Meaning | Recommended Action |
|---|---|---|
| **COMPLIANT** | All use and dimensional standards are met; all overlay requirements satisfied | No action required |
| **LIKELY COMPLIANT** | All indicators appear compliant but data gaps exist | Request missing data; verify with Metro Planning Parcel Viewer |
| **LEGALLY NONCONFORMING** | Noncompliant use or structure predates current zoning; appears lawfully protected | Document nonconforming status; monitor for change of use or expansion |
| **CONDITIONALLY COMPLIANT** | Compliant only if PC conditions or SE/BZA approval can be confirmed | Verify recorded approvals with Metro Planning or Board of Zoning Appeals |
| **POTENTIAL VIOLATION** | One or more indicators suggest noncompliance; further investigation needed | Flag for human review; do not make final determination without verification |
| **VIOLATION — HIGH CONFIDENCE** | Clear, documented noncompliance with no apparent legal protection | Recommend remediation, variance application, or rezoning as appropriate |
| **REQUIRES DTC ANALYSIS** | Property is in the DTC district — standards in this document do not apply | Evaluate under Chapter 17.37 Downtown Code |
| **REQUIRES SP REVIEW** | Property is zoned SP — must read specific plan ordinance | Locate adopting ordinance via Parcel Viewer; apply SP-specific standards |
| **INSUFFICIENT DATA** | Too little information to evaluate | Request additional property data |

---

### Key Nashville Resources for Verification

| Resource | Use | Contact |
|---|---|---|
| Metro Parcel Viewer | Look up zoning, overlays, parcel data | Nashville.gov → Planning |
| District Land Use Table (17.08.030) | Verify use permissions | Nashville.gov Metro Code |
| District Bulk Tables (17.12.020) | Verify dimensional standards | Nashville.gov Metro Code |
| Street Setbacks (17.12.030) | Verify setback requirements | Nashville.gov Metro Code |
| Metro Historic Zoning Commission | HPZO / NCZO compliance, Preservation Permits | 615-862-7970 |
| Metro Planning Department | General zoning questions, SP districts, UDOs | planningstaff@nashville.gov / 615-862-7190 |
| Downtown Code questions | DTC compliance | designstudio@nashville.gov / Eric Hammer 615-862-7165 |
| MDHA Development Office | Redevelopment district properties | 615-252-3750 |
| Board of Zoning Appeals | Verify SE approvals, variances | Metro Codes |

---

### Caveats and Limitations

> **Critical:** This knowledge base reflects Nashville's Title 17 zoning code as of April 2026. Nashville's zoning code is actively amended by Metro Council — individual ordinance amendments may change specific district standards, use permissions, or overlay boundaries after this document's compilation date. For legally authoritative determinations, always consult the current Metro Code and verify with the Metro Planning Department. This knowledge base is intended to support preliminary AI-assisted analysis only and does not constitute legal advice. High-stakes decisions (purchases, construction, financing) require review by a licensed land use attorney or professional planner.

---

*Jurisdiction: Metropolitan Nashville and Davidson County, Tennessee*  
*Primary Authority: Title 17 Metro Code of Ordinances*  
*Compiled: April 2026 | Designed for expansion to additional jurisdictions*
