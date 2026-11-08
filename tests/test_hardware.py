"""Offline tests for the Windows hardware audit adapter.

The committed dxdiag report is parsed directly; audit/load tests fake dxdiag
(no process is ever spawned) and fake psutil's disk usage, so the suite is
Windows-independent and never touches the real ``C:`` drive or ``generated/``.
"""

from __future__ import annotations

import inspect
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from keniran.adapters import hardware
from keniran.adapters.hardware import windows
from keniran.core.models import SystemSpec

FIXTURES = Path(__file__).parent / "fixtures"
DXDIAG_FIXTURE = FIXTURES / "dxdiag_sample.txt"
SAMPLE_TEXT = DXDIAG_FIXTURE.read_text(encoding="utf-8")

OLD_SPEC = SystemSpec(
    cpu_name="Old CPU",
    ram_gb=8.0,
    gpu_name="Old GPU",
    vram_gb=2.0,
    disk_free_gb=10.0,
    audited_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
)

TWO_GPU_TEXT = """\
------------------
System Information
------------------
              Processor: AMD Ryzen 5 5600G with Radeon Graphics (12 CPUs), ~3.9GHz
                 Memory: 16GB RAM

---------------
Display Devices
---------------
           Card name: NVIDIA GeForce GTX 1060 6GB
        Manufacturer: NVIDIA
     Dedicated Memory: 6144 MB
        Shared Memory: 8192 MB
           Card name: AMD Radeon(TM) Graphics
        Manufacturer: Advanced Micro Devices, Inc.
     Dedicated Memory: 512 MB
        Shared Memory: 8192 MB
"""


