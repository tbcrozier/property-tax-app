"""
Report service — runs the full analyst loop non-streaming, formats a
markdown report, saves it to data/reports/, and feeds learnings back
into the self-improvement loop.

Self-improvement after a report:
  - Every SQL query the analyst ran that returned rows is saved to
    saved_queries (with an embedding) so future chat requests can use
    it as a few-shot example.
  - The LLM distills key insights from the report into a short summary
    that gets appended to valuation_anomaly_guide.md and re-embedded,
    so the knowledge vector store grows richer over time.
"""

import logging
import os
import re
import time
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import chat_completion
from app.services.analyst_service import (
    AnalystState,
    SYSTEM_PROMPT_BASE,
    REACT_TOOL_INSTRUCTIONS,
    _parse_react_response,
    _tool_execute_sql,
    _tool_run_python,
    _tool_detect_anomalies,
    _tool_search_docs,
    _keyword_sql_bootstrap,
    _build_bootstrap_seed_message,
)

# Full system prompt including tool instructions — used for all non-streaming loops
_FULL_SYSTEM_PROMPT = SYSTEM_PROMPT_BASE + REACT_TOOL_INSTRUCTIONS

logger = logging.getLogger(__name__)

REPORTS_DIR = "data/reports"


# ──────────────────────────────────────────────────────────────────────────────
# Core: run analyst loop non-streaming, collect all results
# ──────────────────────────────────────────────────────────────────────────────

