"""Linux hardware audit parsers: ``/proc``, ``lspci``, ``nvidia-smi``, vulkaninfo.

Implements the CPU/RAM half (LIN-001) and the GPU/VRAM half (LIN-002) of the
Linux backend described in ``.spec/units/0.2.0/linux-audit/spec.md``, following
the hardware audit design of ``plan/decisions.md`` §4 and the dxdiag
multi-card "best wins" approach of :mod:`keniran.adapters.hardware.windows`.
The parsers are pure functions over recorded text, so tests run against WSL
fixtures without reading ``/proc`` or spawning tools.

The honesty gate (``plan/decisions.md`` §2) applies: malformed or absent data
returns ``None`` instead of raising, and the caller degrades that field to
``unverified`` rather than fabricating a value.

**WSL ≠ native Linux caveat.** ``sys.platform`` is ``"linux"`` under WSL2 too,
so a spec audited inside WSL is cached as ``platform="linux"`` and reused by
native Linux runs of the same version — the two are *not* equivalent: WSL2
exposes the GPU through the paravirtualized ``/dev/dxg`` device (so ``lspci``
sees no discrete card and ``nvidia-smi`` works only with the WSL driver
stack), and ``.wslconfig`` can cap guest RAM, making ``/proc/meminfo``
under-report the physical machine. Treat a WSL-audited spec as a WSL spec.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol, cast

import psutil  # type: ignore[import-untyped]

from keniran.adapters.hardware import windows
from keniran.adapters.hardware.storage import Partition
from keniran.adapters.hardware.windows import (
    DEFAULT_SPEC_PATH,
    HardwareAuditError,
    UnsupportedPlatformError,
)
from keniran.core.models import SystemSpec

_WHITESPACE_RE: Final = re.compile(r"\s+")
_CLOCK_NOISE_RE: Final = re.compile(r"\s*@\s*\d+(?:\.\d+)?\s*(?:GHz|MHz)", re.IGNORECASE)
_PROC_MODEL_NAME_RE: Final = re.compile(r"^\s*model name\s*:\s*(.+?)\s*$")
_LSCPU_MODEL_NAME_RE: Final = re.compile(r"^\s*Model name\s*:\s*(.+?)\s*$", re.IGNORECASE)
_MEM_TOTAL_RE: Final = re.compile(r"^\s*MemTotal\s*:\s*(\d+)\s*kB\s*$")
_KB_PER_GB: Final = 1024.0 * 1024.0


def parse_proc_cpuinfo(text: str) -> str | None:
    """Extract the CPU model name from ``/proc/cpuinfo`` or ``lscpu`` text.

    Fallback ladder:

    1. ``/proc/cpuinfo``-style ``model name`` key (lowercase). The key repeats
       once per logical CPU on x86/x86_64; the first non-empty value wins.
    2. ``lscpu``-style ``Model name:`` line. This is the ARM safety valve: ARM
       ``/proc/cpuinfo`` has no ``model name`` key, while ``lscpu`` normally
       reports one.

    Clock decorations (``@ 3.60GHz``, ``@ 1.8MHz``) are stripped from the
    value; other vendor formatting (``(R)``, ``(TM)``, a trailing ``CPU``) is
    preserved for the fuzzy benchmark matcher. Returns ``None`` when neither
    rung yields a non-empty name, or when the text is malformed.
    """
    for line in text.splitlines():
        match = _PROC_MODEL_NAME_RE.match(line)
        if match is not None:
            name = _clean_model_name(match.group(1))
            if name:
                return name

    for line in text.splitlines():
        match = _LSCPU_MODEL_NAME_RE.match(line)
        if match is not None:
            name = _clean_model_name(match.group(1))
            if name:
                return name
    return None


def parse_proc_meminfo(text: str) -> float | None:
    """Extract total RAM in GB from ``/proc/meminfo`` text.

    Reads the ``MemTotal: <n> kB`` line (the unit Linux reports there),
    converts kB to GB (1024²), and rounds to two decimals. Returns ``None``
    when the line is absent, its value is not an integer number of kB, or the
    text is malformed.
    """
    for line in text.splitlines():
        match = _MEM_TOTAL_RE.match(line)
        if match is not None:
            try:
                return round(int(match.group(1)) / _KB_PER_GB, 2)
            except (OverflowError, ValueError):
                return None
    return None


def _clean_model_name(value: str) -> str:
    """Strip clock decorations and collapse whitespace in a raw model name."""
    without_clock = _CLOCK_NOISE_RE.sub(" ", value)
    return _WHITESPACE_RE.sub(" ", without_clock).strip()


# --- GPU parsing (LIN-002) ---------------------------------------------------

# ``lspci -mm`` class strings resolved from pci.ids, ranked dGPU-before-iGPU.
# On a hybrid setup the discrete card reports as "3D controller" (NVIDIA
# Optimus laptops) or as the desktop's "VGA compatible controller", while the
# integrated adapter surfaces as "Display controller"; see windows.py's
# multi-card "best wins" selection for the equivalent dxdiag logic.
_PCI_CLASS_RANKS: Final[dict[str, int]] = {
    "3d controller": 0,
    "class 0302": 0,  # Display controller subclass codes for unresolvable names
    "vga compatible controller": 1,
    "class 0300": 1,
    "display controller": 2,
    "class 0380": 2,
}

_QUOTED_FIELD_RE: Final = re.compile(r'"([^"]*)"')

# Bracketed sub-names in lspci output may be marketing names worth promoting
# (``GA102 [GeForce RTX 3080]``) or hexadecimal ``-nn`` identifiers to discard
# (``[10DE:2206]``); a bracket is promoted only when it contains real
# marketing vocabulary so the fuzzy PassMark matcher sees compatible words.
_MARKETING_TOKENS: Final = (
    "geforce",
    "gtx",
    "rtx",
    "gts",
    "quadro",
    "tesla",
    "titan",
    "radeon",
    "instinct",
    "firepro",
    "arc",
    "iris",
    "uhd",
    "graphics",
)

_BRACKET_RE: Final = re.compile(r"\[([^\[\]]+)\]")
_PCI_REV_RE: Final = re.compile(r"\(\s*rev\s+[^)]*\)", re.IGNORECASE)
_LITE_HASH_RATE_RE: Final = re.compile(r"\blite\s+hash\s+rate\b", re.IGNORECASE)

# ``nvidia-smi`` default report: ``<used>MiB / <total>MiB`` per GPU column.
_NVIDIA_SMI_MEMORY_RE: Final = re.compile(r"(\d+)\s*MiB\s*/\s*(\d+)\s*MiB")
_MIB_PER_GB: Final = 1024.0
_BYTES_PER_GB: Final = 1024.0**3

# VK_MEMORY_HEAP_DEVICE_LOCAL_BIT: the on-device heap backing VRAM, as
# opposed to the unflagged host-side heap which is just system RAM.
_DEVICE_LOCAL_BIT: Final = 0x1


def parse_lspci(text: str) -> str | None:
    """Extract the GPU model name from ``lspci -mm`` machine-readable text.

    Pure function over recorded text. Only VGA/3D/Display-class devices are
    considered; when several are present the best one wins by class
    precedence, dGPU before iGPU (``3D controller`` first, ``VGA compatible
    controller`` next, ``Display controller`` last), mirroring the dxdiag
    multi-card selection in windows.py. The raw ``lspci`` name is passed
    through :func:`_clean_linux_name` so codenames, revision tags, and
    ``[10DE:2206]``-style identifiers do not reach the fuzzy PassMark matcher.

    Returns ``None`` when no display-class device is found, when its name
    cleans to empty, or when the text is malformed.
    """
    best_rank: int | None = None
    best_name: str | None = None

    for line in text.splitlines():
        fields = _QUOTED_FIELD_RE.findall(line)
        if len(fields) < 3:
            continue
        rank = _PCI_CLASS_RANKS.get(fields[0].strip().casefold())
        if rank is None:
            continue
        name = _clean_linux_name(fields[2])
        if not name:
            continue
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best_name = name

    return best_name


def parse_nvidia_smi_vram(text: str) -> float | None:
    """Extract the total VRAM in GB from ``nvidia-smi`` text output.

    Reads the ``<used>MiB / <total>MiB`` memory column of the default report
    and converts the total MiB to GB (1024), rounded to two decimals. When
    several GPUs are listed the largest total wins, matching the dxdiag
    "best wins" approach. Returns ``None`` when no memory column is found or
    the text is malformed.
    """
    best_mib: int | None = None
    for match in _NVIDIA_SMI_MEMORY_RE.finditer(text):
        total_mib = int(match.group(2))
        if best_mib is None or total_mib > best_mib:
            best_mib = total_mib
    if best_mib is None:
        return None
    try:
        return round(best_mib / _MIB_PER_GB, 2)
    except (OverflowError, ValueError):
        return None


def parse_vulkaninfo(text: str) -> float | None:
    """Extract the device-local heap size in GB from ``vulkaninfo`` JSON.

    Parses the JSON report and, for every physical device, takes the largest
    ``memoryHeaps`` entry flagged with ``VK_MEMORY_HEAP_DEVICE_LOCAL_BIT``
    (the VRAM heap, not the host system-RAM heap). The largest device-local
    heap across devices wins, mirroring the dxdiag multi-card selection.
    Returns ``None`` when the JSON is malformed, the report has no devices,
    or no device exposes a device-local heap.
    """
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    vulkan = data.get("vulkan")
    if not isinstance(vulkan, dict):
        return None
    devices = vulkan.get("devices")
    if isinstance(devices, dict):
        candidates = list(devices.values())  # pre-1.2.155 keyed-by-"GPU0" form
    elif isinstance(devices, list):
        candidates = devices
    else:
        return None

    best_gb: float | None = None
    for device in candidates:
        if not isinstance(device, dict):
            continue
        memory = device.get("memory")
        if not isinstance(memory, dict):
            continue
        heaps = memory.get("memoryHeaps")
        if not isinstance(heaps, list):
            continue
        for heap in heaps:
            if not isinstance(heap, dict):
                continue
            flags = heap.get("flags")
            size = heap.get("size")
            if not isinstance(flags, int) or not isinstance(size, int):
                continue
            if not flags & _DEVICE_LOCAL_BIT:
                continue
            try:
                gb = round(size / _BYTES_PER_GB, 2)
            except (OverflowError, ValueError):
                continue
            if best_gb is None or gb > best_gb:
                best_gb = gb
    return best_gb


def _clean_linux_name(value: str) -> str:
    """Normalize a raw Linux GPU name to PassMark-compatible vocabulary.

    lspci names carry codename prefixes with the marketing name bracketed
    (``GA102 [GeForce RTX 3080]``) plus hexadecimal ``-nn`` identifier
    brackets (``[10DE:2206]``), while other Linux sources append revision
    tags (``(rev a1)``) and vendor suffixes such as ``Lite Hash Rate``.
    A bracket containing real marketing vocabulary is promoted to the name;
    remaining brackets, revision tags, and hash-rate suffixes are stripped,
    and whitespace is collapsed.
    """
    name = value.strip()
    for content in _BRACKET_RE.findall(name):
        folded = content.casefold()
        if any(token in folded for token in _MARKETING_TOKENS):
            name = content
            break
    else:
        name = _BRACKET_RE.sub(" ", name)
    name = _PCI_REV_RE.sub(" ", name)
    name = _LITE_HASH_RATE_RE.sub(" ", name)
    return _WHITESPACE_RE.sub(" ", name).strip()


# --- Audit orchestration (LIN-003) -------------------------------------------

LSPCI_EXECUTABLE: Final = "lspci"
NVIDIA_SMI_EXECUTABLE: Final = "nvidia-smi"
VULKANINFO_EXECUTABLE: Final = "vulkaninfo"
TOOL_TIMEOUT_SECONDS: Final = 30.0

PROC_CPUINFO: Final = Path("/proc/cpuinfo")
PROC_MEMINFO: Final = Path("/proc/meminfo")


class LinuxAuditError(HardwareAuditError):
    """The Linux audit produced an unusable spec (no CPU *and* no RAM found)."""


def _run_tool(argv: Sequence[str]) -> str | None:
    """Run *argv* and return stdout, or ``None`` on any tool failure.

    A missing executable, a non-zero exit, a timeout, or any OS error counts
    as "tool absent" and degrades to ``None`` — it must never raise. stdout
    text is handed to the pure parsers, which treat malformed content the
    same way.
    """
    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _read_proc(path: Path) -> str | None:
    """Return the text of a ``/proc`` file, or ``None`` when it is unreadable."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _psutil_total_ram_gb() -> float | None:
    """Return total RAM in GB from :mod:`psutil`, or ``None`` when it fails."""
    try:
        total_bytes = float(psutil.virtual_memory().total)
        return round(total_bytes / _BYTES_PER_GB, 2)
    except (OSError, ValueError, AttributeError):
        return None


