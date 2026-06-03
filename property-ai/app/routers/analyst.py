import json

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import AnalystRequest, ReportRequest, ReportResponse, SaveExampleRequest
from app.services.analyst_service import run_analyst_stream, save_query_example
from app.services.report_service import generate_report

router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.post("/ask")
async def ask(
    request: AnalystRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Streaming analyst endpoint. The LLM iteratively uses tools
    (execute_sql, detect_anomalies, run_python, search_docs) to answer
    your question. Responses stream as server-sent events.

    Each event has a 'type' field:
    - progress: status update
    - tool_call: which tool is being called
    - tool_done: tool finished, row_count included
    - knowledge: which docs were retrieved
    - thinking: intermediate LLM reasoning
    - answer: final answer text
    - done: finished, includes sql_queries list
    - error: something went wrong
    """
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


@router.post("/report", response_model=ReportResponse)
async def create_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Run a full deep analysis and save a markdown report to data/reports/.

    The analyst runs up to max_iterations tool calls (SQL queries,
    anomaly detection, Python analysis) then writes a structured report.

    After saving the report the service automatically:
    - Saves all SQL queries that returned data to the saved_queries library
      (used as few-shot examples in future chat requests)
    - Distills key findings into valuation_anomaly_guide.md and re-embeds
      it so the knowledge vector store improves immediately

    parcel_id is optional — omit to run a broad county-wide analysis.

    Example questions:
    - "Find the top 20 most over-assessed residential parcels in ZIP 37206"
    - "Detect anomalous commercial properties and explain why they stand out"
    - "Analyze parcels near rail lines for potential value impacts"
    - "Which neighborhoods have the most zoning/land-use mismatches?"
    """
    result = await generate_report(
        db=db,
        question=request.question,
        parcel_id=request.parcel_id,
        max_iterations=request.max_iterations,
    )
    return ReportResponse(**result)


@router.post("/examples")
async def save_example(
    request: SaveExampleRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually save a question+SQL example to query_examples.md and re-embed.
    Use this to seed the query library with known-good queries.
    """
    await save_query_example(
        db,
        question=request.question,
        sql=request.sql,
        insight=request.insight,
        tags=request.tags,
    )
    return {"status": "saved", "question": request.question}
