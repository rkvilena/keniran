unit-id: v1.0.0
task-prefix: REL10

## Goal & Version

The UI release: keniran grows its first interactive surface — a Textual TUI as the
second renderer of `Report` — while the one-shot CLI stays untouched as the default
identity. Release id is **v1.0.0**; per the version-single-source-of-truth rule
(plan/decisions.md §8) the pyproject version is bumped to `1.0.0` by the release
chore (it currently reads `0.2.1` — the release id deliberately leads the pyproject
number until this chore lands, as discussed with the user 2026-11-11).

Feature delivered:
1. `keniran tui` — lightweight, terminal-native, tech-minimalist UI (Textual,
   theme `tokyo-night`, runtime-swappable), rendering the shared `Report` with all
   honesty semantics inherited. `--search` explicitly stays deferred.

## Feature Units

| Order | unit-id | One-line scope | Why here |
|---|---|---|---|
| 1 | v1.0.0/tui | Textual TUI renderer (`keniran tui`): App ID input → worker-run pipeline → shared-renderer verdict display + honest error paths | the release's single feature; carries the new `textual` dep and the shared `rendering/` extraction |
| 2 | v1.0.0 (this unit) | version bump, docs sweep, full gate | after all features |

No parallel-order units; the feature table is linear this time.

## Prerequisites

`v1.0.0/tui` must be fully done (TUI-001 through TUI-004 checked) before the gated
chores below run; each chore carries its `gated:` line. Run semantics follow the
Release-run contract in `.spec/conventions.md`.

## Changed Contracts (cross-cutting summary)

See `v1.0.0/tui/spec.md`. User-visible deltas vs 0.2.1:
- New entry point `keniran tui` (Textual TUI); `keniran <APP_ID>` one-shot CLI
  behavior unchanged; bare `keniran` help unchanged.
- New dependency: `textual` (exact pin). Shared renderer module
  `keniran.rendering.report_view` replaces the private helpers in `cli/app.py`
  (refactor, byte-identical CLI output).
- Version: pyproject `[project] version` → `1.0.0`.

Deferred (not in this release, noted to prevent scope creep): `--search` box,
TUI session history, custom "keniran" verdict-colored theme, `--theme` flag /
theme persistence, `--refresh-spec` control in the TUI.

## Open Questions

- None blocking. pyproject target `1.0.0` **confirmed** (user 2026-11-11: v1.0.0 is
  the first *public* release — repo goes public with the UI; the 0.x era was private
  development). Global `.spec/spec.md` §3/§5 patched by blueprint at user request on
  2026-11-11 (Planned v1.0.0 shape note + backlog row in-progress).
