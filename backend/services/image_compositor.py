import io
import logging

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720


def composite_person(
    background_bytes: bytes,
    person_bytes: bytes,
    style: dict,
) -> bytes:
    """Composite a person photo onto a background image."""
    bg = Image.open(io.BytesIO(background_bytes)).convert("RGBA")
    bg = bg.resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)

    person = Image.open(io.BytesIO(person_bytes)).convert("RGBA")

    # Calculate person size
    person_height_pct = style.get("person_size_pct", 70) / 100
    target_height = int(THUMBNAIL_HEIGHT * person_height_pct)
    aspect = person.width / person.height
    target_width = int(target_height * aspect)
    person = person.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # Calculate position
    position = style.get("person_position", "right")
    vertical = style.get("person_vertical", "bottom-aligned")

    if position == "right":
        x = THUMBNAIL_WIDTH - target_width - int(THUMBNAIL_WIDTH * 0.02)
    elif position == "left":
        x = int(THUMBNAIL_WIDTH * 0.02)
    else:  # center
        x = (THUMBNAIL_WIDTH - target_width) // 2

    if vertical == "bottom-aligned":
        y = THUMBNAIL_HEIGHT - target_height
    elif vertical == "top-aligned":
        y = 0
    else:  # center
        y = (THUMBNAIL_HEIGHT - target_height) // 2

    bg.paste(person, (x, y), person if person.mode == "RGBA" else None)

    output = io.BytesIO()
    bg.convert("RGB").save(output, format="PNG", quality=95)
    return output.getvalue()


def overlay_text(
    image_bytes: bytes,
    title: str,
    style: dict,
    font_bytes: bytes | None = None,
) -> bytes:
    """Overlay title text on a thumbnail image."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    # Text settings from style
    text_color = style.get("text_color", "#FFFFFF")
    stroke_color = style.get("text_stroke_color", "#000000")
    stroke_width = style.get("text_stroke_width", 2)
    has_stroke = style.get("text_stroke", True)
    size_ratio = style.get("text_size_ratio", 0.08)
    max_width_ratio = style.get("text_max_width_ratio", 0.5)

    font_size = int(THUMBNAIL_HEIGHT * size_ratio)
    max_text_width = int(THUMBNAIL_WIDTH * max_width_ratio)

    # Load font
    if font_bytes:
        try:
            font = ImageFont.truetype(io.BytesIO(font_bytes), font_size)
        except Exception:
            logger.warning("Failed to load custom font, using default")
            font = ImageFont.load_default()
    else:
        font = ImageFont.load_default()

    # Wrap text
    draw = ImageDraw.Draw(img)
    words = title.upper().split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip() if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] > max_text_width and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    # Calculate text position
    text_pos = style.get("text_position", "left")
    text_vert = style.get("text_vertical", "center")
    line_height = font_size * 1.15

    total_text_height = len(lines) * line_height

    if text_vert == "top":
        start_y = int(THUMBNAIL_HEIGHT * 0.1)
    elif text_vert == "bottom":
        start_y = int(THUMBNAIL_HEIGHT * 0.9 - total_text_height)
    else:  # center
        start_y = int((THUMBNAIL_HEIGHT - total_text_height) / 2)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]

        if text_pos == "left":
            x = int(THUMBNAIL_WIDTH * 0.05)
        elif text_pos == "right":
            x = int(THUMBNAIL_WIDTH * 0.95) - text_width
        else:  # center
            x = (THUMBNAIL_WIDTH - text_width) // 2

        y = start_y + int(i * line_height)

        if has_stroke and stroke_width > 0:
            draw.text(
                (x, y), line, font=font, fill=text_color,
                stroke_width=stroke_width, stroke_fill=stroke_color,
            )
        else:
            draw.text((x, y), line, font=font, fill=text_color)

    output = io.BytesIO()
    img.convert("RGB").save(output, format="PNG", quality=95)
    return output.getvalue()
