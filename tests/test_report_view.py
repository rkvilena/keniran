"""Offline tests for the shared report renderer.

``keniran.rendering.report_view`` is pure: it turns a real pydantic
:class:`~keniran.core.models.Report` into an ordered list of rich renderables
without touching Steam, hardware, a terminal, or the network. The fixtures
below use the canonical scoring helpers so the asserted strings stay anchored
to their single source of truth.
"""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console
from rich.table import Table
from rich.text import Text

from keniran.cli.app import render_report
from keniran.core import scoring
from keniran.core.models import ComponentName, ComponentRow, Report, Verdict, VerdictBand
from keniran.rendering.report_view import (
    AMBER_COLOR,
    BADGE_NOTE,
    FAIL_COLOR,
    PASS_COLOR,
    ST_WARNING_NOTE,
    UNVERIFIED_NOTE,
    UNVERIFIED_STYLE,
    badge_text,
    report_renderables,
    result_style,
    result_text,
    verdict_style,
)
from keniran.services.check_game import NO_REQUIREMENTS_MESSAGE

APP_ID = 72850


@pytest.fixture
def message_only_report() -> Report:
    """Report shape for a game without published PC requirements."""
    return Report(
        game_name=f"Steam app {APP_ID}",
        app_id=APP_ID,
        message=NO_REQUIREMENTS_MESSAGE,
    )


@pytest.fixture
def full_report() -> Report:
    """Full verdict report: scored CPU, unverified GPU, and an ST warning."""
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


def _render(report: Report) -> str:
    """Render through the CLI to a wide, color-free console."""
    output = StringIO()
    render_report(report, Console(file=output, width=200, color_system=None))
    return output.getvalue()


# --- message-only path -----------------------------------------------------


def test_message_only_report_returns_a_single_message_renderable(
    message_only_report: Report,
) -> None:
    renderables = report_renderables(message_only_report)

    assert len(renderables) == 1
    message = renderables[0]
    assert isinstance(message, Text)
    assert message.plain == NO_REQUIREMENTS_MESSAGE
    assert message.style == ""


def test_message_only_report_renders_nothing_else(message_only_report: Report) -> None:
    assert _render(message_only_report) == f"{NO_REQUIREMENTS_MESSAGE}\n"


# --- full verdict path -----------------------------------------------------


def test_full_verdict_report_returns_ordered_renderables(full_report: Report) -> None:
    assert full_report.verdict is not None

    renderables = report_renderables(full_report)

    assert len(renderables) == 7
    (
        title,
        table,
        badge_line,
        unverified_line,
        st_warning_line,
        blank_line,
        verdict_line,
    ) = renderables

    assert isinstance(title, Text)
    assert title.plain == f"Example Game (Steam app {APP_ID})"
    assert title.style == f"bold {AMBER_COLOR}"

    assert isinstance(badge_line, Text)
    assert badge_line.plain == BADGE_NOTE
    assert badge_line.style == "dim"

    assert isinstance(table, Table)
    assert table.border_style == AMBER_COLOR
    assert [column.header for column in table.columns] == [
        "Component",
        "Required",
        "Your System",
        "Result",
        "Badge / Notes",
    ]
    assert [tuple(column.cells) for column in table.columns[:3]] == [
        ("CPU", "GPU", "RAM"),
        ("Intel Core i5-2300", "unverified", "8 GB"),
        ("Intel Core i7-9700K", "NVIDIA GeForce GTX 1060 6GB", "16 GB"),
    ]
    result_cells = list(table.columns[3].cells)
    assert [cell.plain for cell in result_cells] == [
        "100% (meets requirement)",
        "unverified",
        "meets requirement",
    ]
    assert [cell.style for cell in result_cells] == [
        PASS_COLOR,
        UNVERIFIED_STYLE,
        PASS_COLOR,
    ]
    assert tuple(table.columns[4].cells) == (
        "🔎 'Intel Core i5-2300 @ 2.80GHz' (100%)",
        "",
        "",
    )

    assert isinstance(unverified_line, Text)
    assert unverified_line.plain == f"⚠ GPU: {UNVERIFIED_NOTE}"

    assert isinstance(st_warning_line, Text)
    assert st_warning_line.plain == ST_WARNING_NOTE

    assert isinstance(blank_line, Text)
    assert blank_line.plain == ""

    assert isinstance(verdict_line, Text)
    assert verdict_line.plain == full_report.verdict.percentage_text
    assert verdict_line.style == f"bold {PASS_COLOR}"


def test_full_verdict_report_renders_renderables_in_order(full_report: Report) -> None:
    output = _render(full_report)

    title_at = output.index(f"Example Game (Steam app {APP_ID})")
    table_at = output.index("Component")
    badge_at = output.index(BADGE_NOTE)
    unverified_at = output.index(f"⚠ GPU: {UNVERIFIED_NOTE}")
    st_warning_at = output.index(ST_WARNING_NOTE)
    verdict_at = output.index("100% of the game's minimum requirement")

    assert title_at < table_at < badge_at < unverified_at < st_warning_at < verdict_at


