- [x] T-001: Scaffold Keniran package, pinned toolchain, and green validator loop
  depends: -
  files: pyproject.toml, .gitignore, src/keniran/__init__.py, src/keniran/cli/app.py, tests/test_cli.py
  pattern: new project scaffold (follow .spec/spec.md §3 tree)
  acceptance: src layout with `keniran` package + typer CLI entry `keniran --version` printing `keniran 0.1.0`; pyproject pins python 3.11 and all §2 deps at current stable versions, configures ruff (lint+format), mypy (strict on src/keniran/core), pytest; `.gitignore` ignores `generated/` and `database/.cache/`; one trivial CLI smoke test present
    pytest -q && ruff format --check . && ruff check . && mypy src
    keniran --version  (resolves from installed/project venv; expect stdout containing "0.1.0")
  out-of-scope: any pipeline logic beyond the `--version` stub; no scaffolding of empty module files for later tasks (each task creates its own)
  status: done (commit 6b00fb2)

- [x] T-002: Core domain models + scoring math (pure, mypy-strict)
  depends: T-001
  files: src/keniran/core/models.py, src/keniran/core/scoring.py, tests/test_scoring.py
  pattern: new; pydantic v2 idioms
  acceptance: pydantic models SystemSpec (per §4.3 keys incl. audited_at), GameRequirements (§4.2, unknown/categorical fields nullable), MatchResult (best_entry, score_ratio, alternatives, matched_by), Report (game info + per-component rows + final verdict) all defined; scoring.py implements: CPU/GPU ratio, final=min(...), status bands (>=1.0 Pass/100% display cap, 0.85–0.99 Borderline, 0.65–0.84 Poor, <0.65 Unplayable), hard RAM/VRAM/Storage shortfall → verdict capped at Fail, MT-pass-but-ST<0.70 warning flag; unit tests cover every band boundary (1.0, 0.99, 0.85, 0.84, 0.65, 0.64), shortfall-caps-Pass case, ST-warning case, and 100% display cap; pure modules import no I/O libraries (requests/typer/psutil)
    ruff format --check . && ruff check . && mypy src && pytest tests/test_scoring.py -q
  out-of-scope: any file/network I/O; parser and lookup logic (later tasks)
  status: done (commit 3f16d23)

- [x] T-003: Benchmark lookup pipeline (normalize → exact → fuzzy → disambiguate → release)
  depends: T-002
  files: src/keniran/adapters/benchmarks.py, tests/test_benchmark_lookup.py, tests/fixtures/benchmark_mini.json
  pattern: per plan/benchmark-db.md §4–5 exactly
  acceptance: shared `lookup(db, name_text, kind="cpu"|"gpu")` implementing Stage 0 normalization (lowercase, keep `+ - .`, drop `@ 2.60ghz`/`(tm)`/`(r)`/`cpu`/`processor`/`or better`/`or equivalent`, keep trailing VRAM suffix tokens, alias map incl. `gtx 1060→geforce gtx 1060`), Stage 1 exact, Stage 2 rapidfuzz token-set matching with shared-token tiebreak, Stage 3 CPU disambiguation (prefer cpuCount==1, then desktop cat, then newest date, then highest samples) + GPU disambiguation (VRAM-suffix match, else highest samples), confidence gate 0.80 (best-guess-with-badge for targets, `unverified` for no-model-number names), Stage 4: CPU scores from cpumark/thread, GPU from g3d_mark, `"NA"` → null never 0, no match → null score; tests on a small committed fixture DB cover exact hit, fuzzy hit with tiebreak, duplicate-name cpuCount disambiguation, GTX-1060-3GB vs 6GB variant selection, generic-text unverified, and no-match path
    ruff format --check . && ruff check . && mypy src && pytest tests/test_benchmark_lookup.py -q
  out-of-scope: scraper and gpu_db.json (T-004); db loading/caching policy beyond "already-loaded db passed in"
  status: done (commit 65b700b)

