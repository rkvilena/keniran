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
    filter_linux_partitions,
)
from keniran.adapters.hardware.storage import Partition, select_storage_free
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

FIXTURES = Path(__file__).parent / "fixtures"
DISK_PARTITIONS_FIXTURE = FIXTURES / "linux" / "disk_partitions.json"

EXPECTED_PSEUDO_FSTYPES = frozenset(
    {"tmpfs", "ramfs", "devtmpfs", "proc", "sysfs", "efivarfs", "squashfs", "overlay"}
)


def _raw_partition(
    mountpoint: str,
    *,
    device: str = "/dev/sda2",
    fstype: str = "ext4",
    opts: str = "rw,relatime",
) -> types.SimpleNamespace:
    """Build a duck-typed ``psutil.disk_partitions`` entry."""
    return types.SimpleNamespace(device=device, mountpoint=mountpoint, fstype=fstype, opts=opts)


def _fixture_records() -> list[dict[str, object]]:
    """Load the recorded psutil-style partition entries."""
    payload = json.loads(DISK_PARTITIONS_FIXTURE.read_text(encoding="utf-8"))
    return list(payload["partitions"])


def _fixture_raw_parts() -> list[types.SimpleNamespace]:
    """Convert the recorded fixture into duck-typed psutil entries."""
    return [
        _raw_partition(
            str(entry["mountpoint"]),
            device=str(entry["device"]),
            fstype=str(entry["fstype"]),
            opts=str(entry["opts"]),
        )
        for entry in _fixture_records()
    ]


def _fixture_free_by_mount() -> dict[str, float]:
    """Map the recorded fixture mountpoints to their measured free space."""
    return {str(entry["mountpoint"]): float(entry["free_gb"]) for entry in _fixture_records()}


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


def _install_partitions(
    monkeypatch: pytest.MonkeyPatch, partitions: list[Partition] | None = None
) -> None:
    """Replace the psutil partition collection with an injected list."""
    if partitions is None:
        partitions = [
            Partition(
                mountpoint="/",
                fstype="ext4",
                opts=("rw", "relatime"),
                free_gb=148.25,
            )
        ]
    monkeypatch.setattr(linux, "_collect_partitions", lambda: partitions)


