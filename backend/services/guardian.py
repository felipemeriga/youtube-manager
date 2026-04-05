import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


async def ask_guardian(prompt: str, system: str, timeout: int = 120) -> str:
    url = f"{settings.guardian_url}/api/ask"
    logger.info("POST %s (prompt=%d chars, timeout=%ds)", url, len(prompt), timeout)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json={"prompt": prompt, "system": system, "timeout": timeout * 1000},
                headers={"Authorization": f"Bearer {settings.guardian_api_key}"},
                timeout=timeout + 10,
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Guardian responded: status=%d response=%d chars",
                response.status_code,
                len(data.get("response", "")),
            )
            return data["response"]
        except httpx.HTTPStatusError as e:
            logger.error("Guardian HTTP error: %s body=%s", e, e.response.text[:500])
            raise Exception(f"Guardian request failed: {e}")
        except httpx.RequestError as e:
            logger.error("Guardian connection error: %s", e)
            raise Exception(f"Guardian request failed: {e}")
