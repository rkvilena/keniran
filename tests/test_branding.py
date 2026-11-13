"""Offline tests for the pure ``keniran`` wordmark module.

``keniran.tui.branding`` is pure presentation (plan v1.1.0-tui-redesign,
R12/AD1): the ASCII-art ``keniran`` wordmark and its gray gradient builder are
tested here with no running Textual app, no I/O, and no terminal. The wordmark
rows must all share one width within the 80-column budget (AD3) and spell
``keniran``, the compact fallback must be shorter than the full set (R7), and
the gradient endpoints must be grays inside the R2 luminance band stepping
monotonically left→right.
"""

from __future__ import annotations

import pytest
from rich.text import Text

from keniran.tui.branding import (
    WORDMARK_COMPACT,
    WORDMARK_GRAY_END,
    WORDMARK_GRAY_START,
    WORDMARK_LINES,
    wordmark_renderable,
    wordmark_renderable_for,
)

# The gray luminance band of the wordmark gradient (plan v1.1.0-tui-redesign,
# R2): both endpoint grays — and therefore every interpolated color — must sit
# between a mid gray and a light gray, keeping the wordmark a gray gradient.
BAND_LOW = 0.35
BAND_HIGH = 0.85


def _channels(color: str) -> tuple[int, int, int]:
    """Return the red/green/blue channels of a ``#RRGGBB`` *color*."""
    digits = color.removeprefix("#")
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


def _luminance(color: str) -> float:
    """Return the mean sRGB luminance of *color* in the 0..1 range."""
    red, green, blue = _channels(color)
    return (red + green + blue) / (3 * 255)


def _is_gray(color: str) -> bool:
    """Return whether *color* has equal red/green/blue channels."""
    red, green, blue = _channels(color)
    return red == green == blue


def _spelled(row: str) -> str:
    """Return the word a wordmark *row* spells.

    In the block font every letter is drawn with its own lowercase character
    repeated across the stroke, so joining a row's non-space glyph cells gives
    one run of characters per word position; collapsing consecutive duplicate
    cells reduces them to exactly the letters of ``keniran`` in order.
    """
    cells = "".join(char for char in row if not char.isspace())
    return "".join(
        char for index, char in enumerate(cells) if index == 0 or char != cells[index - 1]
    )


@pytest.mark.parametrize("rows", [WORDMARK_LINES, WORDMARK_COMPACT], ids=["full", "compact"])
def test_rows_are_non_empty_equal_width_and_fit_80_columns(rows: tuple[str, ...]) -> None:
    """Every row of a wordmark set shares one width within the 80-column budget."""
    assert rows
    width = len(rows[0])
    assert 0 < width <= 80
    assert all(len(row) == width for row in rows)


@pytest.mark.parametrize("rows", [WORDMARK_LINES, WORDMARK_COMPACT], ids=["full", "compact"])
def test_rows_spell_keniran(rows: tuple[str, ...]) -> None:
    """Each row's non-space glyph cells spell ``keniran`` in order."""
    for row in rows:
        assert set(row) <= set("keniran ")
        assert _spelled(row) == "keniran"


def test_compact_wordmark_is_shorter_than_full() -> None:
    """The compact fallback has fewer rows than the full wordmark (R7)."""
    assert len(WORDMARK_COMPACT) < len(WORDMARK_LINES)


def test_wordmark_renderable_returns_one_text_with_newlines_and_spans() -> None:
    """The full wordmark is one Text: literal newlines, one span per character."""
    text = wordmark_renderable(WORDMARK_GRAY_START, WORDMARK_GRAY_END)
    assert isinstance(text, Text)
    assert text.plain == "\n".join(WORDMARK_LINES)
    assert len(text.spans) == sum(len(row) for row in WORDMARK_LINES)
    assert all(span.end - span.start == 1 for span in text.spans)


