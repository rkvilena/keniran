"""Headless pilot tests for the keniran Textual scaffold and its CLI dispatch.

The TUI tests use Textual's ``run_test`` pilot so they never touch a real
terminal, network, or hardware. CLI dispatch tests monkeypatch the lazily
imported ``run_tui`` (or ``check_game``) and pin the three public contracts:
one-shot ``keniran <APP_ID>``, ``keniran tui``, and bare ``keniran`` help.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

import pytest
from textual.app import App
from textual.containers import Container
from textual.widgets import Button, Footer, Header, Input
from typer.testing import CliRunner

import keniran.cli.app as cli_app
from keniran.cli.app import app as cli
from keniran.core.models import Report
from keniran.tui.app import (
    APP_ID_INPUT_ID,
    RESULTS_ID,
    RUN_BUTTON_ID,
    KeniranTui,
)

APP_ID = 72850


def _run(scenario: Coroutine[Any, Any, None]) -> None:
    """Run one async pilot scenario on a fresh event loop."""
    asyncio.run(scenario)


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


def test_run_button_with_app_id_does_not_crash() -> None:
    async def scenario() -> None:
        tui = KeniranTui()
        async with tui.run_test() as pilot:
            app_id_input = tui.query_one(f"#{APP_ID_INPUT_ID}", Input)
            app_id_input.focus()
            await pilot.press("7", "2", "8", "5", "0")

            await pilot.click(f"#{RUN_BUTTON_ID}")
            await pilot.pause()

            results = tui.query_one(f"#{RESULTS_ID}", Container)
            assert len(results.children) == 1
            assert str(APP_ID) in str(results.children[0].render())
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
