import base64
import logging

import voyageai
from anthropic import AsyncAnthropic

from config import settings

logger = logging.getLogger(__name__)

DESCRIBE_SYSTEM = (
    "You describe photos of a person for thumbnail matching. "
    "Include: facial expression, emotion, pose, body language, "
    "angle, lighting, background, outfit, energy level. "
    "Be specific and concise (2-3 sentences)."
)


async def describe_photo(image_bytes: bytes) -> str:
    """Use Haiku vision to describe a photo."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    b64 = base64.standard_b64encode(image_bytes).decode()

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=DESCRIBE_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": "Describe this photo."},
                ],
            }
        ],
    )
    return response.content[0].text


def embed_text(text: str) -> list[float]:
    """Embed text using Voyage."""
    client = voyageai.Client(api_key=settings.voyage_api_key)
    result = client.embed([text], model="voyage-3")
    return result.embeddings[0]


async def index_photo(sb, user_id: str, file_name: str, image_bytes: bytes) -> None:
    """Describe and embed a single photo, store in photo_embeddings."""
    try:
        description = await describe_photo(image_bytes)
        embedding = embed_text(description)

        await (
            sb.table("photo_embeddings")
            .upsert(
                {
                    "user_id": user_id,
                    "file_name": file_name,
                    "description": description,
                    "embedding": embedding,
                },
                on_conflict="user_id,file_name",
            )
            .execute()
        )
        logger.info(
            "indexed photo %s for user=%s: %s", file_name, user_id, description[:80]
        )
    except Exception:
        logger.exception("failed to index photo %s for user=%s", file_name, user_id)