def _disk_free_gb() -> float:
    """Return free space in GB on the Linux root filesystem.

    Unlike the CPU/RAM/GPU/VRAM fields there is no optional representation
    for disk space in :class:`SystemSpec`, so an unexpected psutil failure
    degrades to ``0.0`` rather than aborting the audit.
    """
    try:
        free_bytes = float(psutil.disk_usage("/").free)
        return round(free_bytes / _BYTES_PER_GB, 2)
    except (OSError, ValueError, AttributeError):
        return 0.0


def _gather_cpu_name() -> str | None:
    """CPU chain: ``/proc/cpuinfo`` first, ``lscpu`` as the fallback rung."""
    text = _read_proc(PROC_CPUINFO)
    if text is not None:
        name = parse_proc_cpuinfo(text)
        if name is not None:
            return name
    lscpu_text = _run_tool(("lscpu",))
    if lscpu_text is not None:
        return parse_proc_cpuinfo(lscpu_text)
    return None


def _gather_ram_gb() -> float | None:
    """RAM chain: ``/proc/meminfo`` first, :mod:`psutil` as the fallback rung."""
    text = _read_proc(PROC_MEMINFO)
    if text is not None:
        ram_gb = parse_proc_meminfo(text)
        if ram_gb is not None:
            return ram_gb
    return _psutil_total_ram_gb()


