# Conventions

## Acceptance commands (verified against the repo / `pyproject.toml` tool section)

Run from repo root with the dev extras installed (`pip install -e ".[dev]"`). All four are
part of the agent loop; "green" = all pass.

```
python -m pytest -q                 # testpaths=["tests"], pythonpath=["src"]
python -m ruff format .             # line-length 100, double quotes, py311 target
python -m ruff check .              # E,F,W,I,UP,B,SIM,RUF
python -m mypy                      # files=["src"]; strict on keniran.core
```

Pytest fixtures are recorded files — tests never touch network or real hardware except
explicitly flagged WSL smoke steps.

## Code style

- Docstrings reference `plan/decisions.md` sections (e.g. "§4.5") — keep that convention.
- Pure functions in `core/` + pure parsers in adapter modules: business logic stays
  fixture-testable without subprocess/OS. mypy strict zone is `core/`; adapters moderate.
- Type-annotate everything, `from __future__ import annotations` at module top.
- Windows path/OS specifics stay inside `adapters/`; `core/` never imports platform libs.

## Commits

One task = one commit: `<task-id>: <title>` (e.g. `LIN-002: parse lspci/vulkaninfo output`).
Keep a task's tests inside its own commit. Release chores may reference gates.

## Release-run contract

Running a release unit-id (e.g. `/run 0.2.0`, where that unit-id names the release
coordination unit) means: execute the release's **Feature Units** in their declared
table order — units marked with the same order value are parallel-safe — honoring each
unit's `Prerequisites` section as cross-unit ordering, and then run the release unit's
own chore tasks, whose `gated:` lines must all be satisfied first. A feature unit whose
prerequisites are unfinished is deferred (not skipped-forever) by the release run.
Running a *feature* unit id directly runs just that unit: its tasks' `depends:` field
is unit-scoped and says nothing about cross-unit ordering — cross-unit edges exist
only in the release spec's Feature Units table and per-unit Prerequisites sections.
