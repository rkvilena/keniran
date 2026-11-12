# Active context — v1.0.1 (release)

RESOLVE (unblocks ALT-001 → ALT-003 → all REL101 chores): for `split_alternatives`, how
should a disjunction whose candidates are ALL qualifier words behave — e.g.
`split_alternatives("or better")`? Verifier requires `()` (drop qualifier words whenever
the input contains an `or` separator); implementer kept `("better",)` (drop only when >1
candidate remains, preserving "non-empty without disjunction ⇒ 1-tuple"). The written
acceptance does not pin this raw-text edge; it never occurs in the pipeline because
`_clean_name` removes qualifiers before splitting. Decide, then rerun `/run v1.0.1`.

## Run summary (autonomous run, 2026-11-12) — every task accounted for

Completed (with commits):
- ALT-002 — done (commit c63b69c): vendor-alias normalization (NVIDIA≡GeForce →
  `geforce`, AMD≡Radeon → `amd`), token-level via `_TOKEN_RE` with presence guard,
  applied in `normalize_name` for both probe and DB rows; gate/ladder/score release
  unchanged. Verified PASS (cycle 2).
- TUIX-001 — done (commit cb4ce93): branded home hierarchy (Keniran title, large
  `keniran` wordmark, tagline, bordered App ID/Run command box) with theme-token CSS;
  `tokyo-night` retained; all ids/handlers unchanged. Verified PASS.
- TUIX-002 — done (commit b4efff2): `VerticalScroll` body (`#home` auto + `#results`
  auto/min-height 3), headless pilots at 100x30 + 80x16 prove no horizontal clipping,
  keyboard reachability, and scroll-to-end for long results/home; Header/Footer stay
  docked. Verified PASS.

Blocked (with reasons):
- ALT-001 — blocked: failed-review. Three verifier cycles, three FAILs; the code is green
  on every acceptance command (18 parser tests, full gate 272→279 passed); the final
  dispute is the unspecified raw-text edge `split_alternatives("or better")` →
  `("better",)` vs `()`. Work is preserved UNCOMMITTED in the tree
  (`src/keniran/core/requirements_parser.py`, `tests/test_requirements_parser.py`); the
  cached brief is `requirement-alternatives/briefs/ALT-001.md`. Resolve the RESOLVE entry,
  apply the one-line behavior change, re-verify, commit.
- ALT-003 — blocked: depends-on ALT-001.
- REL101-001..005 — blocked: pending-feature (gated on v1.0.1/requirement-alternatives,
  which cannot complete while ALT-001 is blocked).

Unvisited: none — every task in the release is done or blocked with a recorded reason.

## Standing context

- state: both feature units executed; tui-redesign is COMPLETE; requirement-alternatives
  is 1/3 done with the remainder blocked behind the ALT-001 review dispute. Release
  chores cannot start until the feature units are complete (gating enforced).
- preserved choices: meet-any OR semantics; lowest positive score among independently
  matched candidates; original requirement string kept in `GameRequirements` and the
  report; vendor aliases normalized; `best_guess` remains scorable and visibly badged.
- environment note: run all acceptance gates with `./.venv/Scripts/python.exe` (bare
  `python`/`pnpm exec python` may resolve to a miniconda interpreter lacking
  rapidfuzz/textual → spurious mypy import errors). `.venv` now has rapidfuzz 3.14.6 +
  textual 8.2.8 installed (environment-only fix made during ALT-001).
- version/history: v1.0.1 is the intended first public version; v1.0.0 remains frozen
  unpublished local history. Do not edit global `.spec/spec.md` in this release.
- open: the ALT-001 RESOLVE above; GitHub publication is user-controlled.
