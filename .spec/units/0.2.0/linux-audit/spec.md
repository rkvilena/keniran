unit-id: 0.2.0/linux-audit
task-prefix: LIN

## Goal

Implement the Linux hardware adapter as the second backend behind the hardware port:
pure parsers for `/proc/*`, `lspci`, `nvidia-smi`, `vulkaninfo`, a name-cleanup layer,
and the assembled `audit()` with fallback chains that degrade to `unverified` (None),
never crash. Validated via WSL-recorded fixtures; WSL≠native caveat documented.

## Touched Areas

- `src/keniran/adapters/hardware/linux.py` (new — parsers, subprocess runners, `run_audit`)
- `src/keniran/adapters/hardware/__init__.py` (dispatch entry for non-win32)
- `scripts/capture_linux_fixtures.sh` (new — fixture capture helper, run inside WSL)
- `tests/fixtures/linux/` (new) + `tests/test_hardware_linux.py` (new)

## Changed Contracts

- Adds `hardware/audit` Linux path on non-win32 platforms producing the same
  `SystemSpec` (with `platform="linux"` and possibly `vram_gb=None`).
- No dependency additions; all Linux detection = stdlib psutil + shelling out to
  `lspci`/`nvidia-smi`/`vulkaninfo` when present.
- End state of every unresolvable field is `None` in `SystemSpec` (renders as
  `unverified ⚠`), per the honesty gate — never a fabricated number, never an exception.

## Acceptance Runner

`python -m pytest tests/test_hardware_linux.py -q` plus full gate
`python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy`;
the smoke step runs the suite inside WSL: `wsl -e bash -lc "cd '<repo on /mnt/e>' && python -m pytest -q"`.

## Prerequisites

MUST be done before this unit: `0.2.0/model-layout` (package facade + model changes).

Open Questions (parked):
- Exact `wsl.exe` invocation for fixture capture is an implementation nuance; the
  capture script is the contract, not the shell command.
