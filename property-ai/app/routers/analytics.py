"""Admin and analytics endpoints for system monitoring and improvement."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import QueryMetricRead, KnowledgeGapReport
from app.services.analytics_service import (
    identify_knowledge_gaps,
    update_query_metrics,
    get_metrics_dashboard,
    get_low_rating_queries,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/refresh-metrics")
async def refresh_metrics(db: AsyncSession = Depends(get_db)):
    """
    Recalculate query metrics from feedback data.
    Run this periodically to update dashboard statistics.
    
    Returns:
        Status message
    """
    await update_query_metrics(db)
    return {"status": "ok", "message": "Metrics refreshed"}


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """
    Get analytics dashboard with overall system health metrics.
    
    Returns:
        Dashboard data: total_queries, avg_rating, worst_patterns, health_score
    """
    return await get_metrics_dashboard(db)


@router.get("/knowledge-gaps", response_model=list[KnowledgeGapReport])
async def get_knowledge_gaps(
    min_query_count: int = 3,
    min_avg_rating: float = 2.5,
    db: AsyncSession = Depends(get_db)
):
    """
    Identify knowledge base gaps based on low-performing queries.
    
    Args:
        min_query_count: Minimum occurrences to flag as gap (default: 3)
        min_avg_rating: Rating threshold (topics below this = gap)
    
    Returns:
        List of identified gaps with suggested improvements
    """
    gaps = await identify_knowledge_gaps(
        db=db,
        min_query_count=min_query_count,
        min_avg_rating=min_avg_rating
    )
    
    # Convert gaps to KnowledgeGapReport format
    reports = []
    for gap in gaps:
        # Get sample low-rated queries for this topic
        low_rated = await get_low_rating_queries(db=db, min_rating=3, days=30)
        topic_queries = [q for q in low_rated if gap["topic"] in q.query_text.lower()]
        
        reports.append(
            KnowledgeGapReport(
                query_pattern=gap["topic"],
                total_queries=gap["query_count"],
                avg_rating=gap["avg_rating"],
                low_rating_queries=topic_queries[:5],
                suggested_improvement=gap["suggested_action"],
            )
        )
    
    return reports


@router.get("/system-health")
async def get_system_health(db: AsyncSession = Depends(get_db)):
    """
    Get system health summary.
    
    Returns:
        Health metrics: status, health_score, queries_needing_attention
    """
    dashboard = await get_metrics_dashboard(db)
    gaps = await identify_knowledge_gaps(db=db)
    
    health_score = dashboard.get("health_score", 0)
    
    # Determine status
    if health_score >= 80:
        status = "healthy"
    elif health_score >= 60:
        status = "warning"
    else:
        status = "critical"
    
    return {
        "status": status,
        "health_score": health_score,
        "total_queries": dashboard.get("total_queries", 0),
        "avg_rating": dashboard.get("avg_rating", 0),
        "identified_gaps": len(gaps),
        "queries_with_low_ratings": dashboard.get("low_rating_queries", 0),
        "next_action": (
            "Monitor performance - system healthy" if status == "healthy"
            else "Review low-rated queries" if status == "warning"
            else "Add knowledge base sections to address gaps"
        ),
    }
