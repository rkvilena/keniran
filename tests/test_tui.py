"""Headless pilot tests for the keniran Textual app and its CLI dispatch.

The TUI tests use Textual's ``run_test`` pilot so they never touch a real
terminal, network, or hardware. Pipeline runs are faked at the
``keniran.tui.app.check_game`` seam: the fakes record the injection kwargs the
app forwards and return canned :class:`~keniran.core.models.Report` fixtures
shaped like the ones in ``test_report_view.py``.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
import sys
import threading
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from rich.table import Table
from rich.text import Text
from textual.app import App
from textual.containers import Center, Container, VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Button, Footer, Input, Rule, Static
from textual.worker import WorkerFailed
from typer.testing import CliRunner

import keniran.cli.app as cli_app
import keniran.tui.app as tui_app
from keniran.adapters import steam
from keniran.adapters.steam import SteamRequirements
from keniran.cli.app import app as cli
from keniran.core import scoring
from keniran.core.models import ComponentName, ComponentRow, Report, SystemSpec
from keniran.rendering.report_view import (
    BADGE_NOTE,
    ST_WARNING_NOTE,
    UNVERIFIED_NOTE,
    badge_text,
    report_renderables,
)
from keniran.tui import branding
from keniran.tui.app import (
    APP_ID_INPUT_ID,
    BODY_ID,
    COMMAND_BOX_CENTER_ID,
    COMMAND_BOX_ID,
    ERROR_ID,
    ERROR_STYLE,
    HERO_ID,
    RESET_BUTTON_ID,
    RESULTS_ID,
    RULE_CENTER_ID,
    STATUS_ID,
    SUBTITLE,
    SUBTITLE_ID,
    WORDMARK_ID,
    KeniranTui,
)
from keniran.tui.theme import KENIRAN_THEME_NAME

APP_ID = 72850


def _run(scenario: Coroutine[Any, Any, None]) -> None:
    """Run one async pilot scenario on a fresh event loop."""
    asyncio.run(scenario)


async def _wait_until(
    predicate: Callable[[], bool],
    pilot: Pilot,
    *,
    timeout: float = 5.0,
) -> None:
    """Yield to the event loop until *predicate* becomes true."""
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("timed out waiting for the TUI state")
        await pilot.pause(0.01)


async def _wait_for_check(tui: KeniranTui, pilot: Pilot) -> None:
    """Wait for the pipeline worker and its completion message to settle.

    Worker failures are surfaced by the app as inline errors; the wait helper
    only cares that the worker finished, not whether it succeeded.
    """
    with contextlib.suppress(WorkerFailed):
        await tui.workers.wait_for_complete()
    await pilot.pause()


def _menu_footer_keys(footer: Footer) -> list[Any]:
    """Return the Footer's rendered command-palette key widgets."""
    return [key for key in footer.query("FooterKey") if key.action == "command_palette"]


def _error_texts(tui: KeniranTui) -> list[str]:
    """Return the plain text of every inline error currently mounted."""
    return [
        child.content.plain
        for child in tui.query(f"#{ERROR_ID}")
        if isinstance(child, Static) and isinstance(child.content, Text)
    ]


async def _submit(tui: KeniranTui, pilot: Pilot) -> None:
    """Focus the App ID input and press Enter to submit the check.

    Enter only submits from the focused input, so the helper pins the focus
    the same way a keyboard user would.
    """
    tui.query_one(f"#{APP_ID_INPUT_ID}", Input).focus()
    await pilot.press("enter")


# --- offline pipeline fixtures ---------------------------------------------


def _system_spec() -> SystemSpec:
    """Minimal audited machine so the real pipeline runs without hardware I/O."""
    return SystemSpec(
        platform="win32",
        cpu_name="Intel Core i7-9700K",
        ram_gb=16.0,
        gpu_name="NVIDIA GeForce GTX 1060 6GB",
        vram_gb=6.0,
        disk_free_gb=100.0,
        audited_at=datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
    )


def _requirements_html() -> str:
    """Minimum-requirements HTML understood by the real rules-only parser."""
    return (
        "<strong>Minimum:</strong><br><ul>"
        "<li><strong>Processor:</strong> Intel Core i5-2300</li>"
        "<li><strong>Memory:</strong> 8 GB</li>"
        "<li><strong>Graphics:</strong> NVIDIA GeForce GTX 650 Ti, 2 GB VRAM</li>"
        "<li><strong>Storage:</strong> 30 GB</li>"
        "</ul>"
    )


def _fake_load_spec(*, refresh: bool = False) -> SystemSpec:
    """Stand-in for the hardware audit; never touches the machine."""
    return _system_spec()


