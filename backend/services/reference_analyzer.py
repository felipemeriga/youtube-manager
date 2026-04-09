import base64
import json
import logging
import re

from anthropic import AsyncAnthropic

from config import settings

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM = """You analyze YouTube thumbnail reference images to extract precise layout and styling information.

Study ALL reference thumbnails provided and identify the CONSISTENT patterns across them.

Return ONLY a valid JSON object with these fields:
{
  "person_position": "left" | "right" | "center",
  "person_size_pct": 50-80 (percentage of image height the person takes up),
  "person_vertical": "bottom-aligned" | "center" | "top-aligned",
  "text_position": "left" | "right" | "center",
  "text_vertical": "top" | "center" | "bottom",
  "text_color": "#hex color of the main title text",
  "text_stroke": true | false,
  "text_stroke_color": "#hex or empty",
  "text_stroke_width": number (0-5),
  "text_shadow": true | false,
  "text_size_ratio": 0.05-0.15 (text height as ratio of image height),
  "text_max_width_ratio": 0.3-0.7 (max text width as ratio of image width),
  "logo_position": "top-left" | "top-right" | "bottom-left" | "bottom-right",
  "logo_size_ratio": 0.05-0.15 (logo size as ratio of image width)
}"""


async def analyze_references(reference_images: list[bytes]) -> dict:
    """Analyze reference thumbnails and extract layout/styling info."""
    if not settings.anthropic_api_key or not reference_images:
        return {}

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    content = []
    content.append({
        "type": "text",
        "text": "Analyze these YouTube thumbnail references and extract the consistent layout pattern:",
    })
    for img_bytes in reference_images[:6]:  # Max 6 references
        b64 = base64.standard_b64encode(img_bytes).decode()
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    content.append({"type": "text", "text": "Return the JSON analysis."})

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )

    text = response.content[0].text.strip()
    # Extract JSON from response
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse reference analysis: %s", text[:200])
        return {}
