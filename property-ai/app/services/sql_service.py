"""
Text-to-SQL service with a self-improving query library.

Flow for each data question:
  1. Vector-search saved_queries for similar past questions (few-shot examples)
  2. Ask LLM to generate SQL using schema + few-shot context
  3. Validate (SELECT only, LIMIT enforced) and execute
  4. Save successful queries back to the library with embeddings
  5. Ratings submitted later via the feedback endpoint update avg_rating,
     demoting poor queries so they stop being used as examples.
"""

import json
import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import chat_completion, embed_text

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Schema context – fed to the LLM on every SQL generation call
# ──────────────────────────────────────────────────────────────────────────────

SCHEMA_CONTEXT = """
PostgreSQL database for Davidson County, Nashville TN property tax analysis.

TABLE: parcels
  par_id TEXT PK          -- unique parcel identifier
  prop_addr TEXT          -- street address
  prop_city TEXT
  prop_zip TEXT(10)
  owner_name TEXT
  lu_code TEXT(20)        -- land use code (NUMERIC): 010-019=Residential, 020-069=Commercial, 070-079=Industrial/Warehouse, 080-089=Agricultural/Rural
  lu_desc TEXT            -- land use description
  zoning TEXT(20)         -- zoning district code
  nbhd TEXT(20)           -- neighborhood code
  nbhd_desc TEXT          -- neighborhood description
  acres FLOAT
  land_appr FLOAT         -- land appraised value
  impr_appr FLOAT         -- improvement appraised value
  totl_appr FLOAT         -- total appraised value
  land_assd FLOAT         -- land assessed value
  impr_assd FLOAT         -- improvement assessed value
  totl_assd FLOAT         -- total assessed value
  sale_price FLOAT        -- most recent sale price
  sale_date TEXT          -- sale date
  year_built INT
  bldg_sqft FLOAT         -- building square footage
  num_rooms INT
  num_beds INT
  num_baths FLOAT
  stories FLOAT
  exterior TEXT
  heat_type TEXT
  tax_dist TEXT(20)
  school_dist TEXT(20)
  council_dist TEXT(20)
  location GEOMETRY(POINT,4326)

TABLE: parcel_signals
  par_id TEXT PK FK->parcels.par_id
  z_score_zip FLOAT           -- statistical z-score vs ZIP peer group
  pct_above_zip_median FLOAT  -- % above ZIP+lu_code median (0.20 = 20% above)
  pct_above_lu_median FLOAT   -- % above land-use-wide median
  zip_peer_count INT          -- comparable parcel count
  assessment_to_sale_ratio FLOAT  -- assessed / sale price (>1.0 = over-assessed)
  assessed_above_sale BOOL    -- TRUE if assessed > sale price
  zoning_lu_mismatch BOOL     -- TRUE if numeric lu_code range conflicts with zoning district (e.g. industrial lu 070-079 in commercial zoning)
  appeal_score FLOAT          -- 0-100 composite appeal potential (higher = better case)
  recommendation TEXT         -- STRONG_CANDIDATE | MODERATE_CANDIDATE | REVIEW_ZONING | NORMAL

TABLE: building_permits
  id INT PK
  permit_number TEXT
  parcel TEXT             -- FK to parcels.par_id
  permit_type TEXT
  description TEXT
  date_issued TEXT
  date_completed TEXT
  construction_cost FLOAT
  contractor TEXT
  location GEOMETRY(POINT,4326)

TABLE: building_characteristics
  id INT PK
  apn TEXT               -- FK to parcels.par_id
  finished_area FLOAT    -- finished square footage
  year_built INT
  structure_type TEXT
  exterior TEXT
  geom GEOMETRY(MULTIPOLYGON,4326)

TABLE: building_footprints
  id INT PK
  building_type TEXT
  height FLOAT
  bldg_id TEXT
  roof_type TEXT
  shape_area FLOAT       -- square feet
  geom GEOMETRY(MULTIPOLYGON,4326)

TABLE: flood_zones
  id INT PK
  flood_zone TEXT(20)    -- e.g. AE, X, AH
  sfha_tf BOOL           -- TRUE = Special Flood Hazard Area
  zone_description TEXT
  shape_area FLOAT
  geom GEOMETRY(MULTIPOLYGON,4326)

TABLE: cell_towers
  id INT PK
  company TEXT
  fcc_site_id TEXT
  height FLOAT
  tower_type TEXT
  location GEOMETRY(POINT,4326)

TABLE: rail_lines
  id INT PK
  owner TEXT
  passenger_rail BOOL
  tracks INT
  miles FLOAT
  geom GEOMETRY(MULTILINESTRING,4326)

TABLE: zoning_districts
  id INT PK
  zoning_code TEXT(20)
  zoning_district TEXT
  description TEXT
  geom GEOMETRY(MULTIPOLYGON,4326)

TABLE: public_schools
  id INT PK
  ncessch TEXT(12)
  name TEXT
  street TEXT
  city TEXT
  zip TEXT
  location GEOMETRY(POINT,4326)

TABLE: school_performance
  id INT PK
  ncessch TEXT(12) FK->public_schools.ncessch
  school_year TEXT
  overall_rating TEXT
  achievement_score FLOAT
  graduation_rate FLOAT
  test_scores_math FLOAT
  test_scores_reading FLOAT

TABLE: crime_incidents
  id INT PK
  incident_number TEXT
  incident_type TEXT
  offense_description TEXT
  offense_group TEXT       -- Violent, Property, etc.
  rpa TEXT(10)             -- Reporting Police Area
  incident_occurred TIMESTAMPTZ
  location GEOMETRY(POINT,4326)

TABLE: police_reporting_areas
  id INT PK
  rpa TEXT(10) UNIQUE
  precinct TEXT
  sector TEXT
  beat TEXT
  geom GEOMETRY(MULTIPOLYGON,4326)

TABLE: correctional_facilities
  id INT PK
  name TEXT
  address TEXT
  city TEXT
  state TEXT
  zipcode TEXT
  location GEOMETRY(POINT,4326)

KEY JOINS:
  parcels JOIN parcel_signals ON parcels.par_id = parcel_signals.par_id
  building_permits JOIN parcels ON building_permits.parcel = parcels.par_id
  building_characteristics ON building_characteristics.apn = parcels.par_id
  school_performance JOIN public_schools ON school_performance.ncessch = public_schools.ncessch
"""

