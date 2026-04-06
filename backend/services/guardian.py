import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)
TIMEOUT = 300.0


async def ask_guardian(prompt: str, context: str = "") -> str:
    full_prompt = f"{prompt}\n\n{context}".strip() if context else prompt
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
    logger.info("guardian responded, length=%d", len(answer))
    return answer
