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


# --- LIN-002: GPU/VRAM parsers -----------------------------------------------

LSPCI_MM_TEXT = (FIXTURES / "lspci_mm.txt").read_text(encoding="utf-8")
NVIDIA_SMI_TEXT = (FIXTURES / "nvidia_smi.txt").read_text(encoding="utf-8")
VULKANINFO_TEXT = (FIXTURES / "vulkaninfo.json").read_text(encoding="utf-8")


# Inline ``lspci -mm`` dumps are built through this helper because real recorded
# lines exceed the 100-column limit; the rendered text is identical to what
# ``lspci -mm`` emits on the wire (``slot "class" "vendor" "device"
# "subvendor" "subdevice"``, no bare flags — ``(rev a1)`` only ever appears
# inside the quoted device field).
def _lspci_mm_line(slot: str, klass: str, vendor: str, device: str) -> str:
    return f'{slot} "{klass}" "{vendor}" "{device}" "ASUSTeK Computer Inc." "Device 8867"'


NVIDIA_VENDOR = "NVIDIA Corporation"
INTEL_VENDOR = "Intel Corporation"
RTX_3080 = "GA102 [GeForce RTX 3080]"
UHD_730 = "Alder Lake-S GT1 [UHD Graphics 730]"

# Recorded iGPU-first order: the integrated Intel adapter appears before the
# discrete NVIDIA card, so class precedence (not line order) must pick the dGPU.
LSPCI_LAPTOP_IGPU_FIRST_TEXT = (
    "\n".join(
        [
            _lspci_mm_line("00:02.0", "VGA compatible controller", INTEL_VENDOR, UHD_730),
            _lspci_mm_line("01:00.0", "3D controller", NVIDIA_VENDOR, RTX_3080),
        ]
    )
    + "\n"
)

# Desktop case: the dGPU reports as "VGA compatible controller" while the
# iGPU reports as "Display controller"; VGA must still win.
LSPCI_DESKTOP_DGPU_VGA_TEXT = (
    "\n".join(
        [
            _lspci_mm_line("01:00.0", "VGA compatible controller", NVIDIA_VENDOR, RTX_3080),
            _lspci_mm_line("00:02.0", "Display controller", INTEL_VENDOR, UHD_730),
        ]
    )
    + "\n"
)

LSPCI_UNRESOLVED_CLASS_TEXT = (
    _lspci_mm_line("01:00.0", "Class 0302", NVIDIA_VENDOR, RTX_3080) + "\n"
)

LSPCI_SINGLE_VGA_TEXT = (
    _lspci_mm_line("00:02.0", "VGA compatible controller", INTEL_VENDOR, UHD_730) + "\n"
)

LSPCI_REV_TAG_TEXT = (
    _lspci_mm_line("01:00.0", "3D controller", NVIDIA_VENDOR, "GM204 [GeForce GTX 970] (rev a1)")
    + "\n"
)

LSPCI_LHR_TEXT = (
    _lspci_mm_line(
        "01:00.0",
        "VGA compatible controller",
        NVIDIA_VENDOR,
        "GA102 [GeForce RTX 3080 Lite Hash Rate]",
    )
    + "\n"
)


def test_parse_lspci_returns_fixture_dgpu_name() -> None:
    assert linux.parse_lspci(LSPCI_MM_TEXT) == "GeForce RTX 3080"


def test_parse_lspci_picks_dgpu_when_igpu_listed_first() -> None:
    assert linux.parse_lspci(LSPCI_LAPTOP_IGPU_FIRST_TEXT) == "GeForce RTX 3080"


def test_parse_lspci_vga_dgpu_beats_display_igpu() -> None:
    assert linux.parse_lspci(LSPCI_DESKTOP_DGPU_VGA_TEXT) == "GeForce RTX 3080"


def test_parse_lspci_handles_unresolvable_class_code() -> None:
    assert linux.parse_lspci(LSPCI_UNRESOLVED_CLASS_TEXT) == "GeForce RTX 3080"


def test_parse_lspci_returns_single_vga_device_name() -> None:
    assert linux.parse_lspci(LSPCI_SINGLE_VGA_TEXT) == "UHD Graphics 730"


def test_parse_lspci_strips_revision_tag() -> None:
    assert linux.parse_lspci(LSPCI_REV_TAG_TEXT) == "GeForce GTX 970"


def test_parse_lspci_strips_lite_hash_rate_suffix() -> None:
    assert linux.parse_lspci(LSPCI_LHR_TEXT) == "GeForce RTX 3080"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n\n",
        "not an lspci dump at all",
        '01:00.0 "3D controller" "NVIDIA Corporation"',
        '01:00.0 "Host bridge" "Intel Corporation" "12th Gen Core Processor"',
        '01:00.0 "3D controller" "NVIDIA Corporation" ""',
        "💥",
        "\x00\x01\x02",
    ],
)
def test_parse_lspci_returns_none_for_malformed_text(text: str) -> None:
    assert linux.parse_lspci(text) is None