# ──────────────────────────────────────────────────────────────────────────────
# Intent detection
# ──────────────────────────────────────────────────────────────────────────────

_DATA_KEYWORDS = {
    "list", "show", "find", "give", "provide", "top", "bottom", "which",
    "how many", "count", "average", "total", "highest", "lowest", "most",
    "least", "parcels", "properties", "addresses", "ids", "parcel id",
    "ranked", "sorted", "filter", "select", "query", "retrieve",
    "what are the", "who has", "where are", "identify",
}


def is_data_question(question: str) -> bool:
    """Heuristic: does this question need a live DB query?"""
    q = question.lower()
    return any(kw in q for kw in _DATA_KEYWORDS)


# ──────────────────────────────────────────────────────────────────────────────
# Few-shot retrieval from saved query library
# ──────────────────────────────────────────────────────────────────────────────

async def get_similar_queries(
    db: AsyncSession, question: str, top_k: int = 3
) -> list[dict]:
    """Vector-search saved_queries for similar past questions with good ratings."""
    embedding = await embed_text(question)
    emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
    try:
        result = await db.execute(
            text("""
                SELECT question, sql, result_count, avg_rating
                FROM saved_queries
                WHERE avg_rating >= 3 OR avg_rating = 0
                ORDER BY embedding <=> CAST(:emb AS vector)
                LIMIT :top_k
            """),
            {"emb": emb_str, "top_k": top_k},
        )
        return [
            {
                "question": r.question,
                "sql": r.sql,
                "result_count": r.result_count,
                "rating": r.avg_rating,
            }
            for r in result.fetchall()
        ]
    except Exception:
        # Table may be empty on first run
        return []


# ──────────────────────────────────────────────────────────────────────────────
# SQL generation
# ──────────────────────────────────────────────────────────────────────────────

async def _extract_sql_blocks(content: str) -> list[str]:
    """Pull out ```sql ... ``` blocks from markdown content."""
    return re.findall(r"```sql\s*(.*?)```", content, re.DOTALL | re.IGNORECASE)


def _remove_percentile_cont_over(sql: str) -> str:
    """
    Strip PERCENTILE_CONT(...) WITHIN GROUP (...) OVER (...) column expressions.
    PostgreSQL does not support OVER for ordered-set aggregates.
    The model keeps generating this pattern despite the prompt rule.

    Removes the comma + full expression up to and including the alias.
    If the CTE that contained it becomes unused after removal, it will be
    caught by _strip_unused_ctes.
    """
    if "PERCENTILE_CONT" not in sql.upper():
        return sql

    # Remove: ,<ws>PERCENTILE_CONT(...) WITHIN GROUP (...) OVER (...)<ws>AS alias
    # Use a character-level approach to handle nested parens in the args.
    result = []
    i = 0
    upped = sql.upper()
    while i < len(sql):
        # Look for ", PERCENTILE_CONT"
        pc_idx = upped.find("PERCENTILE_CONT", i)
        if pc_idx == -1:
            result.append(sql[i:])
            break

        # Walk back to find the preceding comma (skipping whitespace)
        comma_idx = pc_idx - 1
        while comma_idx >= 0 and sql[comma_idx] in " \t\n\r":
            comma_idx -= 1
        if comma_idx >= 0 and sql[comma_idx] == ",":
            result.append(sql[i:comma_idx])
        else:
            result.append(sql[i:pc_idx])

        # Skip past the full expression: PERCENTILE_CONT(...) WITHIN GROUP (...) OVER (...) AS alias
        j = pc_idx + len("PERCENTILE_CONT")
        # Skip argument parens
        depth = 0
        while j < len(sql):
            if sql[j] == "(":
                depth += 1
            elif sql[j] == ")":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        # Skip WITHIN GROUP (...)
        rest = sql[j:].lstrip()
        m = re.match(r"WITHIN\s+GROUP\s*\(", rest, re.IGNORECASE)
        if m:
            j += len(sql[j:]) - len(rest) + m.end()
            depth = 1
            while j < len(sql) and depth > 0:
                if sql[j] == "(":
                    depth += 1
                elif sql[j] == ")":
                    depth -= 1
                j += 1
        # Skip OVER (...)
        rest = sql[j:].lstrip()
        m = re.match(r"OVER\s*\(", rest, re.IGNORECASE)
        if m:
            j += len(sql[j:]) - len(rest) + m.end()
            depth = 1
            while j < len(sql) and depth > 0:
                if sql[j] == "(":
                    depth += 1
                elif sql[j] == ")":
                    depth -= 1
                j += 1
        # Skip AS alias
        rest = sql[j:].lstrip()
        m = re.match(r"AS\s+\w+", rest, re.IGNORECASE)
        if m:
            j += len(sql[j:]) - len(rest) + m.end()
        i = j
        upped = sql.upper()  # refresh (same string, position tracking only)

    result_sql = "".join(result)
    # Clean up any double-commas or trailing commas before FROM/WHERE
    result_sql = re.sub(r",\s*,", ",", result_sql)
    result_sql = re.sub(r",\s*(FROM|WHERE|ORDER|GROUP|HAVING|LIMIT)", r" \1", result_sql, flags=re.IGNORECASE)
    return result_sql


