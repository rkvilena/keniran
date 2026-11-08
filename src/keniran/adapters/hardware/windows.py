"""Windows hardware audit: dxdiag report parsing plus psutil free-disk space.

Implements section 4 of ``plan/decisions.md``: run ``dxdiag /t`` once, parse the
CPU, RAM, GPU, and dedicated VRAM facts from the report text, record free space
on the system drive via :mod:`psutil`, and persist the validated
:class:`~keniran.core.models.SystemSpec` to ``generated/system_spec.json``.
Later runs reuse that cache unless ``refresh=True`` (the CLI's
``--refresh-spec``).

The report parser is a pure function (:func:`parse_dxdiag`) so tests run
against a recorded report without spawning dxdiag or touching a real disk.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import psutil  # type: ignore[import-untyped]
from pydantic import ValidationError

from keniran.core.models import SystemSpec

GENERATED_DIR: Final = Path("generated")
DEFAULT_SPEC_PATH: Final = GENERATED_DIR / "system_spec.json"

DXDIAG_EXECUTABLE: Final = "dxdiag"
DXDIAG_TIMEOUT_SECONDS: Final = 120.0
DXDIAG_OUTPUT_WAIT_SECONDS: Final = 15.0
DXDIAG_POLL_SECONDS: Final = 0.1

_WHITESPACE_RE: Final = re.compile(r"\s+")
_CPU_AT_CLOCK_RE: Final = re.compile(r"\s*@\s*\d+(?:\.\d+)?\s*GHz", re.IGNORECASE)
_CPU_CORES_SUFFIX_RE: Final = re.compile(
    r"\s*\(\d+\s+CPUs?\)(?:,\s*~?\s*\d+(?:\.\d+)?\s*GHz)?\s*$", re.IGNORECASE
)
_PROCESSOR_RE: Final = re.compile(r"^\s*Processor:\s*(.+?)\s*$", re.IGNORECASE)
_MEMORY_RE: Final = re.compile(r"^\s*Memory:\s*(\d+(?:\.\d+)?)\s*(MB|GB)\b", re.IGNORECASE)
_CARD_NAME_RE: Final = re.compile(r"^\s*Card name:\s*(.+?)\s*$", re.IGNORECASE)
_DEDICATED_MEMORY_RE: Final = re.compile(
    r"^\s*Dedicated Memory:\s*(\d+(?:\.\d+)?)\s*(MB|GB)\b", re.IGNORECASE
)


class HardwareAuditError(Exception):
    """Base class for hardware audit failures."""


class UnsupportedPlatformError(HardwareAuditError):
    """The audit cannot run on this operating system (v1 is Windows-only)."""


class DxDiagError(HardwareAuditError):
    """dxdiag could not run, timed out, or produced no output file."""


class DxDiagParseError(HardwareAuditError):
    """The report text lacks one or more required hardware facts.

    ``missing_fields`` names the :class:`SystemSpec` fields that could not be
    determined, e.g. ``("vram_gb",)`` when no ``Dedicated Memory`` line was
    found under any display device.
    """

    def __init__(self, missing_fields: Sequence[str]) -> None:
        self.missing_fields = tuple(missing_fields)
        fields = ", ".join(self.missing_fields)
        super().__init__(f"dxdiag report is missing required field(s): {fields}")


class HardwareCacheError(HardwareAuditError):
    """The persisted ``system_spec.json`` cache exists but cannot be used."""


@dataclass(frozen=True, slots=True)
class DxDiagInfo:
    """The four hardware facts dxdiag reports (disk space comes from psutil)."""

    cpu_name: str
    ram_gb: float
    gpu_name: str
    vram_gb: float


def parse_dxdiag(text: str) -> DxDiagInfo:
    """Extract CPU, RAM, GPU, and dedicated VRAM from a DxDiag report.

    Pure function over the report text. CPU clock/count suffixes are stripped
    from the ``Processor`` line, the first ``Memory: <n>MB RAM`` line supplies
    total RAM, and when several display devices are present the card with the
    highest ``Dedicated Memory`` value wins (iGPU + dGPU laptops).

    Raises :class:`DxDiagParseError` naming every missing field when the report
    has no usable CPU, RAM, GPU, or dedicated-memory section.
    """
    lines = text.splitlines()
    cpu_name = _parse_cpu_name(lines)
    ram_gb = _parse_ram_gb(lines)
    gpu_name, vram_gb = _parse_gpu(lines)

    if cpu_name is None or ram_gb is None or gpu_name is None or vram_gb is None:
        missing = tuple(
            field
            for field, value in (
                ("cpu_name", cpu_name),
                ("ram_gb", ram_gb),
                ("gpu_name", gpu_name),
                ("vram_gb", vram_gb),
            )
            if value is None
        )
        raise DxDiagParseError(missing)

    return DxDiagInfo(
        cpu_name=cpu_name,
        ram_gb=ram_gb,
        gpu_name=gpu_name,
        vram_gb=vram_gb,
    )


def audit(*, path: Path = DEFAULT_SPEC_PATH) -> SystemSpec:
    """Run a fresh dxdiag audit, persist the result, and return it.

    The report is written to a temporary file, parsed, combined with the
    system drive's free space, and atomically saved to *path*. Raises
    :class:`UnsupportedPlatformError` on non-Windows platforms and
    :class:`DxDiagError` when dxdiag cannot be executed.
    """
    if sys.platform != "win32":
        msg = f"hardware audit requires Windows: dxdiag is not available on {sys.platform}"
        raise UnsupportedPlatformError(msg)

    with tempfile.TemporaryDirectory(prefix="keniran-dxdiag-") as directory:
        report_path = Path(directory) / "dxdiag.txt"
        _run_dxdiag(report_path)
        report_text = _read_report(report_path)

    info = parse_dxdiag(report_text)
    spec = SystemSpec(
        platform=sys.platform,
        cpu_name=info.cpu_name,
        ram_gb=info.ram_gb,
        gpu_name=info.gpu_name,
        vram_gb=info.vram_gb,
        disk_free_gb=_disk_free_gb(),
        audited_at=datetime.now(UTC),
    )
    save(spec, path=path)
    return spec


def load(*, refresh: bool = False, path: Path = DEFAULT_SPEC_PATH) -> SystemSpec:
    """Return the cached audit, running a fresh one only when needed.

    ``refresh=False`` reads an existing ``system_spec.json`` only when it was
    written on the current platform; a missing, legacy, or other-platform cache
    triggers an audit. ``refresh=True`` always re-audits (``--refresh-spec``).
    """
    if not refresh:
        cached = _read_cache(path)
        if cached is not None:
            return cached
    return audit(path=path)


def save(spec: SystemSpec, *, path: Path = DEFAULT_SPEC_PATH) -> Path:
    """Persist *spec* atomically: write a sibling temp file, then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = spec.model_dump_json(indent=2) + "\n"

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return path


