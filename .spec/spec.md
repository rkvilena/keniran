# Project Blueprint — Keniran ("Can I Run It?" — CLI Edition)

> Source of truth: `plan/decisions.md` (BINDING), detailed in `plan/general-plan.md`,
> `plan/detailed-flow.md`, `plan/benchmark-db.md`. Where the plan docs say `canirun`,
> read **`keniran`** — rebranded by user decision on 2026-11-07 (see `.spec/decisions.md`).
> Everything else in the plan docs is reproduced contractually below.

## 1. Goal & Scope

Keniran is a one-command terminal tool for low-end gamers: `keniran <APP_ID>` audits the
local machine, fetches a Steam game's published **minimum** PC requirements, parses them
into structured data, maps both sides to PassMark benchmark scores, and prints a
comparison table plus a percentage-based performance verdict ("84% of minimum —
Borderline, playable on low settings"). Zero interactivity, no API keys, no LLM calls,
scoring offline via vendored databases.

Explicitly in scope (v1 = 0.1.0): Windows-only hardware audit (dxdiag primary + psutil
free-disk), Steam `appdetails` requirements fetch, deterministic labeled-line requirement
parser, CPU (`cpus2a.json`) + GPU (`gpu_db.json` via PassMark G3D scraper) score lookup
with fuzzy fallback and deterministic disambiguation, ratio math with hard spec-shortfall
cap, rich CLI report.

**Out of scope (v1):** title→AppID search, `--json` flag, recommended-requirements
comparison, LLM requirement extraction (interface stub only), non-Windows audit,
disk-level API/response caching, any interactive prompt.

## 2. Stack & Constraints

- **Python 3.11** (pinned) — as per plan/decisions.md §7.
- **typer + rich** — CLI entry and table/color rendering; zero-prompt contract.
- **pydantic v2** — schemas for Steam responses, requirement targets, `Report` (all data contracts in §4).
- **requests** — Steam endpoints + PassMark scrape (desktop User-Agent, small retry/backoff).
- **beautifulsoup4 (w/ lxml)** — HTML strip of `pc_requirements` blocks; G3D table parsing.
- **rapidfuzz** — Stage 2 fuzzy name matching.
- **psutil** — free-disk space only (dxdiag has no free-space notion).
- **ruff** — lint + format (single tool); **mypy** — strict on `core/`, moderate on adapters; **pytest** — recorded fixtures, **no network in tests**.
- Dependency versions are fixed at scaffold time in `pyproject.toml`; `version = "0.1.0"` is the single version source, surfaced as `--version`.
- **Agent-loop contract (green = done):** `ruff format` → `ruff check` → `mypy` → `pytest`, all pass.

## 3. Architecture

Layered ports & adapters — domain logic never touches I/O. The swap contract:
`services/` consumes adapters and returns plain data; **CLI and any future UI are just
different renderers of the same `Report`**.

```
keniran/                        # package under src/, name = project name (rebrand)
├── core/                       # PURE domain, no I/O — mypy strict
│   ├── models.py               # pydantic: SystemSpec, GameRequirements, MatchResult, Report
│   ├── scoring.py              # ratio math, status bands, shortfall cap, ST-note rule
│   └── requirements_parser.py  # labeled-line parser: cleaned text → GameRequirements
├── adapters/                   # I/O at the edges — mypy moderate
│   ├── steam.py                # appdetails fetch + HTML strip → raw requirement text
│   ├── hardware.py             # dxdiag /t (+psutil disk) → SystemSpec, cache-aware
│   ├── benchmarks.py           # lookup(db, name, kind) — Stages 0–4 of benchmark-db.md
│   └── llm/base.py             # RequirementExtractor protocol — INTERFACE ONLY in v1
├── services/
│   └── check_game.py           # pipeline orchestrator; returns Report; in-memory Steam cache
└── cli/
    └── app.py                  # typer entry `keniran <APP_ID> [flags]`; renders Report
scripts/
└── scrape_gpu.py               # maintenance tool → database/gpu_db.json (NOT part of app)
database/
├── cpus2a.json                 # vendored PassMark CPU export — used AS-IS
└── gpu_db.json                 # generated once by scrape_gpu.py; committed
generated/                      # runtime artifacts (system_spec.json) — gitignored
tests/                          # pytest + recorded fixtures; network-free
```

**Flow:** `keniran <APP_ID>` → 1. spec cache check (else dxdiag audit → `generated/system_spec.json`) →
2. Steam `appdetails` fetch (in-memory) → 3. extract `pc_requirements.minimum` (HTML) →
4. strip/normalize text → 5. rule-based parse → 6. benchmark lookup for CPU/GPU names +
hard checks for RAM/VRAM/Storage → 7. ratio + verdict → 8. CLI table render.

## 4. Data Contracts

### 4.1 Steam endpoints (unauthenticated)
- App metadata: `https://store.steampowered.com/api/appdetails?appids=<ID>&filters=basic,pc_requirements`
  → JSON: `{ "<appid>": { "success": bool, "data": { "name": str, "pc_requirements": { "minimum": <html-string>|null, "recommended": <html-string> } } } }`
- Missing `pc_requirements` or `"Unavailable"` → graceful exit: *"No PC requirements published"* (not an error).
- **Cache:** per-run in-memory only. No disk caching.
- NOTE: title search endpoint (`steamcommunity.com/actions/SearchApps`) is BACKLOG; v1 takes the AppID from argv only.

### 4.2 Requirement target schema (parser output, pydantic-validated)
```json
{
  "cpu_name": "Intel Core i5-2300",
  "gpu_name": "NVIDIA GeForce GTX 650 Ti",
  "ram_gb": 8.0,
  "vram_gb": 2.0,
  "storage_gb": 30.0,
  "target_resolution": "720p",
  "target_fps": 30
}
```
Parser duties: label detection (`Processor/CPU`, `Memory/RAM`, `Graphics/Video`, `Storage`, `OS` → context);
strip noise (`or better`, `or equivalent`, `@ X.XXGHz`); unit conversion (MB→GB); split
`"GTX 650 Ti, 2 GB VRAM"` into `gpu_name` + `vram_gb`; missing fields → `null`.
**Honesty gate:** a name with no model number (`"2.0 GHz quad-core"`, `"DX11-compatible card"`)
→ component marked `unverified` immediately — neither parser nor any backend scores a generic.

### 4.3 SystemSpec / `generated/system_spec.json` (gitignored)
```json
{ "cpu_name": "…", "ram_gb": 16.0, "gpu_name": "…", "vram_gb": 4.0, "disk_free_gb": 148.2, "audited_at": "…ISO8601…" }
```
- Primary source: `dxdiag /t` (CPU name, RAM GB, GPU name, GPU **"Dedicated Memory"** — WMI `AdapterRAM` caps at 4 GB and is NOT used).
- Free disk: psutil. First run audits + writes cache; later runs read cache; `--refresh-spec` forces re-audit.

### 4.4 Benchmark DBs
- `database/cpus2a.json` — vendored AS-IS: `{"data": [{"id", "name", "cpumark" (MT, str), "thread" (ST, str), "tdp", "date", "socket", "cat", "cpuCount", "samples", "href", …]}`; stringi-fied numbers, `"NA"` → treat as `null`, never 0; duplicate names across `cpuCount` rows exist (Stage 3 resolves).
- `database/gpu_db.json` — generated by `scripts/scrape_gpu.py` from PassMark G3D list, committed:
```json
{ "meta": { "source_url": "https://www.videocardbenchmark.net/gpu_list.html", "scraped_at": "YYYY-MM-DD", "entry_count": 4000 },
  "data": [ { "id": 3342, "name": "NVIDIA GeForce GTX 1060 6GB", "g3d_mark": 11083, "thread": null, "tdp": 120, "samples": 1521, "href": "…" } ] }
```
  `thread` stays `null` (GPU SThread doesn't exist) purely to keep files structurally parallel for shared lookup code.
- Raw scrape HTML cached to `database/.cache/gpu_list.html` for re-parsing; atomic writes (temp file → replace).

### 4.5 Benchmark lookup API (shared, CPU & GPU)
```python
lookup(db, name_text, kind: "cpu"|"gpu") -> MatchResult(best_entry, score_ratio, alternatives, matched_by)
```
Stage 0 normalize (lowercase; keep `+ - .`; drop noise tokens `@ 2.60ghz`, `(tm)`, `(r)`, `cpu`, `processor`, `or better/equivalent`; keep VRAM suffixes `2gb/6gb`; small alias map `gtx 1060 → geforce gtx 1060`) → Stage 1 exact key hit → Stage 2 rapidfuzz on token sets (shared-token count wins ties; drop `or better`/mobile qualifiers first) → Stage 3 disambiguation: CPU prefer `cpuCount==1`, then desktop `cat`, then newest `date`, then highest `samples`; GPU prefer VRAM-suffix match, else highest `samples` → Stage 4 score release: CPU primary = `cpumark` (MT), `thread` (ST) computed too; GPU = `g3d_mark`.
- **Confidence gate 0.80:** below threshold → for *targets* (game text is approximate) still take deterministic best-guess with matched-name + confidence badge in report; for components with genuinely no model number → `unverified` (⚠ in report, no ratio, run completes).
- No match at all → `None` score → component shows ⚠ "unverified — manual review suggested".

### 4.6 Scoring & verdict
- Compare **vs. minimum only**. `CPU_ratio = user_cpumark / target_cpumark`; `GPU_ratio` analog (`g3d_mark`). **Final = min(CPU_ratio, GPU_ratio)**.
- Bands: ratio ≥ 1.0 → **Pass** (displays as `100%`, "meets requirement"); 0.85–0.99 → **Borderline (playable on low settings)**; 0.65–0.84 → **Poor / Low FPS**; < 0.65 → **Unplayable / Below minimum**.
- **RAM/VRAM/Storage = hard pass/fail:** any shortfall caps the verdict at **Fail (spec shortfall)** regardless of ratio.
- ST informational column: if MT passes but ST ratio < 0.70 → one-line ⚠ CPU note.
- `Report` (returned by `services.check_game`, rendered by CLI): game name + app id, per-component rows (user value vs required, ratio %/check, confidence badge/⚠), never-missing-unverified policy, final verdict line with percentage text (e.g. "84% of minimum…").

## 5. Non-Goals / Backlog (do NOT implement in v1)

| Item | Trigger |
|---|---|
| LLM requirement-parsing adapter (OpenAI first, multi-provider later) | Only if rules-parser accuracy proves poor on fixture corpus; `adapters/llm/base.py` interface exists so adding it is additive |
| `--search` title→AppID helper | After core loop works end-to-end |
| `--json` output | Cheap later add; CLI UX first |
| Recommended-requirements comparison | v2 (v1 = minimum only) |
| Refined CPU scoring (ST-weighted/composite) | v2 (v1 = cpumark + informational ST column) |
| UI (TUI/web) | Renderer of `Report` |
| SteamDB as data source | Dead end: no public API, Cloudflare-blocked, same upstream data |
| Non-Windows audit | v1 targets only formally Windows |

## 6. Open Questions (with assumptions in force)

1. **`target_resolution` / `target_fps` extraction depth** — schema fields exist; Steam text rarely states both. *Assumption: parser fills them only when trivially present (e.g. "720p" / "30 FPS" tokens), else `null`; they never affect scoring math in v1.*
2. **GPU DB refresh cadence** — `gpu_db.json` is scraped once at build time and committed. *Assumption: orchestrator/implementer may run `scripts/scrape_gpu.py` (networked, manual, one-off) during T-004; CLI itself never hits PassMark.*
3. **Windows test environment** — dxdiag parsing and audit tests must run against recorded fixture text, not live `dxdiag /t` (slow, GUI-spawning). *Assumption: `tests/fixtures/dxdiag_sample.txt` approach suffices; live audit is exercised manually.*
4. **Exact dependency pin numbers** — fixed at T-001 scaffold time; not pre-decided in plan docs.