def _strip_unused_ctes(sql: str) -> str:
    """
    Remove CTE definitions that are never referenced in the outer SELECT
    or in other CTE bodies.  Handles the common model pattern of generating
    a 'peer_stats' CTE with a complex window function that then never
    actually gets used in the final query.
    """
    if "WITH" not in sql.upper():
        return sql

    # Find all CTE name definitions: "name AS ("
    cte_defs = list(re.finditer(r"\b(\w+)\s+AS\s*\(", sql, re.IGNORECASE))
    if not cte_defs:
        return sql

    cte_names = [m.group(1) for m in cte_defs]

    # Find the outer SELECT (after all CTEs)
    depth = 0
    outer_start = -1
    for i, c in enumerate(sql):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and sql[i : i + 6].upper() == "SELECT":
            outer_start = i
            break

    if outer_start == -1:
        return sql

    outer_part = sql[outer_start:]

    # For each CTE, check if its name appears in:
    #   a) the outer SELECT portion
    #   b) the body of any other CTE (i.e. it feeds another CTE)
    # If it doesn't appear anywhere else, it's dead.
    # Build a map: cte_name -> body text
    cte_bodies: dict[str, str] = {}
    for idx, m in enumerate(cte_defs):
        start = m.end()  # position right after the "("
        # Find matching close paren
        depth = 1
        j = start
        while j < len(sql) and depth > 0:
            if sql[j] == "(":
                depth += 1
            elif sql[j] == ")":
                depth -= 1
            j += 1
        cte_bodies[m.group(1)] = sql[start : j - 1]

    dead_ctes: set[str] = set()
    for name in cte_names:
        # Build the "other text" that could reference this CTE name
        other_bodies = " ".join(
            body for n, body in cte_bodies.items() if n != name
        )
        other_text = outer_part + " " + other_bodies
        # A reference is a word-boundary match (not the definition itself)
        if not re.search(rf"\b{re.escape(name)}\b", other_text, re.IGNORECASE):
            dead_ctes.add(name)

    if not dead_ctes:
        return sql

    # Remove dead CTE blocks from the WITH clause.
    # Strategy: reconstruct the WITH clause without the dead CTEs.
    # Find the WITH...outer-SELECT span and rebuild the CTE list.
    with_match = re.match(r"\s*WITH\s+", sql, re.IGNORECASE)
    if not with_match:
        return sql

    # Split CTEs by extracting each "name AS (...)" block
    kept_ctes: list[str] = []
    pos = with_match.end()

    while pos < outer_start:
        # Skip optional comma and whitespace
        m = re.match(r"\s*,?\s*", sql[pos:])
        if m:
            pos += m.end()

        # Match "name AS ("
        m = re.match(r"(\w+)\s+AS\s*\(", sql[pos:], re.IGNORECASE)
        if not m:
            break
        name = m.group(1)
        body_start = pos + m.end()

        # Find closing paren
        depth = 1
        j = body_start
        while j < len(sql) and depth > 0:
            if sql[j] == "(":
                depth += 1
            elif sql[j] == ")":
                depth -= 1
            j += 1
        block = sql[pos : j].strip().rstrip(",").strip()
        pos = j

        if name not in dead_ctes:
            kept_ctes.append(block)

    if not kept_ctes:
        # All CTEs were dead — just return the outer SELECT
        return sql[outer_start:].strip()

    return "WITH " + ",\n".join(kept_ctes) + "\n" + sql[outer_start:]


_ADDR_STOP = {
    "rd", "road", "ave", "avenue", "blvd", "boulevard", "st", "street",
    "dr", "drive", "ln", "lane", "way", "pike", "ct", "court", "pl",
    "place", "cir", "circle", "trl", "trail", "nashville", "tn",
    "tennessee", "n", "s", "e", "w", "north", "south", "east", "west",
}


def _extract_street_keyword(addr_value: str) -> str | None:
    parts = addr_value.strip().split()
    for part in parts:
        p = part.lower().strip(",%")
        if p.isdigit():
            continue
        if p in _ADDR_STOP:
            continue
        candidate = part.upper().strip(",%")
        # Only allow alphanumeric + hyphen — reject anything that could
        # break or escape out of an ILIKE string literal in generated SQL.
        if re.match(r"^[A-Z0-9\-]+$", candidate):
            return candidate
    return None


