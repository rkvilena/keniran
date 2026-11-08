# Tasks — 0.2.1/bench-honesty

- [ ] HON-001: Placeholder-name detection + lookup-entry honesty gate
  depends: -
  files: src/keniran/adapters/benchmarks.py, tests/test_benchmarks.py
  pattern: has_model_number() model-less → matched_by="unverified" path in lookup()
  acceptance:
    New module-private `_is_placeholder_name(name_text) -> bool` in benchmarks.py:
    1) normalizes via `normalize_name()` first (so `(R)`/clock noise never mask a
    placeholder shape);
    2) returns True for lspci/USB-style placeholder shapes — denylist is a module
    constant of compiled patterns covering at minimum: `device <hex>` (one or more
    hex chars, e.g. `Device 008e`), bare hex token of 4+ chars (e.g. `008e`,
    `0x25a2`-style after normalization), and `unknown device` phrasing;
    3) returns False for every real-name shape: `geforce rtx 3080`,
    `ryzen 5 3600`, `intel core i5-2300`, `arc a380`, `radeon rx 6600` — including
    digit-heavy but real names (`rx 6600`, `gtx 1060 6gb`);
    4) `lookup()` calls it before `has_model_number()` and returns
    `MatchResult(matched_by="unverified")` (no `best_entry`, no score) when True —
    the regression test pins the WSL-smoke case: `lookup(gpu_db_fixture,
    "Device 008e", kind="gpu")` returns `matched_by="unverified"` and would-have-
    scored-false-pass is gone; a companion positive control asserts
    `lookup(..., "GA102 [GeForce RTX 3080]", kind="gpu")` still resolves fuzzy/exact
    as before (cleanup output from LIN-002 is unaffected). No existing test
    expectations change (best_guess stays scorable; gate value 0.80 untouched).
    acceptance commands:
      python -m pytest tests/test_benchmarks.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: scoring/_match_score changes, MatchResult/ComponentRow model
    changes, CLI renderer changes, native-Linux validation, linux.py (LSTO's files)
