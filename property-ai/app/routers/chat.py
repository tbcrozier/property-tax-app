import time
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import ChatRequest, ChatResponse, QueryFeedbackRequest, QueryFeedbackRead
from app.services.chat_service import handle_chat
from app.services.analytics_service import (
    log_query_performance,
    submit_feedback,
    get_low_rating_queries,
)
from app.services.auto_eval_service import run_auto_eval

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Chat endpoint — answers using live DB queries + knowledge docs.

    After every response, automatically scores quality in the background
    using implicit signals + LLM self-evaluation. No user input required
    for the self-improvement loop to work.

    Response fields:
    - answer: the actual answer (with real data when applicable)
    - sources: knowledge doc filenames used
    - sql_used: SQL query that was executed (if any)
    - result_count: number of DB rows returned (if any)
    - query_id: use to submit a manual rating override via POST /chat/{id}/feedback
    """
    start_ms = time.time() * 1000
    response = await handle_chat(db, request)
    latency_ms = time.time() * 1000 - start_ms

    query_text = request.messages[-1].content if request.messages else ""

    feedback_record = await log_query_performance(
        db=db,
        query_text=query_text,
        response_text=response.answer,
        parcel_id=request.parcel_id,
        retrieved_docs=response.sources,
        latency_ms=latency_ms,
        sql_used=response.sql_used,
        result_count=response.result_count,
    )

    # Fire auto-eval in the background — doesn't block the response
    background_tasks.add_task(
        run_auto_eval,
        feedback_id=feedback_record.id,
        question=query_text,
        answer=response.answer,
        sql_used=response.sql_used,
        result_count=response.result_count,
        parcel_id=request.parcel_id,
    )

    return ChatResponse(
        answer=response.answer,
        sources=response.sources,
        sql_used=response.sql_used,
        result_count=response.result_count,
        query_id=feedback_record.id,
    )


@router.post("/{feedback_id}/feedback", response_model=QueryFeedbackRead)
async def submit_query_feedback(
    feedback_id: int,
    feedback: QueryFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Optional: submit a manual 1-5 star rating to override the auto-score.

    The system already scores every response automatically. Use this only
    when you disagree with how the system rated its own answer.

    Side effects:
    - Rating >= 4: promotes the SQL query in the saved_queries library
    - Rating <= 2: triggers a knowledge improvement pass (background)
    """
    try:
        updated = await submit_feedback(
            db=db,
            feedback_id=feedback_id,
            rating=feedback.rating,
            comments=feedback.comments,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Manual rating overrides — trigger improvement actions immediately
    from app.services.sql_service import promote_query_rating
    from app.services.knowledge_service import maybe_improve_knowledge

    if feedback.rating >= 4 and updated.sql_used:
        await promote_query_rating(db, updated.query_text, float(feedback.rating))

    if feedback.rating <= 2:
        updated_docs = await maybe_improve_knowledge(db)
        if updated_docs:
            logger.info("Knowledge docs improved after manual low rating: %s", updated_docs)

    return updated


@router.get("/stats/low-rated", response_model=list[QueryFeedbackRead])
async def get_low_rated_queries(
    min_rating: int = 3,
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """
    Get queries rated poorly (< min_rating) in the last N days.
    Includes both auto-scores and manual ratings.
    """
    return await get_low_rating_queries(db=db, min_rating=min_rating, days=days)