def _replace_addr_match(m: re.Match) -> str:
    addr_value = m.group(1)
    keyword = _extract_street_keyword(addr_value)
    if not keyword:
        return m.group(0)
    return f"prop_addr ILIKE '%{keyword}%'"


def _rewrite_address_cte_as_flat_join(sql: str) -> str | None:
    """
    Detect CTE queries that do an address (ILIKE) lookup and rewrite them as a
    flat JOIN. The model keeps generating CTEs for comparison questions despite
    the prompt rules. These CTEs cause CardinalityViolationError because ILIKE
    matches multiple rows which can't be used as scalar subquery expressions.

    Returns the rewritten flat query, or None if the SQL is not a rewritable CTE.
    """
    if "WITH" not in sql.upper():
        return None

    # Must contain an ILIKE address search
    addr_match = re.search(r"prop_addr\s+ILIKE\s+'%(\w+)%'", sql, re.IGNORECASE)
    if not addr_match:
        return None

    keyword = addr_match.group(1).upper()

    # Extract ZIP if present
    zip_match = re.search(r"prop_zip\s*=\s*'(\d{5})'", sql, re.IGNORECASE)
    zip_val = zip_match.group(1) if zip_match else None

    # Build a flat, reliable comparison query:
    # Fetch the target parcel + nearby parcels of the same lu_code / zip
    # ordered so the target parcel appears first.
    outer_zip_clause = f"p.prop_zip = '{zip_val}'" if zip_val else "TRUE"
    inner_zip_clause = f"AND prop_zip = '{zip_val}'" if zip_val else ""

    flat_sql = (
        f"SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_code,\n"
        f"       p.totl_appr, p.sale_price, p.year_built, p.acres,\n"
        f"       ps.appeal_score, ps.recommendation, ps.z_score_zip,\n"
        f"       ps.pct_above_zip_median, ps.assessment_to_sale_ratio,\n"
        f"       ps.assessed_above_sale,\n"
        f"       CASE WHEN p.prop_addr ILIKE '%{keyword}%' THEN 'TARGET' ELSE 'COMPARABLE' END AS parcel_type\n"
        f"FROM parcels p\n"
        f"JOIN parcel_signals ps ON ps.par_id = p.par_id\n"
        f"WHERE {outer_zip_clause}\n"
        f"  AND p.lu_code = (\n"
        f"      SELECT lu_code FROM parcels\n"
        f"      WHERE prop_addr ILIKE '%{keyword}%' {inner_zip_clause}\n"
        f"      LIMIT 1\n"
        f"  )\n"
        f"ORDER BY\n"
        f"  CASE WHEN p.prop_addr ILIKE '%{keyword}%' THEN 0 ELSE 1 END,\n"
        f"  ps.appeal_score DESC\n"
        f"LIMIT 10"
    )
    return flat_sql


def _fix_cte_alias_leakage(sql: str) -> str:
    """
    Fix the common CTE outer alias bug:
      WITH peer_stats AS (
          SELECT ..., ps.appeal_score
          FROM parcels p JOIN parcel_signals ps ON ...
      )
      SELECT ps.appeal_score   ← ERROR: ps not in outer scope, outer alias is p
      FROM peer_stats p

    Strategy:
      1. Walk character-by-character to find the outer SELECT (depth == 0).
      2. In the outer SELECT portion, find every `FROM cte_name alias` pattern
         to build a map of what's in scope.
      3. Replace any alias.column reference where the alias is not in the outer
         scope but IS the parcel_signals inner alias (`ps`).
    """
    if "WITH" not in sql.upper():
        return sql

    # Walk to find the outer SELECT (not inside any parentheses)
    depth = 0
    outer_start = -1
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and sql[i : i + 6].upper() == "SELECT":
            outer_start = i
            break
        i += 1

    if outer_start == -1:
        return sql

    cte_part = sql[:outer_start]
    outer_part = sql[outer_start:]

    # Build outer scope: aliases defined directly in the outer FROM/JOIN clauses
    outer_aliases: set[str] = set()
    for m in re.finditer(
        r"\b(?:FROM|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?",
        outer_part,
        re.IGNORECASE,
    ):
        # m.group(1) = table/CTE name, m.group(2) = alias (if present)
        outer_aliases.add(m.group(1).lower())
        if m.group(2):
            outer_aliases.add(m.group(2).lower())

    # Collect aliases used inside CTEs (inner scope) that might leak
    # Specifically look for `parcel_signals alias` patterns inside CTE bodies
    inner_ps_aliases: set[str] = set()
    for m in re.finditer(
        r"\bparcel_signals\s+(?:AS\s+)?(\w+)", cte_part, re.IGNORECASE
    ):
        alias = m.group(1).lower()
        if alias not in outer_aliases:
            inner_ps_aliases.add(alias)

    if not inner_ps_aliases:
        return sql

    # For each leaked alias, find the correct outer alias to substitute.
    # The outer alias is the alias used for the CTE in the outer FROM.
    # Heuristic: pick the first FROM alias that maps to a CTE (not a real table).
    cte_names = {
        m.group(1).lower()
        for m in re.finditer(r"\bWITH\s+(\w+)\s+AS\s*\(", cte_part, re.IGNORECASE)
    }
    # Add subsequent CTEs separated by commas
    cte_names.update(
        m.group(1).lower()
        for m in re.finditer(r",\s*(\w+)\s+AS\s*\(", cte_part, re.IGNORECASE)
    )

    # Map: cte_name → outer alias
    outer_cte_alias_map: dict[str, str] = {}
    for m in re.finditer(
        r"\b(?:FROM|JOIN)\s+(\w+)\s+(?:AS\s+)?(\w+)", outer_part, re.IGNORECASE
    ):
        tbl = m.group(1).lower()
        alias = m.group(2).lower()
        if tbl in cte_names:
            outer_cte_alias_map[tbl] = alias

    # Replace leaked inner aliases in the outer SELECT with the correct outer alias.
    # Use the first CTE's outer alias as the replacement target.
    fixed_outer = outer_part
    for leaked_alias in inner_ps_aliases:
        replacement_alias = None
        if outer_cte_alias_map:
            # Use the alias of the first CTE in the outer FROM
            first_cte = next(iter(outer_cte_alias_map))
            replacement_alias = outer_cte_alias_map[first_cte]
        if replacement_alias:
            fixed_outer = re.sub(
                rf"\b{re.escape(leaked_alias)}\.",
                f"{replacement_alias}.",
                fixed_outer,
                flags=re.IGNORECASE,
            )

    return cte_part + fixed_outer


