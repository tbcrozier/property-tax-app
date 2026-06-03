import ollama

from app.config import settings


async def embed_text(text: str) -> list[float]:
    client = ollama.AsyncClient(host=settings.ollama_base_url, timeout=30)
    response = await client.embeddings(
        model=settings.ollama_embed_model,
        prompt=text,
    )
    return response["embedding"]


async def chat_completion(
    messages: list[dict],
    system_prompt: str | None = None,
    tools: list[dict] | None = None,
) -> dict:
    """
    Returns the full message dict so callers can inspect tool_calls.
    """
    # 300s timeout — local 14b models can take 60-120s per response under load.
    # Without a timeout, a stalled Ollama process hangs the entire request forever.
    client = ollama.AsyncClient(host=settings.ollama_base_url, timeout=300)

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    kwargs: dict = {"model": settings.ollama_llm_model, "messages": full_messages}
    if tools:
        kwargs["tools"] = tools

    response = await client.chat(**kwargs)
    return response["message"]
