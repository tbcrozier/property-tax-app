import json
import logging
import os
import re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import chat_completion
from app.services.embed_service import embed_document, search_documents
from app.services.sql_service import _COL_FIXES
from app.utils.code_executor import SQLSafetyError, execute_python_on_df

logger = logging.getLogger(__name__)

DB_SCHEMA = """
DATABASE SCHEMA — Davidson County Property Tax (PostgreSQL + PostGIS + pgvector)

TABLE: parcels
  par_id          TEXT PK       — unique parcel identifier
  prop_addr       TEXT          — street address
  prop_city       TEXT
  prop_zip        TEXT          — 5-digit ZIP
  owner_name      TEXT
  lu_code         TEXT          — land use code (NUMERIC): 010-019=Residential, 020-069=Commercial, 070-079=Industrial/Warehouse, 080-089=Agricultural/Rural
  lu_desc         TEXT          — land use description
  zoning          TEXT          — zoning code
  nbhd            TEXT          — neighborhood code
  acres           FLOAT         — parcel size in acres
  land_appr       FLOAT         — appraised land value
  impr_appr       FLOAT         — appraised improvement value
  totl_appr       FLOAT         — total appraised value (land + improvements)
  land_assd       FLOAT         — assessed land value (25% of appr for commercial)
  impr_assd       FLOAT         — assessed improvement value
  totl_assd       FLOAT         — total assessed value
  sale_price      FLOAT         — most recent sale price
  sale_date       TEXT          — most recent sale date
  tax_dist        TEXT          — tax district
  year_built      INT
  bldg_sqft       FLOAT
  num_beds        INT
  num_baths       FLOAT
  location        GEOMETRY(POINT, 4326)

KEY FORMULA: value_per_acre = totl_appr / NULLIF(acres, 0)

TABLE: parcel_signals  (pre-computed at session start)
  par_id                  TEXT PK
  z_score_zip             FLOAT   — how many std devs above zip+lu peers
  pct_above_zip_median    FLOAT   — % above zip+lu median (0.20 = 20% above)
  pct_above_lu_median     FLOAT   — % above lu-only median
  zip_peer_count          INT     — number of comparable parcels in same zip+lu
  assessment_to_sale_ratio FLOAT  — totl_appr / sale_price (>1.0 means over-assessed)
  assessed_above_sale     BOOL    — TRUE if assessed > sale price
  zoning_lu_mismatch      BOOL    — TRUE if land use and zoning codes conflict
  appeal_score            FLOAT   — composite 0-100 appeal strength score (higher = stronger appeal case)
                                    Formula: LEAST(100, z_score_zip*20 + pct_above_zip_median*30 + pct_above_lu_median*20
                                             + (assessed_above_sale ? 15 : 0) + (zoning_lu_mismatch ? 15 : 0))
                                    z_score_zip: standard deviations above ZIP+lu_code peer group (per value/acre)
                                    pct_above_zip_median: fraction above ZIP+lu median (0.20 = 20% above)
                                    pct_above_lu_median: fraction above county-wide lu_code median
  recommendation          TEXT    — STRONG_CANDIDATE: z_score>=2.0 AND pct_above_zip>=0.20, or z_score>=1.5 AND pct_above_zip>=0.30
                                    MODERATE_CANDIDATE: z_score>=1.5 OR pct_above_zip>=0.15
                                    REVIEW_ZONING: zoning_lu_mismatch=TRUE but not statistically over-assessed
                                    NORMAL: no significant over-assessment detected

APPEAL QUERY PATTERNS (use these for any "appeal", "over-assessed", "should appeal" questions):
  — Top properties to appeal (highest appeal score):
      SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_code, p.totl_appr, p.sale_price,
             ps.appeal_score, ps.recommendation, ps.z_score_zip, ps.pct_above_zip_median,
             ps.assessment_to_sale_ratio
      FROM parcels p JOIN parcel_signals ps ON ps.par_id = p.par_id
      WHERE ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
      ORDER BY ps.appeal_score DESC LIMIT 10
  — Only strong candidates:  WHERE ps.recommendation = 'STRONG_CANDIDATE'
  — Over-assessed vs sale:   WHERE ps.assessed_above_sale = TRUE AND p.sale_price > 0

TABLE: parcel_rail_proximity  (pre-computed — run POST /admin/compute-enrichments)
  par_id                TEXT PK — matches parcels.par_id
  nearest_rail_owner    TEXT    — railroad company name (CSX, NS, etc.)
  passenger_rail        BOOL    — TRUE if used for passenger service
  rail_tracks           INT     — number of tracks
  distance_m            FLOAT   — distance in meters to nearest rail line
  within_100m           BOOL    — TRUE if within 100m of rail
  within_250m           BOOL    — TRUE if within 250m of rail
  within_500m           BOOL    — TRUE if within 500m of rail
  within_1000m          BOOL    — TRUE if within 1000m of rail

TABLE: parcel_flood_zone  (pre-computed — run POST /admin/compute-enrichments)
  par_id                TEXT PK — matches parcels.par_id
  flood_zone            TEXT    — FEMA zone code: A, AE, X, V, VE, D, or NULL if not in zone
  sfha_tf               BOOL    — TRUE = Special Flood Hazard Area (high risk)
  zone_description      TEXT    — human-readable zone description
  flood_risk_category   TEXT    — HIGH_RISK_COASTAL | HIGH_RISK | MODERATE_RISK | MINIMAL_RISK | UNDETERMINED | NOT_IN_FLOOD_ZONE
  in_flood_zone         BOOL    — TRUE if parcel intersects any flood zone

VIEW: v_assessment_sale_ratio  (auto-created by compute-enrichments)
  par_id, prop_addr, prop_zip, lu_code, lu_desc
  totl_appr, sale_price, sale_date
  assessment_ratio      FLOAT   — totl_appr / sale_price (>1.15 = OVER_ASSESSED)
  assessment_excess     FLOAT   — dollar amount over sale price
  ratio_flag            TEXT    — OVER_ASSESSED | UNDER_ASSESSED | FAIR
  potential_annual_savings FLOAT — estimated tax savings if reduced to sale price

VIEW: v_condo_building_stats  (auto-created by compute-enrichments)
  par_id, prop_addr, prop_zip, lu_desc, totl_appr, building_key
  building_unit_count   INT
  building_median       FLOAT   — median appraisal for this building
  building_avg          FLOAT
  building_z_score      FLOAT   — how far this unit is from building average
  pct_from_building_median FLOAT
  building_assessment_flag TEXT — HIGH_OUTLIER | ABOVE_AVERAGE | NORMAL | BELOW_AVERAGE | LOW_OUTLIER
  potential_annual_savings FLOAT

TABLE: building_characteristics
  apn             TEXT   — parcel ID (matches par_id)
  finished_area   FLOAT  — finished square footage
  year_built      INT
  structure_type  TEXT
  exterior        TEXT

TABLE: building_permits
  permit_number       TEXT
  parcel              TEXT  — matches par_id
  permit_type         TEXT
  description         TEXT
  date_issued         TEXT
  construction_cost   FLOAT
  location            GEOMETRY(POINT, 4326)

TABLE: cell_towers
  company     TEXT
  fcc_site_id TEXT
  height      FLOAT
  tower_type  TEXT
  location    GEOMETRY(POINT, 4326)

TABLE: flood_zones
  flood_zone        TEXT
  sfha_tf           BOOL  — TRUE = Special Flood Hazard Area
  zone_description  TEXT
  shape_area        FLOAT
  geom              GEOMETRY(MULTIPOLYGON, 4326)

TABLE: zoning_districts
  zoning_code     TEXT
  zoning_district TEXT
  description     TEXT
  geom            GEOMETRY(MULTIPOLYGON, 4326)

TABLE: rail_lines
  owner           TEXT
  passenger_rail  BOOL
  tracks          INT
  miles           FLOAT
  geom            GEOMETRY(MULTILINESTRING, 4326)

TABLE: public_schools
  ncessch     TEXT    — NCES school ID (links to school_poverty_estimates.ncessch)
  leaid       TEXT    — school district ID
  name        TEXT    — school name
  street      TEXT
  city        TEXT
  state       TEXT
  zip         TEXT
  cnty        TEXT    — county FIPS (47037 = Davidson County)
  locale      TEXT    — urbanicity code
  school_year TEXT
  location    GEOMETRY(POINT, 4326)

TABLE: postsecondary_schools
  unitid      TEXT    — IPEDS institution ID
  name        TEXT
  street, city, state, zip
  cnty        TEXT
  locale      TEXT
  school_year TEXT
  location    GEOMETRY(POINT, 4326)

TABLE: private_schools
  ppin        TEXT    — private school ID
  name        TEXT
  street, city, state, zip
  cnty        TEXT
  locale      TEXT
  school_year TEXT
  location    GEOMETRY(POINT, 4326)

TABLE: school_poverty_estimates
  ncessch     TEXT    — links to public_schools.ncessch
  leaid       TEXT
  name        TEXT
  ipr_est     INT     — income-to-poverty ratio (100=at poverty, 200=2x poverty, 400+=affluent)
  ipr_se      INT     — standard error of estimate
  school_year TEXT
  location    GEOMETRY(POINT, 4326)

USEFUL JOIN: public_schools ps JOIN school_poverty_estimates spe ON spe.ncessch = ps.ncessch
NOTE: ipr_est < 200 = high poverty neighborhood; ipr_est > 400 = affluent neighborhood

TABLE: correctional_facilities
  name        TEXT    — facility name
  address     TEXT
  city        TEXT
  state       TEXT
  zipcode     TEXT
  fcode       INT     — feature code (facility subtype)
  admin_type  INT     — 1=Federal, 2=Tribal, 3=State, 4=Regional, 5=County, 6=Municipal, 7=Private
  location    GEOMETRY(POINT, 4326)

NOTE: admin_type 3=State prison, 5=County jail, 7=Private prison

ZONING MISMATCH INTERPRETATION:
  zoning_lu_mismatch = TRUE is a pre-computed flag — trust it, do not re-evaluate it.
  To explain a mismatch, JOIN zoning_districts to get the official zoning_district and description.
  NOTE: zoning codes may have suffixes like CS-NS, RS10-A — use SPLIT_PART to match the base code.
  Example JOIN: LEFT JOIN zoning_districts zd ON zd.zoning_code = SPLIT_PART(p.zoning, '-', 1)

USEFUL PATTERNS:
- value_per_acre = totl_appr / NULLIF(acres, 0)
- Over-assessed vs sale: totl_appr > sale_price AND sale_price > 0
- Join building_characteristics: ON bc.apn = p.par_id
- Pre-computed scores: JOIN parcel_signals ps ON ps.par_id = p.par_id
- Top appeal candidates: ORDER BY ps.appeal_score DESC WHERE ps.recommendation IN ('STRONG_CANDIDATE','MODERATE_CANDIDATE')
- Miszoned parcels: WHERE ps.zoning_lu_mismatch = TRUE
- Over-assessed: WHERE ps.assessed_above_sale = TRUE
- Rail proximity: JOIN parcel_rail_proximity rp ON rp.par_id = p.par_id WHERE rp.within_500m = TRUE
- Flood zone: JOIN parcel_flood_zone pfz ON pfz.par_id = p.par_id WHERE pfz.in_flood_zone = TRUE
- Assessment vs sale: SELECT * FROM v_assessment_sale_ratio WHERE ratio_flag = 'OVER_ASSESSED'
- Condo outliers: SELECT * FROM v_condo_building_stats WHERE building_assessment_flag = 'HIGH_OUTLIER'

CRITICAL — peer comparison metrics are PRE-COMPUTED in parcel_signals:
  Use ps.z_score_zip, ps.pct_above_zip_median, ps.appeal_score — no window functions needed.
  NEVER use PERCENTILE_CONT(...) WITHIN GROUP (...) OVER (PARTITION BY ...) —
  PostgreSQL does NOT support OVER() on ordered-set aggregates. It will throw an error.
  NEVER use CTEs for peer stats — parcel_signals already has everything pre-computed.
"""

