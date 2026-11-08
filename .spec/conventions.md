# Conventions

## Acceptance commands

Run from the repo root (verified working 2026-11-08, all green per the v0.1
run summary in `.spec/units/v0.1/active-context.md`):

- `ruff format .` — check formatting (read-only gate: `ruff format --check .`)
- `ruff check src tests`
- `mypy src` — strict mode for `keniran.core.*` (pyproject override)
- `pytest -q` — testpaths `tests/`, pythonpath `src`
- `keniran --version` — smoke gate, must print `keniran 0.1.0`

Every task's final `acceptance:` line should end with the subset of these
that proves it (normally: the task's own tests via `pytest -q`, plus lint).

## Code style

- Python 3.11 pinned (`>=3.11,<3.12`); ruff target py311, line length 100.
- Double quotes, ruff rules: E, F, W, I, UP, B, SIM, RUF.
- PEP 420 namespace packages: subpackages carry NO `__init__.py`
  (decisions.md architecture entry).
- Layered ports & adapters: `core/` pure + mypy strict, I/O confined to
  `adapters/`; `services/` returns plain dataclasses.
- Zero interactivity: no prompts ever; best-guess with confidence badges.
- Fuzzy-match honesty rules (confidence threshold 0.80, `unverified`
  badges, VRAM-suffix tokens) live in `decisions.md` — a feature touching
  matching MUST read the global `decisions.md` first, not only this file.

## Commits

- One commit per task, made by the orchestrator, only after review AND
  acceptance pass.
- Message format: `<task-id>: <task title>` — task ids are unit-prefixed
  (e.g. `AUTH-003: rate-limit login`; v0.1 legacy tasks were `T-001: ...`).
- Never amend, rebase, or squash during a pipeline run.
