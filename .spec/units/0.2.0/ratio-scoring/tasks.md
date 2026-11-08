# Tasks — 0.2.0/ratio-scoring

- [ ] SCO-001: Scoring core: RAM/VRAM ratios join the verdict min
  depends: -
  files: src/keniran/core/scoring.py, src/keniran/core/models.py, tests/test_scoring.py
  pattern: component_ratio + final_ratio + build_verdict in scoring.py
  acceptance:
    `final_ratio` (or its successor) accepts and includes capacity ratios; capacity
    ratio = `component_ratio(user, required)` reused, validated non-negative. Unverified
    (None) sides excluded from min(); min() returns None only when everything is
    unscorable (unchanged rule). `minimum_shortfalls` narrows to STORAGE only; the
    `Fail (spec shortfall)` cap logic moves to storage-only. Docstring of build_verdict
    updated to the new composition. Exact test cases: RAM user=15.5 req=16 → ratio
    ≈ 0.969 → BORDERLINE; VRAM user=4 req=6 → ratio ≈ 0.667 → POOR; RAM user=3.5
    req=8 → ratio ≈ 0.44 → UNPLAYABLE; RAM-unverified + CPU/GPU pass → PASS (not
    capped); storage short + great benchmarks → FAIL cap preserved.
    acceptance commands:
      python -m pytest tests/test_scoring.py -q
      python -m pytest -q && python -m mypy
  out-of-scope: check_game/report wiring, storage mounting, any display change

- [ ] SCO-002: Pipeline wiring: RAM/VRAM rows show ratios, storage stays binary
  depends: SCO-001
  files: src/keniran/services/check_game.py, tests/test_check_game.py
  pattern: _benchmark_row for ratio rows; _hard_check_row kept for storage
  acceptance:
    RAM/VRAM rows are built as ratio rows (`ratio` filled, `passed=None`); storage
    keeps the boolean `passed` path unchanged this unit. RAM ratio = ram_gb / required;
    VRAM ratio uses spec.vram_gb only when not None (None → unverified row, excluded
    from min). Required-side None ("not published") behaves like today: row without
    ratio, unverified flag, component excluded from verdict math. Report rows for
    RAM/VRAM render a ratio in the same shape CPU/GPU rows already use (CLI renderer
    needs no change; renderer already handles ratio rows). Integration tests pin the
    Metaphor-style scenario end-to-end: VRAM 4 vs 6 → verdict band Poor with
    percentage ≈ 67%.
    acceptance commands:
      python -m pytest tests/test_check_game.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: storage semantic change, Linux adapter, CLI renderer edits