def _offline_tui(fetch_steam: Callable[[int], SteamRequirements]) -> KeniranTui:
    """Build a TUI running the real pipeline with fully offline seams."""
    return KeniranTui(
        fetch_steam=fetch_steam,
        load_spec=_fake_load_spec,
        cpu_db={"data": []},
        gpu_db={"data": []},
    )


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def full_report() -> Report:
    """Canned full verdict report mirroring ``test_report_view.full_report``."""
    return Report(
        game_name="Example Game",
        app_id=APP_ID,
        components=[
            ComponentRow(
                component=ComponentName.CPU,
                user_value="Intel Core i7-9700K",
                required_value="Intel Core i5-2300",
                ratio=1.5,
                confidence=1.0,
                matched_name="Intel Core i5-2300 @ 2.80GHz",
            ),
            ComponentRow(
                component=ComponentName.GPU,
                user_value="NVIDIA GeForce GTX 1060 6GB",
                required_value="unverified",
                unverified=True,
            ),
            ComponentRow(
                component=ComponentName.RAM,
                user_value="16 GB",
                required_value="8 GB",
                passed=True,
            ),
        ],
        verdict=scoring.build_verdict(1.5, None, st_ratio=0.69),
    )


# --- Textual shell ---------------------------------------------------------


def test_app_mounts_shell_with_keniran_theme() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test():
            assert isinstance(tui, App)
            assert tui.theme == KENIRAN_THEME_NAME
            assert tui.current_theme.name == KENIRAN_THEME_NAME
            # No Header chrome: the shell is the scrollable body plus the Footer.
            assert isinstance(tui.query_one(Footer), Footer)
            assert not list(tui.query("Header"))
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            assert app_id_input.restrict == r"[0-9]*"
            results = tui.query_one(f"#{RESULTS_ID}", Container)
            assert len(results.children) == 0

    _run(scenario())


def test_home_screen_shows_the_keniran_brand_block() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test() as pilot:
            await pilot.pause()

            home = tui.query_one("#home")
            hero = tui.query_one(f"#{HERO_ID}", Container)
            wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)
            rule_center = tui.query_one(f"#{RULE_CENTER_ID}", Center)
            rule = tui.query_one("#keniran-rule", Rule)
            subtitle = tui.query_one(f"#{SUBTITLE_ID}", Static)
            # The hero and centered command-box wrapper are siblings in #home.
            assert hero in list(home.children)
            box = tui.query_one(f"#{COMMAND_BOX_ID}", Container)
            box_center = tui.query_one(f"#{COMMAND_BOX_CENTER_ID}", Center)
            assert box_center in list(home.children)
            assert box in list(box_center.children)
            assert box not in list(hero.children)
            assert rule_center in list(hero.children)
            assert rule in list(rule_center.children)

            # The wordmark is the ASCII art (the default 80x24 terminal shows
            # the full six-row variant).
            wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)
            assert wordmark.content.plain == "\n".join(branding.WORDMARK_LINES)
            assert wordmark.has_class("brand-wordmark")

            subtitle = tui.query_one(f"#{SUBTITLE_ID}", Static)
            assert (
                SUBTITLE == "Can I run it? Enter the target game's Steam App ID to audit this PC."
            )
            assert str(subtitle.content) == SUBTITLE

            # The brand block is stacked above the command box, never in #results,
            # which stays empty on mount.
            assert wordmark.region.y < rule.region.y < subtitle.region.y < box.region.y
            assert rule.region.width == 40
            assert rule.region.x == (hero.region.width - rule.region.width) // 2 + hero.region.x
            assert box.region.x == (tui.size.width - box.region.width) // 2
            assert len(tui.query_one(f"#{RESULTS_ID}", Container).children) == 0

    _run(scenario())


def test_app_id_control_is_grouped_in_the_command_box() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test():
            box = tui.query_one(f"#{COMMAND_BOX_ID}", Container)
            box_center = tui.query_one(f"#{COMMAND_BOX_CENTER_ID}", Center)
            assert box.has_class("command-box")
            assert box in list(box_center.children)

            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            reset_button = tui.query_one(f"#{RESET_BUTTON_ID}", Button)
            assert app_id_input in list(box.query(Input))
            assert reset_button in list(box.query(Button))

            # The grouping is visual: a rounded panel border on the surface pane.
            border_style, border_color = box.styles.border_top
            assert border_style == "round"
            assert border_color.hex == tui.get_css_variables()["panel"]
            assert box.styles.background.hex == tui.get_css_variables()["surface"]

            # The panel hugs its controls instead of a fixed wide width, stays
            # centered as one block, and leaves a gap below before the results.
            assert box.styles.is_auto_width is True
            assert box.styles.margin.top == 1
            assert box.styles.margin.bottom == 1
            assert box.region.x == (tui.size.width - box.region.width) // 2
            assert box.region.right <= tui.size.width

            # Both controls keep a real, visible region inside the box.
            assert app_id_input.region.width > 0
            assert reset_button.region.width > 0
            assert app_id_input.region.x == box.region.x + 2
            assert reset_button.region.x > app_id_input.region.x

            # Width hugs the controls: input + Reset (with its left margin) plus
            # the panel's horizontal padding and border, never a wide fixed span.
            chrome = 2 + 2  # padding (1 each side) + border (1 each side)
            assert box.region.width == (
                app_id_input.region.width + 2 + reset_button.region.width + chrome
            )
            assert box.region.width < box_center.region.width

    _run(scenario())