# Column name normalization — fixes names the model generates without underscores.
# Single authoritative list imported by analyst_service to avoid duplication.
_COL_FIXES = [
    (r"\btaxdist\b", "tax_dist"),
    (r"\bschooldist\b", "school_dist"),
    (r"\bcouncildist\b", "council_dist"),
    (r"\blucode\b", "lu_code"),
    (r"\bludesc\b", "lu_desc"),
    (r"\byearbuilt\b", "year_built"),
    (r"\bbldgsqft\b", "bldg_sqft"),
    (r"\bsaledate\b", "sale_date"),
    (r"\bsaleprice\b", "sale_price"),
    (r"\blandappr\b", "land_appr"),
    (r"\bimprappr\b", "impr_appr"),
    (r"\btotlappr\b", "totl_appr"),
    (r"\blandassd\b", "land_assd"),
    (r"\bimprassd\b", "impr_assd"),
    (r"\btotlassd\b", "totl_assd"),
    (r"\bownername\b", "owner_name"),
    (r"\bpropaddr\b", "prop_addr"),
    (r"\bpropcity\b", "prop_city"),
    (r"\bpropzip\b", "prop_zip"),
    (r"\bnbhddesc\b", "nbhd_desc"),
    (r"\bnumrooms\b", "num_rooms"),
    (r"\bnumbeds\b", "num_beds"),
    (r"\bnumbaths\b", "num_baths"),
    (r"\bheattype\b", "heat_type"),
    (r"\bparid\b", "par_id"),
    (r"\bzscore_?zip\b", "z_score_zip"),
    (r"\bappealscore\b", "appeal_score"),
    (r"\bpctabovezipmedian\b", "pct_above_zip_median"),
    (r"\bpctabovelumedian\b", "pct_above_lu_median"),
    (r"\bzippeercount\b", "zip_peer_count"),
    (r"\bassessmenttosaleratio\b", "assessment_to_sale_ratio"),
    (r"\bassessedabovesale\b", "assessed_above_sale"),
    (r"\bzoninglumismatch\b", "zoning_lu_mismatch"),
]


def _extract_sql_from_response(raw: str) -> str | None:
    """
    Robustly extract a SQL query from an LLM response.

    The model (qwen2.5-coder:7b) sometimes:
      - Wraps the full query in one ```sql block  (ideal)
      - Puts a CTE header (WITH x AS () OUTSIDE the fence and the inner
        SELECT inside it — yielding a broken partial query if we only
        grab the fenced block
      - Returns bare SQL with no fences at all

    Strategy:
      1. Strip ALL backtick fences from the full response so a split CTE
         gets merged back into one text block.
      2. Find the SQL start using patterns that can't match English prose:
         - WITH <identifier> AS ( — unambiguous SQL; "with the highest..."
           never matches because it lacks <ident> AS (
         - SELECT (fallback)
      3. Truncate at the last LIMIT clause to drop trailing explanation text.
    """
    # Remove all code fences (```sql, ```, etc.) so split CTEs are reunited
    cleaned = re.sub(r"```\w*\s*", "", raw)
    cleaned = re.sub(r"```", "", cleaned)

    # Find SQL start — WITH <name> AS ( is unambiguous SQL
    m = re.search(r"\bWITH\s+\w+\s+AS\s*\(", cleaned, re.IGNORECASE)
    if not m:
        # No CTE — look for a SELECT statement
        m = re.search(r"\bSELECT\b", cleaned, re.IGNORECASE)
    if not m:
        return None

    sql = cleaned[m.start():].strip()

    # Truncation strategy: prefer semicolons (SQL statement terminator) over
    # LIMIT scanning, because LIMIT often appears in trailing explanation text
    # and would include that prose in the SQL string.
    semi_pos = sql.rfind(";")
    if semi_pos > 10:
        sql = sql[:semi_pos].strip()
    else:
        # No semicolon — fall back to last LIMIT clause
        limit_matches = list(re.finditer(r"\bLIMIT\s+\d+", sql, re.IGNORECASE))
        if limit_matches:
            sql = sql[: limit_matches[-1].end()].strip()

    sql = sql.rstrip(";").strip()
    if not sql:
        return None

    # Post-process: convert address matches BEFORE CTE rewrite so the rewrite
    # can reliably detect the ILIKE pattern regardless of what the model produced.
    sql = re.sub(
        r"prop_addr\s*(?:I?LIKE|=)\s*'([^']+)'",
        _replace_addr_match,
        sql,
        flags=re.IGNORECASE,
    )

    # Post-process: strip PERCENTILE_CONT OVER and dead CTEs before any other
    # CTE rewriting so downstream fixers see a cleaner query.
    sql = _remove_percentile_cont_over(sql)
    sql = _strip_unused_ctes(sql)

    # Post-process: rewrite CTE-based address comparison queries as flat JOINs.
    # The model ignores rule 9 for "comparison" questions and generates CTEs that
    # cause CardinalityViolationError. Replace with a reliable flat JOIN.
    rewritten = _rewrite_address_cte_as_flat_join(sql)
    if rewritten:
        logger.info("Rewrote CTE address query as flat JOIN")
        sql = rewritten
    else:
        # Fall back to alias leakage fix for non-rewritable CTEs
        sql = _fix_cte_alias_leakage(sql)

    # Post-process: fix common column name mistakes (model drops underscores).
    for pattern, replacement in _COL_FIXES:
        sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)

    return sql


