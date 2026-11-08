"""Offline tests for the Linux hardware audit adapter.

Every execution path is simulated with monkeypatched subprocess runners and
temp ``/proc``-style files, so the suite runs on any host (this dev host is
Windows) without spawning lspci, nvidia-smi, or vulkaninfo and without a real
``/proc``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from keniran.adapters import hardware
from keniran.adapters.hardware import linux
from keniran.adapters.hardware.linux import (
    _gather_cpu_name,
    _gather_gpu_name,
    _gather_ram_gb,
    _gather_vram_gb,
)
from keniran.core.models import SystemSpec

CPUINFO_TEXT = "processor\t: 0\nmodel name\t: Intel(R) Core(TM) i7-9700K CPU @ 3.60GHz\n"
LSCPU_TEXT = "Architecture: x86_64\nModel name: AMD Ryzen 7 5800X\n"
MEMINFO_TEXT = "MemTotal:       16777216 kB\nMemFree:         8388608 kB\n"

# ``lspci -mm`` fields as consumed by parse_lspci: class, then free-form
# fields; the GPU name field carries the bracketed marketing sub-name.
LSPCI_TEXT = '"VGA compatible controller" "NVIDIA Corporation" "GA102 [GeForce RTX 3080]"'
NVIDIA_SMI_NAME_TEXT = "NVIDIA GeForce RTX 3080\n"
NVIDIA_SMI_TEXT = (
    "+-----------------------------------------------------------------------------+\n"
    "|   0  Tesla V100         On   00000000:00:1E.0 Off |\n"
    "| 30%   50C    P0    60W / 300W |   6144MiB /  8192MiB |\n"
    "+-----------------------------------------------------------------------------+\n"
)
VULKANINFO_JSON = json.dumps(
    {
        "vulkan": {
            "devices": [
                {
                    "memory": {
                        "memoryHeaps": [
                            {"flags": 0, "size": 16 * 1024**3},
                            {"flags": 0x1, "size": 8589934592},
                        ]
                    }
                }
            ]
        }
    }
)

NONEXISTENT = Path("Z:") / "nonexistent" / "proc" / "cpuinfo"


def _proc_file(tmp_path: Path, name: str, text: str | None) -> Path:
    """Return a path holding *text*, or a guaranteed-missing path."""
    path = tmp_path / name
    if text is not None:
        path.write_text(text, encoding="utf-8")
    return path


def _install_runner(
    monkeypatch: pytest.MonkeyPatch, outputs: dict[tuple[str, ...], str | Exception]
) -> list[tuple[str, ...]]:
    """Replace subprocess.run with a table-driven fake; return recorded calls."""
    calls: list[tuple[str, ...]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        key = tuple(argv)
        calls.append(key)
        outcome = outputs.get(key)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:  # non-zero exit with empty output
            return subprocess.CompletedProcess(argv, 1)
        return subprocess.CompletedProcess(argv, 0, stdout=outcome, stderr="")

    monkeypatch.setattr(linux.subprocess, "run", fake_run)
    return calls


def _install_posix_host(monkeypatch: pytest.MonkeyPatch, free_gb: float = 148.25) -> None:
    """Make the linux backend believe it runs on a POSIX host; fake the disk."""
    monkeypatch.setattr(linux, "os", types.SimpleNamespace(name="posix"))
    monkeypatch.setattr(linux.sys, "platform", "linux")
    monkeypatch.setattr(linux, "_disk_free_gb", lambda: free_gb)


# --- CPU chain: /proc -> lscpu ------------------------------------------------


def test_cpu_chain_reads_proc_cpuinfo(tmp_path: Path) -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(linux, "PROC_CPUINFO", _proc_file(tmp_path, "cpuinfo", CPUINFO_TEXT))

    assert _gather_cpu_name() == "Intel(R) Core(TM) i7-9700K CPU"


def test_cpu_chain_falls_back_to_lscpu_when_proc_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux, "PROC_CPUINFO", _proc_file(tmp_path, "cpuinfo", None))
    _install_runner(monkeypatch, {("lscpu",): LSCPU_TEXT})

    assert _gather_cpu_name() == "AMD Ryzen 7 5800X"


def test_cpu_chain_falls_back_to_lscpu_when_proc_text_is_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux, "PROC_CPUINFO", _proc_file(tmp_path, "cpuinfo", "garbage\n"))
    _install_runner(monkeypatch, {("lscpu",): LSCPU_TEXT})

    assert _gather_cpu_name() == "AMD Ryzen 7 5800X"


def test_cpu_chain_degrades_to_none_when_lscpu_tool_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux, "PROC_CPUINFO", _proc_file(tmp_path, "cpuinfo", None))
    _install_runner(monkeypatch, {("lscpu",): FileNotFoundError("lscpu")})

    assert _gather_cpu_name() is None


def test_cpu_chain_degrades_to_none_when_lscpu_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux, "PROC_CPUINFO", _proc_file(tmp_path, "cpuinfo", None))
    _install_runner(monkeypatch, {("lscpu",): None})

    assert _gather_cpu_name() is None


def test_cpu_chain_degrades_to_none_when_lscpu_output_is_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux, "PROC_CPUINFO", _proc_file(tmp_path, "cpuinfo", None))
    _install_runner(monkeypatch, {("lscpu",): "not a cpu report\n"})

    assert _gather_cpu_name() is None


# --- RAM chain: /proc -> psutil ------------------------------------------------


def test_ram_chain_reads_proc_meminfo(tmp_path: Path) -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(linux, "PROC_MEMINFO", _proc_file(tmp_path, "meminfo", MEMINFO_TEXT))

    assert _gather_ram_gb() == 16.0


def test_ram_chain_falls_back_to_psutil_when_proc_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux, "PROC_MEMINFO", _proc_file(tmp_path, "meminfo", None))
    monkeypatch.setattr(linux, "_psutil_total_ram_gb", lambda: 32.0)

    assert _gather_ram_gb() == 32.0


def test_ram_chain_degrades_to_none_when_psutil_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux, "PROC_MEMINFO", _proc_file(tmp_path, "meminfo", None))

    def explode() -> object:
        raise OSError("psutil exploded")

    monkeypatch.setattr(linux.psutil, "virtual_memory", explode)

    assert _gather_ram_gb() is None


def test_ram_chain_degrades_to_none_when_proc_and_psutil_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux, "PROC_MEMINFO", _proc_file(tmp_path, "meminfo", "garbage"))
    monkeypatch.setattr(linux, "_psutil_total_ram_gb", lambda: None)

    assert _gather_ram_gb() is None


# --- GPU chain: lspci -> nvidia-smi --------------------------------------------


def test_gpu_chain_reads_lspci_and_promotes_marketing_bracket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_runner(monkeypatch, {("lspci", "-mm"): LSPCI_TEXT})

    assert _gather_gpu_name() == "GeForce RTX 3080"
    assert calls == [("lspci", "-mm")]


def test_gpu_chain_falls_back_to_nvidia_smi_when_lspci_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_runner(
        monkeypatch,
        {
            ("lspci", "-mm"): FileNotFoundError("lspci"),
            ("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"): NVIDIA_SMI_NAME_TEXT,
        },
    )

    assert _gather_gpu_name() == "NVIDIA GeForce RTX 3080"
    assert calls == [
        ("lspci", "-mm"),
        ("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"),
    ]


def test_gpu_chain_falls_back_to_nvidia_smi_when_lspci_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_runner(
        monkeypatch,
        {
            ("lspci", "-mm"): "00:00.0 garbage line\n",
            ("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"): NVIDIA_SMI_NAME_TEXT,
        },
    )

    assert _gather_gpu_name() == "NVIDIA GeForce RTX 3080"


def test_gpu_chain_degrades_to_none_when_both_tools_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_runner(
        monkeypatch,
        {
            ("lspci", "-mm"): FileNotFoundError("lspci"),
            ("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"): FileNotFoundError(
                "nvidia-smi"
            ),
        },
    )

    assert _gather_gpu_name() is None


def test_gpu_chain_degrades_to_none_when_nvidia_smi_output_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_runner(
        monkeypatch,
        {
            ("lspci", "-mm"): FileNotFoundError("lspci"),
            ("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"): "   \n",
        },
    )

    assert _gather_gpu_name() is None


# --- VRAM chain: nvidia-smi -> vulkaninfo -> None -------------------------------


def test_vram_chain_reads_nvidia_smi(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_runner(monkeypatch, {("nvidia-smi",): NVIDIA_SMI_TEXT})

    assert _gather_vram_gb() == 8.0


def test_vram_chain_falls_back_to_vulkaninfo(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_runner(
        monkeypatch,
        {
            ("nvidia-smi",): FileNotFoundError("nvidia-smi"),
            ("vulkaninfo", "--summary"): VULKANINFO_JSON,
        },
    )

    assert _gather_vram_gb() == 8.0  # heap sizes are BYTES (vulkaninfo semantics)
    assert calls == [("nvidia-smi",), ("vulkaninfo", "--summary")]


def test_vram_chain_degrades_to_none_when_both_tools_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_runner(
        monkeypatch,
        {
            ("nvidia-smi",): FileNotFoundError("nvidia-smi"),
            ("vulkaninfo", "--summary"): FileNotFoundError("vulkaninfo"),
        },
    )

    assert _gather_vram_gb() is None


def test_vram_chain_degrades_to_none_when_vulkaninfo_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_runner(
        monkeypatch,
        {
            ("nvidia-smi",): None,
            ("vulkaninfo", "--summary"): "{not json",
        },
    )

    assert _gather_vram_gb() is None


# --- audit orchestration --------------------------------------------------------


def _install_healthy_chains(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Wire a fully healthy Linux environment through temp files and fakes."""
    _install_posix_host(monkeypatch)
    monkeypatch.setattr(linux, "PROC_CPUINFO", _proc_file(tmp_path, "cpuinfo", CPUINFO_TEXT))
    monkeypatch.setattr(linux, "PROC_MEMINFO", _proc_file(tmp_path, "meminfo", MEMINFO_TEXT))
    _install_runner(
        monkeypatch,
        {
            ("lspci", "-mm"): LSPCI_TEXT,
            ("nvidia-smi",): NVIDIA_SMI_TEXT,
            ("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"): NVIDIA_SMI_NAME_TEXT,
            ("vulkaninfo", "--summary"): VULKANINFO_JSON,
        },
    )


