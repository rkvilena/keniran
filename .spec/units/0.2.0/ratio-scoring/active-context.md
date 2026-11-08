# Active context — 0.2.0/ratio-scoring

- current task: unit complete — both ratio-scoring tasks done.
- last commit: e0a0802 SCO-002: RAM/VRAM ratio rows wired into pipeline; storage stays binary
- state: ratio-scoring unit DONE (SCO-001 3142f3f, SCO-002 e0a0802); suite 169 green; ruff/mypy clean.
- interpretation notes (SCO-002, reviewer-approved):
  - required-side 0 GB guard: degenerate "0 GB" minimum → unverified row (matches
    _benchmark_row's target_score>0 pattern; NOT treated as shortfall).
  - "percentage ≈ 67%": display_percent floors → 4/6 renders 66% (band Poor either
    way); test pins 66.0 exactly.
  - test_cli_report.py needed no change; renderer already prefers row.ratio.
- interpretation notes (SCO-001, reviewer-approved):
  - new `capacity_ratio(user_gb, required_gb)` helper reuses component_ratio validation.
  - `build_verdict` grew keyword-only ram_ratio/vram_ratio (positional callers unaffected).
  - collateral: 2 assertions in tests/test_check_game.py pinned 0.1.0 shortfall
    semantics; updated to storage-only (forced by full-suite acceptance command;
    check_game.py itself untouched — wiring is SCO-002).