def test_branded_styles_use_textual_theme_tokens() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test():
            css = KeniranTui.CSS
            for token in (
                "$background",
                "$surface",
                "$panel",
                "$primary",
                "$accent",
                "$text-muted",
            ):
                assert token in css
            assert tui.current_theme.name == KENIRAN_THEME_NAME

            variables = tui.get_css_variables()
            assert variables["text"] != variables["background"]
            assert variables["primary"] == "#9A9AA0"

            # The declared amber is #E0A64B; Textual's ColorSystem resolves
            # every base colour through a LAB round-trip (lighten(0)) that can
            # shift a saturated channel by one step, so the resolved variable
            # is #DFA64B (the old tokyo-night pin encoded the same artifact:
            # declared #FF9E64 resolved to #FE9E64).
            assert tui.available_themes[KENIRAN_THEME_NAME].accent == "#E0A64B"
            assert variables["accent"] == "#DFA64B"

            # Exactly one amber accent (R1): the $accent token paints only the
            # Reset button border, and it really resolves to the theme amber.
            assert KeniranTui.CSS.count("$accent") == 1
            reset_button = tui.query_one(f"#{RESET_BUTTON_ID}", Button)
            assert reset_button.styles.border_top[1].hex == variables["accent"]

            # The wordmark is the large gray brand mark (bold + $primary).
            wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)
            assert wordmark.styles.color.hex == variables["primary"]
            assert wordmark.styles.text_style.bold

            # Body copy stays on the muted text colour, never on the warm accent.
            subtitle = tui.query_one(f"#{SUBTITLE_ID}", Static)
            assert subtitle.styles.color.a >= 0.5
            assert subtitle.styles.color.hex != variables["accent"]

            # The hero text is centered in its full-width region; the wordmark
            # and subtitle retain their own centered text alignment.
            hero = tui.query_one(f"#{HERO_ID}", Container)
            rule = tui.query_one("#keniran-rule", Rule)
            rule_center = tui.query_one(f"#{RULE_CENTER_ID}", Center)
            assert hero.styles.content_align == ("center", "middle")
            assert rule_center.styles.align_horizontal == "center"
            assert rule.styles.width.value == 40
            assert wordmark.styles.text_align == "center"
            assert subtitle.styles.text_align == "center"

    _run(scenario())


def test_keniran_theme_is_selected_and_repaints_when_switched() -> None:
    """R8/R12: ``keniran`` boots by default and ``tokyo-night`` stays selectable.

    Switching must actually repaint: a token-derived widget style changes with
    the resolved theme, not just the reported name. The command palette stays
    enabled, so F1 keeps offering the built-in theme switch.
    """

    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test() as pilot:
            assert tui.theme == KENIRAN_THEME_NAME
            assert tui.current_theme.name == KENIRAN_THEME_NAME
            assert "tokyo-night" in tui.available_themes

            keniran_variables = tui.get_css_variables()
            wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)
            keniran_color = wordmark.styles.color

            tui.theme = "tokyo-night"
            await pilot.pause()

            assert tui.current_theme.name == "tokyo-night"
            variables = tui.get_css_variables()
            assert variables["primary"] != keniran_variables["primary"]
            assert wordmark.styles.color != keniran_color
            assert wordmark.styles.color.hex == variables["primary"]

            # R8: F1 keeps the command palette (and its theme switcher). The
            # single-key binding is labelled "Menu".
            assert KeniranTui.ENABLE_COMMAND_PALETTE is True
            assert KeniranTui.COMMAND_PALETTE_BINDING == "f1"
            menu_binding = next(b for b in tui.BINDINGS if b.key == "f1")
            assert menu_binding.description == "Menu"

            # The Footer shows exactly one Menu hint: the left-side "f1" key,
            # never a second docked command-palette entry on the right.
            footer = tui.query_one(Footer)
            assert footer.show_command_palette is False
            await _wait_until(
                lambda: bool(_menu_footer_keys(footer)),
                pilot,
            )
            menu_keys = _menu_footer_keys(footer)
            assert len(menu_keys) == 1
            assert menu_keys[0].key == "f1"

    _run(scenario())


