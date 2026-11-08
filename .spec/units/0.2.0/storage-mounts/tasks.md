# Tasks — 0.2.0/storage-mounts

- [x] STO-001: Any-local-mount storage check, wired into both hardware backends
  status: done (commit 12ca965)
  depends: -
  files: src/keniran/adapters/hardware/storage.py, src/keniran/adapters/hardware/windows.py, src/keniran/core/models.py, src/keniran/services/check_game.py, tests/test_hardware.py, tests/test_check_game.py
  pattern: psutil.disk_usage usage in windows.py (cross-platform core already)
  acceptance:
    Shared pure-core helper (`select_storage_free(required_gb, partitions)`) with
    injected partition list so tests need no real filesystem: given fake partitions →
    1) any local fixed mount with free ≥ required → PASS and picked mount = largest
    free mount; 2) none qualifies → FAIL with the best mount still recorded; 3)
    removable/network partitions are excluded per filtering rule and their kinds are
    returned as `skipped_kinds` (noted, not silent); 4) empty partition list → None
    free, honest unverified row. Fields stored: `disk_free_gb` (best eligible) +
    `storage_used_mount`. Windows `audit()` replaces the SYSTEMDRIVE lookup with the
    helper (real-partitions test mocked; existing single-drive test updated to the
    multi-mount shape). Storage row in `check_game` renders `"<free> GB (<mount>)"`
    and keeps binary pass semantics; a skipped-network edge test asserts the note
    surface exists for renderer use. Linux wiring happens in LIN-003 via dispatch —
    this task only guarantees the helper is backend-agnostic (no win32 imports).
    acceptance commands:
      python -m pytest tests/test_hardware.py tests/test_check_game.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: Steam-library mount detection (backlog), any scoring change,
  changing the binary nature of the storage check, UI/CLI renderer edits beyond the
  user_value string it already renders verbatim
