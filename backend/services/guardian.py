import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)
TIMEOUT = 120.0


async def ask_guardian(prompt: str, context: str = "") -> str:
    full_prompt = f"{prompt}\n\n{context}".strip() if context else prompt
    logger.info("ask_guardian prompt=%s", full_prompt[:120])
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{settings.guardian_url}/api/ask",
            json={"message": full_prompt},
        )
        response.raise_for_status()
        data = response.json()
    answer = data.get("response", "")
    logger.info("guardian responded, length=%d", len(answer))
    return answer
