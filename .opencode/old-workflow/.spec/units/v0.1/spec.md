unit-id: v0.1
task-prefix: T

# Unit v0.1 — Initial build (Keniran v1)

## Goal

Deliver the complete Keniran v1: CLI `keniran <APP_ID>` auditing this
machine against a Steam game's minimum requirements. Full concept lives in
the global `.spec/spec.md`.

## Note — legacy migration

This unit wraps the project's original flat spec (authored 2026-11-07 from
the `plan/` docs, tasks T-001–T-009). Task IDs keep their original `T-<nnn>`
form; the ledger and interactive run history were moved verbatim from the
flat `.spec/tasks.md` and `.spec/active-context.md` during the wrap migration
(2026-11-08). All 9 tasks are `status: done` — this unit is frozen history.

## Touched Areas

Whole repository (initial build) — see the global blueprint.

## Changed Contracts

N/A — initial build; all contracts are defined for the first time in the
global blueprint.

## Acceptance Runner

See `.spec/conventions.md` — all gates passed at run close:
`ruff format`, `ruff check`, `mypy src`, `pytest -q` (119 passed),
`keniran --version`.
