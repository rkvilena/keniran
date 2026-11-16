unit-id: v1.0.1/tui-redesign
task-prefix: TUIX

## Goal

Redesign the existing Textual home screen so it feels polished and intentional while
remaining utility-first. Use the user's Bagels terminal screenshot as a mood reference:
dark slate/navy, muted lavender highlights, restrained warm accent, bordered/pane-like
grouping, and a calm terminal aesthetic. Add a clear Keniran title/header, a large
`keniran` wordmark, the short tagline “Check whether your PC can run a Steam game.”, and
the existing App ID / Run controls as the primary command box.

## Touched Areas

- `src/keniran/tui/app.py` — compose the branded home hierarchy, styling, and vertically
  scrollable content for short terminal heights.
- `tests/test_tui.py` — pilot checks for branded widgets, preserved interaction, and
  compact-terminal visibility/scroll behavior.

No changes to `keniran.rendering.report_view`, `check_game`, scoring, CLI dispatch, or
dependencies.

## Changed Contracts

- Visual/layout change only. `keniran tui` still collects an App ID, runs the same worker,
  and mounts the same report renderables; inline errors and recovery remain unchanged.
- Keep the Textual `tokyo-night` default and runtime theme switching. CSS should use
  theme-aware styling where practical so the command-palette theme switch is not removed.
- Preserve the App ID input and Run action, keyboard accessibility, and one-shot
  `keniran <APP_ID>` CLI behavior. Keep horizontal layout usable; on short terminal
  heights, all home content and long results must remain reachable through vertical
  scrolling rather than clipping.
- No history, search, theme persistence, new dependency, or report redesign.

## Acceptance Runner

Focused: `python -m pytest tests/test_tui.py -q`.
Full gate: `python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q`.

## Prerequisites

`v1.0.1/requirement-alternatives` must be complete first per the release spec. This unit
does not depend on matching implementation details; the sequence is the user's requested
correctness-first order.

## Open Questions

- Exact CSS hex values, borders, and spacing remain intentionally flexible. Assumption:
  visual review follows the screenshot's mood, uses readable contrast, and does not try to
  clone its finance-dashboard pane arrangement.
