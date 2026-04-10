import json
import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import chat_completion
from app.services.embed_service import embed_document, search_documents
from app.utils.code_executor import SQLSafetyError, execute_python_on_df, validate_sql

DB_SCHEMA = """
DATABASE SCHEMA — Davidson County Property Tax (PostgreSQL + PostGIS + pgvector)

TABLE: parcels
  par_id          TEXT PK       — unique parcel identifier
  prop_addr       TEXT          — street address
  prop_city       TEXT
  prop_zip        TEXT          — 5-digit ZIP
  owner_name      TEXT
  lu_code         TEXT          — land use code (R=residential, C=commercial, I=industrial...)
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
  appeal_score            FLOAT   — composite 0-100 score
  recommendation          TEXT    — STRONG_CANDIDATE | MODERATE_CANDIDATE | REVIEW_ZONING | NORMAL

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

USEFUL PATTERNS:
- value_per_acre = totl_appr / NULLIF(acres, 0)
- Peer comparison: PARTITION BY lu_code, prop_zip
- Window median: PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ...) OVER (PARTITION BY ...)
- Over-assessed vs sale: totl_appr > sale_price AND sale_price > 0
- Join building_characteristics: ON bc.apn = p.par_id
- Pre-computed scores: JOIN parcel_signals ps ON ps.par_id = p.par_id
"""

SYSTEM_PROMPT_BASE = f"""{DB_SCHEMA}

You are an expert property tax analyst for Davidson County, Nashville TN.
You have access to tools to query the database and analyze data.
Always ground your answers in actual data from the database.
When you find anomalies, explain WHY they are anomalous with specific numbers.
Use parcel_signals table for fast pre-computed scores when doing large scans.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Execute a SELECT SQL query against the property tax database. "
                "Returns results as a markdown table. Use this to explore data, "
                "find patterns, and retrieve specific parcels."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL SELECT query to execute.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": (
                "Run Python code against the last SQL result DataFrame (variable: df). "
                "Use pandas (pd) and numpy (np). Print results. "
                "Good for aggregations, sorting, charts descriptions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute. Use print() to output results.",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_anomalies",
            "description": (
                "Run IsolationForest multi-dimensional anomaly detection on parcels. "
                "Detects properties that are statistically unusual across multiple "
                "features simultaneously. Specify lu_code and/or prop_zip to narrow scope."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lu_code": {
                        "type": "string",
                        "description": "Filter by land use code (optional).",
                    },
                    "prop_zip": {
                        "type": "string",
                        "description": "Filter by ZIP code (optional).",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top anomalies to return (default 20).",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": (
                "Search the knowledge base for relevant documentation, "
                "assessment rules, appeal procedures, or query examples."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string.",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


@dataclass
class AnalystState:
    last_df: pd.DataFrame | None = None
    sql_history: list[str] = field(default_factory=list)
    steps: int = 0


async def _tool_execute_sql(db: AsyncSession, query: str, state: AnalystState) -> str:
    try:
        safe_query = validate_sql(query)
    except SQLSafetyError as e:
        return f"SQL Safety Error: {e}"

    try:
        result = await db.execute(text(safe_query))
        rows = result.fetchall()
        cols = list(result.keys())
    except Exception as e:
        return f"SQL Error: {e}"

    if not rows:
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

    from tabulate import tabulate

    table = tabulate(top, headers="keys", tablefmt="pipe", showindex=False, floatfmt=".2f")
    return (
        f"**IsolationForest detected {top_n} most anomalous parcels** "
        f"(lower score = more anomalous, trained on {len(df)} parcels)\n\n{table}"
    )


async def _tool_search_docs(db: AsyncSession, query: str) -> str:
    docs = await search_documents(db, query, top_k=3)
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

    docs = await search_documents(db, question, top_k=5)
    knowledge_ctx = ""
    if docs:
        titles = [d["title"] for d in docs]
        yield {"type": "knowledge", "titles": titles}
        knowledge_ctx = "\n\nRelevant knowledge from vector store:\n"
        for doc in docs:
            knowledge_ctx += f"\n[{doc['title']}]\n{doc['content']}\n"

    system_prompt = SYSTEM_PROMPT_BASE + knowledge_ctx
    messages: list[dict] = [{"role": "user", "content": question}]
    state = AnalystState()

    for iteration in range(max_iterations):
        state.steps += 1
        yield {"type": "progress", "message": f"Iteration {iteration + 1}/{max_iterations}..."}

        try:
            msg = await chat_completion(messages, system_prompt=system_prompt, tools=TOOLS)
        except Exception as e:
            yield {"type": "error", "message": f"LLM error: {e}"}
            return

        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            # LLM produced a final answer
            yield {"type": "thinking", "content": msg.get("content", "")}
            yield {
                "type": "answer",
                "content": msg.get("content", ""),
            }
            yield {
                "type": "done",
                "steps": state.steps,
                "sql_queries": state.sql_history,
            }
            return

        # Execute each tool call
        messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": tool_calls})

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            raw_args = tc["function"].get("arguments", "{}")
            try:
                args: dict[str, Any] = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}

            yield {"type": "tool_call", "tool": fn_name, "args": args}

            if fn_name == "execute_sql":
                result = await _tool_execute_sql(db, args.get("query", ""), state)
            elif fn_name == "run_python":
                result = await _tool_run_python(args.get("code", ""), state)
            elif fn_name == "detect_anomalies":
                result = await _tool_detect_anomalies(
                    db,
                    lu_code=args.get("lu_code"),
                    prop_zip=args.get("prop_zip"),
                    top_n=args.get("top_n", 20),
                    state=state,
                )
            elif fn_name == "search_docs":
                result = await _tool_search_docs(db, args.get("query", ""))
            else:
                result = f"Unknown tool: {fn_name}"

            row_count = len(state.last_df) if state.last_df is not None else None
            yield {"type": "tool_done", "tool": fn_name, "row_count": row_count}

            messages.append(
                {
                    "role": "tool",
                    "content": result,
                }
            )

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
