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
from keniran.core.models import ComponentRow, Report

UNVERIFIED_NOTE: Final = "unverified — manual review suggested"
ST_WARNING_NOTE: Final = (
    "⚠ Warning: Single-thread performance is below 70% of the required CPU score."
)
BADGE_NOTE: Final = (
    "🔎 marks the benchmark match for the listed CPU/GPU requirement; its % is "
    "match confidence. Result compares your system with that benchmark."
)
BADGE_NOTE_STYLE: Final = "dim"


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


def badge_text(row: ComponentRow) -> str:
    """Return the 🔎 confidence badge for a matched (possibly best-guess) name."""
    if row.matched_name is None:
        return ""
    if row.confidence is None:
        return f"🔎 {row.matched_name!r}"
    return f"🔎 {row.matched_name!r} ({row.confidence:.0%})"


def _component_table(report: Report) -> Table:
    """Build the per-component comparison table."""
    table = Table(show_header=True, header_style="bold")
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
            result_text(row),
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
        Text(f"{report.game_name} (Steam app {report.app_id})", style="bold")
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
        renderables.append(Text(report.verdict.percentage_text, style="bold"))

    return renderables
