"""OpenAI gpt-image-1.5 provider — drop-in replacement for nano_banana.py.

Same async function signatures, same return type (bytes). Internally translates
the Gemini-flavored kwargs (aspect_ratio, image_size in 4K/2K/1K) into OpenAI's
size + quality params, and collapses Gemini's interleaved text+image Parts into
a single prompt with positional image markers.
"""

import base64
import io
import logging

import httpx
from openai import AsyncOpenAI

from config import settings

logger = logging.getLogger(__name__)


# Bounded timeout for fetching images by URL (rare path — gpt-image-1.5 returns
# b64_json by default). Without this, a slow OpenAI CDN response can hang the
# whole event loop indefinitely.
_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


# Aspect ratio + tier → explicit size string.  gpt-image-1.5 only supports
# three fixed sizes: 1536x1024 (landscape), 1024x1024 (square), 1024x1536
# (portrait).  All tiers map to the same size per aspect ratio; the quality
# parameter (high/medium/low) controls output fidelity instead.
SIZE_BY_ASPECT_TIER: dict[str, dict[str, str]] = {
    "16:9": {"4K": "1536x1024", "2K": "1536x1024", "1K": "1536x1024"},
    "1:1": {"4K": "1024x1024", "2K": "1024x1024", "1K": "1024x1024"},
    "9:16": {"4K": "1024x1536", "2K": "1024x1536", "1K": "1024x1536"},
}

# 4K/2K both use "high" quality (visual quality), differ in target dimensions.
# 1K uses "medium" since the lower resolution doesn't justify the latency cost
# of "high".
QUALITY_BY_TIER: dict[str, str] = {"4K": "high", "2K": "high", "1K": "medium"}


def _translate_size(aspect_ratio: str, image_size: str) -> tuple[str, str]:
    """Map (aspect_ratio, image_size) → (size, quality) for gpt-image-1.5."""
    sizes = SIZE_BY_ASPECT_TIER.get(aspect_ratio)
    if sizes is None:
        # Unknown ratio — fall back to YouTube 16:9 to avoid hard failure.
        sizes = SIZE_BY_ASPECT_TIER["16:9"]
    size = sizes.get(image_size) or sizes["2K"]
    quality = QUALITY_BY_TIER.get(image_size, "high")
    return size, quality


def _bytes_to_filelike(data: bytes, idx: int) -> io.BytesIO:
    """Wrap raw image bytes as a named BytesIO so the SDK can multipart-upload."""
    bio = io.BytesIO(data)
    # OpenAI infers content-type from the filename extension. Use .png — it
    # accepts the actual bytes regardless and detects format internally.
    bio.name = f"image_{idx}.png"
    return bio


def _decode_response(response) -> bytes:
    """Pull image bytes out of an Images API response (b64 or url)."""
    item = response.data[0]
    b64 = getattr(item, "b64_json", None)
    if b64:
        return base64.b64decode(b64)
    url = getattr(item, "url", None)
    if url:
        # Synchronous httpx fetch is fine here — this path is rare (b64 is
        # the default for gpt-image-1.5).
        import httpx

        response = httpx.get(url, timeout=_HTTP_TIMEOUT)
        response.raise_for_status()
        return response.content
    raise RuntimeError("OpenAI image response had neither b64_json nor url")


async def _call_image_api(
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    images: list[bytes],
    aspect_ratio: str,
    image_size: str,
) -> bytes:
    """Single call with size-fallback chain: requested → 2K → 1K.

    Mirrors nano_banana._generate_image's resilience pattern: if the requested
    size 400s for any reason, retry at smaller sizes before giving up.
    """
    fallback_chain: list[str] = [image_size]
    for tier in ["2K", "1K"]:
        if tier not in fallback_chain:
            fallback_chain.append(tier)

    last_exc: Exception | None = None
    for tier in fallback_chain:
        size, quality = _translate_size(aspect_ratio, tier)
        try:
            if images:
                files = [_bytes_to_filelike(b, i) for i, b in enumerate(images)]
                response = await client.images.edit(
                    model=model,
                    image=files,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                )
            else:
                response = await client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                )
            if tier != image_size:
                logger.info("OpenAI succeeded with fallback tier=%s", tier)
            return _decode_response(response)
        except Exception as exc:
            logger.warning(
                "OpenAI %s failed (tier=%s, size=%s, quality=%s): %s",
                model,
                tier,
                size,
                quality,
                exc,
            )
            last_exc = exc
    assert last_exc is not None
    # Re-raise with provider context so the SSE error event surfaces a
    # message the user can act on instead of a bare OpenAI traceback.
    raise RuntimeError(
        f"OpenAI {model} failed for all sizes ({', '.join(fallback_chain)}): {last_exc}"
    ) from last_exc


def _section(heading: str, body: str) -> str:
    return f"=== {heading} ===\n{body.strip()}\n"


