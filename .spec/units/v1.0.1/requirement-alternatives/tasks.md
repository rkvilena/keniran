# Tasks — v1.0.1/requirement-alternatives

- [ ] ALT-001: Split cleaned CPU/GPU requirement alternatives
  depends: -
  files: src/keniran/core/requirements_parser.py, tests/test_requirements_parser.py
  pattern: `_clean_name`, `_parse_cpu`, `_parse_gpu` in src/keniran/core/requirements_parser.py; parser tests in tests/test_requirements_parser.py
  context: src/keniran/core/models.py
  acceptance:
    Add pure `split_alternatives(name_text: str) -> tuple[str, ...]`. It splits standalone
    case-insensitive `or`, trims/drops empty candidates, returns `()` for empty input,
    and returns a single candidate for non-empty input without a disjunction. After parser
    cleanup, `or better` / `or equivalent`
    still produce a single candidate rather than an alternative list. Parsing
    FC27-style Processor/Graphics lines keeps the original cleaned OR expression in the
    existing `cpu_name` / `gpu_name` fields; no `GameRequirements` schema change. Tests
    cover CPU and GPU alternatives, mixed-case separator, empty/single-item values, and
    qualifiers.
    acceptance commands:
      python -m pytest tests/test_requirements_parser.py -q
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
  out-of-scope: benchmark aliasing, service scoring, new model fields, comma/slash alternatives

- [ ] ALT-002: Normalize common GPU vendor aliases for benchmark lookup
  depends: -
  files: src/keniran/adapters/benchmarks.py, tests/test_benchmark_lookup.py
  pattern: `normalize_name` / `_apply_aliases` in src/keniran/adapters/benchmarks.py; stage-zero tests in tests/test_benchmark_lookup.py
  context: tests/fixtures/benchmark_mini.json
  acceptance:
    Probe and database normalization treat NVIDIA/GeForce and AMD/Radeon as equivalent
    vendor terms without changing the confidence gate or best-guess score release. Offline
    lookup tests build small inline database rows and prove `Nvidia GTX 1050 Ti` resolves
    to the GeForce GTX 1050 Ti row at exact/high confidence, and `AMD RX 570` resolves to
    a Radeon RX 470/570-like row at or above the existing gate. Existing unrelated
    exact/fuzzy/placeholder tests remain unchanged and pass; no fixture database file is
    modified.
    acceptance commands:
      python -m pytest tests/test_benchmark_lookup.py -q
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
  out-of-scope: requirement parsing, OR reduction, confidence-policy changes, network/database refresh

- [ ] ALT-003: Score OR alternatives using meet-any semantics
  depends: ALT-001, ALT-002
  files: src/keniran/services/check_game.py, tests/test_check_game.py
  pattern: `check_game`, `_benchmark_row`, `_single_thread_ratio` in src/keniran/services/check_game.py; offline `_check` helpers in tests/test_check_game.py
  context: src/keniran/core/requirements_parser.py, src/keniran/core/models.py, src/keniran/adapters/benchmarks.py
  acceptance:
    For CPU and GPU alternatives, run lookup independently for every candidate and select
    the lowest positive `best_entry.score` among usable matches (ties keep the first
    listed candidate; distinct-score selection is independent of list order).
    A scored `best_guess` remains usable; candidates with no entry or absent/non-positive
    score are ignored. If none is usable, the row stays unverified as before. The report
    retains the original full OR string in `required_value`, displays the chosen entry and
    confidence, and uses the selected CPU target's single-thread score. Add an offline FC27
    regression using inline Steam text and inline CPU/GPU database rows (the normal
    `_check` injection seams): user RTX 3050 Laptop score 11718, RX 470/570 score 7904,
    GTX 1050 Ti score 6368, and a CPU above both listed CPU minima. Selected GPU target is
    GTX 1050 Ti, GPU ratio is approximately 1.84, and the complete report verdict is Pass
    with 100% display. Add coverage for one unmatched alternative alongside a usable
    alternative and for no usable alternatives. Full gate green.
    acceptance commands:
      python -m pytest tests/test_check_game.py -q
      python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q
  out-of-scope: Report/GameRequirements schema changes, verdict confidence policy, RAM/VRAM/storage scoring
