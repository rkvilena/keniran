# Learnings — v1.1.0-tui-redesign

## 2026-11-13 (Plan init)
- Base branch `main`, base SHA `f79f6db` ("v1.0.1: interrupted on REL101-003").
- Repo is src-layout; Textual app is a single 279-line module `src/keniran/tui/app.py`.
- The TUI test suite `tests/test_tui.py` (892 lines) imports id constants and pins
  theme/hex/Header/Run-button behavior; every app task must update it in the same commit.
- Textual 8.2.8 confirmed installed in `.venv/Scripts/python.exe` (Python 3.11.5).
- `textual.theme.Theme` dataclass fields: name, primary, secondary, warning, error,
  success, accent, foreground, background, surface, panel, boost, dark,
  luminosity_spread, text_alpha, variables, ansi. `App.register_theme(theme)` takes one
  `Theme`; `App.theme` is `Reactive("textual-dark")`.
- `Input.Submitted` exists; rich `Text.stylize(style, start, end)` appends `Span`s.

## 2026-11-13 (Wave 1 verified)
- W1-1 (`branding.py`): `WORDMARK_LINES` (6×38), `WORDMARK_COMPACT` (4×32), gray
  endpoints `#8A8A8A`/`#D4D4D4`. Public API: `wordmark_renderable(start, end)` (full art)
  and `wordmark_renderable_for(lines, start, end)` (general) — **W3-1 must use the latter to
  render `WORDMARK_COMPACT`**. 16 focused tests; full suite 313 passed.
- W1-2 (`theme.py`): `KENIRAN_THEME` name "keniran"; bg `#0D0D0F`, gray fg `#C9C9CE` /
  primary `#9A9AA0`, single amber `accent #E0A64B`; `register_keniran_theme(app)` registers once
  and does NOT select. 8 focused tests.
- W1-3 (`.spec/units/v1.1.0/spec.md` + `.spec/decisions.md` append): mapping TUI11-001..006 /
  REL110-001..005; dated 2026-11-13 decision supersedes `.spec/decisions.md:230-235` and `:46-49`.

## 2026-11-13 (Wave 2 verified)
- W2-1 (`app.py` + `tests/test_tui.py`): `Header` dropped (import removed), `Footer` kept; class
  attr `theme="tokyo-night"` removed; `__init__` registers `KENIRAN_THEME` then `self.theme = "keniran"`
  (AD8, pre-mount assignment works). CSS left as-is (already token-only, `$accent` used once on the Run
  button) — the monochrome look comes from the theme. 23 focused tests; full suite 322 passed.
- **Textual color quantization gotcha**: `get_css_variables()` resolves declared colors through a
  LAB round-trip (`lighten(0)`); a saturated amber shifts one step (`#E0A64B` → `#DFA64B`) while grays
  are exact. Tests pin the declared value on `available_themes["keniran"].accent` and the resolved value
  on the CSS variable. Expect the same for any future saturated color pins.
- Independence note: the venv editable install points at the MAIN checkout's `src`, so ad-hoc scripts
  must `sys.path.insert(0, "src")` (or set PYTHONPATH) to exercise a worktree's code; pytest already
  does this via `pythonpath=["src"]`.

## 2026-11-13 (Wave 3 verified)
- W3-1 (`app.py` + `tests/test_tui.py`): `#hero` Container nested in `#home`, holding the wordmark
  Static + subtitle Static (`SUBTITLE = "Can I run it? Enter the target game's Steam App ID to audit this PC."`);
  command box stays a sibling of `#hero`. Removed `TITLE_ID`, `TAGLINE_ID`, `TAGLINE` and their CSS.
  Added `HERO_ID`, `SUBTITLE_ID`, `WORDMARK_MIN_WIDTH=44`, `WORDMARK_MIN_HEIGHT=22`.
  Wordmark filled in `on_mount`/`on_resize` via `_apply_wordmark(event.size)`. 25 focused tests; 324 full.
