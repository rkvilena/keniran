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

from keniran.adapters import steam
from keniran.core.models import Report
from keniran.rendering.report_view import (
    ST_WARNING_NOTE,
    UNVERIFIED_NOTE,
    report_renderables,
)
from keniran.services.check_game import check_game

__all__ = [
    "ST_WARNING_NOTE",
    "UNVERIFIED_NOTE",
    "app",
    "main",
    "render_report",
]

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


def render_report(report: Report, console: Console | None = None) -> None:
    """Render one :class:`Report` to *console* (the module console by default).

    Rendering is presentation-only: the ordered rich renderables come from
    :func:`keniran.rendering.report_view.report_renderables`, shared with every
    other renderer, and their comparison values, percentages, and verdict
    phrases all come from the report or the canonical scoring helpers.
    """
    target = console if console is not None else _console
    for renderable in report_renderables(report):
        target.print(renderable)


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
