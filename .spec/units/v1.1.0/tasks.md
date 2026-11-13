# Tasks — v1.1.0

- [x] TUI11-001: Pure wordmark module (art + gray gradient)
  depends: -
  gated: -
  files: src/keniran/tui/branding.py, tests/test_branding.py
  pattern: pure presentation module mirroring `rendering/report_view.py` (text in, rich `Text` out); the art is hardcoded as a `Final[tuple[str, ...]]` of equal-width rows ≤ 80 cols with no new dependency (plan AD1/AD3)
  context: .spec/units/v1.1.0/spec.md, src/keniran/rendering/report_view.py, .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W1-1)
  acceptance:
    `WORDMARK_LINES` and `WORDMARK_COMPACT` are non-empty tuples of equal-width rows
    (≤ 80 cols; the compact set shorter than the full set); `wordmark_renderable(start, end)`
    returns a `rich.text.Text` whose first/last span styles resolve to the gray endpoints,
    span count equals the non-newline glyph cells, endpoint colors sit in a gray luminance
    band and step monotonically left→right; imports limited to `rich`/stdlib.
    acceptance commands:
      python -m pytest tests/test_branding.py -q
  out-of-scope: theme wiring and app CSS (TUI11-002/003), compact-vs-full selection in the app (TUI11-004)
  status: done (commit 75efc64)

- [x] TUI11-002: Custom near-black theme module (gray + single amber)
  depends: -
  gated: -
  files: src/keniran/tui/theme.py, tests/test_theme.py
  pattern: palette as declarative data plus a registration helper (plan AD2) — a textual `Theme` named `keniran` with gray `foreground`/`primary` and exactly one amber `accent`, not hex overrides in app CSS
  context: .spec/units/v1.1.0/spec.md, textual.theme conventions, .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W1-2)
  acceptance:
    `KENIRAN_THEME` is a `textual.theme.Theme` named `"keniran"` with a near-black
    `background`, gray `foreground`/`primary`, and only `accent` amber-hued;
    `register_keniran_theme(app)` calls `app.register_theme` once and the name appears in
    `app.available_themes`; no new dependency.
    acceptance commands:
      python -m pytest tests/test_theme.py -q
  out-of-scope: selecting the theme in the app (TUI11-003), the CSS rewrite (TUI11-003)
  status: done (commit a653470)

- [x] TUI11-003: Theme wiring, chrome, and palette
  depends: TUI11-002
  gated: -
  files: src/keniran/tui/app.py, tests/test_tui.py
  pattern: register first, then select through the `theme` reactive (plan AD8); token-only CSS; drop `Header` / keep `Footer` (plan AD7)
  context: src/keniran/tui/theme.py, prior tests/test_tui.py Header/theme-hex pins, .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W2-1)
  acceptance:
    `compose()` no longer yields `Header()` (`Footer()` kept, unused import dropped) and the
    pinned Header tests are updated; `__init__` registers `KENIRAN_THEME` then sets
    `self.theme = "keniran"` through the reactive; a pilot test asserts the default theme
    name is `keniran`, that switching to `tokyo-night` changes `current_theme` and repaints a
    token-derived style, and that the Ctrl+P command palette stays enabled; the CSS is
    rewritten to theme tokens with a single accent.
    acceptance commands:
      python -m pytest tests/test_tui.py -q
  out-of-scope: hero content (TUI11-004), submit mechanics (TUI11-005), results/reset flow (TUI11-006)
  status: done (commit 3810d82)

