unit-id: 0.2.0/ratio-scoring
task-prefix: SCO

## Goal

Convert the verdict math so RAM and VRAM become scored ratios instead of hard
pass/fail caps. Rationale settled in design discussion: proportional leniency beats a fixed
1 GB margin (15.5/16 GB RAM → ~97% Borderline; 4/6 GB VRAM → ~67% Poor) and shortfalls
degrade the report honestly instead of flipping a cliff at Fail.

## Touched Areas

- `src/keniran/core/scoring.py` (ratio composition, verdict cap semantics)
- `src/keniran/core/models.py` (`Verdict.spec_shortfall` narrows to storage-caused)
- `src/keniran/services/check_game.py` (RAM/VRAM rows become ratio rows)
- `tests/test_scoring.py`, `tests/test_check_game.py`

## Changed Contracts

- Final ratio = **min(CPU, GPU, RAM, VRAM)** where RAM/VRAM ratios are
  `user / required` (values ≥ 1.0 display-capped at 100% as today).
- Unverified components (None ratio or None user value) are excluded from min() —
  mirroring how CPU/GPU unverified ratios already behave.
- Shortfall cap (`Fail (spec shortfall)`) now fires **only for Storage**; RAM/VRAM
  shorts surface via the ratio/bands instead. `VerdictBand.FAIL` keeps its meaning
  (shortfall storage OR unplayable ratio).
- Storage comparison is untouched here (its any-mount rework is a separate unit).

## Acceptance Runner

`python -m pytest tests/test_scoring.py tests/test_check_game.py -q` + full gate
(`pytest -q && ruff format . && ruff check . && mypy`).

## Prerequisites

MUST be done before this unit: `0.2.0/model-layout` (optional `vram_gb` exists).
Runs in parallel with the linux-audit and storage-mounts units (disjoint areas).

## Open Questions

- None.
