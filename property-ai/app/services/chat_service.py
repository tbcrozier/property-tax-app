"""
Unified chat service — single entry point for all question types.

Flow for every request:

  Step 1 — INTENT CLASSIFICATION
    keyword pass → DATA (default) | REPORT

  Step 2 — RAG (always runs first, feeds fallback context)
    vector search on knowledge docs

  Step 3 — Intent-specific data gathering

    DATA (all non-report questions):
      ReAct agentic loop — always runs, no SQL fast path.
      The LLM drives its own investigation using tools:
        execute_sql, detect_anomalies, run_python, search_docs
      Up to 8 iterations. If it produces a Final Answer → return it.
      If ReAct fails or produces nothing → fall back to RAG-only answer.

    REPORT:
      report_service full loop — bootstraps detect_anomalies, saves .md,
      extracts SQL + findings back into knowledge base

  Step 4 — RAG-only fallback (DATA only, only reached if ReAct failed)
    system prompt = RAG chunks + any parcel analysis data
    LLM writes best-effort answer from knowledge docs alone
"""

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import chat_completion
from app.schemas import ChatRequest, ChatResponse
from app.services.analytics_service import identify_knowledge_gaps, update_query_metrics
from app.services.embed_service import search_documents
from app.services.intent_router import (
    DATA, REPORT,
    classify_intent, extract_parcel_id,
)
from app.services.parcel_service import get_comprehensive_parcel_analysis
from app.services.report_service import generate_report, _run_analyst_non_streaming

logger = logging.getLogger(__name__)

_METRICS_REFRESH_INTERVAL = 3600
_last_metrics_refresh = 0.0