def test_message_line_precedes_the_verdict(full_report: Report) -> None:
    report = full_report.model_copy(update={"message": "Steam metadata note"})

    renderables = report_renderables(report)

    message_indices = [
        index
        for index, renderable in enumerate(renderables)
        if isinstance(renderable, Text) and renderable.plain == "Steam metadata note"
    ]
    assert message_indices == [len(renderables) - 3]
    assert isinstance(renderables[-2], Text)
    assert renderables[-2].plain == ""


# --- cell helpers ----------------------------------------------------------


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (1.5, "100% (meets requirement)"),
        (1.0, "100% (meets requirement)"),
        (0.84, "84%"),
        (0.654, "65%"),
    ],
)
def test_result_text_uses_canonical_display_percent(ratio: float, expected: str) -> None:
    row = ComponentRow(
        component=ComponentName.CPU,
        user_value="user",
        required_value="required",
        ratio=ratio,
    )

    assert result_text(row) == expected


@pytest.mark.parametrize(
    ("passed", "expected"),
    [(True, "meets requirement"), (False, "below requirement"), (None, "unverified")],
)
def test_result_text_falls_back_to_the_pass_state(passed: bool | None, expected: str) -> None:
    row = ComponentRow(
        component=ComponentName.RAM,
        user_value="user",
        required_value="required",
        passed=passed,
    )

    assert result_text(row) == expected


def test_badge_text_is_empty_without_a_matched_name() -> None:
    row = ComponentRow(
        component=ComponentName.CPU,
        user_value="user",
        required_value="required",
    )

    assert badge_text(row) == ""


def test_badge_text_shows_the_matched_name_without_confidence() -> None:
    row = ComponentRow(
        component=ComponentName.CPU,
        user_value="user",
        required_value="required",
        matched_name="Intel Core i5-2300",
    )

    assert badge_text(row) == "🔎 'Intel Core i5-2300'"


def test_badge_text_shows_the_matched_name_and_confidence() -> None:
    row = ComponentRow(
        component=ComponentName.CPU,
        user_value="user",
        required_value="required",
        matched_name="Intel Core i5-2300",
        confidence=0.98,
    )

    assert badge_text(row) == "🔎 'Intel Core i5-2300' (98%)"


# --- semantic colors -------------------------------------------------------


@pytest.mark.parametrize(
    ("ratio", "expected_style"),
    [
        (1.5, PASS_COLOR),
        (1.0, PASS_COLOR),
        (0.85, AMBER_COLOR),
        (0.84, AMBER_COLOR),
        (0.65, AMBER_COLOR),
        (0.64, FAIL_COLOR),
    ],
)
def test_result_style_follows_the_scoring_ratio_bands(
    ratio: float,
    expected_style: str,
) -> None:
    row = ComponentRow(
        component=ComponentName.CPU,
        user_value="user",
        required_value="required",
        ratio=ratio,
    )

    assert result_style(row) == expected_style


@pytest.mark.parametrize(
    ("passed", "expected_style"),
    [(True, PASS_COLOR), (False, FAIL_COLOR), (None, UNVERIFIED_STYLE)],
)
def test_result_style_follows_the_component_pass_state(
    passed: bool | None,
    expected_style: str,
) -> None:
    row = ComponentRow(
        component=ComponentName.RAM,
        user_value="user",
        required_value="required",
        passed=passed,
    )

    assert result_style(row) == expected_style


def test_unverified_component_result_stays_neutral() -> None:
    row = ComponentRow(
        component=ComponentName.GPU,
        user_value="NVIDIA GeForce GTX 1060 6GB",
        required_value="unverified",
        unverified=True,
    )

    assert result_style(row) == UNVERIFIED_STYLE


@pytest.mark.parametrize(
    ("band", "expected_style"),
    [
        (VerdictBand.PASS, PASS_COLOR),
        (VerdictBand.BORDERLINE, AMBER_COLOR),
        (VerdictBand.POOR, AMBER_COLOR),
        (VerdictBand.UNPLAYABLE, FAIL_COLOR),
        (VerdictBand.FAIL, FAIL_COLOR),
        (VerdictBand.UNVERIFIED, UNVERIFIED_STYLE),
    ],
)
def test_verdict_style_maps_every_band(band: VerdictBand, expected_style: str) -> None:
    assert verdict_style(band) == expected_style


@pytest.mark.parametrize(
    ("verdict", "expected_style"),
    [
        (scoring.build_verdict(1.5, None), PASS_COLOR),
        (scoring.build_verdict(0.85, None), AMBER_COLOR),
        (scoring.build_verdict(0.84, None), AMBER_COLOR),
        (scoring.build_verdict(0.5, None), FAIL_COLOR),
        (scoring.build_verdict(None, None), UNVERIFIED_STYLE),
        (
            scoring.build_verdict(1.5, None, shortfalls=[ComponentName.STORAGE]),
            FAIL_COLOR,
        ),
    ],
)
def test_overall_verdict_line_is_colored_from_its_band(
    verdict: Verdict,
    expected_style: str,
) -> None:
    report = Report(
        game_name="Example Game",
        app_id=APP_ID,
        components=[
            ComponentRow(
                component=ComponentName.CPU,
                user_value="user",
                required_value="required",
                ratio=1.5,
            )
        ],
        verdict=verdict,
    )

    verdict_line = report_renderables(report)[-1]

    assert isinstance(verdict_line, Text)
    assert verdict_line.plain == verdict.percentage_text
    assert verdict_line.style == f"bold {expected_style}"

