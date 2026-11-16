# Active context — 0.2.1/linux-storage

- current task: unit complete — LSTO-001 + LSTO-002 done.
- last commit: 971b743 LSTO-002 (reviewer-approved; suite 213 green; WSL smoke
  212 passed + 1 expected skip on Linux host).
- state: linux-storage unit DONE. Notes: (1) acceptance WSL smoke ran via
  `.venv-wsl/venv311/bin/python` — the distro's bare `python` is 3.8 without
  pytest; record for REL21-003. (2) Test determinism: audit tests inject
  partitions via `_install_partitions` (host-agnostic). (3) Honesty upgrade live:
  no measurable mount → disk_free_gb=None + unverified row, legacy 0.0 gone.