- [x] T-004: GPU database — scraper script + committed gpu_db.json
  depends: T-003
  files: scripts/scrape_gpu.py, database/gpu_db.json, tests/fixtures/gpu_list_sample.html, tests/test_scrape_gpu.py
  pattern: per plan/benchmark-db.md §3 exactly
  acceptance: scrape_gpu.py fetches videocardbenchmark.net/gpu_list.html (desktop User-Agent, retry/backoff, follows pagination if any), caches raw HTML to database/.cache/gpu_list.html, BeautifulSoups the table (name, Average G3D Mark, samples, TDP if present, id from `...&id=NNNN` href), keeps unparsed raw strings in a `raw` field, writes gpu_db.json atomically with meta.source_url + meta.scraped_at, and prints a console report (rows fetched / kept / skipped); unit test parses committed fixture HTML fragment (no network) asserting ≥3 rows extracted and int coercion; a run of the script has produced committed database/gpu_db.json with meta.entry_count ≥ 3000, no null/empty g3d_mark among kept entries, and gpu names pass `lookup(..., kind="gpu")` spot-checks (e.g. "NVIDIA GeForce GTX 1060 6GB")
    pytest tests/test_scrape_gpu.py -q && python -c "import json;d=json.load(open('database/gpu_db.json'));assert d['meta']['entry_count']>=3000;assert all(e['g3d_mark'] for e in d['data'])" && python scripts/scrape_gpu.py --dry-report  (optional: only verifies fixture-parse offline; full scrape run is a one-off)
  out-of-scope: auto-refresh/scheduling in the app runtime; DirectCompute chart (explicitly rejected); making the CLI depend on scrape availability
  status: done (commit 7fecd5b)

- [x] T-005: Steam adapter — appdetails fetch + HTML strip to labeled text
  depends: T-002
  files: src/keniran/adapters/steam.py, tests/fixtures/steam/appdetails_minimum.json, tests/fixtures/steam/appdetails_missing.json, tests/test_steam_adapter.py
  pattern: per plan/detailed-flow.md Step A/B, plan/decisions.md §6
  acceptance: fetch(app_id) calls `https://store.steampowered.com/api/appdetails?appids=<ID>&filters=basic,pc_requirements`, validates response with pydantic, returns game name + raw `pc_requirements.minimum` HTML string; BeautifulSoup strip converts `<li>`/`<br>` to `\n`, removes HTML entities (`&nbsp;`, `&reg;`, `&trade;`), trims trailing legal/copyright noise; missing requirements or `"Unavailable"` raises a typed NoRequirementsPublished (service later maps to graceful message, not error); in-memory per-run cache escapes no disk; tests run fully offline on the two recorded fixture JSONs (success path + missing path)
    ruff format --check . && ruff check . && mypy src && pytest tests/test_steam_adapter.py -q
  out-of-scope: title search endpoint; disk caching; recommended-requirements handling; network-retry test (behavior implemented, not asserted live)
  status: done (commit 937d98b)

