unit-id: 0.2.0/storage-mounts
task-prefix: STO

## Goal

Replace the single-drive storage check with the any-local-mount rule: PASS when **any**
local fixed mount has ≥ the required free space; the best mount is displayed and the
row stays binary (storage can still cap the verdict). This fixes the 0.1.0 Windows bug
(years of games on `E:` while only `SYSTEMDRIVE`/`C:` was checked) and lands the same
parity on Linux — before the Linux unit wires its audit, so the Linux adapter inherits
the right storage behavior.

## Touched Areas

- `src/keniran/adapters/hardware/storage.py` (new shared helper)
- `src/keniran/adapters/hardware/windows.py` (audit uses helper instead of SYSTEMDRIVE)
- `src/keniran/core/models.py` (SystemSpec provenance for the chosen mount)
- `src/keniran/services/check_game.py` (storage row shows chosen mount)
- `tests/test_hardware.py`, `tests/test_check_game.py`

## Changed Contracts

- New shared helper contract: enumerate `psutil.disk_partitions` → filter to local,
  fixed-disk partitions (exclude removable/network); PASS if any free ≥ required
  (2-decimal GB); picked mount = the one with the largest free space; mounts skipped
  by the filter are recorded (list of their kinds) so a skipped big mount is noted,
  not silent. Linux unit (parallel) wires the same helper into its audit.
- `SystemSpec` gains `storage_used_mount: str` (chosen mount point; provenance only —
  the scored number stays `disk_free_gb`).
- Storage row `user_value` renders as `"<free> GB (<mount>)"`.
- `scoring.meets_minimum`/`minimum_shortfalls` signatures unchanged — the helper feeds
  the canonical best free-space number into the existing hard-check path.

## Acceptance Runner

`python -m pytest tests/test_hardware.py tests/test_check_game.py -q` + full gate.

## Prerequisites

MUST be done before this unit: `0.2.0/model-layout` (package facade exists).
Scheduling note: to avoid two units touching `windows.py` at the same time, run this
unit before or after `0.2.0/linux-audit`, or finish before its LIN-003 assembly step.

## Open Questions

- None.
