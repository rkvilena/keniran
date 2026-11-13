"""Pure ``keniran`` wordmark art and its left→right gray gradient.

The branding presentation layer of the TUI home screen redesign (plan
v1.1.0-tui-redesign, AD1/AD3): the ASCII-art ``keniran`` wordmark and its gray
gradient live here as pure data plus one pure function, mirroring the
pure-renderable convention of :mod:`keniran.rendering.report_view`, so the
wordmark is unit-testable without a running Textual app (R12).

- :data:`WORDMARK_LINES` is the full six-row block-font wordmark; every row
  has the same width and fits an 80-column terminal (AD3).
- :data:`WORDMARK_COMPACT` is the four-row fallback for short terminals (R7).
- :data:`WORDMARK_GRAY_START` / :data:`WORDMARK_GRAY_END` are the canonical
  gray gradient endpoints, both inside the gray luminance band (R2).
- :func:`wordmark_renderable` colors :data:`WORDMARK_LINES` with that gray
  gradient, and :func:`wordmark_renderable_for` builds the same gradient for
  any row set — e.g. :data:`WORDMARK_COMPACT` on short terminals (R7).

Only :mod:`rich` and the standard library are imported — no Textual, no I/O —
and the module is imported only from :mod:`keniran.tui`.
"""

from __future__ import annotations

from typing import Final

from rich.text import Text

# Block-font wordmark: every letter is drawn with its own lowercase character
# repeated across the stroke (so the spelling is machine-checkable), one
# character per font pixel, letters separated by single spaces. Each row is
# exactly 38 columns, so the whole block fits an 80-column terminal (AD3).
WORDMARK_LINES: Final[tuple[str, ...]] = (
    "k   k  eee  nnn   iii rrr   aaa  nnn  ",
    "k  k  e   e n   n  i  r  r a   a n   n",
    "kkk   eeeee n   n  i  r    aaaaa n   n",
    "k  k  e     n   n  i  r    a   a n   n",
    "k   k e   e n   n  i  r    a   a n   n",
    "k   k  eee  n   n  i  r     aaa  n   n",
)

# Short fallback of the same font at four rows (still 32 columns wide) for
# short terminals (R7): same letters, fewer rows, so the home block keeps its
# branding when the full wordmark would eat the vertical budget.
WORDMARK_COMPACT: Final[tuple[str, ...]] = (
    "k  k eee  nnn  iii rrr  aa  nnn ",
    "kkk  e    n  n  i  r r a  a n  n",
    "k  k eeee n  n  i  r   aaaa n  n",
    "k  k eee  n  n  i  r   aa   n  n",
)

# Canonical gray gradient endpoints (R2): grays (equal channels) whose mean
# sRGB luminance — 0.54 and 0.83 — stays inside the gray band (0.35..0.85) and
# rises from the left endpoint to the right endpoint.
WORDMARK_GRAY_START: Final = "#8A8A8A"
WORDMARK_GRAY_END: Final = "#D4D4D4"


def _parse_hex(color: str) -> tuple[int, int, int]:
    """Return the red/green/blue channels of a ``#RRGGBB`` *color*."""
    digits = color.removeprefix("#")
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


def _blend(start: str, end: str, fraction: float) -> str:
    """Return the ``#RRGGBB`` color *fraction* of the way from *start* to *end*.

    Both endpoints are grays (plan v1.1.0-tui-redesign, R2), so each channel
    interpolates independently and the blend stays gray.
    """
    start_red, start_green, start_blue = _parse_hex(start)
    end_red, end_green, end_blue = _parse_hex(end)
    channels = (
        round(start_red + (end_red - start_red) * fraction),
        round(start_green + (end_green - start_green) * fraction),
        round(start_blue + (end_blue - start_blue) * fraction),
    )
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def wordmark_renderable_for(lines: tuple[str, ...], start: str, end: str) -> Text:
    """Return *lines* as one rich ``Text`` with a left→right gray gradient.

    The general builder behind :func:`wordmark_renderable` (plan
    v1.1.0-tui-redesign, R2/R7): pass :data:`WORDMARK_COMPACT` to gradient the
    short fallback exactly like the full wordmark. Invariants for any row set
    (R2): every non-newline character — glyph cells and interior spaces alike
    — is styled exactly once, so the span count equals the number of
    non-newline characters and the row breaks stay literal ``"\\n"`` inside
    the text; the very first character of the first row carries *start*
    verbatim, the very last character of the last row carries *end* verbatim,
    and each row shades from *start* on its left edge to *end* on its right
    edge with the ``#RRGGBB`` color interpolated across the row
    (``fraction = column / (width - 1)``), so gray luminance steps
    monotonically left→right. An empty *lines* yields an empty ``Text``.
    """
    text = Text()
    row_count = len(lines)
    for row_index, row in enumerate(lines):
        if row_index:
            text.append("\n")
        width = len(row)
        for column, char in enumerate(row):
            if row_index == 0 and column == 0:
                style = start
            elif row_index == row_count - 1 and column == width - 1:
                style = end
            elif column == 0:
                style = start
            elif column == width - 1:
                style = end
            else:
                style = _blend(start, end, column / (width - 1))
            text.append(char, style=style)
    return text


def wordmark_renderable(start: str, end: str) -> Text:
    """Return the full wordmark as one rich ``Text`` with a gray gradient.

    plan v1.1.0-tui-redesign (R2): renders :data:`WORDMARK_LINES` via
    :func:`wordmark_renderable_for`, which documents the gradient invariants.
    """
    return wordmark_renderable_for(WORDMARK_LINES, start, end)
