# Engino Blueprint v1.1.1: Center the home screen and simplify the menu footer

## Context & Scope
- The Textual home screen and results share a scrollable body; the Footer stays docked beneath it.
- Center the initial home block—wordmark, subtitle, and App ID/Reset box—as one group in the usable area above the Footer. Preserve scrolling on short terminals and keep result-screen positioning unchanged.
- Replace the duplicate menu hint with one F1 command-palette shortcut. `^p` currently denotes Ctrl+P, a keyboard shortcut rather than a clickable control.
- Touched paths: `src/keniran/tui/app.py`, `tests/test_tui.py`.

## Builder Model Preference (advisory)
- Tier: Balanced
- Reason: Focused UI layout and keyboard-binding changes with responsive behavior to preserve.
- Exact model: not pinned; select with /models

## Tasks

### Task 1: Center the home block vertically
- Target files: `src/keniran/tui/app.py`, `tests/test_tui.py`
- Instructions: Adjust the home layout so the wordmark, subtitle, and App ID/Reset box are vertically centered together in the available body area above the docked Footer. Keep the home/results body scrollable so short terminals can reach all content; do not alter report/result positioning or the behavior of the hidden hero. Update layout tests to assert the home block's centered placement at a normal terminal size and preserve short-terminal scrolling coverage.
- Verification: `pytest tests/test_tui.py`

### Task 2: Use one F1 menu shortcut in the Footer
- Target files: `src/keniran/tui/app.py`, `tests/test_tui.py`
- Instructions: Bind the command palette to F1 using Textual's supported binding configuration and remove or adjust the redundant binding so the Footer displays exactly one menu hint. Keep the command palette available, retain Esc/Reset and quit behavior, and update tests to verify the F1 binding and absence of duplicate menu hints.
- Verification: `pytest tests/test_tui.py`

## Out of Scope
- Changes to the one-shot CLI, report contents, or other application behavior outside the TUI home layout and menu shortcut.