async def generate_sql(
    db: AsyncSession,
    question: str,
    rag_context: str | None = None,
) -> str | None:
    """Ask the LLM to write a PostgreSQL SELECT for this question.

    The prompt is built in four layers:
      1. Full schema  — every table, column, type, and key join
      2. Domain knowledge — passed in from chat_service (already fetched
         via RAG before this function is called) + any additional chunks
         from query_examples.md for SQL patterns
      3. SQL examples — from query_examples.md + high-rated saved_queries
      4. The question itself

    rag_context: pre-fetched RAG chunks from chat_service (avoids a
    duplicate vector search — chat_service already ran search_documents).
    """
    from app.services.embed_service import search_documents

    # Fetch saved examples then doc chunks sequentially — asyncio.gather on the
    # same AsyncSession causes "concurrent operations not permitted" errors.
    saved_examples = await get_similar_queries(db, question, top_k=3)
    doc_chunks = await search_documents(db, question, top_k=4)

    # ── Layer 2: domain knowledge ─────────────────────────────────────────────
    # Primary source: rag_context passed in from chat_service (already fetched)
    # Secondary source: any additional non-query chunks from this search
    domain_knowledge = ""
    sql_doc_examples: list[str] = []

    # Use pre-fetched RAG context if provided (avoids duplicate vector search)
    if rag_context:
        # Strip markdown fences to keep prompt tight
        clean = re.sub(r"```[a-z]*", "", rag_context)
        clean = re.sub(r"^#+\s+", "", clean, flags=re.MULTILINE).strip()
        domain_knowledge += clean + "\n\n"

    for chunk in doc_chunks:
        source = chunk.get("source", "")
        content = chunk.get("content", "")

        if source == "query_examples.md":
            # Extract SQL blocks for use as examples (layer 3)
            blocks = await _extract_sql_blocks(content)
            sql_doc_examples.extend(blocks)
        elif not rag_context:
            # Only add doc chunks as domain knowledge if rag_context not provided
            clean = re.sub(r"```[a-z]*", "", content)
            clean = re.sub(r"^#+\s+", "", clean, flags=re.MULTILINE).strip()
            if clean:
                domain_knowledge += f"[{chunk.get('title', source)}]\n{clean}\n\n"

    # ── Layer 3: SQL examples ─────────────────────────────────────────────────
    few_shot = ""

    if saved_examples:
        few_shot += "EXAMPLES FROM QUERY LIBRARY (past rated sessions):\n"
        for ex in saved_examples:
            few_shot += f"Q: {ex['question']}\nSQL:\n{ex['sql']}\n\n"

    if sql_doc_examples:
        few_shot += "EXAMPLES FROM KNOWLEDGE BASE (query_examples.md):\n"
        for sql_block in sql_doc_examples[:3]:
            few_shot += f"SQL:\n{sql_block.strip()}\n\n"

    # ── Build full prompt ─────────────────────────────────────────────────────
    domain_section = (
        f"DOMAIN KNOWLEDGE (understand value meanings before writing filters):\n"
        f"{domain_knowledge}\n"
        if domain_knowledge
        else ""
    )

    prompt = (
        f"You are a PostgreSQL expert for a Davidson County, Nashville TN property tax database.\n"
        f"Generate ONE valid SELECT query to answer the question.\n\n"
        f"RULES:\n"
        f"1. Return ONLY the SQL query – no markdown fences, no explanation\n"
        f"2. Only SELECT or WITH…SELECT (CTE) statements are allowed\n"
        f"   If using a CTE, the WITH keyword must be the very first word of your response\n"
        f"3. Always include LIMIT (default 25 unless question specifies a number)\n"
        f"4. Use exact table/column names from the schema\n"
        f"5. JOIN parcel_signals when appeal_score, recommendation, or z_score needed\n"
        f"6. Use domain knowledge to write precise WHERE filters "
        f"(e.g. correct zoning prefixes, appeal score thresholds, flood zone codes)\n"
        f"7. Address searches — CRITICAL: database stores UPPERCASE abbreviated addresses.\n"
        f"   NEVER use exact match: prop_addr = '4918 Yorktown Road Nashville TN'  ← WRONG\n"
        f"   NEVER use LIKE: prop_addr LIKE '%Yorktown Road%'  ← WRONG\n"
        f"   ALWAYS use ILIKE on uppercase street name keyword only:\n"
        f"     WHERE prop_addr ILIKE '%YORKTOWN%' AND prop_zip = '37211'  ← CORRECT\n"
        f"   Extract only the street name word (e.g. 'YORKTOWN' from '4918 Yorktown Road').\n"
        f"8. Peer median computation — CRITICAL: PostgreSQL does NOT support\n"
        f"   PERCENTILE_CONT(...) WITHIN GROUP (...) OVER (PARTITION BY ...).\n"
        f"   NEVER write that pattern. Instead join parcel_signals which already has\n"
        f"   pct_above_zip_median, z_score_zip, appeal_score pre-computed:\n"
        f"     JOIN parcel_signals ps ON ps.par_id = p.par_id\n"
        f"   Use ps.pct_above_zip_median and ps.z_score_zip for peer comparison.\n"
        f"9. CRITICAL — NEVER use CTEs (WITH ... AS) for parcel queries or comparisons.\n"
        f"   The parcel_signals table ALREADY has ALL comparison metrics pre-computed:\n"
        f"   pct_above_zip_median, z_score_zip, assessment_to_sale_ratio, appeal_score.\n"
        f"   There is NO reason to compute peer stats — they are already in parcel_signals.\n"
        f"   WRONG (never do this):\n"
        f"     WITH peer_stats AS (SELECT ... FROM parcels p JOIN parcel_signals ps ...)\n"
        f"     SELECT ps.appeal_score FROM peer_stats p ...  ← BREAKS: ps not in outer scope\n"
        f"   CORRECT (always do this — flat JOIN only):\n"
        f"     SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_code, p.totl_appr,\n"
        f"            p.sale_price, ps.appeal_score, ps.recommendation,\n"
        f"            ps.z_score_zip, ps.pct_above_zip_median, ps.assessment_to_sale_ratio\n"
        f"     FROM parcels p\n"
        f"     JOIN parcel_signals ps ON ps.par_id = p.par_id\n"
        f"     WHERE p.prop_addr ILIKE '%YORKTOWN%' AND p.prop_zip = '37211'\n"
        f"     ORDER BY ps.appeal_score DESC\n"
        f"     LIMIT 10\n"
        f"   For peer comparisons, use pct_above_zip_median and z_score_zip — no CTE needed.\n"
        f"10. CTE outer aliasing — if you MUST use a CTE despite rule 9, when a CTE named\n"
        f"    'peer_stats' is aliased as 'p' in outer SELECT, use 'p.column_name' not 'ps.'.\n"
        f"    WRONG: FROM peer_stats p ... SELECT ps.appeal_score\n"
        f"    RIGHT: FROM peer_stats p ... SELECT p.appeal_score\n"
        f"11. ONLY use tables from the SCHEMA below — NEVER invent table names.\n"
        f"    For zoning mismatch detection, use parcel_signals.zoning_lu_mismatch (BOOL)\n"
        f"    and parcel_signals.recommendation, NOT a join to 'zone_codes' or 'lu_codes'.\n"
        f"    ALWAYS include p.lu_desc and p.zoning in miszoned queries so the LLM can\n"
        f"    explain WHY the property is miszoned using its actual land use description.\n"
        f"    Miszoned query example:\n"
        f"      SELECT p.par_id, p.prop_addr, p.prop_zip, p.lu_code, p.lu_desc, p.zoning,\n"
        f"             p.totl_appr, ps.appeal_score, ps.recommendation,\n"
        f"             ps.zoning_lu_mismatch,\n"
        f"             CASE\n"
        f"               WHEN p.lu_code LIKE 'R%%' AND p.zoning NOT LIKE 'R%%'\n"
        f"                 THEN 'Residential land use (' || p.lu_code || ') in ' || p.zoning || ' zone'\n"
        f"               WHEN p.lu_code LIKE 'C%%' AND p.zoning NOT LIKE 'C%%'\n"
        f"                 THEN 'Commercial land use (' || p.lu_code || ') in ' || p.zoning || ' zone'\n"
        f"               WHEN p.lu_code LIKE 'I%%' AND p.zoning NOT LIKE 'I%%'\n"
        f"                 THEN 'Industrial land use (' || p.lu_code || ') in ' || p.zoning || ' zone'\n"
        f"               WHEN p.lu_code LIKE 'M%%' AND p.zoning NOT LIKE 'M%%'\n"
        f"                 THEN 'Mixed-use land use (' || p.lu_code || ') in ' || p.zoning || ' zone'\n"
        f"               WHEN p.lu_code NOT LIKE 'R%%' AND p.zoning LIKE 'R%%'\n"
        f"                 THEN 'Non-residential use (' || p.lu_code || ') in residential ' || p.zoning || ' zone'\n"
        f"               ELSE p.lu_code || ' use in ' || p.zoning || ' zone (mismatch)'\n"
        f"             END AS mismatch_reason\n"
        f"      FROM parcels p\n"
        f"      JOIN parcel_signals ps ON ps.par_id = p.par_id\n"
        f"      WHERE ps.zoning_lu_mismatch = TRUE\n"
        f"      ORDER BY ps.appeal_score DESC\n"
        f"      LIMIT 10\n\n"
        f"SCHEMA:\n{SCHEMA_CONTEXT}\n\n"
        f"{domain_section}"
        f"{few_shot}"
        f"QUESTION: {question}\n"
        f"SQL:"
    )

    msg = await chat_completion(
        [{"role": "user", "content": prompt}],
        system_prompt=(
            "You are a PostgreSQL expert for a property tax database. "
            "Return ONLY a valid SQL query with no markdown fences or commentary."
        ),
    )

    raw = msg.get("content", "").strip()
    sql = _extract_sql_from_response(raw)
    if sql:
        logger.info("Generated SQL:\n%s", sql)
    else:
        logger.warning("SQL extraction failed. Raw LLM response:\n%.500s", raw)
    return sql if sql else None


