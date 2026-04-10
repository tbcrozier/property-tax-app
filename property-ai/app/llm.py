import ollama

from app.config import settings


async def embed_text(text: str) -> list[float]:
    client = ollama.AsyncClient(host=settings.ollama_base_url)
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
    client = ollama.AsyncClient(host=settings.ollama_base_url)

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    kwargs: dict = {"model": settings.ollama_llm_model, "messages": full_messages}
    if tools:
        kwargs["tools"] = tools

    response = await client.chat(**kwargs)
    return response["message"]