def test_parse_nvidia_smi_vram_returns_fixture_total_gb() -> None:
    assert linux.parse_nvidia_smi_vram(NVIDIA_SMI_TEXT) == 10.0


def test_parse_nvidia_smi_vram_converts_mib_to_gb() -> None:
    assert linux.parse_nvidia_smi_vram("| 10240MiB / 12288MiB |") == 12.0
    assert linux.parse_nvidia_smi_vram("  512MiB / 8192MiB ") == 8.0


def test_parse_nvidia_smi_vram_largest_gpu_wins() -> None:
    text = "|   0  ... | 512MiB / 8192MiB |  ...  | 1  ... | 1024MiB / 12288MiB |\n"

    assert linux.parse_nvidia_smi_vram(text) == 12.0


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n\n",
        "not an nvidia-smi report at all",
        "Fri Nov  6 21:14:07 2026",
        "| 512MiB |",
        "| 512MiB / N/A |",
        "| 512MiB / 10240 MB |",
        "| 512MiB / -10240MiB |",
        "| / 10240MiB |",
        "| 512MiB / " + "9" * 400 + "MiB |",
        "💥",
        "\x00\x01\x02",
    ],
)
def test_parse_nvidia_smi_vram_returns_none_for_malformed_text(text: str) -> None:
    assert linux.parse_nvidia_smi_vram(text) is None


def test_parse_vulkaninfo_returns_fixture_device_local_heap_gb() -> None:
    # The RTX 3080's device-local heap (10737418240 B) beats the iGPU's 7.5 GiB;
    # both unflagged host heaps (25769803776 B) must be ignored.
    assert linux.parse_vulkaninfo(VULKANINFO_TEXT) == 10.0


def test_parse_vulkaninfo_ignores_non_device_local_heap() -> None:
    text = """\
{
  "vulkan": {
    "devices": [
      {
        "memory": {
          "memoryHeaps": [
            {"flags": 0, "size": 25769803776},
            {"flags": 1, "size": 1073741824}
          ]
        }
      }
    ]
  }
}
"""

    assert linux.parse_vulkaninfo(text) == 1.0


def test_parse_vulkaninfo_handles_keyed_gpu_dict_form() -> None:
    text = """\
{
  "vulkan": {
    "devices": {
      "GPU0": {
        "memory": {"memoryHeaps": [{"flags": 1, "size": 10737418240}]}
      }
    }
  }
}
"""

    assert linux.parse_vulkaninfo(text) == 10.0


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n\n",
        "not json at all",
        "💥",
        "\x00\x01\x02",
        "{}",
        "[]",
        '{"vulkan": null}',
        '{"vulkan": {}}',
        '{"vulkan": {"devices": []}}',
        '{"vulkan": {"devices": [{"memory": {}}]}}',
        '{"vulkan": {"devices": [{"memory": {"memoryHeaps": []}}]}}',
        '{"vulkan": {"devices": [{"memory": {"memoryHeaps": ['
        '{"flags": 0, "size": 10737418240}]}}]}}',
        '{"vulkan": {"devices": [{"memory": {"memoryHeaps": [{"flags": 1, "size": "huge"}]}}]}}',
        '{"vulkan": {"devices": [null]}}',
    ],
)
def test_parse_vulkaninfo_returns_none_for_malformed_text(text: str) -> None:
    assert linux.parse_vulkaninfo(text) is None


def test_clean_linux_name_promotes_marketing_bracket() -> None:
    assert linux._clean_linux_name("GA102 [GeForce RTX 3080]") == "GeForce RTX 3080"


def test_clean_linux_name_promotes_first_marketing_bracket_only() -> None:
    assert linux._clean_linux_name("GA102 [GeForce RTX 3080] [10DE:2206]") == "GeForce RTX 3080"


def test_clean_linux_name_strips_non_marketing_brackets() -> None:
    assert linux._clean_linux_name("NVIDIA GA102 [10DE:2206]") == "NVIDIA GA102"


def test_clean_linux_name_strips_revision_tag() -> None:
    assert linux._clean_linux_name("GeForce GTX 970 (rev a1)") == "GeForce GTX 970"


def test_clean_linux_name_strips_lite_hash_rate() -> None:
    assert linux._clean_linux_name("GeForce RTX 3080 Lite Hash Rate") == "GeForce RTX 3080"


def test_clean_linux_name_collapses_whitespace() -> None:
    assert linux._clean_linux_name("GA102  [GeForce   RTX 3080]  [10DE:2206] ") == (
        "GeForce RTX 3080"
    )


def test_gpu_parsers_do_not_raise_on_hostile_text() -> None:
    for text in ("\x00\x01\x02", "💥"):
        assert linux.parse_lspci(text) is None
        assert linux.parse_nvidia_smi_vram(text) is None
        assert linux.parse_vulkaninfo(text) is None
