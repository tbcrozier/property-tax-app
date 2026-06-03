"""
Self-improving knowledge base service.

When enough low-rated queries accumulate around a topic, the LLM generates
improved documentation content, which is:
  1. Appended to the relevant .md file in data/knowledge/
  2. Re-embedded into the vector store so future queries benefit immediately.
"""

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import chat_completion
from app.services.analytics_service import identify_knowledge_gaps
from app.services.embed_service import embed_document

logger = logging.getLogger(__name__)

_DOCS_DIR = Path("data/knowledge")

# Map topic keywords → the knowledge file most likely to need updating
_TOPIC_TO_FILE: dict[str, str] = {
    "flood": "flood_zones.md",
    "flooding": "flood_zones.md",
    "fema": "flood_zones.md",
    "zoning": "nashville_zoning.md",
    "zone": "nashville_zoning.md",
    "permit": "property_tax_glossary.md",
    "permits": "property_tax_glossary.md",
    "assessment": "valuation_anomaly_guide.md",
    "assessed": "valuation_anomaly_guide.md",
    "appeal": "valuation_anomaly_guide.md",
    "appeals": "valuation_anomaly_guide.md",
    "value": "valuation_anomaly_guide.md",
    "tax": "property_tax_glossary.md",
    "railroad": "nashville_zoning.md",
    "rail": "nashville_zoning.md",
    "cell": "valuation_anomaly_guide.md",
    "tower": "valuation_anomaly_guide.md",
    "crime": "nashville_zoning.md",
    "school": "nashville_zoning.md",
    "parcel": "query_examples.md",
    "query": "query_examples.md",
    "signal": "valuation_anomaly_guide.md",
    "mismatch": "nashville_zoning.md",
    "comparable": "valuation_anomaly_guide.md",
    "comps": "valuation_anomaly_guide.md",
}


async def maybe_improve_knowledge(
    db: AsyncSession,
    min_query_count: int = 3,
    min_avg_rating: float = 2.5,
) -> list[str]:
    """
    Scan for knowledge gaps and, for each significant gap, have the LLM write
    an improved section that gets appended to the relevant .md file and
    re-embedded into the vector store.

    Returns a list of doc filenames that were updated.
    """
    gaps = await identify_knowledge_gaps(
        db, min_query_count=min_query_count, min_avg_rating=min_avg_rating
    )
    if not gaps:
        return []

    updated: list[str] = []

    # Process at most 2 gaps per call to limit LLM usage
    for gap in gaps[:2]:
        topic = gap["topic"]
        doc_file = _TOPIC_TO_FILE.get(topic)
        if not doc_file:
            continue

        doc_path = _DOCS_DIR / doc_file
        if not doc_path.exists():
            logger.warning("Knowledge file not found: %s", doc_path)
            continue

        existing = doc_path.read_text(encoding="utf-8")

        # Skip if this topic was already auto-improved recently (prevents bloat from
        # repeated low-score events writing duplicate sections).
        marker = f"<!-- auto-improved: topic={topic},"
        if marker in existing:
            logger.info("Knowledge doc '%s' already has auto-improved section for '%s' — skipping", doc_file, topic)
            continue

        sample_qs = "\n".join(f"- {q}" for q in gap["sample_queries"])

        prompt = (
            f"You are a property tax knowledge base editor for Davidson County, Nashville TN.\n"
            f"Users keep asking questions about '{topic}' and the responses are rated poorly.\n\n"
            f"SAMPLE QUERIES THAT GOT LOW RATINGS:\n{sample_qs}\n\n"
            f"EXISTING DOCUMENTATION (first 2000 chars):\n{existing[:2000]}\n\n"
            f"Write a concise markdown section (under 300 words) that directly addresses "
            f"the gaps shown by those queries. Use specific Nashville/Davidson County facts "
            f"where possible. Format with a ## heading."
        )

        msg = await chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt=(
                "You are a concise property tax documentation expert. "
                "Write factual, specific content about Davidson County, Nashville TN."
            ),
        )
        new_section = msg.get("content", "").strip()
        if not new_section:
            continue

        # Append new content and re-embed
        updated_content = (
            existing
            + f"\n\n<!-- auto-improved: topic={topic}, "
            f"avg_rating={gap['avg_rating']}, queries={gap['query_count']} -->\n"
            + new_section
            + "\n"
        )
        doc_path.write_text(updated_content, encoding="utf-8")

        title = doc_file.replace("_", " ").replace(".md", "").title()
        await embed_document(db, title=title, source=doc_file, content=updated_content)

        logger.info("Improved knowledge doc '%s' for topic '%s'", doc_file, topic)
        updated.append(doc_file)

    return updated
