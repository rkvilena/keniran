# Engino State v1.1.1

## Checklist
- [x] Task 1: Center the home block vertically
- [x] Task 2: Use one F1 menu shortcut in the Footer

## Current Task
None

## Completed Summaries
- Task 1: Added a `home-active` class on the scrollable body that applies `align-vertical: middle` (and collapses the empty results area) so the whole home block centers above the Footer; the class is dropped with the hero so results stay top-aligned. Updated `test_home_hierarchy_fits_at_the_normal_terminal_size` to assert centered gaps and `test_results_replace_the_hero_and_reset_restores_the_home_screen` for the new top-aligned box position. `pytest tests/test_tui.py` → 26 passed.
- Task 2: Rebound the command palette to `f1` (`COMMAND_PALETTE_BINDING = "f1"` + a single `Binding("f1", "command_palette", "Menu")`) and set `Footer(show_command_palette=False)` to drop the duplicate docked right-side Menu hint. Updated `test_keniran_theme_is_selected_and_repaints_when_switched` to assert the F1 binding and that exactly one command-palette footer key renders. `pytest tests/test_tui.py` → 26 passed; full suite `pytest` → 325 passed.

## AFK Assumptions Log
- Task 1: Collapsed the empty `#results` `min-height` while the `home-active` class is set so the home block itself is what centers (the reserved results height would otherwise bias the centering); results regain their height as soon as the hero is hidden.
- Task 2: Removed the Footer's docked right-side palette hint (the right-hand duplicate), keeping the left "f1 Menu" key, as the blueprint prefers removing the right side.

## Blockers / Halt Reason
<!-- Keep empty unless the Builder's second verification attempt fails. -->