def _gather_gpu_name() -> str | None:
    """GPU chain: ``lspci -mm`` first, ``nvidia-smi`` as the fallback rung."""
    lspci_text = _run_tool((LSPCI_EXECUTABLE, "-mm"))
    if lspci_text is not None:
        name = parse_lspci(lspci_text)
        if name is not None:
            return name
    smi_text = _run_tool((NVIDIA_SMI_EXECUTABLE, "--query-gpu=name", "--format=csv,noheader"))
    if smi_text is not None:
        lines = smi_text.splitlines()
        if lines:
            name = _clean_linux_name(lines[0])
            if name:
                return name
    return None


def _gather_vram_gb() -> float | None:
    """VRAM chain: ``nvidia-smi`` first, ``vulkaninfo`` second, else ``None``."""
    smi_text = _run_tool((NVIDIA_SMI_EXECUTABLE,))
    if smi_text is not None:
        vram_gb = parse_nvidia_smi_vram(smi_text)
        if vram_gb is not None:
            return vram_gb
    vulkan_text = _run_tool((VULKANINFO_EXECUTABLE, "--summary"))
    if vulkan_text is not None:
        return parse_vulkaninfo(vulkan_text)
    return None


# --- Storage gatherer (LSTO-001) ---------------------------------------------

# Linux pseudo filesystems that must never reach the shared storage helper
# (``plan/decisions.md`` §4). ``tmpfs`` is sized like RAM and its inflated free
# space would fake a storage PASS; ``squashfs`` is read-only snap content; the
# rest carry no usable storage. ``fuseblk``/``ntfs`` data partitions are
# deliberately absent: low-end dual-boot boxes keep games on them.
_PSEUDO_FSTYPES: Final[frozenset[str]] = frozenset(
    {"tmpfs", "ramfs", "devtmpfs", "proc", "sysfs", "efivarfs", "squashfs", "overlay"}
)


