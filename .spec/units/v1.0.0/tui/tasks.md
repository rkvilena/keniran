# Tasks — v1.0.0/tui

- [ ] TUI-001: Scaffold TUI — textual dep, `keniran tui` subcommand, minimal App shell
  depends: -
  files: pyproject.toml, src/keniran/tui/__init__.py, src/keniran/tui/app.py,
    src/keniran/cli/app.py, tests/test_tui.py
  pattern: typer app wiring in src/keniran/cli/app.py (see the group-pitfall note in
    the unit spec Changed Contracts); Textual App class from textual docs — new scaffold
  acceptance:
    `textual` added to `[project] dependencies` exact-pinned (newest stable at
    implementation time; record the pin in the commit message). New package
    `src/keniran/tui/` with a Textual App subclass: `theme = "tokyo-night"`,
    Header + Footer + an App-ID `Input` (digit validation) + a Run button + an empty
    result container; the check itself may remain a stub this task. CLI dispatch
    preserves all three contracts, pinned by tests: `keniran <APP_ID>` one-shot
    behavior unchanged (existing CLI tests stay green untouched), `keniran tui`
    launches the TUI app, bare `keniran` prints help (current `no_args_is_help`
    behavior). Pilot test (headless): app mounts, theme is set, entering an id and
    pressing Run does not crash. Full gate green.
    acceptance commands:
      python -m pytest tests/test_tui.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: pipeline execution/worker (TUI-003), shared renderer extraction
    (TUI-002), error-path polish (TUI-004), search box, history, theme persistence,
    `--refresh-spec` control

- [ ] TUI-002: Extract shared Report renderer — `keniran.rendering.report_view`
  depends: TUI-001
  files: src/keniran/rendering/__init__.py, src/keniran/rendering/report_view.py,
    src/keniran/cli/app.py, tests/test_report_view.py
  pattern: the private helpers `_result_text`, `_badge_text`, `_render_table`,
    `render_report` in src/keniran/cli/app.py — moved, not rewritten
  acceptance:
    New module `keniran/rendering/report_view.py` (docstring cites plan/decisions.md
    §3 renderer contract) exposing pure functions: `result_text(row)`,
    `badge_text(row)`, and `report_renderables(report) -> list[RenderableType]`
    returning the ordered rich renderables (title line, component table, unverified
    ⚠ lines, st-warning line, message line, verdict percentage line) that
    `render_report` prints today — same objects, same order. `cli/app.py` keeps
    `render_report(report, console)` with its exact signature and prints those
    renderables; its private helpers are removed in favor of the shared module.
    CLI output byte-identical: every existing CLI test passes unchanged; new
    tests/test_report_view.py covers the no-requirements message-only report and one
    full verdict report (fixture-driven, offline). Full gate green.
    acceptance commands:
      python -m pytest tests/test_report_view.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: any TUI change (this task is CLI-internal refactor only), Report
    model changes, scoring changes

- [ ] TUI-003: Run the pipeline in a worker and display the verdict
  depends: TUI-001, TUI-002
  files: src/keniran/tui/app.py, tests/test_tui.py
  pattern: check_game() injection seams (fetch_steam/load_spec/cpu_db/gpu_db kwargs)
    per src/keniran/services/check_game.py; report_renderables() per
    src/keniran/rendering/report_view.py
  acceptance:
    Pressing Run with a valid App ID executes `check_game(app_id, fetch_steam=...,
    load_spec=..., cpu_db=..., gpu_db=...)` (pass-through of the App's injection
    kwargs) inside a Textual worker with `thread=True` — the UI stays responsive
    while a fake fetcher sleeps. While running, a status indicator (spinner or
    status line naming the app id) is visible; on completion it is replaced by the
    report display, which mounts the shared `report_renderables()` output (all
    honesty semantics inherited: unverified ⚠ rows, ⚡ best-guess badges, ST-warning,
    verdict percentage). Running a second check while one is in flight is either
    disabled (button disabled) or replaces the pending worker deterministically —
    pick one and pin it in the test. Pilot tests run fully offline with fake
    fetchers returning canned Reports (fixture from test_report_view.py shapes);
    one test asserts the display shows the verdict percentage text and component
    rows from the canned Report. Full gate green.
    acceptance commands:
      python -m pytest tests/test_tui.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: error-path styling (TUI-004), network calls in tests (forbidden),
    search box, refresh-spec toggle, caching Reports between checks beyond
    check_game's own in-memory steam cache

- [ ] TUI-004: Failure paths — honest errors, no crashes
  depends: TUI-003
  files: src/keniran/tui/app.py, tests/test_tui.py
  pattern: cli/app.py `_fail` + `render_report` message-only path; the
    SteamAppNotFound / NoRequirementsPublished handling in check_game's docstring
  acceptance:
    Non-digit or empty App ID input → inline validation message in the TUI (styled
    text), worker never starts, no crash. Fake fetcher raising
    `steam.SteamAppNotFound` → the error is caught and shown inline (message names
    the app id), UI remains usable — a subsequent valid check still works in the
    same session (pilot test proves the recovery). Fake fetcher raising a generic
    `steam.SteamAdapterError` → same inline treatment; unexpected exceptions surface
    as an inline "unexpected error" message rather than killing the app. A Report
    with `message` set, no verdict, no components (No-PC-requirements case) renders
    via the shared renderer's message-only path unchanged. Full gate green.
    acceptance commands:
      python -m pytest tests/test_tui.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: retry/backoff logic, logging frameworks, search box, any new
    adapter or service behavior
