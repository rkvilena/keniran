# Active Context

**Blueprint status:** complete · **Tasks done:** 0/9 · **State:** greenfield repo — only `plan/` docs, `database/cpus2a.json`, `.gitignore` exist; T-001 scaffolds everything.

**Startup notes for orchestrator:**
- Project is **Keniran**; CLI command is `keniran <APP_ID>` — hand-rebrand from the plan docs' `canirun` (user decision 2026-11-07). All plan citations of `canirun` read as `keniran`.
- v1 is **Windows-only** for the hardware audit (.dxdiag primary); non-Windows gets a clear error. Confirmed with user.
- Open Questions live in `spec.md` §6 — assumptions are already in force; none block starting at T-001.
- T-004 includes a one-off networked run of `scripts/scrape_gpu.py` to produce the committed `database/gpu_db.json` — plan it on a machine with internet access.
- Agent-loop contract per task: `ruff format` → `ruff check` → `mypy src` → `pytest` all green = done.