class _RawLinuxPartition(Protocol):
    """Duck-typed ``psutil.disk_partitions`` entry consumed by the pure filter."""

    device: str
    mountpoint: str
    fstype: str
    opts: str


def filter_linux_partitions(
    raw_parts: Iterable[_RawLinuxPartition],
    free_gb_lookup: Callable[[str], float | None],
) -> tuple[list[Partition], frozenset[str]]:
    """Turn raw ``psutil`` partitions into Linux storage-helper candidates.

    Pure function with no I/O: every surviving mountpoint is measured through
    the injected *free_gb_lookup* (tests pass a dict lookup; the real caller
    injects :func:`psutil.disk_usage`). Linux-specific hygiene the Windows path
    never needed (``plan/decisions.md`` §4, unit 0.2.1/linux-storage):

    - Pseudo filesystems (:data:`_PSEUDO_FSTYPES`) are excluded before
      measuring and reported as the ``"pseudo"`` skipped kind, so ``tmpfs``
      free space and read-only ``squashfs`` snap packages can never be
      selected as "best".
    - Ext4 merged-usr and bind setups present one block device under several
      mountpoints; same-``device`` entries are collapsed to the mountpoint
      with the most free space (an unmeasurable mount ranks last, and the
      first entry wins a tie), so one filesystem cannot be counted twice.
    - WSL ``9p``/``drvfs`` mounts are not pseudo filesystems and deliberately
      stay in the result; the shared
      :func:`~keniran.adapters.hardware.storage.select_storage_free` helper
      classifies ``9p`` as a network skip.

    The honesty gate (``plan/decisions.md`` §2) applies: malformed entries and
    failed measurements degrade per field instead of raising — missing string
    fields become ``""``, a lookup that raises or returns a non-finite value
    yields ``free_gb=None``, and an entry without a usable mountpoint is
    dropped. Entries keep their first-appearance order.
    """
    best_by_key: dict[str, Partition] = {}
    skipped_kinds: set[str] = set()

    for raw in raw_parts:
        mountpoint = _raw_text(raw, "mountpoint")
        if not mountpoint:
            continue

        fstype = _raw_text(raw, "fstype")
        if fstype.casefold() in _PSEUDO_FSTYPES:
            skipped_kinds.add("pseudo")
            continue

        partition = Partition(
            mountpoint=mountpoint,
            fstype=fstype,
            opts=_split_opts(_raw_text(raw, "opts")),
            free_gb=_lookup_free_gb(free_gb_lookup, mountpoint),
        )
        # An unreadable device must not collapse unrelated mounts, so fall
        # back to the mountpoint itself as the dedupe key.
        key = _raw_text(raw, "device") or mountpoint
        incumbent = best_by_key.get(key)
        if incumbent is None or _free_rank(partition.free_gb) > _free_rank(incumbent.free_gb):
            best_by_key[key] = partition

    return list(best_by_key.values()), frozenset(skipped_kinds)


