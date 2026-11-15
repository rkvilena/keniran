# Engino State v1.1.2

## Checklist
- [x] Task 1: Clarify the benchmark match badge
- [x] Task 2: Refine the TUI input panel and results spacing

## Current Task
None

## Completed Summaries
- Task 1: Swapped the ⚡ benchmark marker for 🔎 in `badge_text` and added a `dim`-styled `BADGE_NOTE` legend emitted right after the component table (before any ⚠/ST warnings) in `report_renderables`. Updated the renderer docstrings and the shared/CLI test expectations (badge strings, renderable count/order, and legend presence). `pytest tests/test_report_view.py tests/test_cli_report.py` → 32 passed.
- Task 2: Changed `#command-box` to `width: auto` (with `max-width: 100%`, `#app-id-row` auto too) so the panel hugs its controls, and added `margin-bottom: 1` for a single blank row before the first result line. Updated `test_app_id_control_is_grouped_in_the_command_box` (auto width, hugging math, margin-bottom) and added badge-legend/🔎 coverage plus a results-gap assertion. `pytest tests/test_tui.py` → 26 passed; full suite `pytest` → 325 passed; ruff clean.

## AFK Assumptions Log
- Task 1: Rendered the badge legend with the generic `dim` style (no theme token exists for subdued text); placed it as its own line so the renderable order stays title → table → legend → ⚠ rows → ST warning → message → verdict.
- Task 2: Expressed the panel gap as `margin-bottom: 1` on `#command-box` (instead of results padding) so it only depends on the panel and does not disturb the home-active vertical centering; the hugging width keeps `max-width: 100%` for narrow terminals.

## Blockers / Halt Reason
<!-- Keep empty unless the Builder's second verification attempt fails. -->
