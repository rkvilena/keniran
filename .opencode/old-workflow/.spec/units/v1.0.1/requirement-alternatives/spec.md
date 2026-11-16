unit-id: v1.0.1/requirement-alternatives
task-prefix: ALT

## Goal

Correct the FC27 false-negative by treating CPU/GPU names joined by `or` as independent
requirement alternatives, normalizing common vendor aliases before benchmark matching,
and scoring against the least demanding resolvable candidate. Preserve the current
`GameRequirements` and `Report` shapes and the existing best-guess confidence policy.

## Touched Areas

- `src/keniran/core/requirements_parser.py` — add pure splitting of cleaned component
  requirement strings while preserving their existing joined string fields.
- `src/keniran/adapters/benchmarks.py` — normalize NVIDIA/GeForce and AMD/Radeon vendor
  terms consistently on probe and database names.
- `src/keniran/services/check_game.py` — independently look up alternatives and select
  the lowest positive benchmark score among usable matches.
- `tests/test_requirements_parser.py`, `tests/test_benchmark_lookup.py`,
  `tests/test_check_game.py` — fixture/offline coverage of parsing, aliases, selection,
  preserved confidence/report semantics, and the FC27 regression.

## Changed Contracts

- Add `split_alternatives(name_text: str) -> tuple[str, ...]` to the pure requirements
  parser. It takes cleaned component text, splits on standalone case-insensitive `or`
  between model descriptions, drops empty pieces, returns `()` for empty input, and
  returns a single-item tuple for non-empty input with no alternative. Existing qualifier
  cleanup (`or better`, `or equivalent`, etc.) remains intact and those phrases are not
  treated as alternatives.
- `GameRequirements.cpu_name` and `.gpu_name` stay the cleaned original strings; no model
  schema change. Reports show that original requirement string. Matching resolves each
  alternative independently and chooses the candidate with the lowest positive
  `best_entry.score`; a match with `matched_by="best_guess"` is usable when it has a
  score. `none`, `unverified`, missing-score, and non-positive-score candidates are
  ignored. If none is usable, preserve existing unverified behavior. Selected CPU match
  also supplies the single-thread comparison.
- Apply NVIDIA/GeForce and AMD/Radeon alias equivalence to both normalized probes and
  normalized database names. Other fuzzy stages, the confidence threshold, and score
  release rules remain unchanged.
- Offline FC27 regression: `AMD RX 570 or Nvidia GTX 1050 Ti` does not select an A40;
  the RTX 3050 test machine matches the lower-scoring valid target alternative and the
  complete fixture report is Pass with the capped 100% display.

## Acceptance Runner

Focused: `python -m pytest tests/test_requirements_parser.py tests/test_benchmark_lookup.py tests/test_check_game.py -q`.
Full gate: `python -m ruff format . && python -m ruff check . && python -m mypy && python -m pytest -q`.

## Prerequisites

None within this feature. It is the first feature in the v1.0.1 release sequence and must
complete before `v1.0.1/tui-redesign` (per the release spec).

## Open Questions

- None blocking. The alternative separator is standalone English `or`; comma/slash
  lists and translations are not broadened in this fix. Existing qualifier cleanup is
  retained rather than interpreting `or better` as a distinct candidate.
