"""Offline tests for the Linux hardware audit parsers.

CPU/RAM parsing runs against committed WSL2-recorded ``/proc`` fixtures; no test
reads the host's ``/proc`` or invokes a shell tool, so the suite is OS-agnostic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from keniran.adapters.hardware import linux

FIXTURES = Path(__file__).parent / "fixtures" / "linux"
CPUINFO_TEXT = (FIXTURES / "proc_cpuinfo.txt").read_text(encoding="utf-8")
MEMINFO_TEXT = (FIXTURES / "proc_meminfo.txt").read_text(encoding="utf-8")

LSCPU_X86_TEXT = """\
Architecture:            x86_64
CPU op-mode(s):          32-bit, 64-bit
Byte Order:              Little Endian
CPU(s):                  8
On-line CPU(s) list:     0-7
Vendor ID:               GenuineIntel
Model name:              Intel(R) Core(TM) i7-9700K CPU @ 3.60GHz
Thread(s) per core:      1
Core(s) per socket:      8
Socket(s):               1
"""

LSCPU_ARM_TEXT = """\
Architecture:            aarch64
  CPU op-mode(s):        32-bit, 64-bit
  Byte Order:            Little Endian
CPU(s):                  8
On-line CPU(s) list:     0-7
Vendor ID:               ARM
  Model name:            Cortex-A72
    Model:               3
    Thread(s) per core:  1
    Core(s) per socket:  4
    Socket(s):           2
    Stepping:            r0p3
    CPU max MHz:         1800.0000
    CPU min MHz:         600.0000
    BogoMIPS:            108.00
"""

ARM_CPUINFO_TEXT = """\
processor\t: 0
BogoMIPS\t: 108.00
Features\t: fp asimd evtstrm crc32 cpuid
CPU implementer\t: 0x41
CPU architecture: 8
CPU variant\t: 0x0
CPU part\t: 0xd08
CPU revision\t: 3

Hardware\t: BCM2835
Revision\t: c03111
Serial\t\t: 10000000abcdef01
"""


def test_parse_proc_cpuinfo_returns_fixture_model_name() -> None:
    assert linux.parse_proc_cpuinfo(CPUINFO_TEXT) == "Intel(R) Core(TM) i7-9700K CPU"


def test_parse_proc_cpuinfo_strips_clock_decoration_only() -> None:
    name = linux.parse_proc_cpuinfo(CPUINFO_TEXT)

    assert name is not None
    assert "@" not in name
    assert "GHz" not in name
    assert "3.60" not in name
    # LIN-001 scope: vendor formatting survives; LIN-002 owns name cleanup.
    assert "(R)" in name
    assert "(TM)" in name
    assert name.endswith("CPU")


def test_parse_proc_meminfo_returns_fixture_total_gb() -> None:
    assert linux.parse_proc_meminfo(MEMINFO_TEXT) == 15.54


def test_parse_proc_meminfo_converts_kb_to_gb_and_rounds_to_two_decimals() -> None:
    assert linux.parse_proc_meminfo("MemTotal:       1048576 kB\n") == 1.0
    assert linux.parse_proc_meminfo("MemTotal:       1000000 kB\n") == 0.95


def test_parse_proc_cpuinfo_falls_back_to_lscpu_model_name() -> None:
    assert linux.parse_proc_cpuinfo(LSCPU_ARM_TEXT) == "Cortex-A72"


def test_parse_proc_cpuinfo_lscpu_fallback_strips_clock_decoration() -> None:
    assert linux.parse_proc_cpuinfo(LSCPU_X86_TEXT) == "Intel(R) Core(TM) i7-9700K CPU"


def test_parse_proc_cpuinfo_prefers_proc_model_name_over_lscpu() -> None:
    text = "model name\t: First CPU @ 2.00GHz\nModel name:              Second CPU @ 3.00GHz\n"

    assert linux.parse_proc_cpuinfo(text) == "First CPU"


def test_parse_proc_cpuinfo_skips_empty_model_name_and_continues() -> None:
    text = "model name\t:\nmodel name\t: Real CPU @ 1GHz\n"

    assert linux.parse_proc_cpuinfo(text) == "Real CPU"


def test_parse_proc_cpuinfo_returns_none_when_model_name_absent() -> None:
    assert linux.parse_proc_cpuinfo(ARM_CPUINFO_TEXT) is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n\n",
        "not a cpuinfo file at all",
        "model name\t:\n",
        "model name\t:   \n",
        "Model name:\n",
    ],
)
def test_parse_proc_cpuinfo_returns_none_for_malformed_text(text: str) -> None:
    assert linux.parse_proc_cpuinfo(text) is None


def test_parse_proc_meminfo_returns_none_when_mem_total_absent() -> None:
    text = """\
MemFree:         7325152 kB
MemAvailable:   12107840 kB
SwapTotal:       4194304 kB
"""

    assert linux.parse_proc_meminfo(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n\n",
        "not a meminfo file at all",
        "MemTotal: lots kB\n",
        "MemTotal: 16384 MB\n",
        "MemTotal: 16384\n",
        "MemTotal:\n",
        "MemTotal: -16384 kB\n",
        "MemTotal: " + "9" * 400 + " kB\n",
        "MemTotal: " + "9" * 5000 + " kB\n",
    ],
)
def test_parse_proc_meminfo_returns_none_for_malformed_text(text: str) -> None:
    assert linux.parse_proc_meminfo(text) is None


@pytest.mark.parametrize("text", ["\x00\x01\x02", "💥", "= : ; ,", "model name"])
def test_parsers_do_not_raise_on_hostile_text(text: str) -> None:
    assert linux.parse_proc_cpuinfo(text) is None
    assert linux.parse_proc_meminfo(text) is None
