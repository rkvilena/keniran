"""Typer entry point for the ``keniran`` command-line interface."""

from importlib.metadata import version as installed_version

import typer

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


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the keniran version and exit.",
        is_eager=True,
        callback=_show_version,
    ),
) -> None:
    """Check whether this machine can run a Steam game."""
