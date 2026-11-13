"""Custom near-black ``keniran`` theme for the Textual app.

Governing plan: ``v1.1.0-tui-redesign`` (decision AD2, requirements R8 and
R12). The palette is deliberately restrained: a near-black background, gray
``foreground``/``primary``, and exactly ONE amber role — ``accent``. AD2 keeps
the palette as declarative :class:`~textual.theme.Theme` data (never hex
overrides in app CSS), and R8 keeps ``tokyo-night`` selectable: this module only
*defines and registers* the theme — selecting it is a later task (W2-1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from textual.theme import Theme

if TYPE_CHECKING:
    from textual.app import App

KENIRAN_THEME_NAME: Final = "keniran"

KENIRAN_THEME: Final[Theme] = Theme(
    name=KENIRAN_THEME_NAME,
    # Gray roles (R8): mid/light cool grays, never amber-hued.
    primary="#9A9AA0",
    secondary="#74747A",
    foreground="#C9C9CE",
    # Near-black ground (R1): background/surface/panel are near-black grays.
    background="#0D0D0F",
    surface="#131316",
    panel="#1B1B1F",
    # Status hues stay desaturated so amber remains the single accent (AD2).
    warning="#8F9B6A",
    error="#C96A6A",
    success="#7FA97F",
    # The one amber role (R1).
    accent="#E0A64B",
    dark=True,
)


def register_keniran_theme(app: App[Any]) -> None:
    """Register :data:`KENIRAN_THEME` on *app* exactly once.

    The helper only registers: it never selects the theme (W2-1 owns the
    selection wiring), so the app's active theme is left untouched.
    """
    app.register_theme(KENIRAN_THEME)
