"""Smoke tests for the keniran command-line entry point."""

from typer.testing import CliRunner

from keniran.cli.app import app


def test_version_flag_prints_expected_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "keniran 0.1.0"