def _collect_partitions() -> list[Partition]:
    """Measure local ``psutil`` partitions and apply the Linux mount hygiene.

    Mirrors :func:`keniran.adapters.hardware.windows._collect_partitions`:
    ``psutil.disk_partitions(all=False)`` feeds the pure
    :func:`filter_linux_partitions`, which drops pseudo filesystems and
    collapses same-device mounts; free space is measured lazily per surviving
    mountpoint through ``psutil.disk_usage``. A mount that cannot be measured
    stays in the list with ``free_gb=None`` so the shared helper can still see
    it but never picks it as "best".
    """
    measured: dict[str, float | None] = {}

    def free_gb_lookup(mountpoint: str) -> float | None:
        if mountpoint not in measured:
            measured[mountpoint] = _measure_free_gb(mountpoint)
        return measured[mountpoint]

    partitions, _skipped = filter_linux_partitions(
        psutil.disk_partitions(all=False), free_gb_lookup
    )
    return partitions


def _measure_free_gb(mountpoint: str) -> float | None:
    """Return free space in GB on *mountpoint*, or ``None`` when unmeasurable."""
    try:
        free_bytes = float(psutil.disk_usage(mountpoint).free)
    except (OSError, ValueError, AttributeError):
        return None
    return round(free_bytes / _BYTES_PER_GB, 2)