async def handle_chat(db: AsyncSession, request: ChatRequest) -> ChatResponse:
    global _last_metrics_refresh

    question = request.messages[-1].content if request.messages else ""
    parcel_id = extract_parcel_id(question, request.parcel_id)
    context_parts: list[str] = []

    # ── Periodic metrics refresh ──────────────────────────────────────────────
    if time.time() - _last_metrics_refresh > _METRICS_REFRESH_INTERVAL:
        await update_query_metrics(db)
        _last_metrics_refresh = time.time()

    # ── Step 1: Classify intent ───────────────────────────────────────────────
    intent = await classify_intent(question)
    logger.info("Intent: %s | Question: %.80s", intent, question)

    # ── Step 2: RAG — fetched once here, passed into ReAct loop ─────────────
    # top_k=10 gives the LLM a broad knowledge base to reason from.
    # Sequential (not asyncio.gather) — both calls use the same AsyncSession
    # and concurrent operations on one session raise an error.
    logger.info("[RAG] Searching knowledge base (top_k=10)...")
    docs = await search_documents(db, question, top_k=10)
    logger.info("[RAG] Found %d documents: %s", len(docs), [d["title"] for d in docs])
    gaps = await identify_knowledge_gaps(db)

    rag_context = ""
    if docs:
        rag_context = "\nRELEVANT KNOWLEDGE BASE:\n"
        for doc in docs:
            rag_context += f"[{doc['title']}]\n{doc['content']}\n\n"
        context_parts.append(rag_context)

    if gaps:
        context_parts.append("\nRecent feedback highlights these weak areas:")
        for gap in gaps[:2]:
            context_parts.append(
                f"- '{gap['topic']}' (avg rating {gap['avg_rating']}, "
                f"{gap['query_count']} queries) — be extra thorough here."
            )

    # ── Step 3: Intent-specific data gathering ────────────────────────────────

    if intent == DATA:
        # Always run the ReAct agentic loop — no SQL fast path.
        # The LLM uses execute_sql, search_docs, detect_anomalies, and
        # run_python to investigate the question across multiple iterations,
        # then writes a Final Answer grounded in everything it found.
        logger.info("[REACT] Starting ReAct loop (max_iterations=8, bootstrap=True)")
        try:
            analyst_result = await _run_analyst_non_streaming(
                db, question, max_iterations=8, bootstrap_anomalies=True,
                seed_docs=docs,
            )
            logger.info(
                "[REACT] Loop finished — steps=%d, sql_queries=%d, tools_called=%s, has_answer=%s",
                analyst_result["steps"],
                len(analyst_result["sql_history"]),
                [s["tool"] for s in analyst_result["tool_outputs"]],
                bool(analyst_result["final_answer"]),
            )
            if analyst_result["final_answer"]:
                result_count = sum(
                    s.get("row_count", 0) or 0
                    for s in analyst_result["tool_outputs"]
                )
                logger.info("[REACT] Returning data-grounded answer (result_count=%d)", result_count)
                return ChatResponse(
                    answer=analyst_result["final_answer"],
                    sources=[d["source"] for d in docs],
                    sql_used=analyst_result["sql_history"][0] if analyst_result["sql_history"] else None,
                    result_count=result_count,
                )
            logger.warning("[REACT] Loop produced no final answer — falling back to RAG-only")
        except Exception as exc:
            logger.warning("[REACT] Loop failed: %s — falling back to RAG", exc)
            await db.rollback()

        # Parcel analysis — only reached if ReAct failed/produced nothing.
        # Enriches the RAG-only fallback answer with structured parcel data.
        if parcel_id:
            try:
                analysis = await get_comprehensive_parcel_analysis(db, parcel_id)
                if analysis:
                    context_parts.append(_format_parcel_context(parcel_id, analysis))
            except Exception as exc:
                logger.warning("Parcel analysis failed for %s: %s", parcel_id, exc)

    elif intent == REPORT:
        try:
            report_result = await generate_report(
                db,
                question=question,
                parcel_id=parcel_id,
                max_iterations=10,
            )
            answer = (
                f"I've completed a full analysis and saved the report to "
                f"`{report_result['report_path']}`.\n\n"
                f"**Summary:**\n{report_result['summary']}\n\n"
                f"**Queries run:** {len(report_result['sql_queries'])}  \n"
                f"**Parcels analyzed:** {report_result['parcels_analyzed']}"
            )
            return ChatResponse(
                answer=answer,
                sources=[d["source"] for d in docs],
                sql_used=None,
                result_count=report_result["parcels_analyzed"],
            )
        except Exception as exc:
            logger.warning("Report failed, falling back to chat: %s", exc)
            context_parts.append(f"\nNote: Report generation failed: {exc}")

    # ── Step 4: RAG-only fallback ─────────────────────────────────────────────
    # Only reached when ReAct failed or produced no answer.
    # Uses whatever knowledge context is available (RAG chunks + parcel data).
    system_prompt = (
        "You are a property tax analyst for Davidson County, Nashville TN. "
        "Answer the user's question directly and concisely. "
        "Do NOT write SQL queries in your answer. "
        "Do NOT say you cannot run queries. "
        "Do NOT write a 'Thought process' or planning steps. "
        "Just answer using whatever context is available.\n\n"
    )
    if context_parts:
        system_prompt += "CONTEXT:\n" + "\n".join(context_parts)

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    msg = await chat_completion(messages, system_prompt=system_prompt)

    return ChatResponse(
        answer=msg.get("content", ""),
        sources=[d["source"] for d in docs],
        sql_used=None,
        result_count=None,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_parcel_context(parcel_id: str, analysis) -> str:
    p = analysis.parcel
    a = analysis.appeal
    lines = [
        f"\nPARCEL {parcel_id} ({p.prop_addr or 'unknown address'}):",
        f"- Total Appraised: ${p.totl_appr:,.0f}" if p.totl_appr else "",
        f"- Appeal Score: {a.appeal_score:.1f}/100",
        f"- Overall Risk Score: {analysis.overall_risk_score:.1f}/100",
        f"- Recommendation: {a.recommendation}",
        f"- % Above ZIP Median: {(a.pct_above_zip_median or 0) * 100:.1f}%",
        f"- Assessment/Sale Ratio: {a.assessment_to_sale_ratio or 'N/A'}",
        f"- Zoning/LU Mismatch: {a.zoning_lu_mismatch}",
    ]
    if analysis.building_permits.count:
        bp = analysis.building_permits
        lines.append(
            f"- Permits: {bp.count} total, ${bp.total_cost:,.0f} cost, "
            f"{bp.recent_permits} recent"
        )
    if analysis.flood_zone.in_flood_zone:
        fz = analysis.flood_zone
        lines.append(f"- Flood Zone: {fz.zone_type} ({fz.flood_risk} risk)")
    if analysis.cell_towers.nearby_towers:
        ct = analysis.cell_towers
        lines.append(
            f"- Cell Towers: {ct.nearby_towers} nearby, closest {ct.closest_distance:.0f}m"
        )
    if analysis.railroads.nearby_railroads:
        rr = analysis.railroads
        lines.append(
            f"- Rail Lines: {rr.nearby_railroads} nearby, closest {rr.closest_distance:.0f}m"
        )
    if analysis.assessment_errors:
        errs = "; ".join(f"{e.error_type}({e.severity})" for e in analysis.assessment_errors)
        lines.append(f"- Assessment Errors: {errs}")
    return "\n".join(l for l in lines if l)
