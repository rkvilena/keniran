# Active context — v1.0.1/requirement-alternatives

RESOLVE: For `split_alternatives`, how should a disjunction whose candidates are ALL
qualifier words behave — e.g. `split_alternatives("or better")`? The verifier requires
`()` (drop qualifier words whenever the input contains an `or` separator), while the
implementer kept `("better",)` (qualifier words dropped only when >1 candidate remains,
preserving "non-empty input without a disjunction ⇒ 1-tuple"). The written acceptance
("After parser cleanup, `or better` / `or equivalent` still produce a single candidate
rather than an alternative list") does not pin this raw-text edge, which never occurs in
the pipeline (`_clean_name` removes qualifiers before splitting). Decision needed to
unblock ALT-001.

- current task: ALT-002 → **done (commit c63b69c)**. ALT-001 remains **blocked: failed-review**
  (RESOLVE entry below). Next: TUIX-001 (buildable; release-spec sequencing deviation
  noted in the release active-context), then TUIX-002; ALT-003 and all REL101 chores are blocked.
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
