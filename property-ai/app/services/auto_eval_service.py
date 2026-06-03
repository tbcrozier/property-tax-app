"""
Automatic response evaluation — no user input required.

Two-layer scoring runs in the background after every chat response:

Layer 1 — Implicit signals (instant, zero cost)
  Combines observable facts about the response into a score 1.0-5.0:
  - Did SQL run and return rows?         → strong positive
  - Did SQL fail or return nothing?      → negative
  - Was the answer long and specific?    → mild positive
  - Was the answer short/generic?        → mild negative
  - Was a parcel_id given and used?      → positive
  - Did the same question appear recently? → negative (user wasn't satisfied)

Layer 2 — LLM self-evaluation (async, one extra LLM call)
  The LLM grades its own answer against the question:
  - Did it use actual data or just give generic SQL guidance?
  - Was the question actually answered?
  - Returns a score 1-5 with a one-line reason.

Final effective_score = average(implicit, llm_eval)
  - If user later submits a manual rating it overrides both.

The effective score is then used to:
  - promote_query_rating() if score >= 4  → SQL reused as few-shot example
  - maybe_improve_knowledge() if score <= 2 → docs get rewritten
"""

import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import chat_completion
from app.models import QueryFeedback

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Layer 1: Implicit signal scoring
# ──────────────────────────────────────────────────────────────────────────────

async def implicit_score(
    db: AsyncSession,
    question: str,
    answer: str,
    sql_used: str | None,
    result_count: int | None,
    parcel_id: str | None,
) -> tuple[float, str]:
    """
    Compute a score 1.0-5.0 purely from observable signals.
    Returns (score, reason_string).
    """
    score = 3.0
    reasons: list[str] = []

    # SQL ran and returned real data
    if sql_used and result_count and result_count > 0:
        score += 1.0
        reasons.append(f"SQL returned {result_count} rows")
    elif sql_used and (result_count == 0 or result_count is None):
        score -= 1.0
        reasons.append("SQL returned no rows")
    elif not sql_used and _looks_like_data_question(question):
        score -= 0.5
        reasons.append("data question but no SQL was executed")

    # Answer length/specificity
    if len(answer) > 800:
        score += 0.5
        reasons.append("detailed answer")
    elif len(answer) < 200:
        score -= 0.5
        reasons.append("very short answer")

    # Parcel context was used
    if parcel_id and parcel_id.lower() in answer.lower():
        score += 0.25
        reasons.append("answer references the requested parcel")

    # Deflection patterns — LLM gave SQL instructions instead of data
    deflection_phrases = [
        "here is a sql query",
        "you can run this query",
        "use this sql",
        "the following query",
        "run the following",
        "execute this",
    ]
    if any(p in answer.lower() for p in deflection_phrases):
        score -= 1.5
        reasons.append("answer contains SQL instructions instead of data")

    # Check if this exact question was asked recently (user re-asking = dissatisfied)
    try:
        from sqlalchemy import text as sqla_text
        result = await db.execute(
            sqla_text("""
                SELECT COUNT(*) FROM query_feedback
                WHERE query_text = :q
                  AND created_at > NOW() - INTERVAL '10 minutes'
            """),
            {"q": question},
        )
        recent_count = result.scalar_one()
        if recent_count >= 2:
            score -= 0.75
            reasons.append("question asked multiple times recently")
    except Exception:
        pass

    score = round(max(1.0, min(5.0, score)), 2)
    return score, "; ".join(reasons) if reasons else "baseline"


def _looks_like_data_question(question: str) -> bool:
    keywords = {
        "list", "show", "find", "top", "bottom", "which", "how many",
        "count", "highest", "lowest", "parcels", "properties", "ids",
    }
    q = question.lower()
    return any(kw in q for kw in keywords)


# ──────────────────────────────────────────────────────────────────────────────
# Layer 2: LLM self-evaluation
# ──────────────────────────────────────────────────────────────────────────────

