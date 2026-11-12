# Tasks — v1.0.1/tui-redesign

- [ ] TUIX-001: Add the Keniran branded home hierarchy and reference-inspired styling
  depends: -
  files: src/keniran/tui/app.py, tests/test_tui.py
  pattern: `KeniranTui.compose()` / `CSS` in src/keniran/tui/app.py; shell pilot test in tests/test_tui.py
  context: .spec/units/v1.0.0/tui/spec.md, src/keniran/rendering/report_view.py
  acceptance:
    On mount, the app has a clear `Keniran` header/title, large `keniran` wordmark,
    tagline `Check whether your PC can run a Steam game.`, and a visually grouped primary
    App ID/Run command box. Apply the agreed dark slate/navy, muted lavender, and restrained
    warm-accent palette with legible text contrast; use Textual theme tokens where practical
    and retain `theme == "tokyo-night"`. Existing input digit restriction, Run control,
    worker/status/result/error behavior, and CLI contracts continue to pass unchanged.
    Add pilot assertions for the new branded widgets and command-box structure.
    acceptance commands:
      python -m pytest tests/test_tui.py -q
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
  out-of-scope: matching/scoring changes, shared report-renderable redesign, search/history, theme persistence

- [ ] TUIX-002: Keep the home and results usable at short terminal heights
  depends: TUIX-001
  files: src/keniran/tui/app.py, tests/test_tui.py
  pattern: current `KeniranTui.compose()` / `CSS` in src/keniran/tui/app.py; pilot helpers in tests/test_tui.py
  context: .spec/units/v1.0.1/tui-redesign/spec.md, .spec/conventions.md
  acceptance:
    Headless pilot coverage at 100x30 and a compact 80x16 terminal proves no horizontal
    clipping of the App ID/Run controls, the controls remain keyboard-reachable, and the
    long home/results content is vertically scrollable to its end rather than clipped.
    At the normal size, title, tagline, command box, and initial result region fit in the
    expected hierarchy. Keep Header/Footer usable and do not regress existing worker,
    error/recovery, or shared-renderable pilot tests. Full gate green.
    acceptance commands:
      python -m pytest tests/test_tui.py -q
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
  out-of-scope: new commands/controls, report rendering changes, custom persistent theme, new dependencies
