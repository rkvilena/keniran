# Tasks — 0.2.0/model-layout

- [x] SYS-001: Split hardware module into a platform-dispatched package
  status: done (commit f43e66b)
  depends: -
  files: src/keniran/adapters/hardware/__init__.py, src/keniran/adapters/hardware/windows.py (moved content of hardware.py), tests/test_hardware.py
  pattern: existing src/keniran/adapters/hardware.py (move, don't rewrite)
  acceptance:
    The dxdiag logic is byte-for-byte identical in `windows.py`; the facade re-exports
    `audit`/`load`/`save`/`parse_dxdiag` plus `HardwareAuditError` et al., and selects
    the Windows backend on `sys.platform == "win32"`, raising
    `UnsupportedPlatformError` otherwise (behavior identical to today). Facade keeps
    the same signatures; no behavior change yet. Import paths used by tests and
    `check_game.py` keep working; old `hardware.py` file no longer exists at module
    level (as a package dir).
    acceptance commands:
      python -m pytest tests/test_hardware.py tests/test_check_game.py -q
      python -m ruff check . && python -m mypy
  out-of-scope: any Linux code, model changes, scoring changes

- [x] SYS-002: SystemSpec gains `platform` field; cache re-audits on OS mismatch
  status: done (commit 652cb14)
  depends: SYS-001
  files: src/keniran/core/models.py, src/keniran/adapters/hardware/__init__.py, src/keniran/adapters/hardware/windows.py, tests/test_hardware.py
  pattern: existing audit/load/save cache tests
  acceptance:
    `SystemSpec.platform` is required and set to `sys.platform` by both backends; the
    persisted JSON round-trips it. `load(refresh=False)` returns the cache only when
    cached `platform` equals the current `sys.platform`; a mismatch (or a legacy cache
    lacking the key) triggers `audit()` instead. New unit tests cover: mismatch
    triggers re-audit, legacy-cache migration path, matching-platform cache reuse.
    acceptance commands:
      python -m pytest tests/test_hardware.py -q
      python -m pytest -q && python -m mypy
  out-of-scope: vram optionality, anything Linux

- [x] SYS-003: Make `vram_gb` optional with interim unverified handling
  status: done (commit 0c71484)
  depends: SYS-002
  files: src/keniran/core/models.py, src/keniran/adapters/hardware/windows.py, src/keniran/services/check_game.py, tests/test_check_game.py
  pattern: existing `_hard_check_row` None-handling (meets_minimum already returns None for unknown sides)
  acceptance:
    `SystemSpec.vram_gb: float | None` validates with None. The Windows audit still
    fills vram (dxdiag case unchanged, so no Windows behavior change). In
    `check_game`, a spec with `vram_gb=None` produces a VRAM row marked unverified
    (`passed=None`, `unverified=True`) and is NOT counted as a shortfall by
    `scoring.minimum_shortfalls` — interim semantics exactly mirror today's
    unknown-required-value path. Full suite stays green (no test regressions on
    existing Windows-shaped fixtures).
    acceptance commands:
      python -m pytest tests/test_check_game.py tests/test_hardware.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: ratio-based RAM/VRAM scoring (next unit), Linux detection, storage changes
