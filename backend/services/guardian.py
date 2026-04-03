import httpx

from config import settings


async def ask_guardian(prompt: str, system: str, timeout: int = 120) -> str:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.guardian_url}/api/ask",
                json={"prompt": prompt, "system": system, "timeout": timeout * 1000},
                headers={"Authorization": f"Bearer {settings.guardian_api_key}"},
                timeout=timeout + 10,
            )
            response.raise_for_status()
            return response.json()["response"]
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise Exception(f"Guardian request failed: {e}")