- [x] TUI11-004: Centered hero (wordmark + subtitle + compact fallback)
  depends: TUI11-001, TUI11-003
  gated: -
  files: src/keniran/tui/app.py, tests/test_tui.py
  pattern: hero nested inside the kept `#home` container as `#hero` with the command box as a sibling (plan AD5); full-vs-compact wordmark picked in Python on mount and on `on_resize` (plan AD6)
  context: src/keniran/tui/branding.py, prior #home/#command-box tests, .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W3-1)
  acceptance:
    `#hero` holds the wordmark (`branding.wordmark_renderable(...)`) and the subtitle with
    the exact text `Can I run it? Enter the target game's Steam App ID to audit this PC.`,
    both horizontally centered; `TITLE_ID`, `TAGLINE_ID`, and `TAGLINE` are removed with
    their pinned tests; at 80×16 the compact art is shown with `#app-id-input` fully
    on-screen, a tall size shows the full art, and the input keeps first focus.
    acceptance commands:
      python -m pytest tests/test_tui.py -q
  out-of-scope: Enter submit (TUI11-005), results/reset flow (TUI11-006)
  status: done (commit 9a8caf1)

- [x] TUI11-005: Enter-to-submit; remove the Run button
  depends: TUI11-004
  gated: -
  files: src/keniran/tui/app.py, tests/test_tui.py
  pattern: one submit seam via `Input.Submitted` (plan AD4); the removed button's `disabled` concurrency guard is replaced by the existing in-flight worker guard in `_request_check`
  context: prior `on_button_pressed`/`_set_running` call sites in src/keniran/tui/app.py, .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W4-1)
  acceptance:
    The `Run` button, `RUN_BUTTON_ID`, `on_button_pressed`, and `_set_running` are removed
    with all call sites updated (no `Button` queried anywhere); Enter with a valid id starts
    exactly one worker; empty/zero ids show the unchanged message
    `Invalid APP_ID {entered!r}: expected a numeric Steam app id.` and start no worker; a
    second Enter while a check is in flight is a no-op; `restrict=r"[0-9]*"` and the busy
    status line (`Checking Steam app <id>…`) are unchanged.
    acceptance commands:
      python -m pytest tests/test_tui.py -q
  out-of-scope: hero/results swap and Reset/Esc (TUI11-006)
  status: done (commit 82d79c8)

- [x] TUI11-006: Results replace the hero; Reset + Esc
  depends: TUI11-005
  gated: -
  files: src/keniran/tui/app.py, tests/test_tui.py
  pattern: the hero is hidden through a CSS class (`display: none`), never unmounted (plan AD5); one `_reset` seam shared by a `Button.Pressed` handler scoped to reset and the `Esc` binding
  context: src/keniran/tui/app.py hero/results structure, .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W5-1)
  acceptance:
    Once a check starts `#hero` is hidden and the results occupy its space — the shared
    `report_renderables(report)` Statics mounted unchanged, error paths still mounting the
    inline red `Error: …` message, the input visible throughout; a `Reset` button
    (`RESET_BUTTON_ID`) and the `Esc` keybinding both restore the hero, clear the input
    value, and clear the results; after a reset a new id + Enter runs again.
    acceptance commands:
      python -m pytest tests/test_tui.py -q
  out-of-scope: pipeline/`Report` changes, new submit behavior (TUI11-005 owns Enter)
  status: done (commit c36a8c2)

- [x] REL110-001: Release unit spec + superseding decision
  depends: -
  gated: -
  files: .spec/units/v1.1.0/spec.md, .spec/decisions.md
  pattern: flat single release unit headmatter (`task-prefix: TUI11`, chores under `REL110` in the body) mirroring `.spec/units/v1.0.1/spec.md`; dated superseding decision entry
  context: .spec/units/v1.0.1/spec.md, .spec/decisions.md:230-235 (Bagels/lavender) and :46-49 (theme-is-backlog), .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W1-3)
  acceptance:
    `.spec/units/v1.1.0/spec.md` exists with the `unit-id: v1.1.0` / `task-prefix: TUI11`
    headmatter, the Goal & Version, the task-id mapping reproduced by this file,
    Changed Contracts, Prerequisites, and Open Questions; `.spec/decisions.md` gains a dated
    entry (2026-11-13) superseding both the Bagels/lavender TUI direction and the earlier
    "custom `keniran` theme is backlog" stance.
    acceptance commands:
      python -m pytest -q
  out-of-scope: authoring this unit's tasks.md (deferred to REL110-005 by design)
  status: done (commit dd3eb57)

