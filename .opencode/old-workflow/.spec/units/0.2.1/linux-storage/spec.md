unit-id: 0.2.1/linux-storage
task-prefix: LSTO

## Goal

Finish the 0.2.0 follow-up: the Linux audit stops measuring only `/` and uses the same
shared any-local-fixed-mount helper as Windows (`select_storage_free`), with
Linux-specific partition hygiene the Windows path never needed — a pseudo-filesystem
denylist and same-device dedupe — so tmpfs/squashfs noise can never fake a storage PASS.
The Linux audit also starts recording `storage_used_mount` provenance, which STO-001
added to the model but the Linux audit never populated.

Design (agreed 2026-11-08):
- **Reuse, don't touch the helper.** `storage.py` stays pure and backend-agnostic
  (STO-001 contract frozen). All Linux-specific filtering happens in the Linux
  gatherer, mirroring how `windows.py::_collect_partitions()` prepares partitions.
- **Pseudo-fs denylist, Linux-side.** `tmpfs`, `squashfs` (snap), `proc`, `sysfs`,
  `devtmpfs`, `efivarfs`, `overlay`, `ramfs` and similar non-storage mounts are
  excluded before the helper sees them. Rationale for each trap: `tmpfs` is sized
  like RAM (inflated free space → false PASS), `squashfs` is read-only snap package
  content, the rest carry no usable storage. `fuseblk`/ntfs data partitions are
  deliberately **not** excluded (common on low-end dual-boot boxes).
- **Device dedupe.** Merged-usr and bind setups present one filesystem as several
  mountpoints; mounts sharing the same block device (`part.device`) are collapsed,
  keeping the mountpoint with the most free space. `tmpfs` instances are already
  denied, so dedupe only ever collapses real-storage duplicates.
- **WSL is covered by the existing helper, not the denylist.** `/mnt/c` etc. report
  `drvfs`/`9p`; `9p` is already in `storage._NETWORK_FSTYPES`, so guest-accessible
  Windows drives degrade to a *noted* network skip — exactly STO-001's semantics.
- **Honesty upgrade (Linux path):** when no eligible mount can be measured, the audit
  stores `disk_free_gb=None` (unverified ⚠ row) instead of the legacy root-failure
  `0.0`. The legacy `0.0`-on-failure behavior of `linux._disk_free_gb()` is deleted.

## Touched Areas

- `src/keniran/adapters/hardware/linux.py` (denylist + dedupe + gatherer; `audit()` wiring)
- `tests/test_hardware_linux.py` (new tests, LSTO-001 and LSTO-002 both live here)
- `tests/fixtures/linux/disk_partitions.json` (new — recorded psutil-style partition data)

## Changed Contracts

- `linux.audit()` now derives storage from `select_storage_free(None,
  linux._collect_partitions())` — same call shape as `windows.py` — and sets
  `disk_free_gb` **and** `storage_used_mount` from the result. Scoring, the binary
  storage semantics, and the renderer's `"<free> GB (<mount>)"` row are unchanged;
  they already consume these fields.
- `linux._disk_free_gb()` (root-only, `0.0`-on-failure) is removed. Nothing external
  referenced it except the audit itself (module-private, checked grep 2026-11-08).
- New module-private pure function contract in `linux.py`:
  `filter_linux_partitions(raw_parts, free_gb_lookup) -> tuple[list[Partition],
  frozenset[str]]` — plain entries (duck-typed psutil partitions), no I/O, returns
  surviving mounts (denylist + dedupe applied, spaces measured via the injected
  lookup) plus the kinds it skipped as `"pseudo"`. The narrow I/O wrapper
  `_collect_partitions()` feeds it real psutil data, tested via monkeypatch.

## Acceptance Runner

`python -m pytest tests/test_hardware_linux.py -q` plus full gate
`python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy`;
WSL smoke unchanged: `wsl -e bash -lc "cd '<repo-on-/mnt/e>' && python -m pytest -q"`.

## Prerequisites

MUST be done before this unit: none outside the repo (all 0.2.0 units are done; the
helper and the Linux adapter both exist on disk).

## Open Questions

- Native-Linux live validation of the gatherer stays parked (same posture as 0.2.0's
  GPU chain): tests run on fixtures + monkeypatch; the WSL smoke covers the `9p`
  paths but a real box may still surface an unlisted pseudo-fstype. The denylist is
  data, so adding a type later is a one-line change, not a contract change.