SYSTEM_PROMPT_BASE = f"""{DB_SCHEMA}

You are an expert property tax analyst for Davidson County, Nashville TN.
Always ground your answers in actual data from the database.
When you find anomalies, explain WHY they are anomalous with specific numbers.
Use parcel_signals table for fast pre-computed scores when doing large scans.
"""

REACT_TOOL_INSTRUCTIONS = """
## HOW TO USE TOOLS

To use a tool, respond with EXACTLY this format (no code fences, no extra text before Action):

Thought: <your reasoning about what to do next>
Action: <tool_name>
Action Input: <JSON object with arguments>

Available tools:
1. execute_sql — Execute a SELECT SQL query. Args: {"query": "SELECT ..."}
2. detect_anomalies — Run IsolationForest anomaly detection. Args: {"lu_code": "R" or null, "prop_zip": "37206" or null, "top_n": 20}
3. run_python — Run Python on the last SQL result (variable: df). Args: {"code": "print(df.head())"}
4. search_docs — Search the knowledge base for domain context. Args: {"query": "Nashville zoning codes residential"}

WHEN TO USE search_docs:
- Call it BEFORE writing SQL for questions about zoning, land use codes, valuation
  thresholds, appeal scores, flood zones, or any domain term you are unsure about.
- Call it AFTER getting SQL results when you need to interpret lu_code or zoning
  values to explain why a property is anomalous or miszoned.
- You can call it multiple times with different queries during the same investigation.

GOOD INVESTIGATION PATTERN:
  1. search_docs → understand the domain (zoning rules, what codes mean)
  2. execute_sql → get the actual data
  3. search_docs again (optional) → look up specific codes from step 2 results
  4. Final Answer → grounded in both data and domain knowledge

After each Observation (tool result), continue with another Thought/Action or give your final answer.
When finished, respond with EXACTLY:

Final Answer: <your complete, data-grounded analysis>

FINAL ANSWER RULES:
- Return EXACTLY the number of results the user asked for (e.g. "top 5" → show 5, not 10)
- For each result, explain in plain English WHY it qualifies — what is the specific conflict or anomaly
- Use lu_desc and zoning to explain mismatches (e.g. "Warehouse/distribution [lu_code 077] is zoned CS
  (commercial strip) — industrial use in a commercial zone")
- NEVER invent parcel IDs, addresses, or values — use only data from Observations
- NEVER describe what the table columns mean — just answer the question with the data
"""