# ──────────────────────────────────────────────────────────────────────────────
# Safe SQL execution
# ──────────────────────────────────────────────────────────────────────────────

_DANGEROUS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|EXECUTE|COPY)\b",
    re.IGNORECASE,
)

# Authoritative table list — anything not here is a hallucination.
_KNOWN_TABLES = {
    # Core parcel tables
    "parcels", "parcel_signals", "building_permits", "building_characteristics",
    "building_footprints",
    # Pre-computed enrichment tables
    "parcel_flood_zone", "parcel_rail_proximity",
    # Raw spatial/reference tables
    "flood_zones", "cell_towers", "rail_lines", "zoning_districts",
    "correctional_facilities",
    # School tables
    "public_schools", "postsecondary_schools", "private_schools",
    "school_poverty_estimates", "school_performance",
    # Crime / police
    "crime_incidents", "police_reporting_areas",
    # Pre-computed views
    "v_assessment_sale_ratio", "v_condo_building_stats",
    # System tables
    "documents", "saved_queries", "query_feedback", "query_metrics",
}


def _validate_and_cap(sql: str) -> str:
    sql = sql.strip().rstrip(";")
    upper = sql.upper().lstrip()

    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise ValueError("Only SELECT/WITH queries are allowed")
    if _DANGEROUS.search(sql):
        raise ValueError("Query contains disallowed DML/DDL keywords")

    # Strip comments before table-reference validation so words inside
    # "-- ORDER BY the highest..." don't trigger false positives.
    sql_no_comments = re.sub(r"--[^\n]*", " ", sql)          # single-line
    sql_no_comments = re.sub(r"/\*.*?\*/", " ", sql_no_comments, flags=re.DOTALL)

    # Collect CTE names so they're not flagged as unknown tables
    cte_names = {
        m.group(1).lower()
        for m in re.finditer(r"\b(\w+)\s+AS\s*\(", sql_no_comments, re.IGNORECASE)
    }
    # Check every FROM/JOIN reference against the known schema
    for m in re.finditer(r"\b(?:FROM|JOIN)\s+(\w+)", sql_no_comments, re.IGNORECASE):
        ref = m.group(1).lower()
        if ref not in _KNOWN_TABLES and ref not in cte_names:
            raise ValueError(f"Unknown table referenced: {ref!r} — not in schema")

    if "LIMIT" not in sql.upper():
        sql += " LIMIT 25"
    return sql