- [x] REL110-002: Version bump to 1.1.0
  depends: TUI11-006
  gated: TUI11-001, TUI11-002, TUI11-003, TUI11-004, TUI11-005, TUI11-006
  files: pyproject.toml
  pattern: version single source of truth in pyproject.toml (§8); v1.0.0 REL10-001 and v1.0.1 REL101-001 precedent
  context: .spec/units/v1.1.0/spec.md, pyproject.toml
  acceptance:
    `[project] version = "1.1.0"` with no other pyproject field changed; after
    `pip install -e ".[dev]"`, `keniran --version` prints `keniran 1.1.0` (quoted in the
    run log).
    acceptance commands:
      python -m pytest -q
  out-of-scope: changelog/README edits, editable-install refresh (owned here by REL110-005's run)
  status: done (commit 8057c1b)

- [x] REL110-003: CHANGELOG entry for v1.1.0
  depends: TUI11-006
  gated: TUI11-001, TUI11-002, TUI11-003, TUI11-004, TUI11-005, TUI11-006
  files: CHANGELOG.md
  pattern: Keep-a-Changelog release section; extends the file's earlier Added/Changed/Fixed set with a `Removed` group (the Run button)
  context: CHANGELOG.md `## 1.0.1` section, .spec/units/v1.1.0/spec.md, .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W6-2)
  acceptance:
    A `## 1.1.0 - 2026-11-13` section with the one-line scope statement and
    `### Added` / `### Changed` / `### Removed` groups (Removed: the Run button); the
    `## 1.0.1` section stays byte-for-byte untouched.
    acceptance commands:
      python -m pytest -q
  out-of-scope: version bump, README edits, release tag
  status: done (commit 4cc7422)

- [x] REL110-004: README TUI section
  depends: TUI11-006
  gated: TUI11-001, TUI11-002, TUI11-003, TUI11-004, TUI11-005, TUI11-006
  files: README.md
  pattern: README version intro + per-release `## TUI (…)` section (v1.0.0/v1.0.1 precedent)
  context: README.md, CHANGELOG.md, .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W6-3)
  acceptance:
    The intro's documented version reads 1.1.0; `## TUI (1.1.0)` describes the centered
    ASCII wordmark, the monochrome + amber palette, Enter-to-submit (no Run button), the
    results-replace-hero flow, Reset/Esc, and the default `keniran` theme with
    `tokyo-night` still selectable via Ctrl+P; no stale claims remain.
    acceptance commands:
      python -m pytest -q
  out-of-scope: changelog, version bump, release tag
  status: done (commit c964d54)

- [x] REL110-005: Final acceptance run + release unit tasks/log
  depends: REL110-001, REL110-002, REL110-003, REL110-004
  gated: -
  files: .spec/units/v1.1.0/tasks.md, .spec/units/v1.1.0/run-log.md
  pattern: this unit's own ledger in the repo's checkbox-block format, plus the v1.0.1 run-log format recording executed commands and results
  context: .spec/units/v1.0.1/tasks.md, .spec/units/v1.0.1/run-log.md, .spec/units/v1.1.0/spec.md, .opencode/blueprint/plans/v1.1.0-tui-redesign.md (W7-1)
  acceptance:
    Full gate green (`ruff format` / `ruff check` / `mypy` / `pytest -q`); the editable
    install is refreshed and `keniran --version` prints `keniran 1.1.0`; a headless pilot
    smoke (`run_test`, the tests' harness) confirms the hero on mount, Enter-to-run, results
    replacing the hero, Reset and Esc restoring the hero, and the `keniran` theme — the
    interactive `keniran tui` smoke on Windows remains PENDING USER QA; this file
    reproduces the task-id mapping fixed in REL110-001. Results quoted in `run-log.md`.
    acceptance commands:
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
      pip install -e ".[dev]" && keniran --version
      headless TUI smoke via run_test (uncommitted script under the OS temp dir)
  out-of-scope: tag creation/push (user-controlled), reconciling stale v1.0.1 ledger entries, any code change
  status: done (own commit)
