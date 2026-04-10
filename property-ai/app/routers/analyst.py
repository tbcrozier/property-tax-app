import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import AnalystRequest, SaveExampleRequest
from app.services.analyst_service import run_analyst_stream, save_query_example

router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.post("/ask")
async def ask(
    request: AnalystRequest,
    db: AsyncSession = Depends(get_db),
):
    async def event_stream():
        async for event in run_analyst_stream(db, request.question, request.max_iterations):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/examples")
async def save_example(
    request: SaveExampleRequest,
    db: AsyncSession = Depends(get_db),
):
    await save_query_example(
        db,
        question=request.question,
        sql=request.sql,
        insight=request.insight,
        tags=request.tags,
    )
    return {"status": "saved", "question": request.question}
