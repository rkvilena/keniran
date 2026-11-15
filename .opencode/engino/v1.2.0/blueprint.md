# Engino Blueprint v1.2.0: Clarify TUI actions and simplify installation

## Context & Scope
- The Textual home screen is implemented in `src/keniran/tui/app.py`; App ID submission already uses a shared request path, and Reset and Esc already restore the home screen.
- Make the subtitle explain how to enter an App ID and submit, and add a clickable Check button without removing Enter-to-submit or Reset/Esc behavior.
- The package already exposes the `keniran` console script through `pyproject.toml`; document installing it with pipx or uv tool so users can launch it without activating a venv.
- Bump the package metadata to `1.2.0` and align relevant README release, install, and TUI details. Touched paths: `src/keniran/tui/app.py`, `tests/test_tui.py`, `pyproject.toml`, `README.md`.

## Builder Model Preference (advisory)
- Tier: Balanced
- Reason: Moderate UI interaction changes plus release metadata and installation documentation that should stay consistent.
- Exact model: not pinned; select with /models

## Tasks

### Task 1: Clarify TUI instructions and actions
- Target files: `src/keniran/tui/app.py`, `tests/test_tui.py`
- Instructions: Replace the subtitle with “Can I run it? Enter the game's Steam App ID, then press Enter to check this PC against its minimum requirements.” Add a clickable Check button that invokes the existing App ID check request path. Preserve Enter submission from the input, Reset-button and Esc reset behavior, inline invalid-ID handling, and duplicate-request protection while a check is in flight. Keep the controls keyboard reachable in a sensible input → Check → Reset order; test button submission and existing keyboard/reset/error behaviors.
- Verification: `pytest tests/test_tui.py -q`

### Task 2: Bump package version and document installation/usage
- Target files: `pyproject.toml`, `README.md`
- Instructions: Change the package version from `1.1.0` to `1.2.0`. Update README release/version references and install/TUI guidance to describe pipx and uv tool installs from a checkout, launching `keniran tui` without manually activating a venv, the revised subtitle, Check + Reset controls, and the current 🔎 badge wording. Keep Python 3.11 requirements clear; do not imply a standalone executable is provided.
- Verification: `pytest tests/test_cli.py -q`; manually confirm README install commands, package version, and TUI descriptions agree with `pyproject.toml` and the existing `keniran` script entry point (no docs-specific automated check exists).

## Out of Scope
- Standalone executable or OS-specific bundled application builds.
- Changes to Steam lookup, hardware auditing, matching, scoring, or report behavior.
