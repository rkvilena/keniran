# Active context — 0.2.0/linux-audit

- current task: unit complete — all 3 linux-audit tasks done.
- last commit: 2420b9d LIN-003: Linux audit assembly, platform dispatch, degraded-chain tests
- state: linux-audit unit DONE (LIN-001 0a43fa7, LIN-002 81733e8, LIN-003 2420b9d); suite 161 green; ruff/mypy clean.
- DEFERRED: LIN-003's WSL smoke step (wsl pytest) — WSL distro has only Python 3.8,
  project pins 3.11. User decision 2026-11-08: defer to REL-004, which runs the WSL
  loop as part of the release gate. RESOLVE at REL-004: install py3.11 in WSL
  (deadsnakes) or smoke will fail again.
- interpretation notes (LIN-003, reviewer-approved):
  - Fully broken GPU chain → pydantic ValidationError (gpu_name required), NOT
    HardwareAuditError; honesty gate forbids placeholder names. Only VRAM degrades
    to a persisted None. Empty CPU+RAM → LinuxAuditError.
  - linux audit() up-front guard os.name != "posix" → UnsupportedPlatformError
    (mirrors windows.py guard; keeps facade non-win32 dispatch tests green).
  - _disk_free_gb degrades to 0.0 (required ge=0 field) — documented deviation.
- RESOLVE at REL-004: RESOLVED — WSL smoke ran green on a self-contained
  python-build-standalone 3.11.9 under .venv-wsl/ (gitignored); the WSL system
  Python (3.8) was deliberately left untouched.
- interpretation notes (LIN-002, reviewer-approved):
  - vulkaninfo heap size is BYTES not MiB; parser does bytes→GB (task's "MiB → GB"
    wording was the intent; deviation documented in docstring).
  - lspci -mm precedence: 3D > VGA > Display with unresolvable-class fallbacks;
    same-class ties → first occurrence.
  - _clean_linux_name promotes bracketed sub-name only when it has marketing vocab;
    [10DE:xxxx] brackets, (rev a1), Lite Hash Rate always stripped.
