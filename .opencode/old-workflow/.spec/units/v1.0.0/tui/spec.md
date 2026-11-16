unit-id: v1.0.0/tui
task-prefix: TUI

## Goal

Deliver the first interactive UI for keniran: a **Textual TUI** launched as
`keniran tui`, rendering the same renderer-agnostic `Report` the CLI renders
(plan/decisions.md §3 swap contract). The one-shot CLI (`keniran <APP_ID>`) stays
byte-for-byte unchanged — it remains the default identity of the tool. The TUI is
the second renderer, not a replacement: lightweight, terminal-native, tech-minimalist
by way of Textual's built-in themes.

Design decisions (agreed with user 2026-11-11, see `.spec/decisions.md` Release v1.0.0):
- **Textual over tkinter/PyQt6/static-HTML/local-server.** tkinter rejected (dated
  look, theming pain), PyQt6 rejected (~60–150MB runtime for a pip utility),
  static-HTML rejected here (cannot ever host a search box — CORS), local web server
  rejected (heaviest scope). Textual wins on weight (pure Python), identity (stays in
  the terminal, works under WSL/SSH), ecosystem (same author as Rich — existing rich
  renderables embed directly), and future-proofing (`textual serve` later gives a
  browser version with zero rewrite — the "web-UI era" door stays open).
- **`--search` stays deferred** (user decision 2026-11-11), even though the TUI is
  the "UI era" the backlog named. Its future home is one `Input` widget here.
- **Theme: `tokyo-night` shipped as default, explicitly non-binding.** Themes are
  runtime-swappable via Textual's command palette (Ctrl+P) and a custom "keniran"
  theme (verdict-colored) is a later one-dict addition. No task depends on the theme.
- **Minimal scope, utility-first:** App ID input → run → verdict display. No history,
  no comparisons, no settings persistence.

## Touched Areas

- `pyproject.toml` — new exact-pinned dependency `textual` (newest stable at scaffold
  time; do not guess the version in spec — record the chosen pin in the commit).
- `src/keniran/tui/` — NEW package (`__init__.py`, `app.py`): the Textual App.
- `src/keniran/cli/app.py` — wiring for the `tui` subcommand + refactor to delegate
  rendering to the extracted shared module (TUI-002 only; the observable CLI output
  must not change).
- `src/keniran/rendering/report_view.py` — NEW shared pure renderer extracted from
  `cli/app.py` (TUI-002); consumed by both the CLI and the TUI.
- `tests/test_report_view.py` — NEW tests for the extracted renderer (TUI-002).
- `tests/test_tui.py` — NEW Textual pilot tests (headless, fake fetchers — no network,
  per repo fixture rule).

Untouched: `core/`, `services/check_game.py`, `adapters/` — the TUI consumes
`check_game()` and its existing injection seams (`fetch_steam`, `load_spec`,
`cpu_db`, `gpu_db`) exactly as the CLI does.

## Changed Contracts

- **New CLI surface:** `keniran tui` launches the TUI. CRITICAL pitfall pinned here:
  adding a second Typer *command* to `app.py` converts the single-command app into a
  command **group**, which would change `keniran <APP_ID>` into `keniran keniran <APP_ID>`
  — a breaking change to the core contract. The dispatch must preserve:
  `keniran <APP_ID>` (one-shot, unchanged), `keniran tui` (TUI), bare `keniran`
  (current help behavior). Implement via a dispatch strategy that keeps the
  single-command shape (e.g. callback with `invoke_without_command=True` +
  positional interception, or equivalent) — the acceptance pins the three behaviors,
  not the mechanism.
- **New dependency:** `textual` (exact pin). Nothing else added; no existing
  dependency version changes.
- **New module `keniran.rendering.report_view`:** pure functions
  `result_text(row)`, `badge_text(row)`, `report_renderables(report) -> list[rich renderables]`
  — the current `cli/app.py` private helpers made module-public and reusable.
  `cli.render_report(report, console)` keeps its signature and output; internally it
  delegates. This is a refactor with byte-identical CLI output.
- **TUI contract:** the App accepts the same injection kwargs as `check_game`
  (defaults `None` → production adapters) so pilot tests inject fakes and stay
  offline. Blocking work (`check_game`: network fetch, possible first-audit dxdiag
  subprocess) runs in a Textual worker thread (`thread=True`) — the UI never blocks.
- Honesty semantics are inherited, not reimplemented: `unverified ⚠` rows, ST-warning,
  best-guess ⚡ badges, and no-PC-requirements messages all appear because the shared
  renderer and the `Report` model carry them.

## Acceptance Runner

`python -m pytest tests/test_tui.py tests/test_report_view.py -q` plus the full gate
`python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy`.

## Prerequisites

None outside the repo — `check_game()` seams and `render_report()` exist on disk.
Parallel-safety: this is the only feature unit of v1.0.0.

## Open Questions

- None blocking. Exact `textual` pin is chosen at TUI-001 time (newest stable).
  Theme default `tokyo-night` is provisional and swappable in one line — explicitly
  not a binding decision (user asked for reversibility, confirmed 2026-11-11).
