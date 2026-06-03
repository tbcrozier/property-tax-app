"""
Intent router — classifies a user question into one of two intents:

  DATA    — everything that isn't a report:
              1. Try SQL (fast path, one query)
              2. If SQL fails or returns nothing → escalate to ReAct loop
              3. If ReAct fails → answer from RAG only
              Covers: simple lookups, parcel analysis, anomaly detection,
              multi-step investigation, and pure definition questions.

  REPORT  — generate and save a full markdown report
              Non-streaming, bootstraps detect_anomalies automatically,
              saves .md, feeds SQL + findings back into knowledge base.

Routing strategy:
  1. Keyword pass  — fast, no LLM call, handles clear-cut cases
  2. LLM fallback  — only fires when keywords are ambiguous/absent,
                     defaults to DATA if uncertain

Data signals (street address, ZIP, parcel ID, value terms, flood/crime/
school/permit/zoning terms) are checked before any other keyword match
to prevent mis-routing.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Intent constants ──────────────────────────────────────────────────────────
DATA   = "DATA"
REPORT = "REPORT"

# Legacy aliases kept so any code still importing these doesn't break
CONVERSATIONAL = DATA
ANALYSIS       = DATA

# ── Parcel ID pattern — used only by extract_parcel_id ───────────────────────
_PARCEL_RE = re.compile(r"\b\d{5,15}\b")

# ── Keyword maps ─────────────────────────────────────────────────────────────
_REPORT_KW = {
    "report", "generate report", "full analysis", "deep analysis",
    "deep dive", "detailed analysis", "anomaly report", "run analysis",
    "analyze all", "comprehensive report", "create report", "build report",
    "save report", "write report",
}


def _keyword_classify(question: str) -> str | None:
    """
    Fast keyword pass. Returns DATA or REPORT, never None for most questions.

    Priority: REPORT → DATA (everything else)
    Data signals (address, ZIP, parcel ID, value terms, etc.) are checked
    first so they always route to DATA regardless of phrasing.
    Default is DATA — the downstream pipeline handles graceful fallback
    (SQL → ReAct loop → RAG-only) so no question is left unanswered.
    """
    q = question.lower()

    if any(kw in q for kw in _REPORT_KW):
        return REPORT

    # Everything else is DATA — no CONVERSATIONAL or ANALYSIS distinction.
    # The DATA pipeline tries SQL first, escalates to ReAct if needed,
    # and falls back to RAG-only if both fail.
    return DATA


async def classify_intent(question: str) -> str:
    """Classify question intent via keyword pass. Always returns DATA or REPORT."""
    intent = _keyword_classify(question)
    logger.debug("Intent: %s for '%s'", intent, question[:60])
    return intent


def extract_parcel_id(question: str, request_parcel_id: str | None) -> str | None:
    """
    Return a parcel ID from either the request field or the question text.
    Prefers the explicit request field if provided.
    """
    if request_parcel_id:
        return request_parcel_id
    match = _PARCEL_RE.search(question)
    return match.group() if match else None
