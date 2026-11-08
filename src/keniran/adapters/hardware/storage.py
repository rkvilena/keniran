"""Backend-agnostic storage selection for the hardware audit backends.

A pure helper over an *injected* partition list: the caller (Windows, Linux,
tests) supplies psutil-shaped partition data, and
:func:`select_storage_free` filters out non-local kinds (removable, CD-ROM,
network), picks the local fixed mount with the most free space, and reports
which kinds it skipped so the renderer can note them instead of hiding them.

The module imports nothing platform-specific and no I/O at all, so the same
helper serves every backend and tests need no real filesystem.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

_NETWORK_FSTYPES: frozenset[str] = frozenset(
    {"nfs", "nfs4", "cifs", "smbfs", "smb2", "sshfs", "afp", "9p", "ncpfs"}
)
_CDROM_FSTYPES: frozenset[str] = frozenset({"iso9660", "udf", "cdfs", "udf2"})
_REMOVABLE_OPTS: frozenset[str] = frozenset({"removable", "cdrom", "network"})


@dataclass(frozen=True, slots=True)
class Partition:
    """One mounted filesystem, normalized from ``psutil.disk_partitions`` data.

    ``opts`` is the flag tuple (``("rw", "fixed")``, ``("rw", "removable")``,
    ...) split from psutil's comma-joined ``opts`` string. ``free_gb`` is the
    measured free space on the mount (``None`` when the caller could not
    measure it); the helper never touches the filesystem itself.
    """

    mountpoint: str
    fstype: str
    opts: tuple[str, ...] = ()
    free_gb: float | None = None


@dataclass(frozen=True, slots=True)
class StorageResult:
    """Outcome of the any-local-mount storage check.

    ``free_gb``/``mount`` describe the best eligible local fixed mount (the one
    with the most free space), or are both ``None`` when no eligible mount
    could be measured — the honest "unverified" state. ``skipped_kinds`` names
    the non-local partition kinds that were excluded, so "we saw a network
    drive and ignored it" stays visible instead of silent.
    """

    free_gb: float | None = None
    mount: str | None = None
    skipped_kinds: frozenset[str] = frozenset()


def select_storage_free(
    required_gb: float | None,
    partitions: Sequence[Partition],
) -> StorageResult:
    """Pick the local fixed mount with the most free space.

    Partitions flagged (by ``opts`` or ``fstype``) as removable, CD-ROM, or
    network are excluded, with their kinds collected in ``skipped_kinds``.
    Among the remaining mounts the one with the largest ``free_gb`` wins —
    regardless of *required_gb*, so a FAIL still records the best available
    mount. ``required_gb`` is accepted to keep the check's intent at the call
    site; pass/fail semantics stay with :func:`keniran.core.scoring.
    meets_minimum` on the stored ``free_gb``.

    An empty partition list (or no measurable eligible mount) yields
    ``free_gb=None`` with ``mount=None`` — the honest unverified state.
    """
    del required_gb  # pass/fail is computed downstream on the stored free_gb.

    skipped: set[str] = set()
    eligible: list[Partition] = []
    for partition in partitions:
        kind = _excluded_kind(partition)
        if kind is None:
            eligible.append(partition)
        else:
            skipped.add(kind)

    measurable = [p for p in eligible if p.free_gb is not None]
    if not measurable:
        return StorageResult(free_gb=None, mount=None, skipped_kinds=frozenset(skipped))

    best = max(measurable, key=lambda p: p.free_gb if p.free_gb is not None else -1.0)
    return StorageResult(
        free_gb=best.free_gb,
        mount=best.mountpoint,
        skipped_kinds=frozenset(skipped),
    )


def _excluded_kind(partition: Partition) -> str | None:
    """Return the non-local kind of *partition*, or ``None`` for local fixed.

    The rule combines psutil-style ``opts`` flags with filesystem-type
    heuristics, so a network mount is caught whether it announces itself via
    ``opts`` (``network``) or only via ``fstype`` (``cifs``).
    """
    opts = frozenset(partition.opts)
    removable_opts = opts & _REMOVABLE_OPTS
    if removable_opts:
        return sorted(removable_opts)[0]
    if partition.fstype.casefold() in _NETWORK_FSTYPES:
        return "network"
    if partition.fstype.casefold() in _CDROM_FSTYPES:
        return "cdrom"
    return None
