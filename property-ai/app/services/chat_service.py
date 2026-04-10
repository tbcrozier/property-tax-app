from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import chat_completion
from app.schemas import ChatMessage, ChatRequest, ChatResponse
from app.services.embed_service import search_documents
from app.services.parcel_service import get_appeal_score, get_comps


async def handle_chat(db: AsyncSession, request: ChatRequest) -> ChatResponse:
    context_parts = []

    if request.parcel_id:
        appeal = await get_appeal_score(db, request.parcel_id)
        if appeal:
            context_parts.append(
                f"Parcel {request.parcel_id} ({appeal.address or 'unknown address'}):\n"
                f"- Total Appraised: ${appeal.totl_appr:,.0f}\n"
                f"- Appeal Score: {appeal.appeal_score:.1f}/100\n"
                f"- Recommendation: {appeal.recommendation}\n"
                f"- % Above ZIP Median: {(appeal.pct_above_zip_median or 0) * 100:.1f}%\n"
                f"- Assessment/Sale Ratio: {appeal.assessment_to_sale_ratio or 'N/A'}\n"
            )
            comps = await get_comps(db, request.parcel_id, limit=5)
            if comps:
                context_parts.append("Comparable properties (same lu_code, zip, similar acres):")
                for c in comps:
                    context_parts.append(
                        f"  - {c.prop_addr}: ${c.totl_appr:,.0f} "
                        f"(${c.value_per_acre:,.0f}/acre)"
                    )

    last_question = request.messages[-1].content if request.messages else ""
    docs = await search_documents(db, last_question, top_k=3)
    if docs:
        context_parts.append("\nRelevant knowledge:")
        for doc in docs:
            context_parts.append(f"[{doc['title']}]\n{doc['content']}")

    system_prompt = (
        "You are a property tax analyst for Davidson County, Nashville TN. "
        "Help users understand their property assessments and identify potential appeal opportunities. "
        "Be specific, data-driven, and concise.\n\n"
    )
    if context_parts:
        system_prompt += "Context:\n" + "\n".join(context_parts)

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    msg = await chat_completion(messages, system_prompt=system_prompt)

    return ChatResponse(
        answer=msg.get("content", ""),
        sources=[d["source"] for d in docs],
    )
