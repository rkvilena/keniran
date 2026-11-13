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
from textual.containers import Container, VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Button, Footer, Input, Static
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
    ST_WARNING_NOTE,
    UNVERIFIED_NOTE,
    badge_text,
    report_renderables,
)
from keniran.tui import branding
from keniran.tui.app import (
    APP_ID_INPUT_ID,
    BODY_ID,
    COMMAND_BOX_ID,
    ERROR_ID,
    ERROR_STYLE,
    HERO_ID,
    RESULTS_ID,
    RUN_BUTTON_ID,
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


def _error_texts(tui: KeniranTui) -> list[str]:
    """Return the plain text of every inline error currently mounted."""
    return [
        child.content.plain
        for child in tui.query(f"#{ERROR_ID}")
        if isinstance(child, Static) and isinstance(child.content, Text)
    ]


async def _click_run(tui: KeniranTui, pilot: Pilot) -> None:
    """Click Run once the button's press animation no longer swallows clicks."""
    button = tui.query_one(f"#{RUN_BUTTON_ID}", Button)
    await _wait_until(lambda: not button.has_class("-active"), pilot)
    await pilot.click(f"#{RUN_BUTTON_ID}")


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
            assert isinstance(tui.query_one(f"#{RUN_BUTTON_ID}", Button), Button)
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
            # The hero is nested inside #home, and the command box is its sibling.
            assert hero in list(home.children)
            box = tui.query_one(f"#{COMMAND_BOX_ID}", Container)
            assert box in list(home.children)
            assert box not in list(hero.children)

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
            assert wordmark.region.y < subtitle.region.y < box.region.y
            assert len(tui.query_one(f"#{RESULTS_ID}", Container).children) == 0

    _run(scenario())


def test_app_id_and_run_controls_are_grouped_in_the_command_box() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test():
            box = tui.query_one(f"#{COMMAND_BOX_ID}", Container)
            assert box.has_class("command-box")

            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            run_button = tui.query_one(f"#{RUN_BUTTON_ID}", Button)
            assert app_id_input in list(box.query(Input))
            assert run_button in list(box.query(Button))

            # The grouping is visual: a rounded panel border on the surface pane.
            border_style, border_color = box.styles.border_top
            assert border_style == "round"
            assert border_color.hex == tui.get_css_variables()["panel"]
            assert box.styles.background.hex == tui.get_css_variables()["surface"]

            # Both controls keep a real, visible region inside the box.
            assert app_id_input.region.width > 0
            assert run_button.region.width > 0

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

            # Exactly one accent role: the $accent token appears only on the
            # Run button border, which really paints the resolved amber.
            assert KeniranTui.CSS.count("$accent") == 1
            run_button = tui.query_one(f"#{RUN_BUTTON_ID}", Button)
            assert run_button.styles.border_top[1].hex == variables["accent"]

            # The wordmark is the large gray brand mark (bold + $primary).
            wordmark = tui.query_one(f"#{WORDMARK_ID}", Static)
            assert wordmark.styles.color.hex == variables["primary"]
            assert wordmark.styles.text_style.bold

            # Body copy stays on the muted text colour, never on the warm accent.
            subtitle = tui.query_one(f"#{SUBTITLE_ID}", Static)
            assert subtitle.styles.color.a >= 0.5
            assert subtitle.styles.color.hex != variables["accent"]

            # The hero is centered: its content is centered inside the hero and
            # both children center their own text (the repo's only centering
            # rules — there is no prior text-align/content-align rule).
            hero = tui.query_one(f"#{HERO_ID}", Container)
            assert hero.styles.content_align == ("center", "middle")
            assert wordmark.styles.text_align == "center"
            assert subtitle.styles.text_align == "center"

    _run(scenario())


def test_keniran_theme_is_selected_and_repaints_when_switched() -> None:
    """R8/R12: ``keniran`` boots by default and ``tokyo-night`` stays selectable.

    Switching must actually repaint: a token-derived widget style changes with
    the resolved theme, not just the reported name. The command palette stays
    enabled, so Ctrl+P keeps offering the built-in theme switch.
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

            # R8: Ctrl+P keeps the command palette (and its theme switcher).
            assert KeniranTui.ENABLE_COMMAND_PALETTE is True
            assert KeniranTui.COMMAND_PALETTE_BINDING == "ctrl+p"

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
            subtitle = tui.query_one(f"#{SUBTITLE_ID}", Static)
            box = tui.query_one(f"#{COMMAND_BOX_ID}", Container)
            results = tui.query_one(f"#{RESULTS_ID}", Container)

            # The branded hierarchy survives the scroll wrapper unchanged: the
            # hero (wordmark above subtitle) sits above the command box.
            assert wordmark in list(hero.children)
            assert subtitle in list(hero.children)
            assert wordmark.region.y < subtitle.region.y < box.region.y
            assert results.region.y >= box.region.bottom

            # Everything fits inside the visible screen at the normal size.
            assert box.region.bottom <= tui.size.height
            assert results.region.bottom <= tui.size.height
            assert results.region.height > 0
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


def test_app_id_and_run_controls_are_not_horizontally_clipped() -> None:
    async def scenario() -> None:
        for width, height in ((100, 30), (80, 16)):
            tui = KeniranTui()
            async with tui.run_test(size=(width, height)) as pilot:
                await pilot.pause()
                app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
                run_button = tui.query_one(f"#{RUN_BUTTON_ID}", Button)

                for widget in (app_id_input, run_button):
                    region = widget.region
                    assert region.width > 0
                    assert region.height > 0
                    assert region.x >= 0
                    assert region.right <= tui.size.width

                # The controls stay inside the visible screen, never pushed off
                # the bottom by the scroll wrapper.
                assert app_id_input.region.bottom <= tui.size.height
                assert run_button.region.bottom <= tui.size.height

    _run(scenario())


def test_controls_remain_keyboard_reachable_at_a_compact_size() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test(size=(80, 16)) as pilot:
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            run_button = tui.query_one(f"#{RUN_BUTTON_ID}", Button)

            # The scroll region is not focusable, so the tab chain is still
            # exactly the input followed by the Run button.
            assert tui.screen.focus_chain == [app_id_input, run_button]

            app_id_input.focus()
            await pilot.pause()
            assert tui.focused is app_id_input

            await pilot.press("7", "2", "8")
            assert app_id_input.value == "728"

            await pilot.press("tab")
            await pilot.pause()
            assert tui.focused is run_button

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
            await pilot.click(f"#{RUN_BUTTON_ID}")
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


def test_status_and_disabled_run_stay_visible_while_checking(
    monkeypatch: pytest.MonkeyPatch,
    full_report: Report,
) -> None:
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
            run_button = tui.query_one(f"#{RUN_BUTTON_ID}", Button)

            await pilot.click(f"#{RUN_BUTTON_ID}")
            await _wait_until(started.is_set, pilot)
            await pilot.pause()

            try:
                assert run_button.disabled is True
                status = tui.query_one(f"#{STATUS_ID}", Static)
                assert str(APP_ID) in str(status.content)
                assert tui.is_running

                # The UI still reacts while the fake fetcher sleeps.
                app_id_input.focus()
                await pilot.pause()
                await pilot.press("9", "8")
                assert app_id_input.value.endswith("98")
                assert app_id_input.value != str(APP_ID)

                # A second click on the disabled Run button starts no worker.
                await pilot.click(f"#{RUN_BUTTON_ID}")
                await pilot.pause()
                assert calls == [APP_ID]
            finally:
                release.set()

            await _wait_for_check(tui, pilot)

            assert run_button.disabled is False
            assert list(tui.query(f"#{STATUS_ID}")) == []

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
            await pilot.click(f"#{RUN_BUTTON_ID}")
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
            assert "⚡" in actual_cells[4][0]

            texts = [item.plain for item in mounted if isinstance(item, Text)]
            assert full_report.verdict is not None
            assert full_report.verdict.percentage_text in texts
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
            await pilot.click(f"#{RUN_BUTTON_ID}")
            await _wait_for_check(tui, pilot)
            await pilot.pause()

            results = tui.query_one(f"#{RESULTS_ID}", Container)
            contents = [child.content for child in results.children if isinstance(child, Static)]
            assert contents == [Text(message)]
            assert list(tui.query(f"#{ERROR_ID}")) == []

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
            await _click_run(tui, pilot)
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
            assert tui.query_one(f"#{RUN_BUTTON_ID}", Button).disabled is False
            assert list(tui.query(f"#{STATUS_ID}")) == []

            # Non-digit input (programmatic, since the widget restricts typing).
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            app_id_input.value = "abc"
            await _click_run(tui, pilot)
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
            await _click_run(tui, pilot)
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
            await pilot.click(f"#{RUN_BUTTON_ID}")
            await _wait_for_check(tui, pilot)

            content = tui.query_one(f"#{ERROR_ID}", Static).content
            assert isinstance(content, Text)
            assert str(APP_ID) in content.plain
            assert "not found" in content.plain
            assert content.style == ERROR_STYLE
            assert tui.query_one(f"#{RUN_BUTTON_ID}", Button).disabled is False

            # The app stays usable: a valid check recovers in the same session.
            app_id_input.value = str(good_app_id)
            await _click_run(tui, pilot)
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
            await pilot.click(f"#{RUN_BUTTON_ID}")
            await _wait_for_check(tui, pilot)

            content = tui.query_one(f"#{ERROR_ID}", Static).content
            assert isinstance(content, Text)
            assert content.plain == "Error: Steam is unreachable"
            assert content.style == ERROR_STYLE
            assert tui.is_running
            assert tui.query_one(f"#{RUN_BUTTON_ID}", Button).disabled is False

    _run(scenario())


def test_unexpected_exception_surfaces_inline_instead_of_killing_the_app() -> None:
    def fake_fetch_steam(app_id: int) -> SteamRequirements:
        raise RuntimeError("boom")

    async def scenario() -> None:
        tui = _offline_tui(fake_fetch_steam)
        async with tui.run_test() as pilot:
            tui.query_one(f"#{APP_ID_INPUT_ID}", Input).value = str(APP_ID)
            await pilot.click(f"#{RUN_BUTTON_ID}")
            await _wait_for_check(tui, pilot)

            content = tui.query_one(f"#{ERROR_ID}", Static).content
            assert isinstance(content, Text)
            assert "unexpected error" in content.plain.lower()
            assert "boom" in content.plain
            assert content.style == ERROR_STYLE
            assert tui.is_running
            assert tui.query_one(f"#{RUN_BUTTON_ID}", Button).disabled is False

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
