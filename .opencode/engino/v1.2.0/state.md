# Engino State v1.2.0

## Checklist
- [x] Task 1: Clarify TUI instructions and actions
- [x] Task 2: Bump package version and document installation/usage

## Current Task
None

## Completed Summaries
- Task 1: Updated the subtitle with explicit Steam App ID and Enter instructions, added a Check button wired to the existing request path, and kept Enter/Reset/Esc behavior. Tests cover the Check click, three-control focus order/layout, existing validation/reset paths, and duplicate Check while a worker runs. `pytest tests/test_tui.py -q` → 27 passed (Attempt 2 with `.venv/Scripts` on PATH; Attempt 1 used global Python and failed collection because `textual` was unavailable there).
- Task 2: Bumped package metadata to `1.2.0` and updated README install/TUI guidance for pipx and uv, the new controls and subtitle, and 🔎 benchmark-match notes. `pytest tests/test_cli.py -q` → 1 passed (Attempt 2 with `.venv/Scripts` on PATH; Attempt 1 failed collection because global Python lacked `rapidfuzz`). Manually confirmed README commands and version/TUI descriptions match the Python 3.11 requirement and `keniran` script entry point.

## AFK Assumptions Log
<!-- Builder records only minor, non-conflicting decisions it made autonomously. -->

## Blockers / Halt Reason
<!-- Keep empty unless the Builder's second verification attempt fails. -->