def _parse_react_response(content: str) -> tuple[str | None, str | None, dict]:
    """
    Parse a ReAct-style response.
    Returns (action_name, final_answer, args).
    Exactly one of (action_name, final_answer) will be non-None.

    Action takes precedence over Final Answer when both appear in the same response.
    Models sometimes simulate tool execution (write Action + fake results + Final Answer
    all in one turn). We must intercept the Action and actually execute it.
    """
    fa_match = re.search(r"Final Answer:\s*(.+)", content, re.DOTALL | re.IGNORECASE)
    action_match = re.search(r"\*{0,2}Action:\*{0,2}\s*(\w+)", content, re.IGNORECASE)

    # If Action appears BEFORE Final Answer (or Final Answer is absent), execute the action.
    # This handles the "simulated tool call" pattern where the model writes both.
    if action_match:
        fa_pos = fa_match.start() if fa_match else len(content)
        if action_match.start() < fa_pos:
            # Action comes first — execute it, ignore anything after
            action_match = action_match  # use below
            fa_match = None  # suppress the Final Answer

    if fa_match and not action_match:
        return None, fa_match.group(1).strip(), {}

    # Look for Action:
    if not action_match:
        # No structured action found.
        # Only treat as final answer if content doesn't look like planning text.
        # Planning text ("Thought Process:", "I will run a SQL query...", etc.)
        # should NOT be returned as a final answer — the loop should continue.
        _PLANNING_MARKERS = (
            "thought process",
            "to begin the analysis",
            "i will run a sql query",
            "i'll run a sql",
            "once i have executed",
            "the specific query depends",
            "i'll query the database",
            "i need to",
            "let me start",
            "let me run",
        )
        stripped_lower = content.strip().lower()
        is_planning = any(stripped_lower.startswith(m) for m in _PLANNING_MARKERS) or \
                      any(m in stripped_lower[:150] for m in _PLANNING_MARKERS)
        if is_planning:
            return None, None, {}  # No action, no final answer — loop continues
        # Looks like real prose — treat as final answer
        return None, content.strip(), {}

    action_name = action_match.group(1).strip()

    # Parse Action Input — try JSON first, then SQL code block fallback
    args: dict = {}
    input_match = re.search(r"\*{0,2}Action Input:\*{0,2}\s*(\{.*?\})", content, re.DOTALL | re.IGNORECASE)
    if input_match:
        try:
            args = json.loads(input_match.group(1))
        except json.JSONDecodeError:
            args = {}

    # Fallback: model wrote SQL in a ```sql ... ``` block instead of JSON
    # e.g. "Action: execute_sql\n```sql\nSELECT ...\n```"
    if not args and action_name in ("execute_sql", "run_python"):
        code_match = re.search(r"```(?:sql|python)?\s*\n(.*?)```", content, re.DOTALL | re.IGNORECASE)
        if code_match:
            key = "query" if action_name == "execute_sql" else "code"
            args = {key: code_match.group(1).strip()}

    return action_name, None, args


@dataclass
class AnalystState:
    last_df: pd.DataFrame | None = None
    sql_history: list[str] = field(default_factory=list)
    steps: int = 0


