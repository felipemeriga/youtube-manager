import logging

import voyageai

from config import settings

logger = logging.getLogger(__name__)


async def find_best_photos(sb, user_id: str, topic: str, limit: int = 3) -> list[str]:
    """Find the best-matching photo filenames for a topic using vector similarity."""
    if not settings.voyage_api_key:
        return []

    try:
        client = voyageai.Client(api_key=settings.voyage_api_key)
        result = client.embed([topic], model="voyage-3")
        query_embedding = result.embeddings[0]

        # Use Supabase RPC for vector similarity search
        response = await sb.rpc(
            "match_photos",
            {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_count": limit,
            },
        ).execute()

        if response.data:
            filenames = [row["file_name"] for row in response.data]
            logger.info(
                "photo search for '%s': found %d matches", topic[:50], len(filenames)
            )
            return filenames

        return []
    except Exception:
        logger.exception("photo search failed for topic='%s'", topic[:50])
        return []