def test_home_hierarchy_fits_at_the_normal_terminal_size() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert tui.size.width == 100
            assert tui.size.height == 30

            hero = tui.query_one(f"#{HERO_ID}", Container)
            wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)
            rule = tui.query_one("#keniran-rule", Rule)
            subtitle = tui.query_one(f"#{SUBTITLE_ID}", Static)
            box = tui.query_one(f"#{COMMAND_BOX_ID}", Container)
            results = tui.query_one(f"#{RESULTS_ID}", Container)

            # The brand hero sits above the centered command box; its divider
            # is nested in a centering wrapper of its own.
            assert wordmark in list(hero.children)
            assert tui.query_one(f"#{RULE_CENTER_ID}", Center) in list(hero.children)
            assert rule in list(tui.query_one(f"#{RULE_CENTER_ID}", Center).children)
            assert subtitle in list(hero.children)
            assert wordmark.region.y < rule.region.y < subtitle.region.y < box.region.y
            assert results.region.y >= box.region.bottom

            # The whole home block is vertically centered in the body above the
            # Footer: the gap above the wordmark matches the gap below the box,
            # so the block no longer hugs the top edge.
            body = tui.query_one(f"#{BODY_ID}", VerticalScroll)
            gap_above = wordmark.region.y - body.region.y
            gap_below = body.region.bottom - box.region.bottom
            assert abs(gap_above - gap_below) <= 1
            assert gap_above > 0
            assert gap_above > box.styles.margin.top

            # Everything fits inside the visible screen at the normal size.
            assert box.region.bottom <= tui.size.height
            assert results.region.bottom <= tui.size.height
            assert len(results.children) == 0

    _run(scenario())


def test_wordmark_shows_full_art_at_a_tall_terminal() -> None:
    """R7: a 100x30 terminal shows the full six-row wordmark art."""

    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)
            assert wordmark.content.plain == "\n".join(branding.WORDMARK_LINES)

    _run(scenario())


def test_wordmark_falls_back_to_compact_art_at_a_short_terminal() -> None:
    """R7: at 80x16 the compact art keeps the home block on-screen unscrolled."""

    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test(size=(80, 16)) as pilot:
            await pilot.pause()
            wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)
            assert wordmark.content.plain == "\n".join(branding.WORDMARK_COMPACT)

            # The compact fallback must leave the App ID input fully on-screen
            # without scrolling the body.
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            assert app_id_input.region.bottom <= tui.size.height
            body = tui.query_one(f"#{BODY_ID}", VerticalScroll)
            assert body.scroll_offset.y == 0

    _run(scenario())


def test_app_id_control_is_not_horizontally_clipped() -> None:
    async def scenario() -> None:
        for width, height in ((100, 30), (80, 16)):
            tui = KeniranTui()
            async with tui.run_test(size=(width, height)) as pilot:
                await pilot.pause()
                app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
                reset_button = tui.query_one(f"#{RESET_BUTTON_ID}", Button)

                for widget in (app_id_input, reset_button):
                    region = widget.region
                    assert region.width > 0
                    assert region.height > 0
                    assert region.x >= 0
                    assert region.right <= tui.size.width

                # The controls stay inside the visible screen, never pushed
                # off the bottom by the scroll wrapper.
                assert app_id_input.region.bottom <= tui.size.height
                assert reset_button.region.bottom <= tui.size.height

    _run(scenario())


def test_controls_remain_keyboard_reachable_at_a_compact_size() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test(size=(80, 16)) as pilot:
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            reset_button = tui.query_one(f"#{RESET_BUTTON_ID}", Button)

            # The scroll region is not focusable, so the tab chain is still
            # exactly the App ID input followed by the Reset button.
            assert tui.screen.focus_chain == [app_id_input, reset_button]

            app_id_input.focus()
            await pilot.pause()
            assert tui.focused is app_id_input

            await pilot.press("7", "2", "8")
            assert app_id_input.value == "728"

            # Tab moves the focus on to the Reset button: Enter to submit and
            # the reset stay one keystroke away from either control.
            await pilot.press("tab")
            await pilot.pause()
            assert tui.focused is reset_button

    _run(scenario())


def test_long_results_scroll_to_their_end_at_a_compact_size() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test(size=(80, 16)) as pilot:
            results = tui.query_one(f"#{RESULTS_ID}", Container)
            await results.mount(*[Static(f"result line {index}") for index in range(40)])

            body = tui.query_one(f"#{BODY_ID}", VerticalScroll)
            await _wait_until(lambda: body.max_scroll_y > 0, pilot)
            assert body.show_vertical_scrollbar

            # Before scrolling, the tail hangs below the visible body: it would
            # be clipped if the body did not scroll.
            last = results.children[-1]
            await _wait_until(lambda: last.region.bottom > body.region.bottom, pilot)
            assert last.region.bottom > body.region.bottom

            body.scroll_end(animate=False, immediate=True)
            await _wait_until(lambda: body.is_vertical_scroll_end, pilot)
            # The compositor map settles on the next refresh; wait for it.
            await _wait_until(lambda: last.region.bottom <= body.region.bottom, pilot)

            assert body.scroll_offset.y == body.max_scroll_y
            assert body.is_vertical_scroll_end
            # The tail is now inside the visible body.
            assert last.region.y >= body.region.y
            assert last.region.bottom <= body.region.bottom

    _run(scenario())