def _raw_text(raw: object, field: str) -> str:
    """Return a raw partition string field, or ``""`` when it is malformed."""
    value = getattr(raw, field, "")
    return value if isinstance(value, str) else ""


def _split_opts(raw_opts: str) -> tuple[str, ...]:
    """Split psutil's comma-joined ``opts`` string into a flag tuple."""
    return tuple(flag for flag in raw_opts.split(",") if flag)


def _lookup_free_gb(
    free_gb_lookup: Callable[[str], float | None],
    mountpoint: str,
) -> float | None:
    """Measure *mountpoint* through the injected lookup, degrading to ``None``.

    An exception (unmounted mid-audit, permission error, a lookup with no
    entry) or a non-numeric/non-finite return is "cannot measure" — the
    honesty gate must never propagate either.
    """
    try:
        value = free_gb_lookup(mountpoint)
    except Exception:  # the honesty gate must never propagate lookup failures
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return float(value)


def _free_rank(free_gb: float | None) -> float:
    """Rank measured free space for dedupe; unmeasurable mounts rank last."""
    return free_gb if free_gb is not None else float("-inf")


def audit(*, path: Path = DEFAULT_SPEC_PATH) -> SystemSpec:
    """Run the Linux audit chains, persist the result, and return it.

    Builds a :class:`~keniran.core.models.SystemSpec` from the fallback
    chains — CPU ``/proc`` → ``lscpu``, RAM ``/proc`` → ``psutil``, GPU
    ``lspci`` → ``nvidia-smi``, VRAM ``nvidia-smi`` → ``vulkaninfo`` →
    ``None`` — stamps it with ``sys.platform`` and writes it through the
    shared :func:`keniran.adapters.hardware.windows.save`. Missing tools,
    non-zero exits, and malformed output each degrade only their own field
    to ``None``; the audit raises no :class:`HardwareAuditError` for tool
    absence. Only a truly empty spec (no CPU **and** no RAM) fails, via
    :class:`LinuxAuditError`. A non-POSIX host (real Windows, or a test host
    merely pretending to be Linux) has neither ``/proc`` nor the tooling, so
    it raises :class:`UnsupportedPlatformError` up front.
    """
    if os.name != "posix":
        msg = (
            f"the linux hardware audit requires a POSIX host (native Linux or WSL), "
            f"not {os.name} (Windows-only tooling such as dxdiag is unavailable there)"
        )
        raise UnsupportedPlatformError(msg)

    cpu_name = _gather_cpu_name()
    ram_gb = _gather_ram_gb()
    if cpu_name is None and ram_gb is None:
        msg = "linux audit found neither CPU nor RAM information; spec is empty"
        raise LinuxAuditError(msg)

    # The honesty gate degrades each field independently, so a partially
    # degraded spec (e.g. CPU/RAM present but the GPU chain broken) reaches
    # the required-field pydantic validation below and fails there with a
    # ValidationError, never a HardwareAuditError.
    spec = SystemSpec(
        platform=sys.platform,
        cpu_name=cast(str, cpu_name),
        ram_gb=cast(float, ram_gb),
        gpu_name=cast(str, _gather_gpu_name()),
        vram_gb=_gather_vram_gb(),
        disk_free_gb=_disk_free_gb(),
        audited_at=datetime.now(UTC),
    )
    save(spec, path=path)
    return spec


def load(*, refresh: bool = False, path: Path = DEFAULT_SPEC_PATH) -> SystemSpec:
    """Return the cached audit, running a fresh Linux audit only when needed.

    Mirrors :func:`keniran.adapters.hardware.windows.load`: the cache is read
    through the shared reader (which re-audits on a ``platform`` mismatch or
    a legacy cache without the key), and ``refresh=True`` always re-audits.
    """
    if not refresh:
        cached = windows._read_cache(path)
        if cached is not None:
            return cached
    return audit(path=path)


def save(spec: SystemSpec, *, path: Path = DEFAULT_SPEC_PATH) -> Path:
    """Persist *spec* atomically via the shared Windows-backend writer."""
    return windows.save(spec, path=path)