def test_first_and_last_span_carry_the_passed_endpoints_verbatim() -> None:
    """Span one is styled with *start* and the last with *end*, exactly as passed."""
    text = wordmark_renderable(WORDMARK_GRAY_START, WORDMARK_GRAY_END)
    assert text.spans[0].style == WORDMARK_GRAY_START
    assert text.spans[-1].style == WORDMARK_GRAY_END

    other = wordmark_renderable("#707070", "#B0B0B0")
    assert other.spans[0].style == "#707070"
    assert other.spans[-1].style == "#B0B0B0"


def test_gray_endpoints_sit_inside_the_luminance_band() -> None:
    """The canonical gradient endpoints are grays inside the R2 band."""
    assert _is_gray(WORDMARK_GRAY_START)
    assert _is_gray(WORDMARK_GRAY_END)
    assert BAND_LOW <= _luminance(WORDMARK_GRAY_START) <= BAND_HIGH
    assert BAND_LOW <= _luminance(WORDMARK_GRAY_END) <= BAND_HIGH
    assert _luminance(WORDMARK_GRAY_START) < _luminance(WORDMARK_GRAY_END)


def test_gradient_is_gray_in_band_and_steps_monotonically() -> None:
    """Every span color is an in-band gray and luminance rises left→right."""
    text = wordmark_renderable(WORDMARK_GRAY_START, WORDMARK_GRAY_END)
    for span in text.spans:
        assert _is_gray(span.style)
        assert BAND_LOW <= _luminance(span.style) <= BAND_HIGH
    offset = 0
    for row in WORDMARK_LINES:
        luminances = [_luminance(span.style) for span in text.spans[offset : offset + len(row)]]
        assert luminances == sorted(luminances)
        offset += len(row)
    assert offset == len(text.spans)


@pytest.mark.parametrize("rows", [WORDMARK_LINES, WORDMARK_COMPACT], ids=["full", "compact"])
def test_wordmark_renderable_for_renders_any_row_set(rows: tuple[str, ...]) -> None:
    """Any row set renders as one Text: literal newlines, one span per character."""
    text = wordmark_renderable_for(rows, WORDMARK_GRAY_START, WORDMARK_GRAY_END)
    assert isinstance(text, Text)
    assert text.plain == "\n".join(rows)
    assert len(text.spans) == sum(len(row) for row in rows)
    assert all(span.end - span.start == 1 for span in text.spans)


@pytest.mark.parametrize("rows", [WORDMARK_LINES, WORDMARK_COMPACT], ids=["full", "compact"])
def test_wordmark_renderable_for_first_and_last_span_styles(
    rows: tuple[str, ...],
) -> None:
    """Span one carries *start* and the last carries *end*, exactly as passed."""
    text = wordmark_renderable_for(rows, WORDMARK_GRAY_START, WORDMARK_GRAY_END)
    assert text.spans[0].style == WORDMARK_GRAY_START
    assert text.spans[-1].style == WORDMARK_GRAY_END


@pytest.mark.parametrize("rows", [WORDMARK_LINES, WORDMARK_COMPACT], ids=["full", "compact"])
def test_wordmark_renderable_for_gradient_is_gray_monotonic(
    rows: tuple[str, ...],
) -> None:
    """Every span color is an in-band gray and luminance rises left→right."""
    text = wordmark_renderable_for(rows, WORDMARK_GRAY_START, WORDMARK_GRAY_END)
    for span in text.spans:
        assert _is_gray(span.style)
        assert BAND_LOW <= _luminance(span.style) <= BAND_HIGH
    offset = 0
    for row in rows:
        luminances = [_luminance(span.style) for span in text.spans[offset : offset + len(row)]]
        assert luminances == sorted(luminances)
        offset += len(row)
    assert offset == len(text.spans)


def test_wordmark_renderable_delegates_to_the_full_wordmark() -> None:
    """``wordmark_renderable`` is ``wordmark_renderable_for(WORDMARK_LINES, ...)``."""
    pinned = wordmark_renderable(WORDMARK_GRAY_START, WORDMARK_GRAY_END)
    general = wordmark_renderable_for(WORDMARK_LINES, WORDMARK_GRAY_START, WORDMARK_GRAY_END)
    assert pinned.plain == general.plain
    assert pinned.spans == general.spans