def test_home_content_scrolls_to_its_end_at_a_short_height() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test(size=(80, 16)) as pilot:
            home = tui.query_one("#home")
            await home.mount(*[Static(f"home filler {index}") for index in range(30)])

            body = tui.query_one(f"#{BODY_ID}", VerticalScroll)
            await _wait_until(lambda: body.max_scroll_y > 0, pilot)

            body.scroll_end(animate=False, immediate=True)
            await _wait_until(lambda: body.is_vertical_scroll_end, pilot)
            # The long home block is reachable to its end, not clipped.
            last = home.children[-1]
            await _wait_until(lambda: last.region.bottom <= body.region.bottom, pilot)

            assert body.scroll_offset.y == body.max_scroll_y
            assert body.is_vertical_scroll_end
            assert last.region.y >= body.region.y
            assert last.region.bottom <= body.region.bottom

    _run(scenario())


def test_footer_stays_usable_while_the_body_scrolls() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test(size=(80, 16)) as pilot:
            footer = tui.query_one(Footer)
            footer_bottom = footer.region.bottom

            results = tui.query_one(f"#{RESULTS_ID}", Container)
            await results.mount(*[Static(f"result line {index}") for index in range(40)])

            body = tui.query_one(f"#{BODY_ID}", VerticalScroll)
            await _wait_until(lambda: body.max_scroll_y > 0, pilot)

            body.scroll_end(animate=False, immediate=True)
            await _wait_until(lambda: body.is_vertical_scroll_end, pilot)
            # Wait for the compositor map to settle after the scroll.
            await _wait_until(
                lambda: results.children[-1].region.bottom <= body.region.bottom,
                pilot,
            )

            assert body.is_vertical_scroll_end
            # The docked Footer stays put while the body scrolls underneath it.
            assert footer.region.bottom == footer_bottom
            assert footer.region.height > 0

    _run(scenario())


def test_app_id_input_rejects_non_digits() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test() as pilot:
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            app_id_input.focus()

            await pilot.press("a", "b", "c")
            assert app_id_input.value == ""

            await pilot.press("7", "2", "8", "5", "0")
            assert app_id_input.value == str(APP_ID)

    _run(scenario())


# --- pipeline worker -------------------------------------------------------