def _read_cache(path: Path) -> SystemSpec | None:
    """Return the validated cache, or ``None`` when it must be re-audited.

    A missing file, a cache written on another platform, and a legacy 0.1.0
    cache without the ``platform`` key all count as a miss, so :func:`load`
    migrates them by running a fresh audit.
    """
    try:
        payload = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as exc:
        msg = f"cannot read system spec cache at {path}: {exc}"
        raise HardwareCacheError(msg) from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        msg = f"invalid system spec cache at {path}: {exc}"
        raise HardwareCacheError(msg) from exc

    if not isinstance(data, dict):
        msg = f"invalid system spec cache at {path}: expected a JSON object"
        raise HardwareCacheError(msg)

    if data.get("platform") != sys.platform:
        return None

    try:
        return SystemSpec.model_validate(data)
    except ValidationError as exc:
        msg = f"invalid system spec cache at {path}: {exc}"
        raise HardwareCacheError(msg) from exc


def _run_dxdiag(report_path: Path) -> None:
    """Invoke ``dxdiag /t`` and wait until it has written *report_path*."""
    try:
        completed = subprocess.run(
            [DXDIAG_EXECUTABLE, "/t", str(report_path)],
            capture_output=True,
            text=True,
            timeout=DXDIAG_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        msg = "dxdiag executable was not found; the hardware audit requires Windows"
        raise DxDiagError(msg) from exc
    except subprocess.TimeoutExpired as exc:
        msg = f"dxdiag did not finish within {DXDIAG_TIMEOUT_SECONDS:.0f} seconds"
        raise DxDiagError(msg) from exc
    except OSError as exc:
        msg = f"failed to start dxdiag: {exc}"
        raise DxDiagError(msg) from exc

    if completed.returncode != 0:
        msg = f"dxdiag exited with code {completed.returncode}"
        raise DxDiagError(msg)
    _wait_for_report(report_path)


def _wait_for_report(report_path: Path) -> None:
    """Poll briefly for dxdiag's output file to appear and become non-empty."""
    deadline = time.monotonic() + DXDIAG_OUTPUT_WAIT_SECONDS
    while True:
        try:
            if report_path.stat().st_size > 0:
                return
        except OSError:
            pass

        if time.monotonic() >= deadline:
            msg = f"dxdiag did not write a report to {report_path}"
            raise DxDiagError(msg)
        time.sleep(DXDIAG_POLL_SECONDS)


def _read_report(report_path: Path) -> str:
    """Decode a dxdiag report, handling its UTF-16/UTF-8 BOM variants."""
    data = report_path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    if b"\x00" in data:
        return data.decode("utf-16-le", errors="replace")
    return data.decode("utf-8", errors="replace")


def _parse_cpu_name(lines: Sequence[str]) -> str | None:
    """Return the first ``Processor:`` value with clock/count noise removed."""
    for line in lines:
        match = _PROCESSOR_RE.match(line)
        if match is None:
            continue

        name = _CPU_AT_CLOCK_RE.sub(" ", match.group(1))
        name = _CPU_CORES_SUFFIX_RE.sub("", name)
        name = _WHITESPACE_RE.sub(" ", name).strip()
        if name:
            return name
    return None


def _parse_ram_gb(lines: Sequence[str]) -> float | None:
    """Return total system RAM in GB from the ``Memory: <n>MB RAM`` line."""
    for line in lines:
        match = _MEMORY_RE.match(line)
        if match is not None:
            return _to_gb(float(match.group(1)), match.group(2))
    return None


def _parse_gpu(lines: Sequence[str]) -> tuple[str | None, float | None]:
    """Return the display device with the highest dedicated memory.

    dxdiag lists one ``Card name`` / ``Dedicated Memory`` pair per display
    adapter, so an integrated GPU can appear next to a discrete card. The
    discrete card (larger dedicated memory) must win regardless of order.
    """
    cards: list[tuple[str, float | None]] = []
    name: str | None = None
    vram_gb: float | None = None

    for line in lines:
        card_match = _CARD_NAME_RE.match(line)
        if card_match is not None:
            if name is not None:
                cards.append((name, vram_gb))
            name = card_match.group(1).strip()
            vram_gb = None
            continue

        if name is not None:
            memory_match = _DEDICATED_MEMORY_RE.match(line)
            if memory_match is not None:
                vram_gb = _to_gb(float(memory_match.group(1)), memory_match.group(2))

    if name is not None:
        cards.append((name, vram_gb))
    if not cards:
        return None, None

    best_name, best_vram = max(
        cards,
        key=lambda card: card[1] if card[1] is not None else -1.0,
    )
    return best_name, best_vram


def _to_gb(value: float, unit: str) -> float:
    """Convert a dxdiag MB/GB size to GB, rounded to two decimals."""
    if unit.casefold() == "mb":
        return round(value / 1024.0, 2)
    return round(value, 2)


def _disk_free_gb() -> float:
    """Return free space in GB on the Windows system drive."""
    system_drive = os.environ.get("SYSTEMDRIVE") or "C:"
    root = system_drive.rstrip("\\/") + os.sep
    usage = psutil.disk_usage(root)
    free_bytes = float(usage.free)
    return round(free_bytes / (1024.0**3), 2)
