"""Pure :class:`~keniran.core.models.Report` → rich renderables shared by UIs.

This module implements the renderer contract from plan/decisions.md §3: the
pipeline returns a plain ``Report`` and every UI is just a renderer of it. The
functions here are pure presentation — no console, no I/O, and no scoring
beyond the canonical :mod:`keniran.core.scoring` helpers — so the one-shot CLI
and any future UI render the same objects in the same order.

Honesty semantics live here once: ⚠ unverified rows, 🔎 matched-benchmark
confidence badges (with a subdued legend), the single-thread warning, and
graceful message-only reports.
"""

from __future__ import annotations

from typing import Final

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

from keniran.core import scoring
from keniran.core.models import ComponentRow, Report, VerdictBand

UNVERIFIED_NOTE: Final = "unverified — manual review suggested"
ST_WARNING_NOTE: Final = (
    "⚠ Warning: Single-thread performance is below 70% of the required CPU score."
)
BADGE_NOTE: Final = (
    "🔎 marks the benchmark match for the listed CPU/GPU requirement; its % is "
    "match confidence. Result compares your system with that benchmark."
)
BADGE_NOTE_STYLE: Final = "dim"

# Presentation palette shared by every renderer. The amber, muted green, and
# muted red match the ``keniran`` theme's accent/success/error roles; unverified
# results stay neutral instead of borrowing a status hue.
AMBER_COLOR: Final = "#E0A64B"
PASS_COLOR: Final = "#7FA97F"
FAIL_COLOR: Final = "#C96A6A"
UNVERIFIED_STYLE: Final = "dim"



def result_text(row: ComponentRow) -> str:
    """Return the human-facing result/ratio cell for one component row."""
    if row.ratio is not None:
        percent = scoring.display_percent(row.ratio)
        if row.ratio >= scoring.PASS_RATIO:
            return f"{percent:.0f}% (meets requirement)"
        return f"{percent:.0f}%"
    if row.passed is True:
        return "meets requirement"
    if row.passed is False:
        return "below requirement"
    return "unverified"


def result_style(row: ComponentRow) -> str:
    """Return the semantic color for one component Result cell.

    Verified ratios follow the scoring bands (Pass green, Borderline/Poor
    amber, Unplayable red); hard-check rows follow their pass state
    (True green, False red). Anything unverified stays neutral.
    """
    if row.ratio is not None:
        if row.ratio >= scoring.PASS_RATIO:
            return PASS_COLOR
        if row.ratio >= scoring.POOR_RATIO:
            return AMBER_COLOR
        return FAIL_COLOR
    if row.passed is True:
        return PASS_COLOR
    if row.passed is False:
        return FAIL_COLOR
    return UNVERIFIED_STYLE


def verdict_style(band: VerdictBand) -> str:
    """Return the semantic color for the overall verdict band."""
    if band is VerdictBand.PASS:
        return PASS_COLOR
    if band in (VerdictBand.BORDERLINE, VerdictBand.POOR):
        return AMBER_COLOR
    if band in (VerdictBand.UNPLAYABLE, VerdictBand.FAIL):
        return FAIL_COLOR
    return UNVERIFIED_STYLE


def badge_text(row: ComponentRow) -> str:
    """Return the 🔎 confidence badge for a matched (possibly best-guess) name."""
    if row.matched_name is None:
        return ""
    if row.confidence is None:
        return f"🔎 {row.matched_name!r}"
    return f"🔎 {row.matched_name!r} ({row.confidence:.0%})"


def _component_table(report: Report) -> Table:
    """Build the per-component comparison table with semantic result colors."""
    table = Table(show_header=True, header_style="bold", border_style=AMBER_COLOR)
    table.add_column("Component")
    table.add_column("Required")
    table.add_column("Your System")
    table.add_column("Result")
    table.add_column("Badge / Notes")
    for row in report.components:
        table.add_row(
            row.component.value,
            row.required_value,
            row.user_value,
            Text(result_text(row), style=result_style(row)),
            badge_text(row),
        )
    return table


def report_renderables(report: Report) -> list[RenderableType]:
    """Return the ordered rich renderables that render *report*.

    The sequence matches the CLI output exactly: the title line, the component
    table, the subdued badge legend (🔎 match explanation), one ⚠ line per
    unverified row, the single-thread warning, the graceful message, and finally
    the blank line plus bold verdict percentage. A message-only report (no
    requirements published) yields just its message.
    """
    if report.message is not None and report.verdict is None and not report.components:
        return [Text(report.message)]

    renderables: list[RenderableType] = [
        Text(f"{report.game_name} (Steam app {report.app_id})", style=f"bold {AMBER_COLOR}")
    ]

    if report.components:
        renderables.append(_component_table(report))
        renderables.append(Text(BADGE_NOTE, style=BADGE_NOTE_STYLE))
        for row in report.components:
            if row.unverified:
                renderables.append(Text(f"⚠ {row.component.value}: {UNVERIFIED_NOTE}"))
        if report.verdict is not None and report.verdict.st_warning:
            renderables.append(Text(ST_WARNING_NOTE))

    if report.message is not None:
        renderables.append(Text(report.message))

    if report.verdict is not None:
        renderables.append(Text())
        renderables.append(
            Text(
                report.verdict.percentage_text,
                style=f"bold {verdict_style(report.verdict.band)}",
            )
        )

    return renderables
