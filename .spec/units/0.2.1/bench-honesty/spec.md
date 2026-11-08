unit-id: 0.2.1/bench-honesty
task-prefix: HON

## Goal

Close the WSL-smoke honesty finding (decisions.md, app 2679460): `lspci` without the
pciutils ID database reports the GPU as a placeholder like `Device 008e`; because the
hex-looking token contains digits, `has_model_number()` passes, Stage 2 fuzzy-matches
it onto a real card, and the report shows a confident pass for hardware the machine
never named. Add a **name-quality floor at lookup entry**: placeholder-shaped names
are classified model-less *before* any matching and degrade to `matched_by="unverified"`
— reusing the existing honesty path end-to-end, with zero scoring changes.

Design (agreed in interview 2026-11-08):
- **Gate lives in `benchmarks.lookup`, not scoring.** Placeholder names never reach
  Stage 1/2, so no score is ever released for them. `_match_score()` and the ratio
  pipeline stay untouched.
- **Denylist of placeholder patterns, not a marketing whitelist.** A normalized name
  matching a placeholder shape (`^device [0-9a-f]+$`, bare hex `^[0-9a-f]{4}$`, and
  similar lspci/USB-style placeholders) is garbage. Real names never match these
  shapes, so false-unverified risk stays zero. A marketing-vocabulary whitelist was
  rejected: any legitimately named card missing from the list would degrade — the
  opposite failure mode.
- **`best_guess` stays scorable.** Sub-gate fuzzy matches (real-ish names below
  `CONFIDENCE_GATE`) keep releasing scores with the confidence badge, exactly as
  today; only true placeholder garbage is rejected. Windows dxdiag names are
  unaffected.
- Native-Linux re-check of real device names stays parked (same posture as the GPU
  chain and LSTO): fixture + unit tests here; a real box may surface additional
  placeholder shapes — the denylist is data, extendable in one line.

## Touched Areas

- `src/keniran/adapters/benchmarks.py` (placeholder detection + early `unverified` return)
- `tests/test_benchmarks.py` (new cases; existing suite must stay green unchanged)
- `tests/fixtures/linux/lspci_mm.txt` — only if a placeholder variant fixture is
  needed; prefer constructing garbage names inline in tests

## Changed Contracts

- `benchmarks.lookup()` may return `MatchResult(matched_by="unverified")` for names
  that DO contain digits but match a placeholder shape — a deliberate widening of
  `has_model_number()`'s contract ("no digit left → model-less") to
  "no digit left OR placeholder-shaped → model-less". Public via a new module-private
  helper `_is_placeholder_name(name_text) -> bool`, applied inside `lookup()` next to
  the existing `has_model_number()` check.
- `MatchResult`, `ComponentRow`, scoring, and the renderer are unchanged — an
  `unverified` lookup already produces the ⚠ row and `min()` exclusion.
- No new dependencies; no CLI surface change.

## Acceptance Runner

`python -m pytest tests/test_benchmarks.py -q` plus full gate
`python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy`.

## Prerequisites

MUST be done before this unit: none outside the repo (benchmarks.py and the honesty
pipeline exist on disk; independent of 0.2.1/linux-storage — parallel-safe, different
files).

## Open Questions

- None blocking. Exact placeholder pattern set is frozen in HON-001's acceptance;
  native-Linux re-check stays deferred (decisions.md backlog posture).