def test_run_executes_check_game_with_injection_kwargs_in_a_worker(
    monkeypatch: pytest.MonkeyPatch,
    full_report: Report,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_fetch_steam(app_id: int) -> Any:
        raise AssertionError("the TUI must delegate fetching to check_game")

    def fake_load_spec(*, refresh: bool = False) -> Any:
        raise AssertionError("the TUI must delegate the hardware audit to check_game")

    cpu_db: dict[str, Any] = {"data": []}
    gpu_db: dict[str, Any] = {"data": []}

    def fake_check_game(
        app_id: int,
        *,
        fetch_steam: Any = None,
        load_spec: Any = None,
        cpu_db: Any = None,
        gpu_db: Any = None,
    ) -> Report:
        calls.append(
            {
                "app_id": app_id,
                "fetch_steam": fetch_steam,
                "load_spec": load_spec,
                "cpu_db": cpu_db,
                "gpu_db": gpu_db,
                "thread": threading.get_ident(),
            }
        )
        return full_report

    monkeypatch.setattr(tui_app, "check_game", fake_check_game)

    async def scenario() -> None:
        tui = KeniranTui(
            fetch_steam=fake_fetch_steam,
            load_spec=fake_load_spec,
            cpu_db=cpu_db,
            gpu_db=gpu_db,
        )
        async with tui.run_test() as pilot:
            tui.query_one(f"#{APP_ID_INPUT_ID}", Input).value = str(APP_ID)
            await _submit(tui, pilot)
            await _wait_for_check(tui, pilot)

            assert len(calls) == 1
            call = calls[0]
            assert call["app_id"] == APP_ID
            assert call["fetch_steam"] is fake_fetch_steam
            assert call["load_spec"] is fake_load_spec
            assert call["cpu_db"] is cpu_db
            assert call["gpu_db"] is gpu_db
            # thread=True: the pipeline ran off the UI event-loop thread.
            assert call["thread"] != threading.main_thread().ident

    _run(scenario())


def test_status_line_stays_visible_while_checking_and_a_second_enter_is_a_no_op(
    monkeypatch: pytest.MonkeyPatch,
    full_report: Report,
) -> None:
    """Enter starts exactly one worker; a second Enter in flight is a no-op."""
    started = threading.Event()
    release = threading.Event()
    calls: list[int] = []

    def slow_check_game(app_id: int, **kwargs: Any) -> Report:
        calls.append(app_id)
        started.set()
        if not release.wait(timeout=5.0):
            raise AssertionError("pilot never released the fake pipeline")
        return full_report

    monkeypatch.setattr(tui_app, "check_game", slow_check_game)

    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test() as pilot:
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            app_id_input.value = str(APP_ID)

            await _submit(tui, pilot)
            await _wait_until(started.is_set, pilot)
            await pilot.pause()

            try:
                # The busy status line names the requested app id while the
                # worker runs.
                status = tui.query_one(f"#{STATUS_ID}", Static)
                assert str(APP_ID) in str(status.content)
                assert tui.is_running

                # The UI still reacts while the fake fetcher sleeps.
                app_id_input.focus()
                await pilot.pause()
                await pilot.press("9", "8")
                assert app_id_input.value.endswith("98")
                assert app_id_input.value != str(APP_ID)

                # A second Enter while the check is in flight starts no
                # worker: the worker guard drops the duplicate submission.
                await _submit(tui, pilot)
                await pilot.pause()
                assert calls == [APP_ID]
            finally:
                release.set()

            await _wait_for_check(tui, pilot)

            # The finished check replaces the status line with the report.
            assert list(tui.query(f"#{STATUS_ID}")) == []
            results = tui.query_one(f"#{RESULTS_ID}", Container)
            assert len(results.children) > 0

    _run(scenario())


def test_completed_check_mounts_the_shared_report_renderables(
    monkeypatch: pytest.MonkeyPatch,
    full_report: Report,
) -> None:
    def fake_check_game(app_id: int, **kwargs: Any) -> Report:
        return full_report

    monkeypatch.setattr(tui_app, "check_game", fake_check_game)

    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test() as pilot:
            tui.query_one(f"#{APP_ID_INPUT_ID}", Input).value = str(APP_ID)
            await _submit(tui, pilot)
            await _wait_for_check(tui, pilot)
            await pilot.pause()

            results = tui.query_one(f"#{RESULTS_ID}", Container)
            mounted = [child.content for child in results.children if isinstance(child, Static)]
            expected = report_renderables(full_report)
            assert len(mounted) == len(expected)
            assert list(tui.query(f"#{STATUS_ID}")) == []

            actual_table = next(item for item in mounted if isinstance(item, Table))
            expected_table = next(item for item in expected if isinstance(item, Table))
            actual_cells = [tuple(column.cells) for column in actual_table.columns]
            expected_cells = [tuple(column.cells) for column in expected_table.columns]
            assert [column.header for column in actual_table.columns] == [
                column.header for column in expected_table.columns
            ]
            assert actual_cells == expected_cells
            # Component rows from the canned Report.
            assert actual_cells[0] == ("CPU", "GPU", "RAM")
            assert actual_cells[2][0] == "Intel Core i7-9700K"
            assert actual_cells[4][0] == badge_text(full_report.components[0])
            assert "🔎" in actual_cells[4][0]

            texts = [item.plain for item in mounted if isinstance(item, Text)]
            assert full_report.verdict is not None
            assert full_report.verdict.percentage_text in texts
            assert BADGE_NOTE in texts
            assert "⚠ GPU: " + UNVERIFIED_NOTE in texts
            assert ST_WARNING_NOTE in texts

    _run(scenario())


def test_message_only_report_replaces_the_status_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = "No PC requirements published"
    report = Report(
        game_name=f"Steam app {APP_ID}",
        app_id=APP_ID,
        message=message,
    )

    def fake_check_game(app_id: int, **kwargs: Any) -> Report:
        return report

    monkeypatch.setattr(tui_app, "check_game", fake_check_game)

    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test() as pilot:
            tui.query_one(f"#{APP_ID_INPUT_ID}", Input).value = str(APP_ID)
            await _submit(tui, pilot)
            await _wait_for_check(tui, pilot)
            await pilot.pause()

            results = tui.query_one(f"#{RESULTS_ID}", Container)
            contents = [child.content for child in results.children if isinstance(child, Static)]
            assert contents == [Text(message)]
            assert list(tui.query(f"#{ERROR_ID}")) == []

    _run(scenario())


def test_results_replace_the_hero_and_reset_restores_the_home_screen(
    monkeypatch: pytest.MonkeyPatch,
    full_report: Report,
) -> None:
    """R5/R6/R10: results replace the hero; Reset and Esc restore the home screen.

    The hero is hidden with a ``display: none`` class — never unmounted —
    whenever the results area shows anything (status, report, or inline
    error). Reset (the button) and Esc each bring the home screen back with
    an empty input and an empty results area, ready for a new check.
    """

    def fake_check_game(app_id: int, **kwargs: Any) -> Report:
        return full_report

    monkeypatch.setattr(tui_app, "check_game", fake_check_game)

    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test() as pilot:
            home = tui.query_one("#home")
            hero = tui.query_one(f"#{HERO_ID}", Container)
            box = tui.query_one(f"#{COMMAND_BOX_ID}", Container)
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            reset_button = tui.query_one(f"#{RESET_BUTTON_ID}", Button)
            results = tui.query_one(f"#{RESULTS_ID}", Container)

            # Home screen: the hero is mounted and occupies its space.
            await pilot.pause()
            assert not hero.has_class("hidden")
            assert hero in list(home.children)
            assert hero.region.height > 0
            hero_top = hero.region.y

            # A completed check hides the hero without unmounting it: the
            # results take over its space and the command box slides up into
            # the hero's former position (offset by its top margin).
            app_id_input.value = str(APP_ID)
            await _submit(tui, pilot)
            await _wait_for_check(tui, pilot)
            await pilot.pause()

            assert hero.has_class("hidden")
            assert hero in list(home.children)
            await _wait_until(lambda: hero.region.height == 0, pilot)
            assert len(results.children) > 0
            # The body stops centering once the hero is hidden, so the command
            # box drops back to its top-aligned spot above the results.
            top_aligned_y = home.styles.padding.top + box.styles.margin.top
            await _wait_until(lambda: box.region.y == home.region.y + top_aligned_y, pilot)
            assert box.region.y < hero_top
            # A modest blank row separates the panel from the first result line.
            assert results.children[0].region.y - box.region.bottom >= 1
            # The command box (and the input in it) stays visible throughout.
            assert box.region.height > 0
            assert app_id_input.region.width > 0

            # Reset via the button restores the hero and clears everything.
            await pilot.click(reset_button)
            await pilot.pause()
            assert not hero.has_class("hidden")
            await _wait_until(lambda: hero.region.height > 0, pilot)
            assert len(results.children) == 0
            assert app_id_input.value == ""

            # The restored home screen runs a new check again.
            app_id_input.value = str(APP_ID)
            await _submit(tui, pilot)
            await _wait_for_check(tui, pilot)
            await pilot.pause()
            assert hero.has_class("hidden")
            assert len(results.children) > 0

            # Esc does the same as the Reset button.
            await pilot.press("escape")
            await pilot.pause()
            assert not hero.has_class("hidden")
            await _wait_until(lambda: hero.region.height > 0, pilot)
            assert len(results.children) == 0
            assert app_id_input.value == ""

            # The inline-error recovery path still works after a reset: an
            # invalid id mounts the red inline message (and hides the hero)
            # without ever reaching the pipeline.
            await _submit(tui, pilot)
            await _wait_until(
                lambda: "Invalid APP_ID ''" in " ".join(_error_texts(tui)),
                pilot,
            )
            assert hero.has_class("hidden")
            content = tui.query_one(f"#{ERROR_ID}", Static).content
            assert isinstance(content, Text)
            assert content.style == ERROR_STYLE

    _run(scenario())


# --- failure paths ---------------------------------------------------------


def test_invalid_app_id_shows_inline_validation_and_starts_no_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def fake_check_game(app_id: int, **kwargs: Any) -> Report:
        calls.append(app_id)
        raise AssertionError("validation must never reach the pipeline")

    monkeypatch.setattr(tui_app, "check_game", fake_check_game)

    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test() as pilot:
            # Empty input: the worker must not start and the message is styled.
            await _submit(tui, pilot)
            await _wait_until(
                lambda: "Invalid APP_ID ''" in " ".join(_error_texts(tui)),
                pilot,
            )

            assert calls == []
            error = tui.query_one(f"#{ERROR_ID}", Static)
            content = error.content
            assert isinstance(content, Text)
            assert content.plain == ("Error: Invalid APP_ID '': expected a numeric Steam app id.")
            assert content.style == ERROR_STYLE
            assert list(tui.query(f"#{STATUS_ID}")) == []

            # Non-digit input (programmatic, since the widget restricts typing).
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            app_id_input.value = "abc"
            await _submit(tui, pilot)
            await _wait_until(
                lambda: any("Invalid APP_ID 'abc'" in text for text in _error_texts(tui)),
                pilot,
            )

            assert calls == []
            content = tui.query_one(f"#{ERROR_ID}", Static).content
            assert isinstance(content, Text)
            assert content.style == ERROR_STYLE

            # Zero is not a valid Steam app id either.
            app_id_input.value = "0"
            await _submit(tui, pilot)
            await _wait_until(
                lambda: any("Invalid APP_ID '0'" in text for text in _error_texts(tui)),
                pilot,
            )

            assert calls == []
            content = tui.query_one(f"#{ERROR_ID}", Static).content
            assert isinstance(content, Text)
            assert "Invalid APP_ID '0'" in content.plain

    _run(scenario())


def test_steam_app_not_found_is_inline_and_a_later_check_recovers() -> None:
    good_app_id = 730

    def fake_fetch_steam(app_id: int) -> SteamRequirements:
        if app_id == APP_ID:
            raise steam.SteamAppNotFound(app_id)
        return SteamRequirements(
            app_id=app_id,
            name="Recovered Game",
            minimum_html=_requirements_html(),
        )

    async def scenario() -> None:
        tui = _offline_tui(fake_fetch_steam)
        async with tui.run_test() as pilot:
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            app_id_input.value = str(APP_ID)
            await _submit(tui, pilot)
            await _wait_for_check(tui, pilot)

            content = tui.query_one(f"#{ERROR_ID}", Static).content
            assert isinstance(content, Text)
            assert str(APP_ID) in content.plain
            assert "not found" in content.plain
            assert content.style == ERROR_STYLE

            # The app stays usable: a valid check recovers in the same session.
            app_id_input.value = str(good_app_id)
            await _submit(tui, pilot)
            await _wait_for_check(tui, pilot)
            await pilot.pause()

            assert list(tui.query(f"#{ERROR_ID}")) == []
            results = tui.query_one(f"#{RESULTS_ID}", Container)
            mounted = [child.content for child in results.children if isinstance(child, Static)]
            assert any(
                isinstance(item, Text) and item.plain == f"Recovered Game (Steam app {good_app_id})"
                for item in mounted
            )
            assert any(isinstance(item, Table) for item in mounted)

    _run(scenario())


def test_generic_steam_adapter_error_is_shown_inline() -> None:
    def fake_fetch_steam(app_id: int) -> SteamRequirements:
        raise steam.SteamAdapterError("Steam is unreachable")

    async def scenario() -> None:
        tui = _offline_tui(fake_fetch_steam)
        async with tui.run_test() as pilot:
            tui.query_one(f"#{APP_ID_INPUT_ID}", Input).value = str(APP_ID)
            await _submit(tui, pilot)
            await _wait_for_check(tui, pilot)

            content = tui.query_one(f"#{ERROR_ID}", Static).content
            assert isinstance(content, Text)
            assert content.plain == "Error: Steam is unreachable"
            assert content.style == ERROR_STYLE
            assert tui.is_running

    _run(scenario())


def test_unexpected_exception_surfaces_inline_instead_of_killing_the_app() -> None:
    def fake_fetch_steam(app_id: int) -> SteamRequirements:
        raise RuntimeError("boom")

    async def scenario() -> None:
        tui = _offline_tui(fake_fetch_steam)
        async with tui.run_test() as pilot:
            tui.query_one(f"#{APP_ID_INPUT_ID}", Input).value = str(APP_ID)
            await _submit(tui, pilot)
            await _wait_for_check(tui, pilot)

            content = tui.query_one(f"#{ERROR_ID}", Static).content
            assert isinstance(content, Text)
            assert "unexpected error" in content.plain.lower()
            assert "boom" in content.plain
            assert content.style == ERROR_STYLE
            assert tui.is_running

    _run(scenario())


# --- CLI dispatch ----------------------------------------------------------


def test_cli_app_id_still_runs_the_one_shot_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, bool]] = []

    def fake_check_game(app_id: int, refresh_spec: bool = False) -> Report:
        calls.append((app_id, refresh_spec))
        return Report(game_name="Example Game", app_id=app_id, message="stub report")

    monkeypatch.setattr(cli_app, "check_game", fake_check_game)

    result = CliRunner().invoke(cli, [str(APP_ID)])

    assert result.exit_code == 0, result.output
    assert calls == [(APP_ID, False)]
    assert "stub report" in result.stdout


