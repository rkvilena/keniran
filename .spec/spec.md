# Project Blueprint — Keniran "Can I Run It?" (CLI)

> Canonical input plans: `plan/decisions.md` (BINDING when versioned), `plan/detailed-flow.md`,
> `plan/benchmark-db.md`. This file describes the codebase as of **0.1.0**; per-version
> deltas live in `units/<release-id>/spec.md`.

## 1. Goal & Scope

One command, zero interactivity: `keniran <APP_ID>` audits the local machine, fetches and
parses a Steam game's **minimum** PC requirements, maps both sides onto PassMark benchmark
scores and capacity numbers, and prints a verdict report ("can I run it" for low-end
gamers). Audience decisions and honesty policy (unverified ⚠ instead of hallucinated data)
come from `plan/decisions.md` §1–§2.

Out of scope: title search in CLI (`--search` deferred to web-UI era), LLM parsing
(backlog, trigger defined), recommended-requirements comparison, any UI layer beyond the
CLI renderer.

## 2. Stack & Constraints

| Choice | Why |
|---|---|
| Python 3.11 pinned (`pyproject.toml`) | dev env; `datetime.UTC` usage |
| typer + rich | CLI + table rendering |
| pydantic v2 | schemas: Steam responses, requirement targets, Report |
| requests / beautifulsoup4 / lxml / rapidfuzz | Steam fetch / HTML strip / fuzzy benchmark matching |
| psutil | free-disk space (dxdiag has none); *no new deps allowed in 0.2.0* |
| ruff / mypy / pytest (dev extras, exact-pinned) | agent-loop gate: format → check → types → tests |

Single source of truth for the version: `[project] version` in `pyproject.toml`.

## 3. Architecture — layered ports & adapters (NOT MVC)

```
src/keniran/
├── core/                      # pure domain: models, requirements_parser, scoring (no I/O)
├── adapters/
│   ├── steam.py               # appdetails fetch + HTML strip (in-memory per-run cache)
│   ├── hardware.py            # 0.1.0: dxdiag parse + psutil disk → SystemSpec (module)
│   ├── benchmarks.py          # CPU/GPU lookup, benchmark-db.md Stages 0–3
│   └── llm/base.py            # RequirementExtractor protocol — interface ONLY (backlog)
├── services/check_game.py     # pipeline orchestration → plain Report; injection seams:
│                              #   fetch_steam / load_spec / cpu_db / gpu_db callables
└── cli/app.py                 # renders Report (rich tables)
generated/system_spec.json     # hardware audit cache — gitignored runtime artifact
scripts/                       # maintenance tools only
database/                      # vendored cpus2a.json + scraped gpu_db.json (as-is exports)
tests/                         # pytest + recorded fixtures; no network
```

Swap contract: `services/` consumes adapters and returns plain dataclasses; the CLI (and
any future UI) is just a renderer of the same `Report`.

**Planned 0.2.0 shape** (delta lives in `units/0.2.0/`, units: model-layout,
linux-audit, ratio-scoring, storage-mounts, release): `adapters/hardware.py`
becomes a package — `__init__.py` facade (unchanged `audit`/`load`/`save` signatures) + 
`windows.py` + `linux.py`, dispatched on `sys.platform`.

## 4. Data Contracts

### SystemSpec (0.1.0 shape — cached at `generated/system_spec.json`)
`cpu_name: str · ram_gb: float ≥0 · gpu_name: str · vram_gb: float ≥0 · disk_free_gb: float ≥0 · audited_at: datetime (UTC)` — pydantic, `extra="forbid"`.
Semantics behind the numbers: CPU/GPU names are match keys against the vendored PassMark
DBs; RAM/VRAM/Storage are direct numeric minimums (0.1.0 hard checks per `plan/decisions.md` §5).

### GameRequirements (parsed from Steam text, fields stay `None` when not established)
`cpu_name · gpu_name · ram_gb · vram_gb · storage_gb · target_resolution · target_fps`,
plus `unverified: set[ComponentName]` for generic descriptions with no model number
(honesty gate — never guessed).

### Report / verdict pipeline
- Component ratio = `user_score / required_score` (CPU = `cpumark`, GPU = `g3d_mark`); display percent capped at 100.
- **Verdict bands (inclusive):** Pass ≥ 1.0 · Borderline ≥ 0.85 · Poor ≥ 0.65 · Unplayable < 0.65; any hard shortfall (0.1.0: RAM/VRAM/Storage) caps band at `Fail (spec shortfall)`; nothing scorable → `Unverified`.
- Final ratio = **min(CPU, GPU)** in 0.1.0; single-thread CPU ratio is informational only (< 0.70 while MT passes → `st_warning`).
- Steam: `appdetails?appids=<ID>&filters=basic,pc_requirements`; missing/"Unavailable"
  `pc_requirements` → graceful `message="No PC requirements published"`, not an error.
- Storage endpoints: Linux `lspci`/`nvidia-smi`/`vulkaninfo` output formats are the
  0.2.0 parse inputs (fixed fixtures, see unit specs).

## 5. Non-Goals / Backlog

| Item | Status / trigger |
|---|---|
| LLM requirement extraction (OpenAI → multi-provider) | backlog; revisit if rules-parser accuracy proves poor on fixtures |
| `--search` title → App ID helper | explicitly deferred to web-UI era (user decision 2026-11-08) |
| Recommended-requirements comparison | post-0.2.0 backlog |
| Refined CPU scoring (ST-weighted composite) | post-0.2.0 backlog; candidate after Linux audit |
| Steam-library mount detection (`libraryfolders.vdf`) | post-0.2.0 backlog (follows storage rework) |
| UI (TUI/web) | renderer over the same `Report` |
| Native-Linux hardware validation | deferred until real-Linux CI exists (WSL smoke covers plumbing only) |

## 6. Open Questions

- Windows↔WSL fixture-capture ergonomics (`wsl.exe` invocation detail) — implementation
  nuance, parked with the Linux-audit unit.
- None blocking.
