unit-id: v1.1.0
task-prefix: TUI11

## Goal & Version

Ship Keniran **v1.1.0** as a TUI-only visual redesign of `keniran tui`, matched to the
*opencode TUI* aesthetic: a near-black background, monochrome gray content, exactly one
amber accent, a centered multi-line ASCII-art `keniran` wordmark with a left→right gray
gradient, and a small muted subtitle ("Can I run it? Enter the target game's Steam App
ID to audit this PC."). The home screen is input-first: Enter submits (the Run button is
removed), results replace the hero, and a Reset/Esc path returns to the hero. The audit
pipeline, `Report` models, shared report renderables, one-shot CLI, and error semantics
are untouched, and there are no new dependencies. Release chores (version bump,
CHANGELOG, README, and this unit's own ledger) ride along in the same unit.

This direction supersedes v1.0.1's Bagels/lavender TUI visual direction and the earlier
stance that a custom `keniran` theme was backlog; both supersessions are recorded in
`.spec/decisions.md` (entry dated 2026-11-13).

Target version: `pyproject.toml` `[project] version = "1.1.0"`.

v1.1.0 is a **flat single release unit**: the TUI redesign and its release chores share
this unit-id; there are no sub-units. Feature tasks carry the `TUI11` prefix (the
headmatter `task-prefix`); release chores carry the `REL110` prefix, recorded here in
the body. This spec does NOT author `.spec/units/v1.1.0/tasks.md` — W7-1 produces it
after the tasks exist, reproducing the task-id mapping below.

## Feature Units

| task-id | Workstream | Wave | One-line scope |
|---|---|---|---|
| TUI11-001 | W1-1 | 1 | Pure wordmark module: hardcoded ASCII-art `keniran` art (full `WORDMARK_LINES` + `WORDMARK_COMPACT`) and a left→right gray gradient builder |
| TUI11-002 | W1-2 | 1 | Custom near-black `keniran` theme module (gray `foreground`/`primary`, single amber `accent`) plus a registration helper |
| TUI11-003 | W2-1 | 2 | Theme wiring (register + select `keniran` via the reactive), drop `Header` / keep `Footer`, palette CSS rewrite |
| TUI11-004 | W3-1 | 3 | Centered hero: ASCII wordmark + exact subtitle, with the compact fallback on short terminals |
| TUI11-005 | W4-1 | 4 | Enter-to-submit; remove the Run button |
| TUI11-006 | W5-1 | 5 | Results replace the hero; Reset + Esc restore the hero |

## Release Chores (prefix `REL110`)

| task-id | Workstream | Wave | One-line scope |
|---|---|---|---|
| REL110-001 | W1-3 | 1 | This release unit spec + superseding decision entry (dependency-free) |
| REL110-002 | W6-1 | 6 | Version bump to `1.1.0` in `pyproject.toml` |
| REL110-003 | W6-2 | 6 | CHANGELOG entry for v1.1.0 |
| REL110-004 | W6-3 | 6 | README update for v1.1.0 |
| REL110-005 | W7-1 | 7 | Author `.spec/units/v1.1.0/tasks.md` + run-log (this unit's own ledger), reproducing the mapping above |

## Prerequisites

Wave order: Wave 1 (TUI11-001, TUI11-002, and the dependency-free chore REL110-001)
runs in parallel; then the serial UI chain W2-1→W3-1→W4-1→W5-1 =
TUI11-003→TUI11-004→TUI11-005→TUI11-006 (all four edit `src/keniran/tui/app.py` +
`tests/test_tui.py`, so they never overlap); then Wave 6 chores (REL110-002, REL110-003,
REL110-004) in parallel; then W7-1 (REL110-005) last.

Release chores gate on the feature tasks: REL110-002/003/004 require every TUI11 task
complete; REL110-005 additionally requires REL110-002/003/004. Cross-unit execution
follows `.spec/conventions.md`.

## Changed Contracts

- Pipeline, seams, and semantics unchanged: the `check_game` injection seams, the
  shared `report_renderables`, the one-shot `keniran <APP_ID>` CLI and its dispatch,
  the `Report` models, and error messages/semantics are untouched.
- Theme: a new custom `keniran` theme becomes the TUI default; `tokyo-night` remains
  selectable at runtime and Ctrl+P (command palette) stays enabled.
- Home screen: `Header` is dropped; `Footer` is kept. Enter submits the App ID (the Run
  button is removed); results replace the hero; a Reset/Esc path returns to the hero.
- No new dependencies.
- Version target: `pyproject.toml` `[project] version = "1.1.0"`.

## Open Questions

- Exact resolved hex values for the near-black background, the gray ramp, and the
  single amber accent are flexible; pick accessible values within the agreed palette.
- The compact-height breakpoint is flexible; prefer graceful degradation over clipping.
- The wordmark's glyph font (which ASCII-art font to render the `keniran` wordmark
  from) is flexible, as long as it stays multi-line and accepts the left→right gray
  gradient.
- GitHub publication/tagging remains user-controlled; the release unit prepares local
  release artifacts only.