# ── Keyword SQL bootstrap helpers ────────────────────────────────────────────
# Shared by both streaming (/analyst/ask) and non-streaming (/analyst/report)
# paths. Defined here to avoid circular imports — report_service imports these.

def _extract_limit(question: str, default: int = 10) -> int:
    """Parse an explicit result count from the question text (e.g. 'top 5' → 5)."""
    m = re.search(r'\b(?:top\s+|show\s+me\s+)?(\d+)\b', question, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 100:
            return n
    return default


_KEYWORD_QUERIES: list[tuple[list[str], str]] = [
    # ── Zoning / land-use mismatch ──────────────────────────────────────────
    (
        [
            "miszoned", "mis zoned", "mismatch", "zoning conflict", "wrong zone",
            "zoning issue", "zoning mismatch", "land use conflict", "wrong zoning",
            "bad zoning", "zoning problem",
        ],
        """SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_code, p.lu_desc, p.zoning,
                  zd.zoning_district, zd.description AS zoning_description,
                  CASE
                    WHEN p.lu_code BETWEEN '070' AND '079' AND zd.zoning_district = 'Commercial'
                      THEN 'Industrial use (' || p.lu_desc || ', lu_code ' || p.lu_code || ') placed in ' || zd.description || ' (' || p.zoning || ') zoning — industrial operations are not a permitted primary use in commercial districts'
                    WHEN p.lu_code BETWEEN '020' AND '069' AND zd.zoning_district = 'Residential'
                      THEN 'Commercial use (' || p.lu_desc || ', lu_code ' || p.lu_code || ') placed in ' || zd.description || ' (' || p.zoning || ') zoning — commercial activity is not permitted in residential districts'
                    WHEN p.lu_code BETWEEN '010' AND '019' AND zd.zoning_district NOT IN ('Residential', 'Agricultural')
                      THEN 'Residential use (' || p.lu_desc || ', lu_code ' || p.lu_code || ') placed in ' || zd.description || ' (' || p.zoning || ') zoning — residential occupancy is not the primary permitted use here'
                    ELSE p.lu_desc || ' (lu_code ' || p.lu_code || ') conflicts with ' || COALESCE(zd.description, p.zoning) || ' zoning'
                  END AS mismatch_reason,
                  ps.appeal_score, ps.recommendation, p.totl_appr
           FROM parcels p
           JOIN parcel_signals ps ON ps.par_id = p.par_id
           LEFT JOIN zoning_districts zd ON zd.zoning_code = SPLIT_PART(p.zoning, '-', 1)
           WHERE ps.zoning_lu_mismatch = TRUE
           ORDER BY ps.appeal_score DESC
           LIMIT {limit}"""
    ),
    # ── Over/mis-assessed (any phrasing) ────────────────────────────────────
    # NOTE: "mis assessed" / "misassessed" are caught here, NOT in the zoning bucket.
    # LEFT JOINs flood + rail so the LLM can flag those as additional devaluing factors.
    (
        [
            "appeal", "over-assessed", "over assessed", "should appeal",
            "strong candidate", "appeal candidate",
            "mis assessed", "misassessed", "mis-assessed",
            "over appraised", "over-appraised", "overassessed", "overappraised",
            "top properties", "highest appeal", "best appeal", "worst assessment",
            "most over", "most likely to appeal", "appeal score",
            "assessment score", "anomaly score", "score rating",
            "assessment issue", "assessment problem", "assessment error",
        ],
        """SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_code, p.lu_desc, p.zoning,
                  p.totl_appr, p.sale_price,
                  ps.appeal_score, ps.recommendation,
                  ps.z_score_zip, ps.pct_above_zip_median,
                  ps.assessment_to_sale_ratio, ps.assessed_above_sale,
                  ps.zoning_lu_mismatch, ps.pct_above_lu_median,
                  pfz.in_flood_zone, pfz.flood_zone, pfz.flood_risk_category,
                  rp.within_500m AS near_rail, rp.distance_m AS rail_distance_m,
                  rp.nearest_rail_owner
           FROM parcels p
           JOIN parcel_signals ps ON ps.par_id = p.par_id
           LEFT JOIN parcel_flood_zone pfz ON pfz.par_id = p.par_id
           LEFT JOIN parcel_rail_proximity rp ON rp.par_id = p.par_id
           WHERE ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
           ORDER BY ps.appeal_score DESC
           LIMIT {limit}"""
    ),
    # ── Flood zone ───────────────────────────────────────────────────────────
    (
        ["flood", "flood zone", "sfha", "fema", "flood risk", "floodplain", "flood plain"],
        """SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_desc, p.totl_appr,
                  pfz.flood_zone, pfz.flood_risk_category, pfz.sfha_tf,
                  ps.appeal_score, ps.recommendation
           FROM parcels p
           JOIN parcel_signals ps ON ps.par_id = p.par_id
           JOIN parcel_flood_zone pfz ON pfz.par_id = p.par_id
           WHERE pfz.in_flood_zone = TRUE
             AND ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
           ORDER BY ps.appeal_score DESC
           LIMIT {limit}"""
    ),
    # ── Rail proximity ───────────────────────────────────────────────────────
    (
        ["rail", "railroad", "train", "near rail", "near track", "railway"],
        """SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_desc, p.totl_appr,
                  rp.distance_m, rp.nearest_rail_owner, rp.passenger_rail,
                  ps.appeal_score, ps.recommendation
           FROM parcels p
           JOIN parcel_signals ps ON ps.par_id = p.par_id
           JOIN parcel_rail_proximity rp ON rp.par_id = p.par_id
           WHERE rp.within_500m = TRUE
             AND ps.recommendation IN ('STRONG_CANDIDATE', 'MODERATE_CANDIDATE')
           ORDER BY rp.distance_m
           LIMIT {limit}"""
    ),
    # ── Condo outliers ───────────────────────────────────────────────────────
    (
        ["condo", "condominium", "within building", "same building", "building peers", "unit"],
        """SELECT par_id, prop_addr, prop_zip, totl_appr,
                  building_unit_count, building_median, building_z_score,
                  pct_from_building_median, building_assessment_flag,
                  potential_annual_savings
           FROM v_condo_building_stats
           WHERE building_assessment_flag IN ('HIGH_OUTLIER', 'ABOVE_AVERAGE')
           ORDER BY building_z_score DESC
           LIMIT {limit}"""
    ),
    # ── Assessment vs sale price ─────────────────────────────────────────────
    (
        [
            "sale price", "over sale", "assessment ratio", "sold for",
            "sold recently", "recent sale", "below sale", "above sale",
        ],
        """SELECT par_id, prop_addr, prop_zip, lu_desc,
                  totl_appr, sale_price, assessment_ratio,
                  assessment_excess, potential_annual_savings, ratio_flag
           FROM v_assessment_sale_ratio
           WHERE ratio_flag = 'OVER_ASSESSED'
           ORDER BY assessment_ratio DESC
           LIMIT {limit}"""
    ),
]


async def _keyword_sql_bootstrap(
    db: AsyncSession, question: str, state: "AnalystState"
) -> str | None:
    """
    Check if the question matches a known pattern and pre-execute a targeted SQL query.
    Returns the formatted result string (same format as _tool_execute_sql), or None.
    """
    q_lower = question.lower()
    limit = _extract_limit(question)

    for keywords, sql_template in _KEYWORD_QUERIES:
        if any(kw in q_lower for kw in keywords):
            sql = sql_template.format(limit=limit)
            logger.info("[BOOTSTRAP] Matched keyword pattern → running pre-built SQL (LIMIT %d)", limit)
            logger.info("[BOOTSTRAP] SQL: %s", sql.strip()[:300])
            result = await _tool_execute_sql(db, sql, state)
            logger.info("[BOOTSTRAP] Result: %d rows", len(state.last_df) if state.last_df is not None else 0)
            return result

    return None


def _build_bootstrap_seed_message(question: str, bootstrap_result: str, row_count: int) -> str:
    """
    Generate a type-aware seed message for a bootstrap SQL result.
    Different question types need different formatting instructions.
    """
    q_lower = question.lower()

    if any(kw in q_lower for kw in ["miszoned", "mis zoned", "mismatch", "zoning conflict", "wrong zone", "zoning issue"]):
        return (
            f"Query results ({row_count} rows):\n\n{bootstrap_result}\n\n"
            f"CRITICAL CONTEXT: Davidson County lu_codes are NUMERIC assessor classifications:\n"
            f"  070-079 = Industrial/Warehouse (regardless of what the property name sounds like)\n"
            f"  020-069 = Commercial\n"
            f"  010-019 = Residential\n"
            f"A property with lu_code 078 (OPEN STORAGE) IS classified as industrial by the assessor.\n"
            f"The `mismatch_reason` column contains the pre-computed, authoritative explanation.\n\n"
            f"Write your Final Answer as a numbered list. For each property:\n"
            f"1. Address and ZIP\n"
            f"2. Land use: lu_desc (lu_code NUMBER) — always include the numeric lu_code\n"
            f"3. Zoning: zoning code (zoning_district — zoning_description)\n"
            f"4. Why miszoned: copy the mismatch_reason value WORD FOR WORD — do not paraphrase\n\n"
            f"Return EXACTLY {row_count} properties. Do NOT add interpretation beyond mismatch_reason.\n\n"
            f"Final Answer:"
        )
    elif any(kw in q_lower for kw in [
        "appeal", "over-assessed", "over assessed", "should appeal", "strong candidate",
        "mis assessed", "misassessed", "mis-assessed",
        "over appraised", "over-appraised", "overassessed", "overappraised",
        "top properties", "highest appeal", "best appeal", "worst assessment",
        "most over", "most likely to appeal", "appeal score",
        "assessment score", "anomaly score", "score rating",
        "assessment issue", "assessment problem", "assessment error",
    ]):
        want_chart = any(kw in q_lower for kw in ["chart", "graph", "plot", "bar chart", "visualize", "visual"])
        score_formula = (
            "APPEAL SCORE FORMULA (0–100 composite):\n"
            "  z_score_zip × 20         — how many std devs above ZIP+lu_code peers (value/acre)\n"
            "  pct_above_zip_median × 30 — % above median for same ZIP+lu_code group\n"
            "  pct_above_lu_median × 20  — % above county-wide lu_code median\n"
            "  assessed_above_sale  +15  — if appraised value > most recent sale price\n"
            "  zoning_lu_mismatch   +15  — if zoning district conflicts with land use code\n"
            "  STRONG_CANDIDATE:   z_score_zip >= 2.0 AND pct_above_zip_median >= 0.20\n"
            "  MODERATE_CANDIDATE: z_score_zip >= 1.5 OR pct_above_zip_median >= 0.15\n"
            "\n"
            "NOTE: The appeal_score does NOT yet factor in flood zone, rail proximity, or correctional\n"
            "facilities — but these are devaluing factors that strengthen any appeal case. Use the\n"
            "result columns (in_flood_zone, near_rail, rail_distance_m) to flag these qualitatively.\n"
            "To check correctional facility or school proximity, call execute_sql with ST_Distance:\n"
            "  SELECT cf.name, ST_Distance(p.location::geography, cf.location::geography) AS dist_m\n"
            "  FROM parcels p, correctional_facilities cf\n"
            "  WHERE p.par_id = '<par_id>' ORDER BY dist_m LIMIT 1\n"
        )
        location_factors = (
            "LOCATION FACTORS — ASSESSOR BLIND SPOTS (from Davidson County valuation guide):\n"
            "These are devaluing externalities that mass appraisal neighborhood averages typically\n"
            "FAIL to isolate. If any apply, the property is likely over-assessed even before the\n"
            "statistical signals above. Check the result columns and flag them in your answer.\n\n"
            "• Flood zone (in_flood_zone=TRUE):\n"
            "    AE zone (1% annual chance): -8% to -12% residential SC adjustment\n"
            "    VE zone (coastal high hazard): -15% to -25% adjustment\n"
            "    Moderate zone (X500): -2% adjustment\n"
            "  → If CAMA value is at or above neighborhood median and property is in AE/VE, flag as over-assessed.\n\n"
            "• Active railroad (near_rail=TRUE, rail_distance_m < 500):\n"
            "    Residential < 300ft of active mainline: -7% to -10%\n"
            "    Residential 300–750ft: -3% to -5%\n"
            "    Retail/office < 500ft: -2% to -5% (noise nuisance)\n"
            "    Industrial < 1,000ft with siding access: +5% to +15% (accessibility premium)\n"
            "  → Flag residential parcels near active rail as over-assessed if CAMA is at/above median.\n\n"
            "• Correctional facility proximity (check via ST_Distance if needed):\n"
            "    State/federal prison < 0.25mi: -12% to -17% residential\n"
            "    County jail < 0.5mi: -5% to -10% residential\n"
            "    Halfway house < 0.25mi: -5% to -8% residential\n"
            "  → Mass appraisal models almost never isolate correctional facility stigma.\n\n"
            "• School quality (check school_poverty_estimates.ipr_est for nearby public_schools):\n"
            "    ipr_est < 200 = high poverty (depresses residential values)\n"
            "    ipr_est > 400 = affluent (supports values)\n"
            "  → Residential parcels near high-poverty schools may be over-assessed if CAMA used\n"
            "    a neighborhood average that doesn't isolate school quality.\n"
        )
        if want_chart:
            return (
                f"Query results ({row_count} rows):\n\n{bootstrap_result}\n\n"
                f"{score_formula}\n"
                f"{location_factors}\n"
                f"The user wants a CHART. Use run_python to create a horizontal bar chart of appeal_score "
                f"by property address. Then write Final Answer explaining each property, flagging any "
                f"flood/rail factors from the result columns.\n\n"
                f"Action: run_python\n"
                f"Action Input: {{\"code\": \"import matplotlib.pyplot as plt\\n"
                f"fig, ax = plt.subplots(figsize=(10, 6))\\n"
                f"ax.barh(df['prop_addr'].str[:40], df['appeal_score'], color='steelblue')\\n"
                f"ax.set_xlabel('Appeal Score (0-100)')\\n"
                f"ax.set_title('Top Mis-Assessed Properties by Appeal Score')\\n"
                f"plt.tight_layout()\\n"
                f"plt.savefig('/tmp/appeal_chart.png', dpi=100)\\n"
                f"print('Chart saved.')\\n"
                f"print(df[['prop_addr','totl_appr','sale_price','appeal_score','recommendation',"
                f"'z_score_zip','pct_above_zip_median','assessment_to_sale_ratio',"
                f"'in_flood_zone','near_rail','rail_distance_m']].to_string(index=False))\"}}"
            )
        return (
            f"Query results ({row_count} rows):\n\n{bootstrap_result}\n\n"
            f"{score_formula}\n"
            f"{location_factors}\n"
            f"Write your Final Answer as a numbered list. For each property include:\n"
            f"1. Address and ZIP\n"
            f"2. Land use (lu_desc) and total appraised value\n"
            f"3. Sale price and assessment-to-sale ratio (if available)\n"
            f"4. Statistical signals: explain z_score_zip, pct_above_zip_median, assessed_above_sale\n"
            f"5. Location factors: flag in_flood_zone, near_rail, and their expected value discount\n"
            f"6. Appeal score breakdown: which components drove the score\n\n"
            f"After the list, add 2–3 sentences explaining HOW the appeal score is calculated.\n\n"
            f"Return EXACTLY {row_count} properties. NEVER invent data.\n\n"
            f"Final Answer:"
        )
    elif any(kw in q_lower for kw in ["flood", "flood zone", "sfha", "fema"]):
        return (
            f"Query results ({row_count} rows):\n\n{bootstrap_result}\n\n"
            f"Write your Final Answer as a numbered list. For each property include:\n"
            f"1. Address and ZIP\n"
            f"2. Land use (lu_desc) and total appraised value\n"
            f"3. FEMA flood zone code and risk category\n"
            f"4. Whether it's a Special Flood Hazard Area (sfha_tf)\n\n"
            f"Return EXACTLY {row_count} properties. NEVER invent data.\n\n"
            f"Final Answer:"
        )
    elif any(kw in q_lower for kw in ["rail", "railroad", "train", "near rail"]):
        return (
            f"Query results ({row_count} rows):\n\n{bootstrap_result}\n\n"
            f"Write your Final Answer as a numbered list. For each property include:\n"
            f"1. Address and ZIP\n"
            f"2. Land use (lu_desc) and total appraised value\n"
            f"3. Distance to rail (distance_m meters) and railroad operator\n"
            f"4. Appeal score and recommendation\n\n"
            f"Return EXACTLY {row_count} properties. NEVER invent data.\n\n"
            f"Final Answer:"
        )
    elif any(kw in q_lower for kw in ["condo", "condominium"]):
        return (
            f"Query results ({row_count} rows):\n\n{bootstrap_result}\n\n"
            f"Write your Final Answer as a numbered list. For each property include:\n"
            f"1. Address and ZIP\n"
            f"2. Appraised value vs building median\n"
            f"3. Building z-score and assessment flag\n"
            f"4. Estimated annual savings if corrected\n\n"
            f"Return EXACTLY {row_count} properties. NEVER invent data.\n\n"
            f"Final Answer:"
        )
    else:
        # Generic fallback — used primarily for anomaly reports (detect_anomalies bootstrap).
        # Ask the LLM to analyze patterns, not just reformat the table.
        return (
            f"Anomaly detection results ({row_count} parcels):\n\n{bootstrap_result}\n\n"
            f"Write your Final Answer as a structured analysis report. Include:\n"
            f"1. **Top findings** — for each of the {row_count} parcels, one sentence explaining "
            f"WHY it is anomalous. Use the actual column values: e.g. 'value_per_acre of $X is "
            f"far outside the normal range for lu_code YYY' or 'asr of Z.Z means assessed value "
            f"is Z× the sale price'.\n"
            f"2. **Patterns** — are there common land use codes (lu_code), ZIP codes, or acreage "
            f"ranges among the anomalies? Summarize 2–3 patterns you see.\n"
            f"3. **Recommendations** — which parcels most warrant human review and why?\n\n"
            f"NEVER invent data — all numbers must come from the table above.\n\n"
            f"Final Answer:"
        )


async def _tool_execute_sql(db: AsyncSession, query: str, state: AnalystState) -> str:
    from app.services.sql_service import (
        _remove_percentile_cont_over,
        _strip_unused_ctes,
        _fix_cte_alias_leakage,
        _validate_and_cap,
    )

    # Log the raw query as the LLM wrote it
    logger.info("[SQL] ── Raw query from LLM ──────────────────────────────")
    for line in query.strip().splitlines():
        logger.info("[SQL]   %s", line)

    original = query
    query = _remove_percentile_cont_over(query)
    query = _strip_unused_ctes(query)
    query = _fix_cte_alias_leakage(query)
    for pattern, replacement in _COL_FIXES:
        query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

    if query.strip() != original.strip():
        logger.info("[SQL] ── After rewrite ───────────────────────────────")
        for line in query.strip().splitlines():
            logger.info("[SQL]   %s", line)

    try:
        safe_query = _validate_and_cap(query)
    except (ValueError, SQLSafetyError) as e:
        logger.warning("[SQL] Validation rejected query: %s", e)
        return f"SQL Error: {e}"

    logger.info("[SQL] ── Executing against DB ───────────────────────────")
    t0 = time.time()
    try:
        result = await db.execute(text(safe_query))
        rows = result.fetchall()
        cols = list(result.keys())
    except Exception as e:
        logger.warning("[SQL] DB execution error: %s", e)
        return f"SQL Error: {e}"

    elapsed = time.time() - t0
    logger.info("[SQL] ── Result: %d rows, %d cols, %.2fs ─────────────────", len(rows), len(cols), elapsed)
    logger.info("[SQL]    Columns: %s", cols)

    if not rows:
        logger.info("[SQL]    (no rows returned)")
        return "Query returned no results."

    df = pd.DataFrame(rows, columns=cols)
    state.last_df = df
    state.sql_history.append(safe_query)

    from tabulate import tabulate

    table = tabulate(df.head(50), headers="keys", tablefmt="pipe", showindex=False)
    return f"**{len(rows)} rows returned** (showing up to 50)\n\n{table}"


async def _tool_run_python(code: str, state: AnalystState) -> str:
    if state.last_df is None:
        return "No DataFrame available. Run execute_sql first."
    output, error = execute_python_on_df(code, state.last_df)
    if error:
        return f"Error: {error}\nOutput so far:\n{output}"
    return output or "(no output)"


async def _tool_detect_anomalies(
    db: AsyncSession,
    lu_code: str | None,
    prop_zip: str | None,
    top_n: int,
    state: AnalystState,
) -> str:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    where_clauses = ["p.acres > 0", "p.totl_appr > 0"]
    if lu_code:
        where_clauses.append(f"p.lu_code = '{lu_code}'")
    if prop_zip:
        where_clauses.append(f"p.prop_zip = '{prop_zip}'")
    where_str = " AND ".join(where_clauses)

    sql = text(
        f"""
        SELECT
            p.par_id, p.prop_addr, p.prop_zip, p.lu_code,
            p.acres, p.totl_appr, p.impr_appr, p.land_appr,
            p.sale_price, p.year_built, p.bldg_sqft,
            p.totl_appr / p.acres AS value_per_acre,
            COALESCE(bc.finished_area, p.bldg_sqft) AS fin_area,
            CASE WHEN p.sale_price > 0 THEN p.totl_appr / p.sale_price ELSE NULL END AS asr
        FROM parcels p
        LEFT JOIN building_characteristics bc ON bc.apn = p.par_id
        WHERE {where_str}
        LIMIT 50000
        """
    )

    result = await db.execute(sql)
    rows = result.fetchall()
    cols = list(result.keys())

    if not rows:
        return "No data found for the given filters."

    df = pd.DataFrame(rows, columns=cols)

    # Deduplicate — LEFT JOIN on building_characteristics can produce multiple rows
    # per parcel if a property has more than one BC record. Keep the first occurrence.
    df = df.drop_duplicates(subset=["par_id"]).reset_index(drop=True)

    features = ["value_per_acre", "acres", "totl_appr", "impr_appr", "land_appr"]
    optional = ["asr", "fin_area", "year_built"]
    for col in optional:
        if col in df.columns and df[col].notna().sum() > len(df) * 0.3:
            features.append(col)

    df_feat = df[features].fillna(df[features].median())

    scaler = StandardScaler()
    X = scaler.fit_transform(df_feat)

    clf = IsolationForest(n_estimators=200, contamination=0.05, random_state=42, n_jobs=-1)
    clf.fit(X)

    scores = clf.score_samples(X)
    df["anomaly_score"] = scores

    top = df.nsmallest(top_n, "anomaly_score")[
        ["par_id", "prop_addr", "prop_zip", "lu_code", "acres",
         "totl_appr", "value_per_acre", "asr", "anomaly_score"]
    ]
    state.last_df = top
    state.sql_history.append(
        f"IsolationForest(n={len(df)} parcels, top_n={top_n}, features={features})"
    )

    from tabulate import tabulate

    table = tabulate(top, headers="keys", tablefmt="pipe", showindex=False, floatfmt=".2f")
    return (
        f"**IsolationForest detected {top_n} most anomalous parcels** "
        f"(lower score = more anomalous, trained on {len(df)} parcels)\n\n{table}"
    )


async def _tool_search_docs(db: AsyncSession, query: str) -> str:
    docs = await search_documents(db, query, top_k=6)
    if not docs:
        return "No relevant documentation found."
    parts = []
    for doc in docs:
        parts.append(f"**[{doc['title']}]** (distance: {doc['distance']:.3f})\n{doc['content']}")
    return "\n\n---\n\n".join(parts)


async def run_analyst_stream(
    db: AsyncSession,
    question: str,
    max_iterations: int = 8,
) -> AsyncGenerator[dict, None]:
    yield {"type": "progress", "message": "Searching knowledge base..."}

    docs = await search_documents(db, question, top_k=10)
    knowledge_ctx = ""
    if docs:
        titles = [d["title"] for d in docs]
        yield {"type": "knowledge", "titles": titles}
        knowledge_ctx = "\n\nRelevant knowledge from vector store:\n"
        for doc in docs:
            knowledge_ctx += f"\n[{doc['title']}]\n{doc['content']}\n"

    system_prompt = SYSTEM_PROMPT_BASE + REACT_TOOL_INSTRUCTIONS + knowledge_ctx
    state = AnalystState()

    # ── Bootstrap: pre-execute SQL for known question patterns ──────────────────
    # Mirrors the logic in report_service._run_analyst_non_streaming so both
    # streaming and non-streaming paths behave identically.
    yield {"type": "progress", "message": "Pre-loading relevant data..."}
    sql_bootstrap_result = await _keyword_sql_bootstrap(db, question, state)

    if sql_bootstrap_result:
        row_count = len(state.last_df) if state.last_df is not None else 0
        yield {"type": "tool_call", "tool": "execute_sql", "args": {"type": "bootstrap"}}
        yield {"type": "tool_done", "tool": "execute_sql", "row_count": row_count}
        seed_msg = _build_bootstrap_seed_message(question, sql_bootstrap_result, row_count)
        messages: list[dict] = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": "I've queried the database for the relevant data."},
            {"role": "user", "content": seed_msg},
        ]
    else:
        messages: list[dict] = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": "I'll investigate this question using the available tools."},
            {"role": "user", "content": (
                "You MUST call execute_sql to query the database before writing Final Answer.\n\n"
                "Tool format:\n"
                "Action: execute_sql\n"
                "Action Input: {\"query\": \"SELECT ...\"}\n\n"
                "Only write 'Final Answer: ...' AFTER you have received an Observation from execute_sql."
            )},
        ]

    for iteration in range(max_iterations):
        state.steps += 1
        yield {"type": "progress", "message": f"Iteration {iteration + 1}/{max_iterations}..."}

        try:
            msg = await chat_completion(messages, system_prompt=system_prompt)
        except Exception as e:
            yield {"type": "error", "message": f"LLM error: {e}"}
            return

        content = msg.get("content", "")
        action_name, final_answer, args = _parse_react_response(content)

        if final_answer is not None:
            # Guard: reject Final Answer if no SQL has been run on the non-bootstrapped path
            if not sql_bootstrap_result and len(state.sql_history) == 0:
                logger.warning("[STREAM] Final Answer before any SQL — rejecting (iteration %d)", iteration + 1)
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": (
                    "You have NOT queried the database yet. Answering from documentation alone is NOT allowed.\n\n"
                    "Action: execute_sql\n"
                    "Action Input: {\"query\": \"<your SQL>\"}"
                )})
                continue
            yield {"type": "thinking", "content": content}
            yield {"type": "answer", "content": final_answer}
            yield {"type": "done", "steps": state.steps, "sql_queries": state.sql_history}
            return

        # If model output looks like planning but has no Action:, push it to act
        if action_name is None:
            yield {"type": "thinking", "content": content}
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": (
                "Good planning. Now execute the first action. "
                "Respond with exactly:\nAction: <tool_name>\nAction Input: {\"key\": \"value\"}"
            )})
            continue

        # Execute the tool
        yield {"type": "tool_call", "tool": action_name, "args": args}
        messages.append({"role": "assistant", "content": content})

        if action_name == "execute_sql":
            result = await _tool_execute_sql(db, args.get("query", ""), state)
        elif action_name == "run_python":
            result = await _tool_run_python(args.get("code", ""), state)
        elif action_name == "detect_anomalies":
            result = await _tool_detect_anomalies(
                db,
                lu_code=args.get("lu_code"),
                prop_zip=args.get("prop_zip"),
                top_n=args.get("top_n", 20),
                state=state,
            )
        elif action_name == "search_docs":
            query = args.get("query") or args.get("topic") or args.get("q") or ""
            if not query:
                query = next((v for v in args.values() if isinstance(v, str) and v.strip()), "")
            if not query:
                result = "search_docs requires a query string. Retry with Action Input: {\"query\": \"your search term\"}"
            else:
                try:
                    result = await _tool_search_docs(db, query)
                except Exception as e:
                    result = f"search_docs failed: {e}. Proceed with execute_sql instead."
        else:
            result = f"Unknown tool: {action_name}"

        row_count = len(state.last_df) if state.last_df is not None else None
        yield {"type": "tool_done", "tool": action_name, "row_count": row_count}

        # Observation goes back as a user message (standard ReAct pattern)
        messages.append({"role": "user", "content": f"Observation: {result}"})

    yield {"type": "error", "message": "Max iterations reached without final answer."}


async def save_query_example(
    db: AsyncSession,
    question: str,
    sql: str,
    insight: str,
    tags: list[str],
) -> None:
    examples_path = os.path.join("data", "knowledge", "query_examples.md")
    tag_str = ", ".join(tags)
    new_entry = f"\n\n## Example: {question}\n\n**Tags:** {tag_str}\n\n```sql\n{sql}\n```\n\n**Insight:** {insight}\n"

    with open(examples_path, "a", encoding="utf-8") as f:
        f.write(new_entry)

    with open(examples_path, encoding="utf-8") as f:
        content = f.read()

    await embed_document(
        db,
        title="Query Examples",
        source="query_examples.md",
        content=content,
    )
