"""Linux hardware audit parsers: ``/proc/cpuinfo`` and ``/proc/meminfo``.

Implements the CPU/RAM half of the Linux backend described in
``.spec/units/0.2.0/linux-audit/spec.md``, following the hardware audit design of
``plan/decisions.md`` §4. The parsers are pure functions over recorded text, so
tests run against WSL fixtures without reading ``/proc`` or spawning tools.

The honesty gate (``plan/decisions.md`` §2) applies: malformed or absent data
returns ``None`` instead of raising, and the caller degrades that field to
``unverified`` rather than fabricating a value.
"""

from __future__ import annotations

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