def test_cli_tui_launches_the_tui_app(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[str] = []

    monkeypatch.setattr("keniran.tui.app.run_tui", lambda: launched.append("tui"))

    result = CliRunner().invoke(cli, ["tui"])

    assert result.exit_code == 0, result.output
    assert launched == ["tui"]


# The typer app is the console entry point; ``prog_name`` keeps the usage line
# reading ``keniran`` when the command is launched via ``python -c``.
_CONSOLE_PROGRAM = "from keniran.cli.app import app; app(prog_name='keniran')"


def _run_console(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the real CLI entry point in a fresh interpreter (no CliRunner).

    ``CliRunner`` swaps streams in-process; a subprocess reaches the installed
    script's ``standalone_mode`` path end to end, so the assertions cover the
    behavior a user actually sees at the console.
    """
    env = os.environ.copy()
    source_path = str(Path(__file__).resolve().parents[1] / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join([source_path, existing]) if existing else source_path
    return subprocess.run(
        [sys.executable, "-c", _CONSOLE_PROGRAM, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_cli_bare_invocation_prints_help_on_the_real_console() -> None:
    bare = _run_console()

    assert bare.returncode == 0, bare.stderr
    assert bare.stderr == ""
    assert "Usage:" in bare.stdout
    assert "app_id" in bare.stdout
    assert "--refresh-spec" in bare.stdout
    assert "Missing argument" not in bare.stdout

    # Bare ``keniran`` must render exactly the help ``keniran --help`` shows.
    explicit_help = _run_console("--help")
    assert explicit_help.returncode == 0, explicit_help.stderr
    assert bare.stdout == explicit_help.stdout