def _install_posix_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the linux backend believe it runs on a POSIX host; fake the disk."""
    monkeypatch.setattr(linux, "os", types.SimpleNamespace(name="posix"))
    monkeypatch.setattr(linux.sys, "platform", "linux")
    _install_partitions(monkeypatch)


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


# --- storage gatherer: pseudo denylist + same-device dedupe (LSTO-001) ---------


def test_pseudo_fstype_denylist_is_the_documented_set() -> None:
    assert linux._PSEUDO_FSTYPES == EXPECTED_PSEUDO_FSTYPES


@pytest.mark.parametrize("fstype", sorted(EXPECTED_PSEUDO_FSTYPES))
def test_every_denylisted_fstype_is_excluded(fstype: str) -> None:
    partitions, kinds = filter_linux_partitions(
        [_raw_partition("/mnt/pseudo", fstype=fstype)],
        lambda _mountpoint: 999.0,
    )

    assert partitions == []
    assert kinds == frozenset({"pseudo"})


def test_fuseblk_and_ntfs_data_partitions_are_not_excluded() -> None:
    raw_parts = [
        _raw_partition("/mnt/windows", device="/dev/sda3", fstype="fuseblk"),
        _raw_partition("/data", device="/dev/sda4", fstype="ntfs"),
    ]

    partitions, kinds = filter_linux_partitions(raw_parts, lambda _mountpoint: 42.0)

    assert [part.mountpoint for part in partitions] == ["/mnt/windows", "/data"]
    assert [part.fstype for part in partitions] == ["fuseblk", "ntfs"]
    assert kinds == frozenset()


def test_filter_fixture_binds_exact_expected_partitions() -> None:
    free_by_mount = _fixture_free_by_mount()
    measured: list[str] = []

    def lookup(mountpoint: str) -> float | None:
        measured.append(mountpoint)
        return free_by_mount[mountpoint]

    partitions, kinds = filter_linux_partitions(_fixture_raw_parts(), lookup)

    # Pseudo mounts are denied before measurement; dedupe only sees real
    # storage, so the lookup never touches tmpfs/squashfs.
    assert measured == ["/", "/home", "/boot/efi", "/mnt/c"]
    assert kinds == frozenset({"pseudo"})
    # /home shares /dev/sda2 with / and loses the dedupe (equal free space
    # keeps the first mount); /boot/efi and the WSL 9p mount survive the
    # Linux-side filter.
    assert [part.mountpoint for part in partitions] == ["/", "/boot/efi", "/mnt/c"]
    assert [(part.fstype, part.free_gb) for part in partitions] == [
        ("ext4", 148.62),
        ("vfat", 0.48),
        ("9p", 88.4),
    ]
    assert partitions[0].opts == ("rw", "relatime")
    assert "fmask=0077" in partitions[1].opts


def test_helper_drops_fixture_9p_mount_as_network_and_picks_root() -> None:
    partitions, kinds = filter_linux_partitions(
        _fixture_raw_parts(),
        _fixture_free_by_mount().__getitem__,
    )

    # 9p is deliberately not pseudo: the shared helper owns the network skip.
    assert "/mnt/c" in {part.mountpoint for part in partitions}
    assert kinds == frozenset({"pseudo"})

    result = select_storage_free(None, partitions)

    assert result.free_gb == 148.62
    assert result.mount == "/"
    assert result.skipped_kinds == frozenset({"network"})


def test_inflated_tmpfs_free_space_can_never_win() -> None:
    raw_parts = [
        _raw_partition("/run", device="tmpfs", fstype="tmpfs"),
        _raw_partition("/", device="/dev/sda2", fstype="ext4"),
    ]
    free_by_mount = {"/run": 999.0, "/": 20.0}

    partitions, kinds = filter_linux_partitions(raw_parts, free_by_mount.__getitem__)
    result = select_storage_free(30.0, partitions)

    assert "/run" not in {part.mountpoint for part in partitions}
    assert kinds == frozenset({"pseudo"})
    assert result.free_gb == 20.0
    assert result.mount == "/"


def test_dedupe_keeps_same_device_mount_with_most_free_space() -> None:
    raw_parts = [
        _raw_partition("/usr", device="/dev/sda2"),
        _raw_partition("/", device="/dev/sda2"),
    ]
    free_by_mount = {"/usr": 12.5, "/": 140.0}

    partitions, kinds = filter_linux_partitions(raw_parts, free_by_mount.__getitem__)

    assert [(part.mountpoint, part.free_gb) for part in partitions] == [("/", 140.0)]
    assert kinds == frozenset()


def test_dedupe_keeps_first_mount_when_free_space_ties() -> None:
    raw_parts = [
        _raw_partition("/usr", device="/dev/sda2"),
        _raw_partition("/", device="/dev/sda2"),
    ]

    partitions, _kinds = filter_linux_partitions(raw_parts, lambda _mountpoint: 50.0)

    assert [part.mountpoint for part in partitions] == ["/usr"]


def test_dedupe_keeps_first_mount_when_no_mount_is_measurable() -> None:
    raw_parts = [
        _raw_partition("/usr", device="/dev/sda2"),
        _raw_partition("/", device="/dev/sda2"),
    ]

    partitions, _kinds = filter_linux_partitions(raw_parts, lambda _mountpoint: None)

    assert [(part.mountpoint, part.free_gb) for part in partitions] == [("/usr", None)]


def test_dedupe_prefers_a_measured_mount_over_an_unmeasurable_one() -> None:
    raw_parts = [
        _raw_partition("/usr", device="/dev/sda2"),
        _raw_partition("/", device="/dev/sda2"),
    ]
    free_by_mount = {"/usr": None, "/": 30.0}

    partitions, _kinds = filter_linux_partitions(raw_parts, free_by_mount.__getitem__)

    assert [(part.mountpoint, part.free_gb) for part in partitions] == [("/", 30.0)]


def test_unmeasurable_mount_is_never_picked_as_best() -> None:
    raw_parts = [
        _raw_partition("/small", device="/dev/sda1"),
        _raw_partition("/unmounted", device="/dev/sdb1"),
    ]

    partitions, _kinds = filter_linux_partitions(raw_parts, {"/small": 10.0}.get)
    result = select_storage_free(None, partitions)

    assert result.free_gb == 10.0
    assert result.mount == "/small"


def test_filter_never_raises_on_malformed_partial_partitions() -> None:
    raw_parts = [
        None,
        types.SimpleNamespace(),  # no mountpoint at all
        types.SimpleNamespace(mountpoint="", fstype="ext4"),  # unusable mountpoint
        types.SimpleNamespace(device=7, mountpoint="/odd-types", fstype=None, opts=None),
        types.SimpleNamespace(device="/dev/sdz", mountpoint="/boom", fstype="ext4", opts="rw"),
    ]

    def lookup(mountpoint: str) -> float | None:
        if mountpoint == "/boom":
            raise OSError("unmounted mid-audit")
        return 5.0

    partitions, kinds = filter_linux_partitions(raw_parts, lookup)

    assert kinds == frozenset()
    assert [(part.mountpoint, part.fstype, part.opts, part.free_gb) for part in partitions] == [
        ("/odd-types", "", (), 5.0),
        ("/boom", "ext4", ("rw",), None),
    ]


@pytest.mark.parametrize(
    "value",
    [None, "12.5", float("nan"), float("inf"), float("-inf"), True],
)
def test_non_finite_or_non_numeric_lookup_result_degrades_to_none(value: object) -> None:
    partitions, _kinds = filter_linux_partitions(
        [_raw_partition("/")],
        lambda _mountpoint, result=value: result,
    )

    assert [(part.mountpoint, part.free_gb) for part in partitions] == [("/", None)]


def test_collect_partitions_measures_and_applies_linux_hygiene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_parts = [
        _raw_partition("/", device="/dev/sda2", fstype="ext4"),
        _raw_partition("/home", device="/dev/sda2", fstype="ext4"),
        _raw_partition("/boot/efi", device="/dev/sda1", fstype="vfat"),
        _raw_partition("/run", device="tmpfs", fstype="tmpfs"),
    ]
    free_bytes = {
        "/": 140 * 1024**3,
        "/home": 139 * 1024**3,
        "/boot/efi": 512 * 1024**2,
    }

    def fake_disk_partitions(**kwargs: object) -> list[types.SimpleNamespace]:
        assert kwargs == {"all": False}
        return raw_parts

    def fake_disk_usage(mountpoint: str) -> types.SimpleNamespace:
        return types.SimpleNamespace(free=free_bytes[mountpoint])

    monkeypatch.setattr(linux.psutil, "disk_partitions", fake_disk_partitions)
    monkeypatch.setattr(linux.psutil, "disk_usage", fake_disk_usage)

    partitions = linux._collect_partitions()

    assert [(part.mountpoint, part.fstype, part.free_gb) for part in partitions] == [
        ("/", "ext4", 140.0),
        ("/boot/efi", "vfat", 0.5),
    ]


def test_collect_partitions_keeps_unmeasurable_mount_with_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_parts = [_raw_partition("/", device="/dev/sda2", fstype="ext4")]

    def explode(mountpoint: str) -> object:
        raise OSError(f"cannot measure {mountpoint}")

    monkeypatch.setattr(linux.psutil, "disk_partitions", lambda **kwargs: raw_parts)
    monkeypatch.setattr(linux.psutil, "disk_usage", explode)

    partitions = linux._collect_partitions()

    assert [(part.mountpoint, part.free_gb) for part in partitions] == [("/", None)]


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
    assert spec.storage_used_mount == "/"
    assert spec.audited_at.tzinfo is not None

    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["platform"] == "linux"
    assert payload["storage_used_mount"] == "/"
    assert datetime.fromisoformat(payload["audited_at"]).tzinfo is not None


def test_audit_picks_largest_free_mount_across_multiple_local_mounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_healthy_chains(tmp_path, monkeypatch)
    _install_partitions(
        monkeypatch,
        [
            Partition(mountpoint="/", fstype="ext4", opts=("rw", "relatime"), free_gb=20.0),
            Partition(mountpoint="/games", fstype="ext4", opts=("rw",), free_gb=200.0),
        ],
    )
    path = tmp_path / "generated" / "system_spec.json"

    spec = linux.audit(path=path)

    # Root / is a guaranteed candidate, not the only one: parity with the
    # Windows any-local-mount rule lets a roomier data mount win.
    assert spec.disk_free_gb == 200.0
    assert spec.storage_used_mount == "/games"


@pytest.mark.parametrize(
    "partitions",
    [
        [],
        [Partition(mountpoint="/", fstype="ext4", opts=("rw", "relatime"), free_gb=None)],
    ],
    ids=["no-partitions", "unmeasurable-root"],
)
def test_audit_without_any_measurable_mount_records_unverified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    partitions: list[Partition],
) -> None:
    _install_healthy_chains(tmp_path, monkeypatch)
    _install_partitions(monkeypatch, partitions)
    path = tmp_path / "generated" / "system_spec.json"

    spec = linux.audit(path=path)

    # The honest None state (downstream _hard_check_row renders it unverified),
    # never the legacy fabricated 0.0.
    assert spec.disk_free_gb is None
    assert spec.storage_used_mount is None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["disk_free_gb"] is None
    assert payload["storage_used_mount"] is None


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