- [x] T-006: Rule-based labeled-line requirement parser
  depends: T-005
  files: src/keniran/core/requirements_parser.py, tests/fixtures/steam/requirements_text/*.txt, tests/test_requirements_parser.py
  pattern: per plan/detailed-flow.md Step C honesty gate + §4.2 target schema
  acceptance: parse(clean_text) detects labels (`Processor`/`CPU`→cpu_name, `Memory`/`RAM`→ram_gb, `Graphics`/`Video`→gpu_name+vram_gb, `Storage`→storage_gb, `OS`→context only), strips noise (`or better`, `or equivalent`, `@ X.XXGHz`, "or AMD equivalent"), converts MB→GB, splits `"GTX 650 Ti, 2 GB VRAM"` into gpu_name+vram_gb, fills missing fields null, fills target_resolution/target_fps only when trivially present tokens; honesty gate: model-numberless names ("2.0 GHz quad-core", "DX11-compatible card") → component flagged unverified rather than guessed; tests use real-world-shaped fixture text files (Intel-style block, AMD-style block, "60 FPS"/MB-units variants, generic-description block) asserting exact schema outputs incl. one full example matching §4.2 JSON verbatim
    ruff format --check . && ruff check . && mypy src && pytest tests/test_requirements_parser.py -q
  out-of-scope: LLM adapter implementation (interface in adapters/llm/base.py stays protocol-only); benchmark matching of parsed names (T-003 consumes, doesn't belong here)
  status: done (commit 09b188c)

- [x] T-007: Hardware audit adapter — dxdiag parse + psutil disk, cache-aware
  depends: T-002
  files: src/keniran/adapters/hardware.py, tests/fixtures/dxdiag_sample.txt, tests/test_hardware.py
  pattern: per plan/decisions.md §4
  acceptance: audit() (fresh) runs `dxdiag /t` to a temp output file, parses CPU name, total RAM GB, GPU name, GPU "Dedicated Memory" (VRAM) from the report text, adds disk free GB via psutil, and writes pydantic-validated generated/system_spec.json (audited_at ISO8601); load() reads existing cache and only re-audits when `refresh=True` (→ powers `--refresh-spec`); audit() is Windows-only — parsing logic is a pure function over report text so tests run dxdiag-free on the committed fixture file; missing/unparseable dxdiag section → explicit diagnostic error naming the missing field; test asserts fixture parse yields all five spec fields non-null and round-trips through load/save
    ruff format --check . && ruff check . && mypy src && pytest tests/test_hardware.py -q
  out-of-scope: WMI (rejected: 4GB AdapterRAM cap); non-Windows support beyond a clear error; scheduled re-audit
  status: done (commit 1d8d77f)

- [x] T-008: Pipeline service — check_game orchestration assembling Report
  depends: T-003, T-004, T-005, T-006, T-007
  files: src/keniran/services/check_game.py, src/keniran/adapters/llm/base.py, tests/test_check_game.py
  pattern: wiring per .spec/spec.md §3 flow steps 1–8
  acceptance: check_game(app_id, refresh_spec=False) executes full pipeline: spec-cache-or-audit → steam fetch (NoRequirementsPublished → Report with graceful "No PC requirements published" message, exit path non-error) → html strip → parse → CPU+GPU lookup (user + target sides; stale/one-sided render → unverified ⚠ per §4.5) → RAM/VRAM/Storage hard checks → scoring.py verdict; per-run in-memory Steam response cache (identical app id twice in one run → one fetch); returns plain Report dataclass with no rendering logic inside; adapters/llm/base.py defines RequirementExtractor protocol matching parser output schema (v1 stub only — no implementation); tests wire adapters through fakes/monkeypatched fetchers with fixture data, run network-free end-to-end, and cover: pass case, shortfall-cap case, unverified-target case, and no-requirements-published case
    ruff format --check . && ruff check . && mypy src && pytest tests/test_check_game.py -q
  out-of-scope: CLI rendering; true-network integration test (offline fakes only); LLM implementation
  status: done (commit 4408c9e)

- [x] T-009: CLI rendering — tables, verdict line, flags, graceful exits
  depends: T-008
  files: src/keniran/cli/app.py, tests/test_cli_report.py
  pattern: renderer of Report (swap contract: CLI is one renderer among future many)
  acceptance: `keniran <APP_ID> [--refresh-spec]` renders a rich comparison table: per-component rows with user value vs required, ratio % (ratio ≥1.0 shown as 100%), confidence badge for best-guess matches, ⚠ "unverified — manual review suggested" for unverifiable components (run still completes), one-line ⚠ ST note when flagged, and final verdict line with percentage semantics ("84% of the game's minimum requirement (Borderline — playable on low settings)"); no-requirements-published prints the graceful message and exits 0; bad/unknown appid response prints a clear error; `--version` still works; `--refresh-spec` forces re-audit (adapter behavior covered in T-007; here only the flag plumbing is asserted with a fake audit); full CLI tests use typer's test runner / rich console capture — no network
    ruff format --check . && ruff check . && mypy src && pytest -q
  out-of-scope: `--json` flag, `--search` flag, any prompt/interactivity; changing anything under core/ or adapters/
  status: done (commit 945e860)
