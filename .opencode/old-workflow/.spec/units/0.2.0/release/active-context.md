# Active context — 0.2.0 (release coordination)

- current task: unit complete — REL-001..004 all done. Release 0.2.0 CLOSED.
- last commit: 9fc6934 REL-001 fix: read installed version dynamically in --version tests
- state: REL-004 gates all green. Run log:
  - python -m ruff format . → 46 files unchanged
  - python -m ruff check . → All checks passed!
  - python -m mypy → Success: no issues found in 13 source files
  - python -m pytest -q → 183 passed (Windows)
  - WSL loop → 182 passed, 1 skipped (pre-existing intentional dev-host guard)
  - WSL smoke ran on a self-contained python-build-standalone 3.11.9 in
    .venv-wsl/ (gitignored) — system Python in WSL remains 3.8, untouched.
- Gate follow-up fixes (looped back to owning units, reviewer-approved):
  - e286278: tests/test_hardware.py platform-guard tests patched sys.platform only;
    inside WSL (posix) they ran the real linux audit. Fixed via
    _install_unsupported_platform (sys.platform + os.name="java" sentinel).
  - 9fc6934: CLI --version tests hardcoded "keniran 0.1.0"; now dynamic via
    importlib.metadata — no future bump drift.
- Note: REL-002 has no commit (plan/ is gitignored by design).
- REL-002 went through one full retry cycle: reviewer caught 4 factual overclaims
  (storage helper "both OSes", "never an exception", skipped_kinds surfaced, ST
  "informational column") + 3 leftover v1 labels; all fixed and re-approved.
- gated status: model-layout / linux-audit / ratio-scoring / storage-mounts all
  complete at time of REL-001..004 execution.