def _install_fake_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the platform check to Windows so these tests are host-independent."""
    monkeypatch.setattr(hardware.sys, "platform", "win32")


def _install_fake_dxdiag(monkeypatch: pytest.MonkeyPatch, report_text: str) -> list[Path]:
    """Replace the dxdiag invocation with one that writes *report_text*."""
    calls: list[Path] = []

    def fake_run(report_path: Path) -> None:
        calls.append(report_path)
        report_path.write_text(report_text, encoding="utf-8")

    monkeypatch.setattr(windows, "_run_dxdiag", fake_run)
    return calls


def _install_fake_disk(monkeypatch: pytest.MonkeyPatch, free_gb: float) -> None:
    """Replace the psutil disk lookup with a fixed free-space value."""
    monkeypatch.setattr(windows, "_disk_free_gb", lambda: free_gb)


def _completed(returncode: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["dxdiag"], returncode=returncode)


def test_parse_fixture_extracts_cpu_ram_gpu_and_vram() -> None:
    parsed = hardware.parse_dxdiag(SAMPLE_TEXT)

    assert parsed.cpu_name == "Intel(R) Core(TM) i7-9700K CPU"
    assert parsed.ram_gb == 16.0
    assert parsed.gpu_name == "NVIDIA GeForce RTX 3060"
    assert parsed.vram_gb == 12.0


def test_parse_strips_cpu_clock_and_core_count_suffix() -> None:
    parsed = hardware.parse_dxdiag(SAMPLE_TEXT)

    assert "3.60GHz" not in parsed.cpu_name
    assert "~3.6GHz" not in parsed.cpu_name
    assert "(8 CPUs)" not in parsed.cpu_name


def test_parse_prefers_gpu_with_highest_dedicated_memory() -> None:
    parsed = hardware.parse_dxdiag(TWO_GPU_TEXT)

    assert parsed.gpu_name == "NVIDIA GeForce GTX 1060 6GB"
    assert parsed.vram_gb == 6.0


def test_parse_missing_dedicated_memory_names_vram_field() -> None:
    text = "\n".join(
        line
        for line in SAMPLE_TEXT.splitlines()
        if not line.strip().startswith("Dedicated Memory:")
    )

    with pytest.raises(hardware.DxDiagParseError) as excinfo:
        hardware.parse_dxdiag(text)

    assert excinfo.value.missing_fields == ("vram_gb",)
    assert "vram_gb" in str(excinfo.value)


def test_parse_missing_all_hardware_sections_names_every_field() -> None:
    labels = ("Processor:", "Memory:", "Card name:", "Dedicated Memory:")
    text = "\n".join(
        line for line in SAMPLE_TEXT.splitlines() if not line.strip().startswith(labels)
    )

    with pytest.raises(hardware.DxDiagParseError) as excinfo:
        hardware.parse_dxdiag(text)

    assert set(excinfo.value.missing_fields) == {
        "cpu_name",
        "ram_gb",
        "gpu_name",
        "vram_gb",
    }
    for field in excinfo.value.missing_fields:
        assert field in str(excinfo.value)


def test_audit_writes_complete_validated_spec(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_windows(monkeypatch)
    _install_fake_dxdiag(monkeypatch, SAMPLE_TEXT)
    _install_fake_disk(monkeypatch, 148.25)
    path = tmp_path / "generated" / "system_spec.json"

    spec = hardware.audit(path=path)

    assert spec.cpu_name == "Intel(R) Core(TM) i7-9700K CPU"
    assert spec.ram_gb == 16.0
    assert spec.gpu_name == "NVIDIA GeForce RTX 3060"
    assert spec.vram_gb == 12.0
    assert spec.disk_free_gb == 148.25
    assert spec.audited_at.tzinfo is not None

    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {
        "cpu_name",
        "ram_gb",
        "gpu_name",
        "vram_gb",
        "disk_free_gb",
        "audited_at",
    }
    assert datetime.fromisoformat(payload["audited_at"]).tzinfo is not None
    assert SystemSpec.model_validate(payload) == spec


def test_load_reads_existing_cache_without_reauditing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_windows(monkeypatch)
    _install_fake_dxdiag(monkeypatch, SAMPLE_TEXT)
    _install_fake_disk(monkeypatch, 148.25)
    path = tmp_path / "generated" / "system_spec.json"
    audited = hardware.audit(path=path)

    def explode(report_path: Path) -> None:
        raise AssertionError("dxdiag must not run when the cache exists")

    monkeypatch.setattr(windows, "_run_dxdiag", explode)

    assert hardware.load(path=path) == audited


def test_load_without_cache_runs_an_audit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_fake_windows(monkeypatch)
    calls = _install_fake_dxdiag(monkeypatch, SAMPLE_TEXT)
    _install_fake_disk(monkeypatch, 148.25)
    path = tmp_path / "generated" / "system_spec.json"

    spec = hardware.load(path=path)

    assert len(calls) == 1
    assert path.is_file()
    assert spec.disk_free_gb == 148.25


def test_load_refresh_forces_reaudit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "generated" / "system_spec.json"
    hardware.save(OLD_SPEC, path=path)
    _install_fake_windows(monkeypatch)
    calls = _install_fake_dxdiag(monkeypatch, SAMPLE_TEXT)
    _install_fake_disk(monkeypatch, 148.25)

    refreshed = hardware.load(refresh=True, path=path)

    assert len(calls) == 1
    assert refreshed != OLD_SPEC
    assert refreshed.cpu_name == "Intel(R) Core(TM) i7-9700K CPU"
    assert hardware.load(path=path) == refreshed


def test_save_and_load_round_trip_all_fields(tmp_path: Path) -> None:
    spec = SystemSpec(
        cpu_name="Intel Core i5-2300",
        ram_gb=16.0,
        gpu_name="NVIDIA GeForce GTX 1060",
        vram_gb=6.0,
        disk_free_gb=148.2,
        audited_at=datetime(2026, 11, 7, 12, 30, 45, 123456, tzinfo=UTC),
    )
    path = tmp_path / "generated" / "system_spec.json"

    written = hardware.save(spec, path=path)

    assert written == path
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(payload["audited_at"]) == spec.audited_at
    assert payload["cpu_name"] is not None
    assert payload["ram_gb"] is not None
    assert payload["gpu_name"] is not None
    assert payload["vram_gb"] is not None
    assert payload["disk_free_gb"] is not None
    assert hardware.load(path=path) == spec


def test_fixture_parse_yields_all_five_fields_and_round_trips(tmp_path: Path) -> None:
    parsed = hardware.parse_dxdiag(SAMPLE_TEXT)
    spec = SystemSpec(
        cpu_name=parsed.cpu_name,
        ram_gb=parsed.ram_gb,
        gpu_name=parsed.gpu_name,
        vram_gb=parsed.vram_gb,
        disk_free_gb=148.2,
        audited_at=datetime(2026, 11, 7, 8, 15, tzinfo=UTC),
    )
    path = tmp_path / "generated" / "system_spec.json"

    hardware.save(spec, path=path)
    loaded = hardware.load(path=path)

    assert loaded.cpu_name
    assert loaded.ram_gb is not None
    assert loaded.gpu_name
    assert loaded.vram_gb is not None
    assert loaded.disk_free_gb is not None
    assert loaded == spec


def test_load_reads_cache_on_non_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "generated" / "system_spec.json"
    hardware.save(OLD_SPEC, path=path)
    monkeypatch.setattr(hardware.sys, "platform", "linux")

    assert hardware.load(path=path) == OLD_SPEC


def test_load_corrupt_cache_raises_named_cache_error(tmp_path: Path) -> None:
    path = tmp_path / "generated" / "system_spec.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(hardware.HardwareCacheError) as excinfo:
        hardware.load(path=path)

    assert str(path) in str(excinfo.value)


def test_audit_on_non_windows_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(hardware.sys, "platform", "linux")

    def explode(report_path: Path) -> None:
        raise AssertionError("dxdiag must not run on non-Windows platforms")

    monkeypatch.setattr(windows, "_run_dxdiag", explode)

    with pytest.raises(hardware.UnsupportedPlatformError) as excinfo:
        hardware.audit(path=tmp_path / "system_spec.json")

    assert "Windows" in str(excinfo.value)


def test_read_report_decodes_utf16_dxdiag_output(tmp_path: Path) -> None:
    path = tmp_path / "dxdiag.txt"
    path.write_bytes(SAMPLE_TEXT.encode("utf-16"))

    text = windows._read_report(path)

    assert "Card name: NVIDIA GeForce RTX 3060" in text
    assert hardware.parse_dxdiag(text).vram_gb == 12.0


def test_run_dxdiag_missing_executable_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def missing(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("dxdiag")

    monkeypatch.setattr(windows.subprocess, "run", missing)

    with pytest.raises(hardware.DxDiagError) as excinfo:
        windows._run_dxdiag(tmp_path / "dxdiag.txt")

    assert "not found" in str(excinfo.value)


def test_run_dxdiag_nonzero_exit_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(windows.subprocess, "run", lambda *args, **kwargs: _completed(1))

    with pytest.raises(hardware.DxDiagError) as excinfo:
        windows._run_dxdiag(tmp_path / "dxdiag.txt")

    assert "code 1" in str(excinfo.value)


def test_run_dxdiag_timeout_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def timeout(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd="dxdiag", timeout=windows.DXDIAG_TIMEOUT_SECONDS)

    monkeypatch.setattr(windows.subprocess, "run", timeout)

    with pytest.raises(hardware.DxDiagError) as excinfo:
        windows._run_dxdiag(tmp_path / "dxdiag.txt")

    assert "did not finish" in str(excinfo.value)


def test_run_dxdiag_without_output_file_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(windows.subprocess, "run", lambda *args, **kwargs: _completed(0))
    monkeypatch.setattr(windows, "DXDIAG_OUTPUT_WAIT_SECONDS", 0.0)

    with pytest.raises(hardware.DxDiagError) as excinfo:
        windows._run_dxdiag(tmp_path / "dxdiag.txt")

    assert "did not write" in str(excinfo.value)


def test_facade_reexports_backend_errors_and_types() -> None:
    assert hardware.HardwareAuditError is windows.HardwareAuditError
    assert hardware.UnsupportedPlatformError is windows.UnsupportedPlatformError
    assert hardware.DxDiagError is windows.DxDiagError
    assert hardware.DxDiagParseError is windows.DxDiagParseError
    assert hardware.HardwareCacheError is windows.HardwareCacheError
    assert hardware.DxDiagInfo is windows.DxDiagInfo


def test_facade_functions_keep_backend_signatures() -> None:
    for name in ("audit", "load", "save", "parse_dxdiag"):
        assert inspect.signature(getattr(hardware, name)) == inspect.signature(
            getattr(windows, name)
        )


def test_facade_audit_dispatches_to_windows_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = OLD_SPEC
    calls: list[Path] = []

    def fake_audit(*, path: Path) -> SystemSpec:
        calls.append(path)
        return expected

    monkeypatch.setattr(hardware.sys, "platform", "win32")
    monkeypatch.setattr(windows, "audit", fake_audit)
    path = tmp_path / "generated" / "system_spec.json"

    assert hardware.audit(path=path) == expected
    assert calls == [path]


def test_facade_audit_does_not_dispatch_on_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*, path: Path) -> SystemSpec:
        raise AssertionError("the Windows backend must not run on non-Windows")

    monkeypatch.setattr(hardware.sys, "platform", "linux")
    monkeypatch.setattr(windows, "audit", explode)

    with pytest.raises(hardware.UnsupportedPlatformError):
        hardware.audit()


def test_old_hardware_module_file_is_gone() -> None:
    package_dir = Path(hardware.__file__).resolve().parent

    assert package_dir.name == "hardware"
    assert (package_dir / "__init__.py").is_file()
    assert (package_dir / "windows.py").is_file()
    assert not (package_dir.parent / "hardware.py").exists()


def test_save_and_parse_stay_platform_independent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(hardware.sys, "platform", "linux")
    path = tmp_path / "generated" / "system_spec.json"

    assert hardware.save(OLD_SPEC, path=path) == path
    assert hardware.load(path=path) == OLD_SPEC
    assert hardware.parse_dxdiag(SAMPLE_TEXT).vram_gb == 12.0


def test_load_without_cache_on_non_windows_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(hardware.sys, "platform", "linux")

    with pytest.raises(hardware.UnsupportedPlatformError):
        hardware.load(path=tmp_path / "generated" / "system_spec.json")
