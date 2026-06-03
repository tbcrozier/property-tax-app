"""Analytics service for tracking query performance and identifying knowledge gaps."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QueryFeedback, QueryMetric

logger = logging.getLogger(__name__)


async def log_query_performance(
    db: AsyncSession,
    query_text: str,
    response_text: str,
    parcel_id: Optional[str] = None,
    retrieved_docs: Optional[list[str]] = None,
    latency_ms: Optional[float] = None,
    sql_used: Optional[str] = None,
    result_count: Optional[int] = None,
) -> QueryFeedback:
    """
    Log a query and its response for analytics.

    Args:
        db: Database session
        query_text: The user's query
        response_text: The LLM response
        parcel_id: Optional parcel ID from context
        retrieved_docs: List of source documents retrieved
        latency_ms: Response time in milliseconds
        sql_used: SQL query that was executed (if any)
        result_count: Number of rows returned by SQL (if any)

    Returns:
        QueryFeedback object created
    """
    feedback = QueryFeedback(
        query_text=query_text,
        response_text=response_text,
        parcel_id=parcel_id,
        retrieved_docs=json.dumps(retrieved_docs or []),
        latency_ms=latency_ms,
        sql_used=sql_used,
        result_count=result_count,
        rating=0,  # 0 = unrated, auto-score fills this in background
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


async def submit_feedback(
    db: AsyncSession,
    feedback_id: int,
    rating: int,
    comments: Optional[str] = None,
) -> QueryFeedback:
    """
    Submit user feedback on a query response.

    Args:
        db: Database session
        feedback_id: ID of QueryFeedback record
        rating: 1-5 star rating
        comments: Optional user comments

    Returns:
        Updated QueryFeedback object
    """
    stmt = select(QueryFeedback).where(QueryFeedback.id == feedback_id)
    result = await db.execute(stmt)
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise ValueError(f"Feedback ID {feedback_id} not found")

    feedback.rating = min(5, max(1, rating))  # Clamp to 1-5
    feedback.comments = comments

    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


async def get_low_rating_queries(
    db: AsyncSession, min_rating: int = 3, days: int = 7
) -> list[QueryFeedback]:
    """
    Get queries with low ratings from the past N days.

    Args:
        db: Database session
        min_rating: Only return ratings < this value (default: < 3 stars)
        days: Look back N days

    Returns:
        List of low-rated QueryFeedback records
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(QueryFeedback)
        .where(
            and_(
                QueryFeedback.rating < min_rating,
                QueryFeedback.rating > 0,  # Exclude unrated
                QueryFeedback.created_at >= cutoff_date,
            )
        )
        .order_by(QueryFeedback.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def identify_knowledge_gaps(
    db: AsyncSession, min_query_count: int = 3, min_avg_rating: float = 2.5
) -> list[dict]:
    """
    Identify knowledge base gaps by finding query patterns with low performance.

    Args:
        db: Database session
        min_query_count: Minimum queries to consider a pattern
        min_avg_rating: Average rating threshold (below = gap)

    Returns:
        List of dicts with gap info: {topic, avg_rating, count, sample_queries}
    """
    # Group feedback by topic keywords in query_text
    query_topics = {}

    stmt = select(QueryFeedback).where(QueryFeedback.rating > 0)
    result = await db.execute(stmt)
    feedback_records = result.scalars().all()

    for feedback in feedback_records:
        # Extract keywords (simplified - could use NLP)
        words = feedback.query_text.lower().split()
        for word in words:
            if len(word) > 4:  # Skip short words
                if word not in query_topics:
                    query_topics[word] = {"ratings": [], "queries": []}
                query_topics[word]["ratings"].append(feedback.rating)
                query_topics[word]["queries"].append(feedback.query_text)

    # Find gaps
    gaps = []
    for topic, data in query_topics.items():
        if len(data["ratings"]) >= min_query_count:
            avg_rating = sum(data["ratings"]) / len(data["ratings"])
            if avg_rating < min_avg_rating:
                gaps.append(
                    {
                        "topic": topic,
                        "avg_rating": round(avg_rating, 2),
                        "query_count": len(data["ratings"]),
                        "sample_queries": data["queries"][:3],
                        "suggested_action": f"Add/improve documentation for '{topic}' (ratings: {data['ratings']})",
                    }
                )

    return sorted(gaps, key=lambda x: x["avg_rating"])


async def suggest_doc_improvements(
    db: AsyncSession, min_query_count: int = 5, min_avg_rating: float = 2.0
) -> list[dict]:
    """
    Suggest improvements to knowledge documents based on feedback patterns.

    Analyzes low-rated queries to identify topics needing better documentation.
    This enables iterative improvement of RAG knowledge base.

    Args:
        db: Database session
        min_query_count: Minimum queries for a topic to be considered
        min_avg_rating: Rating threshold for flagging improvements

    Returns:
        List of dicts with improvement suggestions: {topic, avg_rating, query_count, sample_queries, suggested_improvements}
    """
    # Reuse gap identification logic but focus on doc improvements
    gaps = await identify_knowledge_gaps(db, min_query_count, min_avg_rating)
    
    improvements = []
    for gap in gaps:
        # Map topics to likely document files
        doc_mapping = {
            "flood": "data/knowledge/flood_zones.md",  # Assuming files exist
            "zoning": "data/knowledge/nashville_zoning.md",
            "permit": "data/knowledge/property_tax_glossary.md",
            "assessment": "data/knowledge/valuation_anomaly_guide.md",
            "tax": "data/knowledge/property_tax_glossary.md",
            "railroad": "data/knowledge/railroad.md",
            # Add more mappings as needed
        }
        
        suggested_doc = doc_mapping.get(gap["topic"], "data/knowledge/general.md")
        
        improvements.append({
            "topic": gap["topic"],
            "avg_rating": gap["avg_rating"],
            "query_count": gap["query_count"],
            "sample_queries": gap["sample_queries"],
            "suggested_doc": suggested_doc,
            "suggested_improvements": [
                f"Add more detailed explanations for '{gap['topic']}' queries",
                f"Include examples or case studies related to {gap['topic']}",
                f"Cross-reference with service data sources for {gap['topic']}",
                "Review and update based on recent legal/tax changes"
            ],
            "priority": "High" if gap["avg_rating"] < 1.5 else "Medium"
        })
    
    return sorted(improvements, key=lambda x: x["avg_rating"])


async def update_query_metrics(db: AsyncSession) -> None:
    """
    Recalculate QueryMetric aggregates based on QueryFeedback.
    Run periodically (e.g., every hour) to keep metrics fresh.
    """
    # Get all feedback records
    stmt = select(QueryFeedback).where(QueryFeedback.rating > 0)
    result = await db.execute(stmt)
    all_feedback = result.scalars().all()

    # Group by query pattern (simplified - first 50 chars as key)
    patterns = {}
    for feedback in all_feedback:
        pattern = feedback.query_text[:50]
        if pattern not in patterns:
            patterns[pattern] = []
        patterns[pattern].append(feedback)

    # Update metrics for each pattern
    for pattern, feedback_list in patterns.items():
        avg_rating = sum(f.rating for f in feedback_list) / len(feedback_list)
        avg_latency = (
            sum(f.latency_ms for f in feedback_list if f.latency_ms)
            / len([f for f in feedback_list if f.latency_ms])
        )
        low_count = len([f for f in feedback_list if f.rating < 3])
        high_count = len([f for f in feedback_list if f.rating >= 4])

        # Find or create metric
        stmt = select(QueryMetric).where(QueryMetric.query_pattern == pattern)
        result = await db.execute(stmt)
        metric = result.scalar_one_or_none()

        if metric:
            metric.total_queries = len(feedback_list)
            metric.avg_rating = round(avg_rating, 2)
            metric.avg_latency_ms = round(avg_latency, 2)
            metric.low_rating_count = low_count
            metric.high_rating_count = high_count
            db.add(metric)
        else:
            metric = QueryMetric(
                query_pattern=pattern,
                total_queries=len(feedback_list),
                avg_rating=round(avg_rating, 2),
                avg_latency_ms=round(avg_latency, 2),
                low_rating_count=low_count,
                high_rating_count=high_count,
            )
            db.add(metric)

    await db.commit()
    logger.info(f"Updated metrics for {len(patterns)} query patterns")


async def get_metrics_dashboard(db: AsyncSession) -> dict:
    """
    Get overall analytics dashboard data.

    Returns:
        Dict with: total_queries, avg_rating, worst_patterns, best_patterns, health_score
    """
    stmt = select(QueryFeedback).where(QueryFeedback.rating > 0)
    result = await db.execute(stmt)
    all_feedback = result.scalars().all()

    if not all_feedback:
        return {
            "total_queries": 0,
            "avg_rating": 0,
            "worst_patterns": [],
            "best_patterns": [],
            "health_score": 0,
        }

    total_queries = len(all_feedback)
    avg_rating = sum(f.rating for f in all_feedback) / total_queries
    low_rating_count = len([f for f in all_feedback if f.rating < 3])
    health_score = round((1 - (low_rating_count / total_queries)) * 100, 1)

    # Get worst and best performing patterns
    stmt = select(QueryMetric).order_by(QueryMetric.avg_rating.asc()).limit(5)
    result = await db.execute(stmt)
    worst = result.scalars().all()

    stmt = select(QueryMetric).order_by(QueryMetric.avg_rating.desc()).limit(5)
    result = await db.execute(stmt)
    best = result.scalars().all()

    return {
        "total_queries": total_queries,
        "avg_rating": round(avg_rating, 2),
        "low_rating_queries": low_rating_count,
        "health_score": health_score,  # % of queries rated 3+
        "worst_patterns": [
            {
                "pattern": m.query_pattern,
                "avg_rating": m.avg_rating,
                "count": m.total_queries,
            }
            for m in worst
        ],
        "best_patterns": [
            {
                "pattern": m.query_pattern,
                "avg_rating": m.avg_rating,
                "count": m.total_queries,
            }
            for m in best
        ],
    }