def test_audit_builds_spec_from_healthy_chains_and_saves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_healthy_chains(tmp_path, monkeypatch)
    path = tmp_path / "generated" / "system_spec.json"

    spec = linux.audit(path=path)

    assert spec.platform == "linux"
    assert spec.cpu_name == "Intel(R) Core(TM) i7-9700K CPU"
    assert spec.ram_gb == 16.0
    assert spec.gpu_name == "GeForce RTX 3080"
    assert spec.vram_gb == 8.0
    assert spec.disk_free_gb == 148.25
    assert spec.audited_at.tzinfo is not None

    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["platform"] == "linux"
    assert datetime.fromisoformat(payload["audited_at"]).tzinfo is not None


def test_audit_reuses_shared_atomic_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_healthy_chains(tmp_path, monkeypatch)
    path = tmp_path / "generated" / "system_spec.json"

    written = linux.save(linux.audit(path=path).model_copy(), path=tmp_path / "other" / "spec.json")

    assert written == tmp_path / "other" / "spec.json"
    assert (tmp_path / "other" / "spec.json").is_file()


def test_audit_degrades_vram_to_none_when_vram_chain_breaks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_healthy_chains(tmp_path, monkeypatch)
    # Re-install runners with both VRAM sources broken.
    _install_runner(
        monkeypatch,
        {
            ("nvidia-smi",): FileNotFoundError("nvidia-smi"),
            ("vulkaninfo", "--summary"): FileNotFoundError("vulkaninfo"),
            ("lspci", "-mm"): LSPCI_TEXT,
            ("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"): NVIDIA_SMI_NAME_TEXT,
        },
    )
    path = tmp_path / "generated" / "system_spec.json"

    spec = linux.audit(path=path)

    assert spec.vram_gb is None
    assert spec.gpu_name == "GeForce RTX 3080"


