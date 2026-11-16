# Tasks — 0.2.0/linux-audit

- [x] LIN-001: Linux CPU/RAM parsers (pure) + fixture-capture script
  status: done (commit 0a43fa7)
  depends: -
  files: src/keniran/adapters/hardware/linux.py, scripts/capture_linux_fixtures.sh, tests/fixtures/linux/proc_cpuinfo.txt, tests/fixtures/linux/proc_meminfo.txt, tests/test_hardware_linux.py
  pattern: tests/fixtures/dxdiag_sample.txt + parse_dxdiag pure-function pattern
  acceptance:
    Pure functions `parse_proc_cpuinfo(text) -> str | None` (model name, clock/@-noise
    stripped) and `parse_proc_meminfo(text) -> float | None` (MemTotal kB → GB, 2
    decimals) both: 1) return exact expected values on the WSL-recorded fixtures, 2)
    return None instead of raising on malformed/absent data, 3) handle `lscpu`-style
    output too if cpuinfo lacks `model name` (ARM safety valve — fallback ladder
    documented in docstring). The capture script records cpuinfo/meminfo into
    `tests/fixtures/linux/`. Tests run OS-agnostic (pure text in, no /proc access).
    acceptance commands:
      python -m pytest tests/test_hardware_linux.py -q
      python -m ruff check . && python -m mypy
  out-of-scope: GPU/VRAM parsing, subprocess running, audit assembly, name cleanup

- [x] LIN-002: GPU/VRAM parsers + Linux name-cleanup normalizer
  status: done (commit 81733e8)
  depends: LIN-001
  files: src/keniran/adapters/hardware/linux.py, tests/fixtures/linux/lspci_mm.txt, tests/fixtures/linux/nvidia_smi.txt, tests/fixtures/linux/vulkaninfo.json, tests/test_hardware_linux.py
  pattern: dxdiag multi-card "best wins" approach in windows.py
  acceptance:
    Pure parsers over recorded tool output: `parse_lspci(text) -> str | None` (VGA/3D/
    Display classes; multiple devices → same device picks by vendor-class precedence
    dGPU-before-iGPU), `_clean_linux_name()` strips `[codename]`/`(rev a1)`/"Lite Hash
    Rate"-style noise so the fuzzy matcher sees PassMark-compatible vocabulary;
    `parse_nvidia_smi_vram(text) -> float | None` and `parse_vulkaninfo(text) -> float
    | None` (device-local heap MiB → GB). Each falls through to None on missing/
    malformed input (honesty gate, no exceptions). Fixture tests bind exact recorded
    text to exact cleaned names/values.
    acceptance commands:
      python -m pytest tests/test_hardware_linux.py -q
      python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: running the tools (subprocess), audit assembly, `eglinfo` (implement
  only if nvidia-smi+lspci both miss a fixture case in LIN-003)

- [x] LIN-003: Linux audit assembly, dispatch wiring, WSL smoke
  status: done (commit 2420b9d)
  depends: LIN-002, SYS-003
  files: src/keniran/adapters/hardware/linux.py, src/keniran/adapters/hardware/__init__.py, tests/test_hardware_linux.py
  pattern: audit/load/save orchestration in windows.py
  acceptance:
    `run_audit()`: builds `SystemSpec` via the fallback chains (CPU: /proc→lscpu;
    RAM: /proc→psutil; GPU: lspci→nvidia-smi; VRAM: nvidia-smi→vulkaninfo→None),
    sets `platform="linux"`, writes through the shared `save()`. Every execution path:
    missing tool / non-zero exit / malformed output → that field degrades to None;
    the audit itself raises no subclass of `HardwareAuditError` for tool absence —
    only a truly empty spec (no CPU **and** no RAM) fails. Facade dispatch returns the
    linux backend on non-win32. New tests simulate each broken chain via monkeypatched
    subprocess runners (no real tools needed). Module docstring records the WSL≠native
    caveat (/dev/dxg, `.wslconfig` RAM cap). CLI-level smoke:
    `wsl -e bash -lc "cd <repo-on-/mnt/e> && python -m pytest -q"` green inside WSL.
    acceptance commands:
      python -m pytest tests/test_hardware_linux.py tests/test_hardware.py tests/test_check_game.py -q
      python -m pytest -q && python -m ruff format . && python -m ruff check . && python -m mypy
  out-of-scope: scoring changes, storage-mount logic (separate unit), native-Linux CI
