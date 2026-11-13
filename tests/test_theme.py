"""Tests for the custom near-black ``keniran`` Textual theme.

Governing plan: ``v1.1.0-tui-redesign`` (AD2, R8, R12). The checks are pure
data + registration tests: they parse the theme's palette offline (no Textual
rendering, no network) and enforce the colour rules — a near-black
background/surface/panel, gray ``foreground``/``primary``, and exactly one
amber-hued role (``accent``) — plus the single-call registration contract.
"""

from __future__ import annotations

from typing import Final

import pytest
from textual.app import App
from textual.theme import Theme

from keniran.tui.theme import KENIRAN_THEME, KENIRAN_THEME_NAME, register_keniran_theme

# Band thresholds: the palette intent (R1/R8) as numeric gates.
NEAR_BLACK_MAX_LUMA: Final = 0.10
DARK_GROUND_MAX_LUMA: Final = 0.20
GRAY_MAX_CHANNEL_SPREAD: Final = 8
GRAY_LUMA_RANGE: Final = (0.45, 0.85)
AMBER_HUE_RANGE: Final = (30.0, 55.0)
AMBER_MIN_SATURATION: Final = 0.2

# Every theme role that carries a colour; ``accent`` is the only amber one.
_COLOUR_ROLES: Final = (
    "primary",
    "secondary",
    "warning",
    "error",
    "success",
    "accent",
    "foreground",
    "background",
    "surface",
    "panel",
)


def _channels(hex_colour: str) -> tuple[int, int, int]:
    """Return the ``(r, g, b)`` channels of a ``#rrggbb`` colour."""
    assert isinstance(hex_colour, str), f"role value is not a string: {hex_colour!r}"
    digits = hex_colour.removeprefix("#")
    assert len(digits) == 6, f"expected #rrggbb, got {hex_colour!r}"
    return int(digits[:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)


def _luma(hex_colour: str) -> float:
    """Return the perceived luma of ``#rrggbb`` as a 0..1 fraction."""
    red, green, blue = _channels(hex_colour)
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255


def _hsv(hex_colour: str) -> tuple[float, float, float]:
    """Return ``(hue, saturation, value)`` of ``#rrggbb`` (hue in degrees)."""
    red, green, blue = (channel / 255 for channel in _channels(hex_colour))
    high, low = max(red, green, blue), min(red, green, blue)
    delta = high - low
    saturation = 0.0 if high == 0 else delta / high
    if delta == 0:
        hue = 0.0
    elif high == red:
        hue = 60.0 * (((green - blue) / delta) % 6)
    elif high == green:
        hue = 60.0 * ((blue - red) / delta + 2)
    else:
        hue = 60.0 * ((red - green) / delta + 4)
    return hue, saturation, high


def _is_near_black(hex_colour: str) -> bool:
    """Whether *hex_colour* reads as near-black (very low luma, any chroma)."""
    return _luma(hex_colour) <= NEAR_BLACK_MAX_LUMA


def _is_gray(hex_colour: str) -> bool:
    """Whether *hex_colour* reads as gray: tiny channel spread, mid luma."""
    red, green, blue = _channels(hex_colour)
    spread = max(red, green, blue) - min(red, green, blue)
    low, high = GRAY_LUMA_RANGE
    return spread <= GRAY_MAX_CHANNEL_SPREAD and low <= _luma(hex_colour) <= high


def _is_amber(hex_colour: str) -> bool:
    """Whether *hex_colour* reads as amber: warm orange-yellow hue, saturated."""
    hue, saturation, _ = _hsv(hex_colour)
    low, high = AMBER_HUE_RANGE
    return saturation >= AMBER_MIN_SATURATION and low <= hue <= high


def test_theme_name_is_keniran() -> None:
    """The theme is named ``keniran`` and exported under its own constant."""
    assert KENIRAN_THEME.name == KENIRAN_THEME_NAME == "keniran"


def test_dark_ground_is_near_black() -> None:
    """Background is near-black and the surface/panel stack stays below it."""
    assert KENIRAN_THEME.dark is True
    assert _is_near_black(KENIRAN_THEME.background)
    for role in ("surface", "panel"):
        ground = getattr(KENIRAN_THEME, role)
        assert _luma(ground) <= DARK_GROUND_MAX_LUMA, f"{role} is too light: {ground}"
    assert _luma(KENIRAN_THEME.surface) < _luma(KENIRAN_THEME.primary)


def test_foreground_and_primary_are_gray() -> None:
    """Both text roles sit in the gray band (R8) — light text, mid primary."""
    assert _is_gray(KENIRAN_THEME.foreground)
    assert _is_gray(KENIRAN_THEME.primary)
    assert _luma(KENIRAN_THEME.foreground) > _luma(KENIRAN_THEME.primary)


def test_accent_is_the_only_amber_role() -> None:
    """Exactly one role is amber-hued: ``accent`` (R1/AD2)."""
    assert _is_amber(KENIRAN_THEME.accent)
    for role in _COLOUR_ROLES:
        colour = getattr(KENIRAN_THEME, role)
        assert _is_amber(colour) is (role == "accent"), f"{role}={colour} amber check"


def test_all_colour_roles_are_six_digit_hex() -> None:
    """Every colour role carries a usable ``#rrggbb`` value (no ``None``)."""
    for role in _COLOUR_ROLES:
        assert len(_channels(getattr(KENIRAN_THEME, role))) == 3, role


class _ThemeProbeApp(App[None]):
    """Minimal app used to exercise theme registration without running it."""

    pass


def test_register_keniran_theme_makes_it_available() -> None:
    """A fresh app exposes ``keniran`` in ``available_themes`` after registering."""
    app = _ThemeProbeApp()
    assert KENIRAN_THEME_NAME not in app.available_themes
    register_keniran_theme(app)
    assert KENIRAN_THEME_NAME in app.available_themes
    assert app.available_themes[KENIRAN_THEME_NAME] is KENIRAN_THEME


def test_register_keniran_theme_calls_register_theme_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The helper delegates to ``App.register_theme`` exactly once."""
    app = _ThemeProbeApp()
    registered: list[Theme] = []
    original = app.register_theme

    def spy(theme: Theme) -> None:
        registered.append(theme)
        original(theme)

    monkeypatch.setattr(app, "register_theme", spy)
    register_keniran_theme(app)
    assert registered == [KENIRAN_THEME]
    assert KENIRAN_THEME_NAME in app.available_themes


def test_register_keniran_theme_does_not_select_the_theme() -> None:
    """Selection stays with the later wiring task: the active theme is unchanged."""
    app = _ThemeProbeApp()
    before = app.theme
    register_keniran_theme(app)
    assert app.theme is before
    assert app.theme != KENIRAN_THEME_NAME