async def _run_analyst_non_streaming(
    db: AsyncSession,
    question: str,
    max_iterations: int = 10,
    bootstrap_anomalies: bool = True,
    seed_docs: list[dict] | None = None,
) -> dict:
    """
    Run the full agentic analyst loop and collect everything:
    - Final answer text
    - All SQL queries executed
    - All tool outputs
    - Row counts

    seed_docs: pre-fetched RAG results from the caller (avoids a duplicate
               vector search when the caller already ran search_documents).
               If None, this function fetches its own top-10 chunks.
    """
    from app.services.embed_service import search_documents

    # Seed with knowledge base — use caller-provided docs if available,
    # otherwise fetch top-10 chunks (more context = better reasoning).
    docs = seed_docs if seed_docs is not None else await search_documents(db, question, top_k=10)
    knowledge_ctx = ""
    if docs:
        knowledge_ctx = "\n\nRelevant knowledge:\n"
        for doc in docs:
            knowledge_ctx += f"\n[{doc['title']}]\n{doc['content']}\n"

    system_prompt = _FULL_SYSTEM_PROMPT + knowledge_ctx
    state = AnalystState()
    tool_outputs: list[dict] = []
    final_answer = ""

    # ── Bootstrap: pre-execute SQL based on question keywords ────────────────
    # Pre-execute a targeted query so the LLM synthesizes from real data
    # rather than having to autonomously generate and execute the first SQL.
    # The LLM then formats the results and may run follow-up queries.
    sql_bootstrap_result = await _keyword_sql_bootstrap(db, question, state)

    if bootstrap_anomalies or sql_bootstrap_result:
        if bootstrap_anomalies and not sql_bootstrap_result:
            logger.info("[LOOP] Bootstrapping with detect_anomalies...")
            sql_bootstrap_result = await _tool_detect_anomalies(
                db, lu_code=None, prop_zip=None, top_n=20, state=state
            )
            tool_label = "detect_anomalies"
        else:
            tool_label = "execute_sql"

        tool_outputs.append({
            "tool": tool_label,
            "args": {},
            "result": sql_bootstrap_result,
            "row_count": len(state.last_df) if state.last_df is not None else None,
        })
        state.steps += 1
        row_count = len(state.last_df) if state.last_df is not None else 0
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

    logger.info("[LOOP] Starting ReAct iterations (max=%d, bootstrap=%s)", max_iterations - 1, bootstrap_anomalies)

    for iteration in range(max_iterations - 1):
        state.steps += 1
        logger.info("[LOOP] ── Iteration %d/%d ─────────────────────────────", iteration + 1, max_iterations - 1)
        msg = await chat_completion(messages, system_prompt=system_prompt)
        content = msg.get("content", "")

        # Log first 300 chars of LLM response so we can see what it produced
        logger.info("[LOOP] LLM response (first 300 chars): %s", content[:300].replace("\n", " ↵ "))

        action_name, fa, args = _parse_react_response(content)
        logger.info("[LOOP] Parsed → action=%s | has_final_answer=%s | args=%s",
                    action_name, fa is not None, args)

        if fa is not None:
            # Guard: reject Final Answer if no SQL has been executed yet (not bootstrapped).
            # The LLM commonly reads RAG chunks or calls search_docs and then answers from
            # knowledge without ever touching the database — force it to run execute_sql first.
            sql_count = sum(1 for t in tool_outputs if t.get("tool") == "execute_sql")
            if not bootstrap_anomalies and sql_count == 0:
                logger.warning(
                    "[LOOP] LLM tried to write Final Answer without running any SQL (iteration %d) — rejecting",
                    iteration + 1,
                )
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": (
                    "You have NOT queried the database yet. Answering from documentation alone is NOT allowed.\n\n"
                    "You MUST call execute_sql to retrieve real parcel data before writing Final Answer. "
                    "Write a query that answers the user's question — use the exact LIMIT they requested, "
                    "include lu_desc so you can explain what type of property it is, and include all columns "
                    "needed to explain WHY each result matches.\n\n"
                    "Action: execute_sql\n"
                    "Action Input: {\"query\": \"<your SQL here>\"}"
                )})
                continue
            logger.info("[LOOP] Final Answer received at iteration %d", iteration + 1)
            final_answer = fa
            break

        messages.append({"role": "assistant", "content": content})

        if action_name == "execute_sql":
            logger.info("[TOOL] execute_sql → query: %s", args.get("query", "")[:200])
            result = await _tool_execute_sql(db, args.get("query", ""), state)
            logger.info("[TOOL] execute_sql result: %s", str(result)[:200])
        elif action_name == "run_python":
            logger.info("[TOOL] run_python → code: %s", args.get("code", "")[:100])
            result = await _tool_run_python(args.get("code", ""), state)
            logger.info("[TOOL] run_python result: %s", str(result)[:200])
        elif action_name == "detect_anomalies":
            logger.info("[TOOL] detect_anomalies → lu_code=%s, zip=%s, top_n=%s",
                        args.get("lu_code"), args.get("prop_zip"), args.get("top_n", 20))
            result = await _tool_detect_anomalies(
                db,
                lu_code=args.get("lu_code"),
                prop_zip=args.get("prop_zip"),
                top_n=args.get("top_n", 20),
                state=state,
            )
            logger.info("[TOOL] detect_anomalies returned %d rows", len(state.last_df) if state.last_df is not None else 0)
        elif action_name == "search_docs":
            # LLM uses many different key names (query, topic, q, domain, subject…)
            # Just grab the first non-empty string value from args, whatever the key.
            query = args.get("query") or args.get("topic") or args.get("q") or ""
            if not query:
                query = next((v for v in args.values() if isinstance(v, str) and v.strip()), "")
            logger.info("[TOOL] search_docs → query: %s", query)
            if not query:
                result = "search_docs requires a query string. Please retry with Action Input: {\"query\": \"your search term\"}"
            else:
                try:
                    result = await _tool_search_docs(db, query)
                except Exception as e:
                    logger.warning("[TOOL] search_docs failed: %s", e)
                    result = f"search_docs failed: {e}. Proceed with execute_sql instead."
            logger.info("[TOOL] search_docs returned %d chars", len(result))
        elif action_name is None:
            # Model output planning text without an action — nudge it forward
            logger.warning("[LOOP] No action detected — nudging LLM to use a tool")
            result = (
                "No action detected. You MUST call a tool before writing Final Answer. "
                "Respond with exactly:\n"
                "Action: <tool_name>\n"
                "Action Input: {\"key\": \"value\"}\n\n"
                "Available tools: execute_sql, search_docs, detect_anomalies, run_python\n"
                "DO NOT write Final Answer yet."
            )
        else:
            logger.warning("[LOOP] Unknown tool requested: %s", action_name)
            result = f"Unknown tool '{action_name}'. Available: execute_sql, detect_anomalies, run_python, search_docs"

        tool_outputs.append({
            "tool": action_name,
            "args": args,
            "result": result,
            "row_count": len(state.last_df) if state.last_df is not None else None,
        })

        messages.append({"role": "user", "content": f"Observation: {result}"})

    # If the LLM never wrote a Final Answer, ask it explicitly
    if not final_answer:
        logger.warning("[LOOP] Max iterations reached without Final Answer — asking explicitly")
        state.steps += 1
        msg = await chat_completion(
            messages + [{"role": "user", "content": (
                "You now have all the data you need. "
                "Write a complete analysis report starting with 'Final Answer:'. "
                "Include specific parcel IDs, addresses, anomaly scores, and recommendations."
            )}],
            system_prompt=system_prompt,
        )
        content = msg.get("content", "")
        _, final_answer, _ = _parse_react_response(content)
        if not final_answer:
            # Use raw content only if it looks like a real answer, not a
            # template/planning response (e.g. "Thought Process:" preamble).
            stripped = content.strip()
            _TEMPLATE_MARKERS = (
                "thought process",
                "to begin the analysis",
                "i will run a sql query",
                "once i have executed",
                "the specific query depends",
                "i'll query the database",
            )
            is_template = any(
                m in stripped.lower()[:200] for m in _TEMPLATE_MARKERS
            )
            final_answer = "" if is_template else stripped

    logger.info(
        "[LOOP] COMPLETE — steps=%d, sql_queries=%d, tools=%s, final_answer_len=%d",
        state.steps,
        len(state.sql_history),
        [t["tool"] for t in tool_outputs],
        len(final_answer),
    )
    if not final_answer:
        logger.warning("[LOOP] No final answer produced after all iterations")

    return {
        "final_answer": final_answer,
        "sql_history": state.sql_history,
        "tool_outputs": tool_outputs,
        "steps": state.steps,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Format as markdown report
# ──────────────────────────────────────────────────────────────────────────────

def _format_report(
    question: str,
    parcel_id: str | None,
    analyst_result: dict,
    latency_s: float,
) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Property Tax Analysis Report",
        f"**Generated:** {now}  ",
        f"**Question:** {question}  ",
    ]
    if parcel_id:
        lines.append(f"**Parcel ID:** {parcel_id}  ")
    lines += [
        f"**Analysis steps:** {analyst_result['steps']}  ",
        f"**Time:** {latency_s:.1f}s  ",
        "",
        "---",
        "",
        "## Summary & Findings",
        "",
        analyst_result["final_answer"] or "_No answer generated._",
        "",
        "---",
        "",
        "## Data Queries Executed",
        "",
    ]

    sql_queries = analyst_result["sql_history"]
    if sql_queries:
        for i, sql in enumerate(sql_queries, 1):
            lines.append(f"### Query {i}")
            lines.append(f"```sql\n{sql}\n```")
            lines.append("")
    else:
        lines.append("_No SQL queries were executed._")
        lines.append("")

    lines += [
        "---",
        "",
        "## Tool Execution Log",
        "",
    ]
    for step in analyst_result["tool_outputs"]:
        tool = step["tool"]
        row_count = step.get("row_count")
        count_str = f" ({row_count} rows)" if row_count is not None else ""
        lines.append(f"**{tool}{count_str}**")
        lines.append(f"\n{step['result']}\n")

    lines += [
        "---",
        "",
        "## Recommendations",
        "",
        "_See Summary & Findings above for specific recommendations._",
        "",
        "---",
        f"_Report generated by Property Tax Analyst AI — Davidson County, Nashville TN_",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Self-improvement: extract learnings from the report
# ──────────────────────────────────────────────────────────────────────────────

async def _extract_report_learnings(
    db: AsyncSession,
    question: str,
    analyst_result: dict,
    report_content: str,
) -> None:
    """
    Feed the report's findings back into the self-improvement loop:
    1. Save each successful SQL query to saved_queries (with embedding)
       so future chat requests get them as few-shot examples.
    2. Ask the LLM to distill key insights and append them to
       valuation_anomaly_guide.md, then re-embed.
    """
    from app.services.sql_service import save_query
    from app.services.embed_service import embed_document

    # 1. Save SQL queries that returned data.
    # Use a separate sql_idx counter — sql_history only tracks execute_sql calls,
    # not all tool calls, so the tool_outputs enumerate index can't be used directly.
    # sql_history only appends when execute_sql returns rows (see _tool_execute_sql:
    # "if not rows: return" fires before the append). sql_idx must mirror that
    # condition exactly — increment only on row-returning calls, never on empty ones.
    sql_idx = 0
    for step in analyst_result["tool_outputs"]:
        if step["tool"] == "execute_sql" and step.get("row_count", 0):
            if sql_idx < len(analyst_result["sql_history"]):
                sql = analyst_result["sql_history"][sql_idx]
                q_label = question if sql_idx == 0 else f"{question} (step {sql_idx + 1})"
                await save_query(
                    db,
                    question=q_label,
                    sql=sql,
                    result_count=step["row_count"],
                )
            sql_idx += 1

    # 2. Distill insights into the knowledge base
    if not analyst_result["final_answer"]:
        return

    prompt = (
        f"The following is a property tax analysis report for Davidson County, Nashville TN.\n\n"
        f"REPORT:\n{analyst_result['final_answer'][:2000]}\n\n"
        f"Extract 2-3 concrete, specific insights from this report that would help "
        f"future analysis. Focus on:\n"
        f"- Specific thresholds or patterns found (e.g. 'ZIP 37206 residential parcels "
        f"show 35% higher value-per-acre than county median')\n"
        f"- Data quality issues discovered\n"
        f"- Effective filters or joins that worked well\n\n"
        f"Write as a short markdown section (## heading, bullet points, under 200 words). "
        f"Only include concrete findings, not generic advice."
    )

    try:
        msg = await chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt="You are a property tax data analyst. Extract specific, concrete findings only.",
        )
        insights = msg.get("content", "").strip()
        if not insights:
            return

        knowledge_path = "data/knowledge/valuation_anomaly_guide.md"
        if not os.path.exists(knowledge_path):
            return

        with open(knowledge_path, encoding="utf-8") as f:
            existing = f.read()
        updated = (
            existing
            + f"\n\n<!-- auto-insight from report: {datetime.utcnow().strftime('%Y-%m-%d')} -->\n"
            + insights
            + "\n"
        )
        with open(knowledge_path, "w", encoding="utf-8") as f:
            f.write(updated)

        await embed_document(
            db,
            title="Valuation Anomaly Guide",
            source="valuation_anomaly_guide.md",
            content=updated,
        )
        logger.info("Appended report insights to valuation_anomaly_guide.md and re-embedded")
    except Exception as exc:
        logger.warning("Could not extract report learnings: %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────

async def generate_report(
    db: AsyncSession,
    question: str,
    parcel_id: str | None = None,
    max_iterations: int = 10,
) -> dict:
    """
    Run a full analysis, save a markdown report, feed learnings back
    into the self-improvement loop.

    Returns:
        {
            "report_path": str,
            "summary": str,        # first 500 chars of findings
            "sql_queries": list[str],
            "parcels_analyzed": int,
        }
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Build question with parcel context if provided
    full_question = question
    if parcel_id:
        full_question = f"Parcel {parcel_id}: {question}"

    start = time.time()
    analyst_result = await _run_analyst_non_streaming(
        db, full_question, max_iterations, bootstrap_anomalies=True
    )
    latency_s = time.time() - start

    report_md = _format_report(question, parcel_id, analyst_result, latency_s)

    # Save report file
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_q = re.sub(r"[^a-z0-9]+", "_", question.lower())[:40]
    filename = f"{timestamp}_{safe_q}.md"
    report_path = os.path.join(REPORTS_DIR, filename)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    logger.info("Report saved: %s", report_path)

    # Feed learnings back asynchronously (don't block the response)
    try:
        await _extract_report_learnings(db, question, analyst_result, report_md)
    except Exception as exc:
        logger.warning("Report learning extraction failed: %s", exc)

    # Count parcels analyzed from SQL results
    parcels_analyzed = sum(
        s.get("row_count", 0) or 0
        for s in analyst_result["tool_outputs"]
        if s["tool"] in ("execute_sql", "detect_anomalies")
    )

    return {
        "report_path": report_path,
        "summary": (analyst_result["final_answer"] or "")[:500],
        "sql_queries": analyst_result["sql_history"],
        "parcels_analyzed": parcels_analyzed,
    }
