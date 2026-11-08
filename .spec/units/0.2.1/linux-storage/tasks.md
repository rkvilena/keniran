# Tasks — 0.2.1/linux-storage

- [x] LSTO-001: Linux partition gatherer — pseudo-fs denylist + same-device dedupe
  status: done (commit 0c692a5)
  depends: -
  files: src/keniran/adapters/hardware/linux.py, tests/fixtures/linux/disk_partitions.json, tests/test_hardware_linux.py
  pattern: windows.py `_collect_partitions()` (STO-001 helper consumption shape)
  acceptance:
    New module-private pure function `filter_linux_partitions(raw_parts,
    free_gb_lookup) -> tuple[list[Partition], frozenset[str]]` in linux.py:
    1) excludes pseudo-filesystem mounts by fstype denylist (tmpfs, ramfs,
    devtmpfs, proc, sysfs, efivarfs, squashfs, overlay — denylist is a module
    constant; `fuseblk`/ntfs data partitions are NOT excluded) and records them
    internally as kind `"pseudo"`;
    2) collapses same-`device` mounts to the single mountpoint with the most free
    space (dedupe documented for merged-usr/bind setups);
    3) measures free space through the injected `free_gb_lookup` callable (no real
    fs in tests); a mount the lookup cannot measure keeps `free_gb=None` and is
    never picked as "best";
    4) never raises on malformed partial data — honesty gate, per-field degrade.
    Next to it, `_collect_partitions()` (I/O wrapper): reads
    `psutil.disk_partitions(all=False)`, measures with `psutil.disk_usage`, and
    returns the filtered list — structurally mirroring windows.py so audit() differs
    from Windows only in the gathering step. Fixture
    `tests/fixtures/linux/disk_partitions.json` records representative mounts
    (`/` ext4, `/home` ext4 same device as `/`, `/boot/efi` vfat, `/run` tmpfs,
    one snap `squashfs`, `/mnt/c` drvfs/9p) with realistic free-space values;
    tests bind the fixture to exact expected filtered output (tmpfs/squashfs/9p
    gone, `/`+`/home` deduped, `/boot/efi` and `/` kept), with a tmpfs-vs-/ case
    asserting the inflated tmpfs free space can never win.
    acceptance commands:
      python -m pytest tests/test_hardware_linux.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: wiring into audit() (LSTO-002), any storage.py/helper change, WSL
    9p handling changes (helper network-list contract is frozen), Steam-library
    mount detection (backlog)

- [x] LSTO-002: Wire the shared helper into linux `audit()` — disk_free_gb + mount provenance
  status: done (commit 971b743)
  depends: LSTO-001
  files: src/keniran/adapters/hardware/linux.py, tests/test_hardware_linux.py
  pattern: windows.py audit() lines 153–161 (storage = select_storage_free(None, _collect_partitions()))
  acceptance:
    `audit()` replaces the root-only `_disk_free_gb()` call with
    `storage = select_storage_free(None, _collect_partitions())`; spec fields:
    `disk_free_gb=storage.free_gb`, `storage_used_mount=storage.mount`. Behavior:
    1) multi-mount pick — audit-level test (gatherer monkeypatched) with `/`
    (20 GB) plus an eligible second mount `/games` (200 GB) stores 200.0 and
    mount `/games`;
    2) nothing measurable — empty/unmeasurable partitions → `disk_free_gb=None`,
    `storage_used_mount=None` (unverified row via the existing `_hard_check_row`
    None path), NOT the legacy `0.0`;
    3) legacy `_disk_free_gb` deleted (test suite must pass without it;
    grep-verified no other references). Docstring/comments updated: root `/` is a
    *guaranteed candidate*, no longer the only one — the user-visible parity with
    the Windows any-mount rule. WSL smoke rerun green (real `/mnt/c` drvfs entries
    now flow through the helper's 9p network skip).
    acceptance commands:
      python -m pytest tests/test_hardware_linux.py tests/test_hardware.py tests/test_check_game.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
      wsl -e bash -lc "cd '<repo-on-/mnt/e>' && python -m pytest -q"
  out-of-scope: scoring changes, renderer changes (mount display already exists),
    storage.py edits, native-Linux live validation, cache-migration logic
    (existing caches re-audit on version/platform mismatch rules already in place)
