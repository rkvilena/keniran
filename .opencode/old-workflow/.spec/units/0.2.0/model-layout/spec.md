unit-id: 0.2.0/model-layout
task-prefix: SYS

## Goal

Prepare the skeleton the rest of 0.2.0 builds on: turn the `hardware` module into a
platform-dispatched package, and make `SystemSpec` carry what 0.2.0 needs (`platform`
field, optional `vram_gb`) with cache invalidation and interim unverified handling.
No behavior change beyond the model plumbing — scoring semantics arrive in the
ratio-scoring unit, Linux implementation in the linux-audit unit.

## Touched Areas

- `src/keniran/adapters/hardware.py` → package (`__init__.py` facade + `windows.py`)
- `src/keniran/core/models.py` (`SystemSpec`, `platform`, optional `vram_gb`)
- `src/keniran/services/check_game.py` (typing only for optional VRAM; logic preserved)
- `tests/test_hardware.py`, `tests/test_check_game.py` (import paths + new cases)

## Changed Contracts

- `SystemSpec`: adds `platform: str` (value = `sys.platform`, e.g. `"win32"`);
  `vram_gb` becomes `float | None` (None = unverified, honest state per §2 honesty gate).
- Cache: `load()` re-audits when the cached `platform` differs from the running OS
  (protects the shared WSL↔Windows project folder). Old 0.1.0 caches (no `platform`
  key) count as mismatched → one re-audit, then fresh cache.
- Public API compat: `keniran.adapters.hardware.{audit,load,save,parse_dxdiag}` remain
  importable from the facade; `check_game.py` keeps calling `hardware.load` unchanged.

## Acceptance Runner

`python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy`

## Prerequisites

None — first unit of 0.2.0.

## Open Questions

- None.
