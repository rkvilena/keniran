"""Offline tests for the rich :class:`Report` renderer in the keniran CLI.

Every check runs through a fake ``check_game`` (or the pure ``render_report``
helper), so no test touches Steam, dxdiag, psutil, or the benchmark databases.
Reports are built with the real pydantic models and scoring helpers, which
keeps the asserted strings anchored to the canonical sources.
"""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console
from typer.testing import CliRunner

import keniran.cli.app as cli_app
from keniran.adapters import steam
from keniran.cli.app import ST_WARNING_NOTE, app, render_report
from keniran.core import scoring
from keniran.core.models import ComponentName, ComponentRow, Report, VerdictBand
from keniran.services.check_game import NO_REQUIREMENTS_MESSAGE

APP_ID = 72850


def _pass_report() -> Report:
    """Fully passing report with two capped CPU/GPU ratios."""
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
                required_value="NVIDIA GeForce GTX 650 Ti",
                ratio=1.25,
                confidence=0.98,
                matched_name="NVIDIA GeForce GTX 650 Ti",
            ),
            ComponentRow(
                component=ComponentName.RAM,
                user_value="16 GB",
                required_value="8 GB",
                passed=True,
            ),
            ComponentRow(
                component=ComponentName.VRAM,
                user_value="6 GB",
                required_value="2 GB",
                passed=True,
            ),
            ComponentRow(
                component=ComponentName.STORAGE,
                user_value="100 GB",
                required_value="30 GB",
                passed=True,
            ),
        ],
        verdict=scoring.build_verdict(1.5, 1.25),
    )


def _84_percent_report() -> Report:
    """Verification of the 84% example from the spec (canonical Poor band)."""
    return Report(
        game_name="Example Game",
        app_id=APP_ID,
        components=[
            ComponentRow(
                component=ComponentName.CPU,
                user_value="Intel Core i5-10400",
                required_value="Intel Core i5-10400",
                ratio=0.84,
                confidence=1.0,
                matched_name="Intel Core i5-10400",
            ),
            ComponentRow(
                component=ComponentName.RAM,
                user_value="16 GB",
                required_value="8 GB",
                passed=True,
            ),
        ],
        verdict=scoring.build_verdict(0.84, 1.0),
    )


def _shortfall_report() -> Report:
    """Passing ratios capped at Fail by a RAM shortfall."""
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
                required_value="NVIDIA GeForce GTX 650 Ti",
                ratio=1.25,
                confidence=0.98,
                matched_name="NVIDIA GeForce GTX 650 Ti",
            ),
            ComponentRow(
                component=ComponentName.RAM,
                user_value="8 GB",
                required_value="16 GB",
                passed=False,
            ),
        ],
        verdict=scoring.build_verdict(1.5, 1.25, shortfalls=[ComponentName.RAM]),
    )


def _unverified_report() -> Report:
    """One unverifiable GPU while the CPU still produces a verdict."""
    return Report(
        game_name="Example Game",
        app_id=APP_ID,
        components=[
            ComponentRow(
                component=ComponentName.CPU,
                user_value="Intel Core i7-9700K",
                required_value="Intel Core i5-2300",
                ratio=1.2,
                confidence=1.0,
                matched_name="Intel Core i5-2300 @ 2.80GHz",
            ),
            ComponentRow(
                component=ComponentName.GPU,
                user_value="NVIDIA GeForce GTX 1060 6GB",
                required_value="unverified",
                unverified=True,
            ),
        ],
        verdict=scoring.build_verdict(1.2, None),
    )


def _st_warning_report() -> Report:
    """Passing multi-thread CPU whose single-thread score triggers the note."""
    return Report(
        game_name="Example Game",
        app_id=APP_ID,
        components=[
            ComponentRow(
                component=ComponentName.CPU,
                user_value="Intel Core i7-9700K",
                required_value="Intel Core i5-2300",
                ratio=1.1,
                confidence=1.0,
                matched_name="Intel Core i5-2300 @ 2.80GHz",
            ),
            ComponentRow(
                component=ComponentName.GPU,
                user_value="NVIDIA GeForce GTX 1060 6GB",
                required_value="NVIDIA GeForce GTX 650 Ti",
                ratio=1.0,
                confidence=0.98,
                matched_name="NVIDIA GeForce GTX 650 Ti",
            ),
        ],
        verdict=scoring.build_verdict(1.1, 1.0, st_ratio=0.69),
    )


def _render(report: Report) -> str:
    """Render to a wide, color-free console so table cells do not wrap."""
    output = StringIO()
    render_report(report, Console(file=output, width=200, color_system=None))
    return output.getvalue()


def _patch_check_game(
    monkeypatch: pytest.MonkeyPatch,
    report: Report | None = None,
    *,
    calls: list[tuple[int, bool]] | None = None,
    error: Exception | None = None,
) -> None:
    """Replace the CLI's pipeline with a recording fake."""

    def fake_check_game(app_id: int, refresh_spec: bool = False) -> Report:
        if calls is not None:
            calls.append((app_id, refresh_spec))
        if error is not None:
            raise error
        assert report is not None
        return report

    monkeypatch.setattr(cli_app, "check_game", fake_check_game)


# --- pure renderer ---------------------------------------------------------


def test_pass_report_renders_table_verdict_and_caps_display_percent() -> None:
    report = _pass_report()
    assert report.verdict is not None
    assert report.verdict.band is VerdictBand.PASS

    output = _render(report)

    assert "Example Game (Steam app 72850)" in output
    for header in ("Component", "Required", "Your System", "Result", "Badge / Notes"):
        assert header in output

    assert "Intel Core i7-9700K" in output
    assert "Intel Core i5-2300 @ 2.80GHz" in output
    assert output.count("100% (meets requirement)") == 2
    assert "125%" not in output
    assert "150%" not in output

    assert "⚡ 'NVIDIA GeForce GTX 650 Ti' (98%)" in output
    assert "100% of the game's minimum requirement (Pass — meets requirement)" in output
    assert "Single-thread" not in output