async def execute_sql_safe(
    db: AsyncSession, sql: str
) -> tuple[list[dict], int]:
    """Validate and execute SQL. Returns (rows_as_dicts, count)."""
    sql = _validate_and_cap(sql)
    result = await db.execute(text(sql))
    keys = list(result.keys())
    rows = [dict(zip(keys, row)) for row in result.fetchall()]
    return rows, len(rows)


# ──────────────────────────────────────────────────────────────────────────────
# Query library – persistence & promotion
# ──────────────────────────────────────────────────────────────────────────────

async def save_query(
    db: AsyncSession,
    question: str,
    sql: str,
    result_count: int,
    result_preview: list[dict] | None = None,
) -> None:
    """Embed the question and save it alongside its SQL to saved_queries."""
    embedding = await embed_text(question)
    emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
    preview_json = json.dumps(
        (result_preview or [])[:3], default=str
    )
    try:
        await db.execute(
            text("""
                INSERT INTO saved_queries
                    (question, sql, result_count, result_preview, avg_rating, use_count, embedding, created_at)
                VALUES (:question, :sql, :result_count, :preview, 0.0, 0, CAST(:emb AS vector), NOW())
            """),
            {
                "question": question,
                "sql": sql,
                "result_count": result_count,
                "preview": preview_json,
                "emb": emb_str,
            },
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Could not save query to library: %s", exc)
        await db.rollback()


async def promote_query_rating(
    db: AsyncSession, question: str, rating: float
) -> None:
    """
    Update the rolling avg_rating for a saved query that matches this question.
    Called when the user submits feedback on a chat response.
    """
    try:
        await db.execute(
            text("""
                UPDATE saved_queries
                SET avg_rating = (avg_rating * use_count + :rating) / (use_count + 1),
                    use_count  = use_count + 1,
                    last_used  = NOW()
                WHERE question = :question
            """),
            {"question": question, "rating": float(rating)},
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Could not promote query rating: %s", exc)
        await db.rollback()
