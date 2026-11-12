# Active context — v1.0.1/requirement-alternatives

RESOLVE — RESOLVED (user decision 2026-11-12): `split_alternatives("or better")` returns
`("better",)`. Qualifier words are dropped only as EXTRA candidates (`"A or better or B"`
→ `("A", "B")`); an all-qualifier residue stays a single candidate, preserving
"non-empty input without a disjunction ⇒ 1-tuple". Recorded in `.spec/decisions.md`
("v1.0.1 run ruling"). The ruled behavior is already what the uncommitted ALT-001 code
implements; the ruling is pinned by test in this unit's task work.

- current task: ALT-001 → **done (commit e7b219c)** after the spec-owner ruling
  (`.spec/decisions.md` "v1.0.1 run ruling": all-qualifier residue stays a single
  candidate, e.g. `"or better"` → `("better",)`). ALT-002 done (c63b69c). Both
  dependencies of ALT-003 are now satisfied → next task: ALT-003 (meet-any scoring +
  FC27 regression).
- state: vendor-alias normalization landed — NVIDIA≡GeForce → canonical `geforce`,
  AMD≡Radeon → canonical `amd`, token-level via `_TOKEN_RE` with a presence guard, applied
  inside `normalize_name` so probe and DB rows share the key space. Gate/ladder/score
  release unchanged. 26 lookup tests pass; full gate 280 passed.
- state: ALT-001 implementation is COMPLETE in the working tree (uncommitted) and green
  on every acceptance command — `python -m pytest tests/test_requirements_parser.py -q`
  → 18 passed; full gate (ruff format/check, mypy, pytest) → all pass, 272 passed. The
  verifier's final FAIL is a dispute over an unspecified raw-text edge case (see RESOLVE
  above), not an acceptance-command failure. Uncommitted diff:
  `src/keniran/core/requirements_parser.py`, `tests/test_requirements_parser.py`.
  Do NOT revert; a future run can finish ALT-001 from this state (brief is cached at
  `briefs/ALT-001.md`).
- verifier findings across cycles: (1) cycle-1 FAIL was an environment artifact (mypy run
  under a miniconda interpreter lacking rapidfuzz/textual — use
  `./.venv/Scripts/python.exe`; deps now installed in `.venv`); (2) cycle-2 FAIL fixed:
  `split_alternatives("A or better or B")` now returns `("A", "B")`; (3) cycle-3 FAIL
  (open): `split_alternatives("or better")` returns `("better",)` — verifier wants `()`.
- contract: preserve scalar `GameRequirements.cpu_name` / `gpu_name` and report source text;
  split alternatives with the parser helper and reduce valid benchmark matches in
  `check_game` using the lowest positive target score. Scored `best_guess` remains valid.
- release prerequisite: complete this feature before `v1.0.1/tui-redesign`.
- acceptance commands are verified in `.spec/conventions.md` and each task block. Always
  run them with `./.venv/Scripts/python.exe` (bare `python` may resolve to miniconda).
- open: separator scope is standalone English `or` only; do not expand to commas/slashes.