def test_percentage_verdict_line_uses_canonical_band_text() -> None:
    report = _84_percent_report()
    assert report.verdict is not None
    assert report.verdict.display_percent == pytest.approx(84.0)
    assert report.verdict.band is VerdictBand.POOR

    output = _render(report)

    assert "84%" in output
    assert "84% of the game's minimum requirement (Poor — low FPS expected)" in output

    borderline = Report(
        game_name="Example Game",
        app_id=APP_ID,
        components=[
            ComponentRow(
                component=ComponentName.CPU,
                user_value="Intel Core i5-10400",
                required_value="Intel Core i5-10400",
                ratio=0.85,
                confidence=1.0,
                matched_name="Intel Core i5-10400",
            )
        ],
        verdict=scoring.build_verdict(0.85, 1.0),
    )
    assert borderline.verdict is not None
    assert borderline.verdict.band is VerdictBand.BORDERLINE
    assert (
        "85% of the game's minimum requirement (Borderline — playable on low settings)"
        in _render(borderline)
    )


def test_shortfall_report_renders_fail_verdict_and_failed_row() -> None:
    report = _shortfall_report()
    assert report.verdict is not None
    assert report.verdict.band is VerdictBand.FAIL

    output = _render(report)

    assert "100% of the game's minimum requirement — Fail (spec shortfall: RAM)" in output
    assert "below requirement" in output


def test_unverified_component_renders_warning_note() -> None:
    report = _unverified_report()
    assert report.verdict is not None
    assert report.verdict.band is VerdictBand.PASS

    output = _render(report)

    assert "⚠ GPU: unverified — manual review suggested" in output


def test_st_warning_renders_note() -> None:
    report = _st_warning_report()
    assert report.verdict is not None
    assert report.verdict.st_warning is True

    output = _render(report)

    assert ST_WARNING_NOTE in output


# --- CLI integration (fake pipeline, no network) ---------------------------


def test_cli_renders_pass_report(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_check_game(monkeypatch, _pass_report())

    result = CliRunner().invoke(app, [str(APP_ID)])

    assert result.exit_code == 0, result.output
    assert "Example Game" in result.stdout
    assert "100% of the game's minimum requirement (Pass — meets requirement)" in result.stdout


def test_cli_unverified_component_completes_with_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_check_game(monkeypatch, _unverified_report())

    result = CliRunner().invoke(app, [str(APP_ID)])

    assert result.exit_code == 0, result.output
    assert "⚠ GPU: unverified — manual review suggested" in result.stdout


def test_cli_st_warning_note_is_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_check_game(monkeypatch, _st_warning_report())

    result = CliRunner().invoke(app, [str(APP_ID)])

    assert result.exit_code == 0, result.output
    assert ST_WARNING_NOTE in result.stdout


def test_cli_no_requirements_prints_message_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = Report(
        game_name=f"Steam app {APP_ID}",
        app_id=APP_ID,
        message=NO_REQUIREMENTS_MESSAGE,
    )
    _patch_check_game(monkeypatch, report)

    result = CliRunner().invoke(app, [str(APP_ID)])

    assert result.exit_code == 0, result.output
    assert NO_REQUIREMENTS_MESSAGE in result.stdout
    assert result.stderr == ""


def test_cli_steam_app_not_found_prints_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_check_game(monkeypatch, error=steam.SteamAppNotFound(APP_ID))

    result = CliRunner().invoke(app, [str(APP_ID)])

    assert result.exit_code != 0
    assert "Error:" in result.stderr
    assert f"Steam app {APP_ID} was not found" in result.stderr


def test_cli_unexpected_error_is_reported_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_check_game(monkeypatch, error=RuntimeError("pipeline exploded"))

    result = CliRunner().invoke(app, [str(APP_ID)])

    assert result.exit_code != 0
    assert "Error:" in result.stderr
    assert "pipeline exploded" in result.stderr
    assert "Traceback" not in result.stderr


def test_version_flag_still_prints_installed_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, bool]] = []
    _patch_check_game(monkeypatch, _pass_report(), calls=calls)

    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "keniran 0.1.0"
    assert calls == []


@pytest.mark.parametrize("raw", ["abc", "12.5", "0"])
def test_non_numeric_app_id_prints_clear_error(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    calls: list[tuple[int, bool]] = []
    _patch_check_game(monkeypatch, _pass_report(), calls=calls)

    result = CliRunner().invoke(app, [raw])

    assert result.exit_code != 0
    assert "Invalid APP_ID" in result.stderr
    assert "numeric Steam app id" in result.stderr
    assert calls == []


@pytest.mark.parametrize(
    ("extra_args", "expected_refresh"),
    [([], False), (["--refresh-spec"], True)],
)
def test_refresh_spec_flag_is_forwarded_to_check_game(
    monkeypatch: pytest.MonkeyPatch,
    extra_args: list[str],
    expected_refresh: bool,
) -> None:
    calls: list[tuple[int, bool]] = []
    _patch_check_game(monkeypatch, _pass_report(), calls=calls)

    result = CliRunner().invoke(app, [str(APP_ID), *extra_args])

    assert result.exit_code == 0, result.output
    assert calls == [(APP_ID, expected_refresh)]
    assert "Example Game" in result.stdout
