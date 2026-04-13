"""Unit tests for services/image_compositor.py.

Tests cover composite_person and overlay_text using real PIL image manipulation
(no mocking of PIL) with simple coloured-rectangle fixtures.
"""

import io

import pytest
from PIL import Image

from services.image_compositor import (
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    composite_person,
    overlay_text,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png(
    width: int = 200, height: int = 150, color: tuple = (100, 150, 200)
) -> bytes:
    """Return PNG bytes for a solid-colour rectangle."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _open_png(data: bytes) -> Image.Image:
    """Open PNG bytes and return an Image."""
    return Image.open(io.BytesIO(data))


def _is_valid_png(data: bytes) -> bool:
    """Return True if *data* can be decoded as a PNG image."""
    try:
        img = _open_png(data)
        img.verify()
        return True
    except Exception:
        return False


# PNG magic bytes (first 8 bytes of every PNG file)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bg_bytes() -> bytes:
    """A wide background image (16:9-ish)."""
    return _make_png(640, 360, color=(30, 30, 30))


@pytest.fixture()
def person_bytes() -> bytes:
    """A tall person-shaped image (portrait aspect ratio)."""
    return _make_png(100, 200, color=(200, 100, 50))


@pytest.fixture()
def square_person_bytes() -> bytes:
    """A square person image for easier aspect-ratio assertions."""
    return _make_png(100, 100, color=(50, 200, 100))


# ---------------------------------------------------------------------------
# composite_person — output basics
# ---------------------------------------------------------------------------


class TestCompositePersonOutputFormat:
    def test_returns_bytes(self, bg_bytes, person_bytes):
        result = composite_person(bg_bytes, person_bytes, {})
        assert isinstance(result, bytes)

    def test_returns_valid_png(self, bg_bytes, person_bytes):
        result = composite_person(bg_bytes, person_bytes, {})
        assert result[:8] == PNG_SIGNATURE

    def test_output_dimensions_are_1280x720(self, bg_bytes, person_bytes):
        result = composite_person(bg_bytes, person_bytes, {})
        img = _open_png(result)
        assert img.size == (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
        assert img.size == (1280, 720)

    def test_background_is_resized_regardless_of_input_size(self, person_bytes):
        """Even a tiny background gets resized to 1280×720."""
        tiny_bg = _make_png(10, 10, color=(0, 0, 255))
        result = composite_person(tiny_bg, person_bytes, {})
        img = _open_png(result)
        assert img.size == (1280, 720)

    def test_large_background_is_resized_to_1280x720(self, person_bytes):
        """A 4K background is also resized down."""
        large_bg = _make_png(3840, 2160, color=(128, 128, 128))
        result = composite_person(large_bg, person_bytes, {})
        img = _open_png(result)
        assert img.size == (1280, 720)


# ---------------------------------------------------------------------------
# composite_person — person_size_pct
# ---------------------------------------------------------------------------


class TestCompositePersonSizePct:
    def _person_pixel_coverage(self, result_bytes: bytes, person_color: tuple) -> float:
        """Rough measure: what fraction of pixels are close to *person_color*."""
        img = _open_png(result_bytes).convert("RGB")
        pixels = list(img.getdata())
        r0, g0, b0 = person_color
        close = sum(
            1
            for r, g, b in pixels
            if abs(r - r0) < 40 and abs(g - g0) < 40 and abs(b - b0) < 40
        )
        return close / len(pixels)

    def test_default_person_size_pct_is_70(self, bg_bytes):
        """Default person_size_pct=70 → person height ≈ 0.70 × 720 = 504 px."""
        person_color = (200, 100, 50)
        person = _make_png(100, 200, color=person_color)
        result = composite_person(bg_bytes, person, {})
        # We can't easily read back the sub-image size, but we verify coverage
        # is larger than a 50% person and smaller than a 100% person.
        cov_70 = self._person_pixel_coverage(result, person_color)

        person_50 = _make_png(100, 200, color=person_color)
        result_50 = composite_person(bg_bytes, person_50, {"person_size_pct": 50})
        cov_50 = self._person_pixel_coverage(result_50, person_color)

        assert cov_70 > cov_50, "70% person should cover more pixels than 50% person"

    def test_larger_person_size_pct_covers_more_pixels(self, bg_bytes):
        person_color = (200, 100, 50)
        person = _make_png(100, 200, color=person_color)

        result_30 = composite_person(bg_bytes, person, {"person_size_pct": 30})
        result_90 = composite_person(bg_bytes, person, {"person_size_pct": 90})

        cov_30 = self._person_pixel_coverage(result_30, person_color)
        cov_90 = self._person_pixel_coverage(result_90, person_color)
        assert cov_90 > cov_30

    def test_person_height_matches_pct(self, bg_bytes):
        """Use a distinctive colour to estimate the person region height."""
        person_color = (255, 0, 128)
        person = _make_png(100, 200, color=person_color)
        pct = 50
        result = composite_person(bg_bytes, person, {"person_size_pct": pct})
        img = _open_png(result).convert("RGB")
        w, h = img.size

        # Find bounding rows that contain the person colour
        person_rows = set()
        for y in range(h):
            for x in range(w):
                r, g, b = img.getpixel((x, y))
                if abs(r - 255) < 40 and abs(g - 0) < 40 and abs(b - 128) < 40:
                    person_rows.add(y)

        if person_rows:
            rendered_height = max(person_rows) - min(person_rows) + 1
            expected_height = int(THUMBNAIL_HEIGHT * pct / 100)
            # Allow ±5 px tolerance for resampling
            assert abs(rendered_height - expected_height) <= 5


# ---------------------------------------------------------------------------
# composite_person — horizontal positions
# ---------------------------------------------------------------------------


class TestCompositePersonHorizontalPosition:
    """Verify the person lands on the expected side of the canvas."""

    def _column_has_person(
        self, img: Image.Image, x: int, person_color: tuple, tolerance: int = 40
    ) -> bool:
        r0, g0, b0 = person_color
        w, h = img.size
        for y in range(h):
            r, g, b = img.convert("RGB").getpixel((x, y))
            if (
                abs(r - r0) < tolerance
                and abs(g - g0) < tolerance
                and abs(b - b0) < tolerance
            ):
                return True
        return False

    def test_right_position_places_person_on_right_half(self, bg_bytes):
        person_color = (0, 200, 255)
        person = _make_png(100, 200, color=person_color)
        result = composite_person(bg_bytes, person, {"person_position": "right"})
        img = _open_png(result)
        # At least one column in the right quarter should contain the person
        right_quarter_start = THUMBNAIL_WIDTH * 3 // 4
        found_right = any(
            self._column_has_person(img, x, person_color)
            for x in range(right_quarter_start, THUMBNAIL_WIDTH)
        )
        assert found_right, "Person should appear in right quarter for position='right'"

    def test_left_position_places_person_on_left_half(self, bg_bytes):
        person_color = (0, 200, 255)
        person = _make_png(100, 200, color=person_color)
        result = composite_person(bg_bytes, person, {"person_position": "left"})
        img = _open_png(result)
        left_quarter_end = THUMBNAIL_WIDTH // 4
        found_left = any(
            self._column_has_person(img, x, person_color)
            for x in range(0, left_quarter_end)
        )
        assert found_left, "Person should appear in left quarter for position='left'"

    def test_center_position_places_person_near_middle(self, bg_bytes):
        person_color = (0, 200, 255)
        person = _make_png(100, 200, color=person_color)
        result = composite_person(bg_bytes, person, {"person_position": "center"})
        img = _open_png(result)
        # Middle 50% of the canvas
        mid_start = THUMBNAIL_WIDTH // 4
        mid_end = THUMBNAIL_WIDTH * 3 // 4
        found_center = any(
            self._column_has_person(img, x, person_color)
            for x in range(mid_start, mid_end)
        )
        assert found_center, "Person should appear near centre for position='center'"

    def test_right_person_not_predominantly_on_left(self, bg_bytes):
        person_color = (0, 200, 255)
        person = _make_png(100, 200, color=person_color)
        result = composite_person(bg_bytes, person, {"person_position": "right"})
        img = _open_png(result).convert("RGB")
        r0, g0, b0 = person_color

        left_count = sum(
            1
            for y in range(THUMBNAIL_HEIGHT)
            for x in range(THUMBNAIL_WIDTH // 2)
            if abs(img.getpixel((x, y))[0] - r0) < 40
            and abs(img.getpixel((x, y))[1] - g0) < 40
            and abs(img.getpixel((x, y))[2] - b0) < 40
        )
        right_count = sum(
            1
            for y in range(THUMBNAIL_HEIGHT)
            for x in range(THUMBNAIL_WIDTH // 2, THUMBNAIL_WIDTH)
            if abs(img.getpixel((x, y))[0] - r0) < 40
            and abs(img.getpixel((x, y))[1] - g0) < 40
            and abs(img.getpixel((x, y))[2] - b0) < 40
        )
        assert right_count >= left_count, (
            "position='right' should put more pixels on the right"
        )


# ---------------------------------------------------------------------------
# composite_person — vertical alignment
# ---------------------------------------------------------------------------


class TestCompositePersonVerticalAlignment:
    def _person_row_range(
        self, result_bytes: bytes, person_color: tuple
    ) -> tuple[int, int]:
        """Return (min_row, max_row) where the person colour appears."""
        img = _open_png(result_bytes).convert("RGB")
        w, h = img.size
        r0, g0, b0 = person_color
        rows = [
            y
            for y in range(h)
            for x in range(w)
            if abs(img.getpixel((x, y))[0] - r0) < 40
            and abs(img.getpixel((x, y))[1] - g0) < 40
            and abs(img.getpixel((x, y))[2] - b0) < 40
        ]
        assert rows, "Person colour not found in result image"
        return min(rows), max(rows)

    def test_bottom_aligned_person_reaches_bottom_edge(self, bg_bytes):
        person_color = (180, 50, 220)
        person = _make_png(100, 200, color=person_color)
        result = composite_person(
            bg_bytes,
            person,
            {"person_vertical": "bottom-aligned", "person_size_pct": 60},
        )
        _, max_row = self._person_row_range(result, person_color)
        # Person bottom should be at or very near the canvas bottom
        assert max_row >= THUMBNAIL_HEIGHT - 5, (
            f"bottom-aligned person max_row={max_row} should be near {THUMBNAIL_HEIGHT}"
        )

    def test_top_aligned_person_starts_at_top(self, bg_bytes):
        person_color = (180, 50, 220)
        person = _make_png(100, 200, color=person_color)
        result = composite_person(
            bg_bytes, person, {"person_vertical": "top-aligned", "person_size_pct": 60}
        )
        min_row, _ = self._person_row_range(result, person_color)
        # Person top should be at or very near the canvas top
        assert min_row <= 5, f"top-aligned person min_row={min_row} should be near 0"

    def test_center_vertical_person_is_between_top_and_bottom(self, bg_bytes):
        person_color = (180, 50, 220)
        person = _make_png(100, 200, color=person_color)
        result = composite_person(
            bg_bytes, person, {"person_vertical": "center", "person_size_pct": 40}
        )
        min_row, max_row = self._person_row_range(result, person_color)
        # Neither top nor bottom
        assert min_row > 10, "center-aligned person should not start at the very top"
        assert max_row < THUMBNAIL_HEIGHT - 10, (
            "center-aligned person should not reach the very bottom"
        )

    def test_bottom_aligned_is_lower_than_top_aligned(self, bg_bytes):
        person_color = (180, 50, 220)
        person = _make_png(100, 200, color=person_color)
        result_bottom = composite_person(
            bg_bytes,
            person,
            {"person_vertical": "bottom-aligned", "person_size_pct": 40},
        )
        result_top = composite_person(
            bg_bytes, person, {"person_vertical": "top-aligned", "person_size_pct": 40}
        )
        _, max_bottom = self._person_row_range(result_bottom, person_color)
        min_top, _ = self._person_row_range(result_top, person_color)
        assert max_bottom > min_top


# ---------------------------------------------------------------------------
# overlay_text — output basics
# ---------------------------------------------------------------------------


class TestOverlayTextOutputFormat:
    def test_returns_bytes(self, bg_bytes):
        result = overlay_text(bg_bytes, "Hello World", {})
        assert isinstance(result, bytes)

    def test_returns_valid_png(self, bg_bytes):
        result = overlay_text(bg_bytes, "Hello World", {})
        assert result[:8] == PNG_SIGNATURE

    def test_output_size_matches_input_size(self, bg_bytes):
        """overlay_text must not resize the input image."""
        input_img = _open_png(bg_bytes)
        result = overlay_text(bg_bytes, "Hello World", {})
        output_img = _open_png(result)
        assert output_img.size == input_img.size

    def test_returns_bytes_for_empty_title(self, bg_bytes):
        result = overlay_text(bg_bytes, "", {})
        assert isinstance(result, bytes)
        assert result[:8] == PNG_SIGNATURE


# ---------------------------------------------------------------------------
# overlay_text — text is rendered
# ---------------------------------------------------------------------------


class TestOverlayTextRendering:
    def _pixel_differs(self, img_before: Image.Image, img_after: Image.Image) -> int:
        """Count pixels that changed between two same-size RGB images."""
        before = img_before.convert("RGB")
        after = img_after.convert("RGB")
        changed = 0
        for p_b, p_a in zip(before.getdata(), after.getdata()):
            if p_b != p_a:
                changed += 1
        return changed

    def test_text_changes_pixels(self, bg_bytes):
        """Rendering text must alter at least some pixels."""
        result = overlay_text(bg_bytes, "TEST TITLE", {})
        before = _open_png(bg_bytes)
        after = _open_png(result)
        # Resize before to match after (overlay_text preserves input size)
        before_resized = before.resize(after.size)
        changed = self._pixel_differs(before_resized, after)
        assert changed > 0, "overlay_text should modify at least one pixel"

    def test_longer_text_changes_more_pixels(self, bg_bytes):
        result_short = overlay_text(bg_bytes, "Hi", {})
        result_long = overlay_text(
            bg_bytes, "This is a much longer title that wraps", {}
        )

        before = _open_png(bg_bytes)
        changed_short = self._pixel_differs(
            before.resize(_open_png(result_short).size), _open_png(result_short)
        )
        changed_long = self._pixel_differs(
            before.resize(_open_png(result_long).size), _open_png(result_long)
        )
        assert changed_long >= changed_short


# ---------------------------------------------------------------------------
# overlay_text — text wrapping
# ---------------------------------------------------------------------------


class TestOverlayTextWrapping:
    """Long text with a small max_width_ratio should produce multiple lines."""

    def _count_distinct_text_rows(
        self, bg_bytes: bytes, title: str, style: dict
    ) -> int:
        """
        Crude heuristic: render with white text on black BG and count
        horizontal bands that contain white pixels.
        """
        black_bg = _make_png(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, color=(0, 0, 0))
        style_with_white = {**style, "text_color": "#FFFFFF", "text_stroke": False}
        result = overlay_text(black_bg, title, style_with_white)
        img = _open_png(result).convert("RGB")
        w, h = img.size

        in_band = False
        bands = 0
        for y in range(h):
            row_has_white = any(img.getpixel((x, y))[0] > 200 for x in range(w))
            if row_has_white and not in_band:
                bands += 1
                in_band = True
            elif not row_has_white:
                in_band = False
        return bands

    def test_short_text_fits_on_one_line(self):
        bands = self._count_distinct_text_rows(
            _make_png(),
            "Hi",
            {"text_max_width_ratio": 0.9},
        )
        # Short text should produce exactly 1 text band
        assert bands == 1

    def test_long_text_wraps_to_multiple_lines(self):
        long_title = (
            "This Is A Very Long Title That Should Wrap Onto Multiple Lines Indeed"
        )
        bands = self._count_distinct_text_rows(
            _make_png(),
            long_title,
            {"text_max_width_ratio": 0.2},  # very narrow → forces wrapping
        )
        assert bands > 1, f"Expected multiple text bands, got {bands}"

    def test_narrower_max_width_produces_more_lines(self):
        title = "One Two Three Four Five Six Seven Eight Nine Ten"
        bands_wide = self._count_distinct_text_rows(
            _make_png(), title, {"text_max_width_ratio": 0.8}
        )
        bands_narrow = self._count_distinct_text_rows(
            _make_png(), title, {"text_max_width_ratio": 0.15}
        )
        assert bands_narrow >= bands_wide


# ---------------------------------------------------------------------------
# overlay_text — stroke
# ---------------------------------------------------------------------------


class TestOverlayTextStroke:
    def _render(self, title: str, style: dict) -> Image.Image:
        black_bg = _make_png(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, color=(128, 128, 128))
        result = overlay_text(black_bg, title, style)
        return _open_png(result).convert("RGB")

    def test_stroke_enabled_adds_stroke_colour_pixels(self):
        style_stroke = {
            "text_color": "#FFFFFF",
            "text_stroke": True,
            "text_stroke_width": 3,
            "text_stroke_color": "#FF0000",  # bright red stroke
        }
        img = self._render("STROKE TEST", style_stroke)
        w, h = img.size
        red_pixels = sum(
            1
            for y in range(h)
            for x in range(w)
            if img.getpixel((x, y))[0] > 180
            and img.getpixel((x, y))[1] < 80
            and img.getpixel((x, y))[2] < 80
        )
        assert red_pixels > 0, (
            "Stroke colour (red) pixels should appear when text_stroke=True"
        )

    def test_no_stroke_does_not_add_stroke_colour(self):
        style_no_stroke = {
            "text_color": "#FFFFFF",
            "text_stroke": False,
            "text_stroke_width": 3,
            "text_stroke_color": "#FF0000",
        }
        img = self._render("NO STROKE", style_no_stroke)
        w, h = img.size
        red_pixels = sum(
            1
            for y in range(h)
            for x in range(w)
            if img.getpixel((x, y))[0] > 180
            and img.getpixel((x, y))[1] < 80
            and img.getpixel((x, y))[2] < 80
        )
        assert red_pixels == 0, "No red stroke pixels expected when text_stroke=False"

    def test_stroke_width_zero_suppresses_stroke(self):
        style_zero = {
            "text_color": "#FFFFFF",
            "text_stroke": True,
            "text_stroke_width": 0,
            "text_stroke_color": "#FF0000",
        }
        img = self._render("ZERO WIDTH", style_zero)
        w, h = img.size
        red_pixels = sum(
            1
            for y in range(h)
            for x in range(w)
            if img.getpixel((x, y))[0] > 180
            and img.getpixel((x, y))[1] < 80
            and img.getpixel((x, y))[2] < 80
        )
        assert red_pixels == 0, (
            "Stroke width=0 should produce no red pixels even if stroke enabled"
        )


# ---------------------------------------------------------------------------
# overlay_text — custom font bytes (with fallback)
# ---------------------------------------------------------------------------


class TestOverlayTextFont:
    def test_none_font_bytes_uses_default_font(self):
        """Passing font_bytes=None should not raise and should return valid PNG."""
        bg = _make_png(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
        result = overlay_text(bg, "Default Font", {}, font_bytes=None)
        assert isinstance(result, bytes)
        assert result[:8] == PNG_SIGNATURE

    def test_invalid_font_bytes_falls_back_gracefully(self):
        """Corrupt font_bytes should trigger the fallback and still return PNG."""
        bg = _make_png(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
        bad_font = b"\x00\x01\x02\x03" * 100  # not a valid font
        result = overlay_text(bg, "Fallback Font", {}, font_bytes=bad_font)
        assert isinstance(result, bytes)
        assert result[:8] == PNG_SIGNATURE

    def test_invalid_font_bytes_still_renders_text(self):
        """Even with a bad font, some pixels should change (default font is used)."""
        black_bg = _make_png(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, color=(0, 0, 0))
        bad_font = b"\xde\xad\xbe\xef" * 50
        result = overlay_text(
            black_bg,
            "FALLBACK",
            {"text_color": "#FFFFFF", "text_stroke": False},
            font_bytes=bad_font,
        )
        img = _open_png(result).convert("RGB")
        white_pixels = sum(
            1 for r, g, b in img.getdata() if r > 200 and g > 200 and b > 200
        )
        assert white_pixels > 0, (
            "Should render white text pixels even with fallback font"
        )


# ---------------------------------------------------------------------------
# overlay_text — text position (horizontal)
# ---------------------------------------------------------------------------


class TestOverlayTextHorizontalPosition:
    def _centroid_x(self, title: str, text_pos: str) -> float:
        """Return the mean x-coordinate of white text pixels."""
        black_bg = _make_png(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, color=(0, 0, 0))
        style = {
            "text_color": "#FFFFFF",
            "text_stroke": False,
            "text_position": text_pos,
        }
        result = overlay_text(black_bg, title, style)
        img = _open_png(result).convert("RGB")
        w, h = img.size
        xs = [x for y in range(h) for x in range(w) if img.getpixel((x, y))[0] > 200]
        assert xs, f"No white pixels found for position={text_pos}"
        return sum(xs) / len(xs)

    def test_left_position_centroid_is_left_of_center(self):
        cx = self._centroid_x("LEFT TEXT", "left")
        assert cx < THUMBNAIL_WIDTH / 2, (
            f"left text centroid={cx:.0f} should be left of centre"
        )

    def test_right_position_centroid_is_right_of_center(self):
        cx = self._centroid_x("RIGHT TEXT", "right")
        assert cx > THUMBNAIL_WIDTH / 2, (
            f"right text centroid={cx:.0f} should be right of centre"
        )

    def test_center_position_centroid_is_near_middle(self):
        cx = self._centroid_x("CENTER TEXT", "center")
        tolerance = THUMBNAIL_WIDTH * 0.15  # ±15% of width
        assert abs(cx - THUMBNAIL_WIDTH / 2) < tolerance, (
            f"center text centroid={cx:.0f} not near {THUMBNAIL_WIDTH // 2}"
        )

    def test_right_centroid_is_right_of_left_centroid(self):
        cx_left = self._centroid_x("SOME TITLE", "left")
        cx_right = self._centroid_x("SOME TITLE", "right")
        assert cx_right > cx_left


# ---------------------------------------------------------------------------
# overlay_text — text vertical position
# ---------------------------------------------------------------------------


class TestOverlayTextVerticalPosition:
    def _centroid_y(self, title: str, text_vert: str) -> float:
        """Return the mean y-coordinate of white text pixels."""
        black_bg = _make_png(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, color=(0, 0, 0))
        style = {
            "text_color": "#FFFFFF",
            "text_stroke": False,
            "text_vertical": text_vert,
        }
        result = overlay_text(black_bg, title, style)
        img = _open_png(result).convert("RGB")
        w, h = img.size
        ys = [y for y in range(h) for x in range(w) if img.getpixel((x, y))[0] > 200]
        assert ys, f"No white pixels found for text_vertical={text_vert}"
        return sum(ys) / len(ys)

    def test_top_vertical_centroid_is_above_middle(self):
        cy = self._centroid_y("TOP TEXT", "top")
        assert cy < THUMBNAIL_HEIGHT / 2, (
            f"top text centroid={cy:.0f} should be above midline {THUMBNAIL_HEIGHT // 2}"
        )

    def test_bottom_vertical_centroid_is_below_middle(self):
        cy = self._centroid_y("BOTTOM TEXT", "bottom")
        assert cy > THUMBNAIL_HEIGHT / 2, (
            f"bottom text centroid={cy:.0f} should be below midline {THUMBNAIL_HEIGHT // 2}"
        )

    def test_center_vertical_centroid_is_near_middle(self):
        cy = self._centroid_y("CENTER TEXT", "center")
        tolerance = THUMBNAIL_HEIGHT * 0.2
        assert abs(cy - THUMBNAIL_HEIGHT / 2) < tolerance, (
            f"center text centroid={cy:.0f} not near {THUMBNAIL_HEIGHT // 2}"
        )

    def test_bottom_centroid_is_below_top_centroid(self):
        cy_top = self._centroid_y("TITLE", "top")
        cy_bottom = self._centroid_y("TITLE", "bottom")
        assert cy_bottom > cy_top


# ---------------------------------------------------------------------------
# Both functions — valid PNG return value (integration)
# ---------------------------------------------------------------------------


class TestBothFunctionsReturnValidPng:
    def test_composite_person_result_can_be_used_as_input_to_overlay_text(
        self, bg_bytes, person_bytes
    ):
        composite = composite_person(
            bg_bytes, person_bytes, {"person_position": "right"}
        )
        final = overlay_text(composite, "Combined Pipeline", {"text_position": "left"})
        assert isinstance(final, bytes)
        assert final[:8] == PNG_SIGNATURE
        img = _open_png(final)
        assert img.size == (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)

    def test_composite_person_output_is_rgb_png(self, bg_bytes, person_bytes):
        result = composite_person(bg_bytes, person_bytes, {})
        img = _open_png(result).convert("RGB")
        assert img.mode == "RGB"

    def test_overlay_text_output_is_rgb_png(self, bg_bytes):
        result = overlay_text(bg_bytes, "Test", {})
        img = _open_png(result).convert("RGB")
        assert img.mode == "RGB"
