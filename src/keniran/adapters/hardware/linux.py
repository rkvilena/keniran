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
"""

from __future__ import annotations

import json
import re
from typing import Final

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
