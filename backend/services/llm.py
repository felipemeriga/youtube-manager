import logging
from typing import AsyncGenerator

import httpx
from anthropic import AsyncAnthropic

from config import settings

logger = logging.getLogger(__name__)

TIMEOUT = 600.0


async def ask_llm(system: str, messages: list[dict], model: str | None = None) -> str:
    if settings.anthropic_api_key:
        return await _ask_anthropic(system, messages, model)
    return await _ask_guardian(system, messages)


async def stream_llm(
    system: str, messages: list[dict], model: str | None = None
) -> AsyncGenerator[str, None]:
    if settings.anthropic_api_key:
        async for token in _stream_anthropic(system, messages, model):
            yield token
    else:
        result = await _ask_guardian(system, messages)
        yield result


WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,
}


async def _ask_anthropic(
    system: str, messages: list[dict], model: str | None = None
) -> str:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=model or settings.anthropic_model,
        max_tokens=16384,
        system=system,
        messages=messages,
        tools=[WEB_SEARCH_TOOL],
    )
    # Extract the text block from the response (may include tool results)
    text_blocks = [block.text for block in response.content if hasattr(block, "text")]
    return text_blocks[-1] if text_blocks else ""


async def _stream_anthropic(
    system: str, messages: list[dict], model: str | None = None
) -> AsyncGenerator[str, None]:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    async with client.messages.stream(
        model=model or settings.anthropic_model,
        max_tokens=16384,
        system=system,
        messages=messages,
        tools=[WEB_SEARCH_TOOL],
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def _ask_guardian(system: str, messages: list[dict]) -> str:
    prompt_parts = [f"System: {system}\n"]
    for msg in messages:
        role = msg["role"].capitalize()
        prompt_parts.append(f"{role}: {msg['content']}\n")
    full_prompt = "\n".join(prompt_parts).strip()

    logger.info("ask_guardian prompt=%s", full_prompt[:120])
    headers = {}
    if settings.guardian_api_key:
        headers["Authorization"] = f"Bearer {settings.guardian_api_key}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{settings.guardian_url}/api/ask",
            json={"prompt": full_prompt},
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
    answer = data.get("response", "")
    logger.info("llm responded via guardian, length=%d", len(answer))
    return answer
