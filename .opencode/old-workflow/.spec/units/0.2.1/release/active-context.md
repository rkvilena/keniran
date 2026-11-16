# Active context — 0.2.1 (release unit)

- current task: release COMPLETE — REL21-001, REL21-002, REL21-003 all done.
- last commit: d0e994e REL21-002 (docs sweep). Feature commits: 0c692a5 (LSTO-001),
  971b743 (LSTO-002), 2abb3aa (HON-001), db9fa59 (REL21-001).
- run log (REL21-003, 2026-11-08, orchestrator-verified):
  - Host gate: ruff format 56 files unchanged · ruff check "All checks passed!" ·
    mypy "no issues in 13 source files" · pytest 235 passed.
  - WSL gate (`.venv-wsl/venv311/bin/python`; bare `python` is 3.8, no pytest):
    234 passed, 1 skipped — skip = tests/test_hardware_linux.py:795 Windows-host
    guard; 234+1=235 reconciles exactly.
  - HON-001 placeholder re-check vs REAL WSL tool output: lspci -mm (pci.ids
    installed) reports paravirtual Microsoft 3D controllers as "Device 008e";
    _gather_gpu_name() → "Device 008e"; _is_placeholder_name → True;
    lookup(gpu_db, "Device 008e", gpu) → matched_by=unverified, no score — the
    REL-004 false-pass is unreachable. (Reviewer note: a "56-file" ruff count
    stat differs from the reviewer's static 25-file estimate — the "unchanged"
    outcome is count-independent; treated as ruff discovery semantics, not a gate.)
- state: 0.2.1 DONE — all 5 tasks checked. Interpretation notes: WSL smoke must
  use the repo venv interpreter (distro python is 3.8; recorded for future gates).
  pipeline idle; blueprint agent next for any new scope (e.g. Steam
  libraryfolders.vdf mount detection — companion to the storage rework, post-0.2.1
  backlog).