async def generate_background(
    prompt: str,
    reference_images: list[bytes],
    logos: list[bytes] | None = None,
    previous_image: bytes | None = None,
    aspect_ratio: str = "16:9",
    image_size: str = "4K",
    model: str = "gpt-image-1.5",
) -> bytes:
    """Generate ONLY background + logo, no person, no text."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    images: list[bytes] = []
    sections: list[str] = []

    if reference_images:
        n = len(reference_images)
        sections.append(
            _section(
                f"REFERENCE THUMBNAILS (images 1-{n})",
                "Use ONLY for layout and logo placement. Ignore their text and "
                "people (those are added in later steps). Generate visuals based "
                "on the TOPIC below, not the references.",
            )
        )
        images.extend(reference_images)

    if logos:
        start = len(images) + 1
        end = start + len(logos) - 1
        label = f"image {start}" if start == end else f"images {start}-{end}"
        sections.append(
            _section(
                f"CHANNEL LOGO ({label})",
                "This is the channel logo. Place it in the same position and "
                "size as in the reference thumbnails.",
            )
        )
        images.extend(logos)

    if previous_image:
        idx = len(images) + 1
        sections.append(
            _section(
                f"CURRENT BACKGROUND (image {idx})",
                "User wants changes. Keep everything unchanged except what they "
                "asked for.",
            )
        )
        images.append(previous_image)

    sections.append(_section("TASK", prompt))
    full_prompt = "\n".join(sections)

    return await _call_image_api(
        client,
        model,
        full_prompt,
        images,
        aspect_ratio,
        image_size,
    )


async def composite_with_effects(
    background_bytes: bytes,
    person_bytes: bytes,
    reference_images: list[bytes],
    extra_instructions: str | None = None,
    previous_image: bytes | None = None,
    composite_mode: str = "natural",
    transform_prompt: str | None = None,
    aspect_ratio: str = "16:9",
    image_size: str = "4K",
    model: str = "gpt-image-1.5",
) -> bytes:
    """Composite person onto background with effects matching references."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    images: list[bytes] = []
    sections: list[str] = []

    if reference_images:
        n = len(reference_images)
        sections.append(
            _section(
                f"REFERENCE THUMBNAILS (images 1-{n})",
                "Study how the person is composited: position, size, glow, "
                "lighting, color grading, edge effects. Replicate this style.",
            )
        )
        images.extend(reference_images)

    if previous_image:
        idx = len(images) + 1
        sections.append(
            _section(
                f"CURRENT COMPOSITE (image {idx})",
                "User wants changes. Keep everything unchanged except what they "
                "asked for.",
            )
        )
        images.append(previous_image)

    bg_idx = len(images) + 1
    sections.append(
        _section(
            f"BACKGROUND IMAGE (image {bg_idx})",
            "Use as-is, do NOT modify.",
        )
    )
    images.append(background_bytes)

    person_idx = len(images) + 1
    sections.append(
        _section(
            f"PERSON PHOTO (image {person_idx})",
            "This is the person to place in the thumbnail.",
        )
    )
    images.append(person_bytes)

    if composite_mode == "transform" and transform_prompt:
        instructions = (
            f"TRANSFORM MODE: {transform_prompt}\n"
            "1. Keep the person's FACE exactly as it is — same face, same features, recognizable\n"
            "2. Transform their body/outfit/appearance as described above\n"
            "3. Remove the person's original background\n"
            "4. Apply reference-style effects (glow, lighting, color grading)\n"
            "5. Position/size the person as in references\n"
            "6. No text. Background must remain pixel-perfect."
        )
    elif extra_instructions:
        instructions = (
            f"MODIFY the person as requested: {extra_instructions}\n"
            "1. Keep the person's FACE recognizable — same face, same features\n"
            "2. Apply the requested modifications (accessories, props, clothing, etc.)\n"
            "3. Remove the person's original background\n"
            "4. Apply reference-style effects (glow, lighting, color grading)\n"
            "5. Position/size the person as in references\n"
            "6. No text. Background must remain pixel-perfect."
        )
    else:
        instructions = (
            "1. Preserve the person's face/body exactly — no redrawing or distortion\n"
            "2. Remove the person's original background\n"
            "3. Apply reference-style effects (glow, lighting, color grading) to the person\n"
            "4. Position/size the person as in references\n"
            "5. No text. Background must remain pixel-perfect."
        )
    sections.append(_section("TASK", instructions))
    full_prompt = "\n".join(sections)

    return await _call_image_api(
        client,
        model,
        full_prompt,
        images,
        aspect_ratio,
        image_size,
    )


async def add_text_with_style(
    composite_bytes: bytes,
    text: str,
    reference_images: list[bytes],
    previous_image: bytes | None = None,
    extra_instructions: str | None = None,
    aspect_ratio: str = "16:9",
    image_size: str = "4K",
    model: str = "gpt-image-1.5",
) -> bytes:
    """Add styled text to the composite, matching reference typography."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    images: list[bytes] = []
    sections: list[str] = []

    if reference_images:
        n = len(reference_images)
        sections.append(
            _section(
                f"REFERENCE THUMBNAILS (images 1-{n})",
                "Replicate the SAME typography: font style, weight, color, size, "
                "position, effects (shadow, stroke, glow).",
            )
        )
        images.extend(reference_images)

    if previous_image:
        idx = len(images) + 1
        sections.append(
            _section(
                f"PREVIOUS VERSION (image {idx})",
                "User wants changes. Keep everything except what they asked for.",
            )
        )
        images.append(previous_image)

    comp_idx = len(images) + 1
    sections.append(
        _section(
            f"CURRENT THUMBNAIL (image {comp_idx})",
            "Add text only, change nothing else.",
        )
    )
    images.append(composite_bytes)

    text_prompt = (
        f'Add this text: "{text}"\n'
        "Match reference typography style. Make it readable and impactful.\n"
        "Do NOT change background, person, logo, or any other element."
    )
    if extra_instructions:
        text_prompt += f"\nUser request: {extra_instructions}"
    sections.append(_section("TASK", text_prompt))
    full_prompt = "\n".join(sections)

    return await _call_image_api(
        client,
        model,
        full_prompt,
        images,
        aspect_ratio,
        image_size,
    )
