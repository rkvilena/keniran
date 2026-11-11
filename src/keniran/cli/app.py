"""Typer entry point for the ``keniran`` command-line interface.

The CLI is one renderer of the renderer-agnostic
:class:`~keniran.core.models.Report` produced by
:func:`keniran.services.check_game.check_game`; future UIs can render the same
plain report without going through typer or rich.
"""

from importlib.metadata import version as installed_version
from typing import Final, NoReturn

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from keniran.adapters import steam
from keniran.core import scoring
from keniran.core.models import ComponentRow, Report
from keniran.services.check_game import check_game

UNVERIFIED_NOTE: Final = "unverified — manual review suggested"
ST_WARNING_NOTE: Final = (
    "⚠ Warning: Single-thread performance is below 70% of the required CPU score."
)
TUI_COMMAND: Final = "tui"

_console: Final = Console()

app = typer.Typer(
    name="keniran",
    help="Check whether this machine can run a Steam game.",
    no_args_is_help=True,
    add_completion=False,
)


def _show_version(value: bool) -> None:
    """Print the installed package version when ``--version`` is passed."""
    if value:
        typer.echo(f"keniran {installed_version('keniran')}")
        raise typer.Exit()


def _fail(message: str) -> NoReturn:
    """Report a CLI-level failure on stderr and exit with a nonzero status."""
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _launch_tui() -> None:
    """Launch the Textual TUI.

    Imported lazily so the one-shot CLI does not pay for importing textual.
    Keeping ``tui`` as a reserved positional value (instead of registering a
    second typer command) preserves the single-command shape of the app:
    ``keniran <APP_ID>``, ``keniran tui``, and bare ``keniran`` help all keep
    working without a command-group indirection.
    """
    from keniran.tui.app import run_tui

    run_tui()


def _parse_app_id(raw: str) -> int:
    """Validate the ``<APP_ID>`` argument and convert it to an integer."""
    candidate = raw.strip()
    if not candidate.isdigit() or int(candidate) <= 0:
        _fail(f"Invalid APP_ID {raw!r}: expected a numeric Steam app id.")
    return int(candidate)


def _result_text(row: ComponentRow) -> str:
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


def _badge_text(row: ComponentRow) -> str:
    """Return the confidence badge for a matched (possibly best-guess) name."""
    if row.matched_name is None:
        return ""
    if row.confidence is None:
        return f"⚡ {row.matched_name!r}"
    return f"⚡ {row.matched_name!r} ({row.confidence:.0%})"


def _render_table(report: Report, console: Console) -> None:
    """Render the per-component comparison table and its footnotes."""
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
            _result_text(row),
            _badge_text(row),
        )
    console.print(table)

    for row in report.components:
        if row.unverified:
            console.print(Text(f"⚠ {row.component.value}: {UNVERIFIED_NOTE}"))

    if report.verdict is not None and report.verdict.st_warning:
        console.print(Text(ST_WARNING_NOTE))


def render_report(report: Report, console: Console | None = None) -> None:
    """Render one :class:`Report` to *console* (the module console by default).

    Rendering is presentation-only: every comparison value, percentage, and
    verdict phrase comes from the report or from the canonical scoring helpers.
    """
    target = console if console is not None else _console

    if report.message is not None and report.verdict is None and not report.components:
        target.print(Text(report.message))
        return

    target.print(Text(f"{report.game_name} (Steam app {report.app_id})", style="bold"))

    if report.components:
        _render_table(report, target)

    if report.message is not None:
        target.print(Text(report.message))

    if report.verdict is not None:
        target.print()
        target.print(Text(report.verdict.percentage_text, style="bold"))


@app.command(name="keniran")
def main(
    app_id: str = typer.Argument(
        ...,
        help="Steam app id of the game to check.",
    ),
    refresh_spec: bool = typer.Option(
        False,
        "--refresh-spec",
        help="Re-run the hardware audit before checking.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the keniran version and exit.",
        is_eager=True,
        callback=_show_version,
    ),
) -> None:
    """Check whether this machine can run a Steam game."""
    if app_id.strip().lower() == TUI_COMMAND:
        _launch_tui()
        return
    numeric_app_id = _parse_app_id(app_id)
    try:
        report = check_game(numeric_app_id, refresh_spec=refresh_spec)
    except steam.SteamAdapterError as exc:
        _fail(str(exc))
    except Exception as exc:
        _fail(f"Unexpected error: {exc}")
    render_report(report)
