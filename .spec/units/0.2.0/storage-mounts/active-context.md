# Active context — 0.2.0/storage-mounts

- current task: unit complete — single task STO-001 done.
- last commit: 12ca965 STO-001: any-local-mount storage check via backend-agnostic helper
- state: storage-mounts unit DONE; suite 183 green; ruff/mypy clean.
- interpretation notes (STO-001, reviewer-approved):
  - audit() calls select_storage_free(None, partitions): helper picks largest-free
    eligible mount; pass/fail stays downstream via meets_minimum (binary semantics).
  - Linux backend left as-is (linux._disk_free_gb unchanged) — wiring the helper into
    the Linux audit was declared out of this task's files by orchestrator correction;
    known follow-up if parity is wanted later (post-0.2.0 or docs note).
  - disk_free_gb widened to float | None (unverified storage row when None, not a
    shortfall); new storage_used_mount field; ComponentRow.note is the skipped-kinds
    renderer surface.
  - collateral: tests/test_scoring.py model_fields set assertion + storage_used_mount.
