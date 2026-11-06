# Decision Log

- Project name: **Keniran**, CLI command `keniran <APP_ID>` — user rebrand overrides plan docs' `_Can I Run It?_` / `canirun` literal (source: user interview 2026-11-07).
- v1 Windows-only hardware audit — dxdiag never exists on Linux/macOS; non-Windows = clear error (source: user interview 2026-11-07 + plan/decisions.md §4).
- Python 3.11 pinned; typer+rich / pydantic v2 / requests / bs4+lxml / rapidfuzz / psutil / ruff / mypy / pytest toolchain per plan/decisions.md §7; dependency versions fixed at T-001 scaffold time (source: plan/decisions.md §7).
- v1 requirement parsing is deterministic rules-only; LLM adapter is backlog, interface stub only (`adapters/llm/base.py`) — revisit only if fixtures prove rules-parser accuracy poor (source: plan/decisions.md §2).
- Architecture is layered ports & adapters, not MVC — core/ pure + mypy strict, I/O confined to adapters/; `services/` returns plain dataclasses; CLI is one renderer of `Report` (source: plan/decisions.md §3).
- Zero interactivity: AppID from argv (title search deferred), best-guess matches with confidence badge, generic names → `unverified ⚠`, no prompts ever (source: plan/decisions.md §1).
- Compare minimum requirements only; final ratio = min(CPU ratio, GPU ratio); bands ≥100% / 85–99 / 65–84 / <65; RAM/VRAM/Storage shortfalls cap verdict at Fail; ratio ≥1.0 displays as 100%; CPU primary score = cpumark (MT) with informational ST column + <70% ST warning (source: plan/decisions.md §5, plan/general-plan.md §3).
- CPU data: vendored `database/cpus2a.json` used AS-IS (string numbers, `"NA"`→null, `cpuCount` duplicates resolved by disambiguation rules); no cpubenchmark.net scrape (source: plan/benchmark-db.md §1 + plan/decisions.md §8).
- GPU data: PassMark G3D chart via `scripts/scrape_gpu.py` → committed `database/gpu_db.json` with meta/scraped_at, atomic writes, raw-HTML debug cache; DirectCompute chart rejected as non-gaming-relevant; SteamDB rejected entirely (source: plan/benchmark-db.md §2–3, plan/decisions.md §6).
- Steam: store `appdetails?appids=<ID>&filters=basic,pc_requirements` only; title search / `--json` / recommended comparison all backlog; in-memory per-run caching only (source: plan/decisions.md §6, §9).
- Fuzzy-match honesty gate: confidence threshold 0.80; below → deterministic best-guess with badge for targets, `unverified` for model-numberless names; hardware names keep VRAM-suffix tokens (GTX 1060 3GB vs 6GB matter) (source: plan/benchmark-db.md §4–5).
- Task order T-001→T-009 follows scaffold→core→lookup→GPU DB→steam→parser→audit→orchestrate→render so each task only references files from earlier tasks or the repo; tests live inside their owning tasks, network-free via recorded fixtures (source: blueprint authoring 2026-11-07).