def test_audit_with_empty_spec_raises_linux_audit_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_posix_host(monkeypatch)
    monkeypatch.setattr(linux, "PROC_CPUINFO", NONEXISTENT)
    monkeypatch.setattr(linux, "PROC_MEMINFO", NONEXISTENT)
    monkeypatch.setattr(linux, "_psutil_total_ram_gb", lambda: None)
    _install_runner(
        monkeypatch,
        {
            ("lscpu",): FileNotFoundError("lscpu"),
            ("lspci", "-mm"): FileNotFoundError("lspci"),
            ("nvidia-smi",): FileNotFoundError("nvidia-smi"),
            ("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"): FileNotFoundError(
                "nvidia-smi"
            ),
        },
    )

    with pytest.raises(linux.LinuxAuditError) as excinfo:
        linux.audit(path=tmp_path / "spec.json")

    assert isinstance(excinfo.value, hardware.HardwareAuditError)
    assert "CPU" in str(excinfo.value) and "RAM" in str(excinfo.value)
    assert not (tmp_path / "spec.json").exists()


def test_audit_without_vram_tools_does_not_raise_hardware_audit_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tool absence degrades fields; only the empty CPU+RAM spec may raise."""
    _install_healthy_chains(tmp_path, monkeypatch)
    _install_runner(
        monkeypatch,
        {
            ("lspci", "-mm"): FileNotFoundError("lspci"),
            ("nvidia-smi",): FileNotFoundError("nvidia-smi"),
            ("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"): FileNotFoundError(
                "nvidia-smi"
            ),
            ("vulkaninfo", "--summary"): FileNotFoundError("vulkaninfo"),
        },
    )

    # GPU degraded to None (chain fully broken): SystemSpec requires a
    # gpu_name, so the audit surfaces pydantic's ValidationError — never a
    # HardwareAuditError for tool absence.
    with pytest.raises(ValidationError):
        linux.audit(path=tmp_path / "spec.json")


def test_audit_on_non_posix_host_raises_unsupported_platform() -> None:
    # This dev host is Windows: os.name is "nt" and the linux backend must
    # refuse to run rather than probe for /proc or Linux tooling.
    if sys.platform != "win32":
        pytest.skip("dev-host guard test requires the Windows host")

    with pytest.raises(hardware.UnsupportedPlatformError) as excinfo:
        linux.audit(path=Path("unused.json"))

    assert "POSIX" in str(excinfo.value)


# --- facade dispatch -------------------------------------------------------------


def test_facade_audit_dispatches_to_linux_backend_on_non_win32(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected_calls: list[Path] = []

    def fake_audit(*, path: Path) -> object:
        expected_calls.append(path)
        return "spec"

    monkeypatch.setattr(hardware.sys, "platform", "linux")
    monkeypatch.setattr(linux, "audit", fake_audit)

    assert hardware.audit(path=tmp_path / "spec.json") == "spec"
    assert expected_calls == [tmp_path / "spec.json"]


def test_facade_audit_dispatches_to_windows_backend_on_win32(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Path] = []

    def fake_windows_audit(*, path: Path) -> object:
        calls.append(path)
        return "spec"

    monkeypatch.setattr(hardware.sys, "platform", "win32")
    monkeypatch.setattr(hardware.windows, "audit", fake_windows_audit)

    assert hardware.audit(path=tmp_path / "spec.json") == "spec"
    assert calls == [tmp_path / "spec.json"]


def test_facade_load_dispatches_to_linux_backend_on_non_win32(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[bool] = []

    def fake_load(*, refresh: bool, path: Path) -> object:
        calls.append(refresh)
        return "spec"

    monkeypatch.setattr(hardware.sys, "platform", "linux")
    monkeypatch.setattr(linux, "load", fake_load)

    assert hardware.load(refresh=True, path=tmp_path / "spec.json") == "spec"
    assert calls == [True]


def test_linux_load_returns_matching_platform_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "generated" / "system_spec.json"
    spec = SystemSpec(
        platform="linux",
        cpu_name="AMD Ryzen 7 5800X",
        ram_gb=16.0,
        gpu_name="GeForce RTX 3080",
        vram_gb=8.0,
        disk_free_gb=148.25,
        audited_at=datetime(2026, 11, 8, 12, 0, tzinfo=UTC),
    )
    written = linux.save(spec, path=path)
    assert written == path
    monkeypatch.setattr(linux.sys, "platform", "linux")

    assert linux.load(path=path) == spec