async def llm_self_eval(
    question: str,
    answer: str,
    sql_used: str | None,
    result_count: int | None,
) -> tuple[float, str]:
    """
    Ask the LLM to grade its own response. Returns (score 1-5, reason).
    """
    data_context = ""
    if sql_used:
        data_context = (
            f"\nThe system executed this SQL: {sql_used}\n"
            f"It returned {result_count or 0} rows.\n"
        )

    prompt = (
        f"You are evaluating the quality of a property tax analyst's response.\n\n"
        f"USER QUESTION: {question}\n"
        f"{data_context}"
        f"ASSISTANT ANSWER:\n{answer}\n\n"
        f"Score this response 1-5 based on:\n"
        f"- 5: Directly answers with specific data (actual parcel IDs, values, addresses)\n"
        f"- 4: Answers well with some specifics\n"
        f"- 3: Partially answers but lacks specific data or is too generic\n"
        f"- 2: Gives SQL instructions or explains how to query instead of answering\n"
        f"- 1: Does not answer the question at all\n\n"
        f"Reply in this exact format (nothing else):\n"
        f"SCORE: <number>\n"
        f"REASON: <one sentence>"
    )

    try:
        # 60s timeout — self-eval runs as a background task and should not
        # queue behind active analyst requests on a single Ollama instance.
        msg = await asyncio.wait_for(
            chat_completion(
                [{"role": "user", "content": prompt}],
                system_prompt="You are a strict response quality evaluator. Follow the format exactly.",
            ),
            timeout=60,
        )
        content = msg.get("content", "").strip()
        score_line = next(
            (l for l in content.splitlines() if l.startswith("SCORE:")), None
        )
        reason_line = next(
            (l for l in content.splitlines() if l.startswith("REASON:")), None
        )
        score = float(score_line.split(":")[1].strip()) if score_line else 3.0
        reason = reason_line.split(":", 1)[1].strip() if reason_line else "llm eval"
        score = max(1.0, min(5.0, score))
        return score, reason
    except asyncio.TimeoutError:
        logger.warning("LLM self-eval timed out after 60s — skipping")
        return 3.0, "llm eval timed out"
    except Exception as exc:
        logger.warning("LLM self-eval failed: %s", exc)
        return 3.0, "llm eval unavailable"


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point — called as a background task after every response
# ──────────────────────────────────────────────────────────────────────────────

async def run_auto_eval(
    feedback_id: int,
    question: str,
    answer: str,
    sql_used: str | None,
    result_count: int | None,
    parcel_id: str | None,
) -> None:
    """
    Background task: score the response, save scores to query_feedback,
    then trigger SQL promotion or knowledge improvement as appropriate.
    """
    from app.db import AsyncSessionLocal
    from app.services.sql_service import promote_query_rating
    from app.services.knowledge_service import maybe_improve_knowledge

    async with AsyncSessionLocal() as db:
        # Layer 1 — implicit signals
        implicit, implicit_reason = await implicit_score(
            db, question, answer, sql_used, result_count, parcel_id
        )

        # Layer 2 — LLM self-eval
        llm_score, llm_reason = await llm_self_eval(
            question, answer, sql_used, result_count
        )

        # Average both layers
        effective = round((implicit + llm_score) / 2, 2)
        combined_reason = f"implicit({implicit}: {implicit_reason}) | llm({llm_score}: {llm_reason})"

        # Persist scores back to the feedback record
        try:
            result = await db.execute(
                select(QueryFeedback).where(QueryFeedback.id == feedback_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.auto_score = effective
                record.auto_score_reason = combined_reason
                # Only set rating if user hasn't rated yet
                if record.rating == 0:
                    record.rating = round(effective)
                db.add(record)
                await db.commit()
        except Exception as exc:
            logger.warning("Could not save auto_score: %s", exc)
            await db.rollback()

        logger.info(
            "Auto-eval feedback_id=%d: implicit=%.1f llm=%.1f effective=%.1f",
            feedback_id, implicit, llm_score, effective,
        )

        # Self-improvement actions
        if sql_used and effective >= 4.0:
            await promote_query_rating(db, question, effective)

        if effective <= 2.0:
            updated = await maybe_improve_knowledge(db)
            if updated:
                logger.info("Knowledge auto-improved after low score: %s", updated)