- **Textual 8.2.8 API notes** (from this task): `App.is_mounted` is a METHOD `is_mounted(widget)`, not a
  property — guard with `not self.screen_stack or not self.query(...)`. App-level `Resize` does not bubble,
  and `on_resize` runs before `App._on_resize` updates `self.size`, so use `event.size` (authoritative).
- Verified manually at 80×16 (compact 4-row art, input bottom 11 ≤ 16, focused) and 100×30 (full 6-row art,
  focused), subtitle exact at both.

## 2026-11-13 (Wave 4 verified)
- W4-1 (`app.py` + `tests/test_tui.py`): removed `RUN_BUTTON_ID`, the `Button` import, the Run widget,
  the `#run-button` CSS rule, `on_button_pressed`, and `_set_running` (all 5 call sites). Added
  `on_input_submitted` → `_request_check`. `$accent` is now absent from `KeniranTui.CSS` (the amber lives in
  the theme; W5-1's Reset button will consume it). 25 focused tests; 324 full.
- Manual check: 0 `Button` widgets mounted; Enter with "730" mounted the results; Enter with "" mounted the
  exact inline error `Invalid APP_ID '': expected a numeric Steam app id.`.

## 2026-11-13 (Wave 5 verified)
- W5-1 (`app.py` + `tests/test_tui.py`): `RESET_BUTTON_ID="reset-button"`, `HERO_HIDDEN_CLASS="hidden"`;
  CSS `#hero.hidden { display: none; }` + `#reset-button { border: tall $accent; }` (single accent restored);
  `_hide_hero()` called by `_show_status`/`_show_error`/`_show_report`; `_reset()` + `on_button_pressed`
  (reset-scoped) + `action_reset` with `BINDINGS = [Binding("escape","reset","Reset")]`. 26 focused; 325 full.
- Manual end-to-end: after a check hero hidden + results mounted; Esc restores hero, clears results/input,
  refocuses input; Reset click identical; active bindings include `escape`, `ctrl+p`, `ctrl+q` (base App
  bindings merge, so the command palette/quit survive the new BINDINGS).

## 2026-11-13 (Wave 6 verified)
- W6-1 (`pyproject.toml`): `[project] version` 1.0.1 → 1.1.0, one line, no other field touched; 325 tests pass.
  ORCHESTRATOR DEVIATION: `pip install -e ".[dev]"` was NOT run here (the venv is shared with the main
  checkout; a worktree editable install would repoint `keniran` and break the other worktrees). The
  `keniran --version == 1.1.0` check is performed once in W7-1 from the plan worktree.
- W6-2 (`CHANGELOG.md`): added `## 1.1.0 - 2026-11-13` (Added/Changed/Removed; Removed = the Run button);
  pure addition (26 insertions, 0 deletions); the `## 1.0.1` section is byte-identical (md5 verified).
- W6-3 (`README.md`): intro documents 1.1.0; `## TUI (1.1.0)` rewritten to the shipped design; grep for
  `Run button|lavender|slate/navy|1.0.1|press Run` in the final file returns nothing.

## 2026-11-13 (Wave 7 verified)
- W7-1 (`.spec/units/v1.1.0/tasks.md` + `run-log.md`): authored the 11-block ledger (TUI11-001..006,
  REL110-001..005) with the landed SHAs and dependency edges, plus the run log. Full gate green
  (96 files unchanged; ruff check ok; mypy 19 files ok; 325 passed). `pip install -e ".[dev]"` →
  `Successfully installed keniran-1.1.0`; `keniran --version` → `keniran 1.1.0`.
- Headless pilot smoke (run_test, fake check_game) passed: hero on mount → Enter runs → hero hidden +
  results mounted → Esc/Reset restore → theme `keniran`. The INTERACTIVE `keniran tui` smoke on Windows
  remains PENDING USER QA.
- SHARED-VENV NOTE: after W7-1 the venv editable install points at the ws-accept worktree; the orchestrator
  re-runs `pip install -e ".[dev]"` from the main checkout after the final merge and worktree cleanup.
- tasks.md's own REL110-005 `status:` reads `done (own commit)` deliberately (a self-referential SHA would be
  invalidated by the commit itself).
