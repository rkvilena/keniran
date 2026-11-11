"""Headless pilot tests for the keniran Textual app and its CLI dispatch.

The TUI tests use Textual's ``run_test`` pilot so they never touch a real
terminal, network, or hardware. Pipeline runs are faked at the
``keniran.tui.app.check_game`` seam: the fakes record the injection kwargs the
app forwards and return canned :class:`~keniran.core.models.Report` fixtures
shaped like the ones in ``test_report_view.py``.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from rich.table import Table
from rich.text import Text
from textual.app import App
from textual.containers import Container
from textual.pilot import Pilot
from textual.widgets import Button, Footer, Header, Input, Static
from typer.testing import CliRunner

import keniran.cli.app as cli_app
import keniran.tui.app as tui_app
from keniran.cli.app import app as cli
from keniran.core import scoring
from keniran.core.models import ComponentName, ComponentRow, Report
from keniran.rendering.report_view import (
    ST_WARNING_NOTE,
    UNVERIFIED_NOTE,
    badge_text,
    report_renderables,
)
from keniran.tui.app import (
    APP_ID_INPUT_ID,
    RESULTS_ID,
    RUN_BUTTON_ID,
    STATUS_ID,
    KeniranTui,
)

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
    """Wait for the pipeline worker and its completion message to settle."""
    await tui.workers.wait_for_complete()
    await pilot.pause()


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


def test_app_mounts_shell_with_tokyo_night_theme() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test():
            assert isinstance(tui, App)
            assert tui.theme == "tokyo-night"
            assert tui.current_theme.name == "tokyo-night"
            assert isinstance(tui.query_one(Header), Header)
            assert isinstance(tui.query_one(Footer), Footer)
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            assert app_id_input.restrict == r"[0-9]*"
            assert isinstance(tui.query_one(f"#{RUN_BUTTON_ID}", Button), Button)
            results = tui.query_one(f"#{RESULTS_ID}", Container)
            assert len(results.children) == 0

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


def test_cli_bare_invocation_prints_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def fake_check_game(app_id: int, refresh_spec: bool = False) -> Report:
        calls.append(app_id)
        return Report(game_name="unused", app_id=app_id)

    monkeypatch.setattr(cli_app, "check_game", fake_check_game)

    result = CliRunner().invoke(cli, [])

    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "app_id" in result.output
    assert calls == []
