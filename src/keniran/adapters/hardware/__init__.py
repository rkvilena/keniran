"""Platform-dispatched hardware audit adapters.

The Windows implementation lives in :mod:`keniran.adapters.hardware.windows`.
This facade re-exports its public API and selects the backend when platform
specific work is requested, so the package imports cleanly everywhere. Backends
stamp :class:`~keniran.core.models.SystemSpec` with ``sys.platform``; a cache
written on another platform (or a legacy cache without the key) is re-audited
rather than reused.
"""

from __future__ import annotations

import sys
from pathlib import Path

from keniran.adapters.hardware import windows
from keniran.adapters.hardware.windows import (
    DEFAULT_SPEC_PATH,
    DXDIAG_EXECUTABLE,
    DXDIAG_OUTPUT_WAIT_SECONDS,
    DXDIAG_POLL_SECONDS,
    DXDIAG_TIMEOUT_SECONDS,
    GENERATED_DIR,
    DxDiagError,
    DxDiagInfo,
    DxDiagParseError,
    HardwareAuditError,
    HardwareCacheError,
    UnsupportedPlatformError,
)
from keniran.core.models import SystemSpec

__all__ = [
    "DEFAULT_SPEC_PATH",
    "DXDIAG_EXECUTABLE",
    "DXDIAG_OUTPUT_WAIT_SECONDS",
    "DXDIAG_POLL_SECONDS",
    "DXDIAG_TIMEOUT_SECONDS",
    "GENERATED_DIR",
    "DxDiagError",
    "DxDiagInfo",
    "DxDiagParseError",
    "HardwareAuditError",
    "HardwareCacheError",
    "UnsupportedPlatformError",
    "audit",
    "load",
    "parse_dxdiag",
    "save",
]


def _require_windows_backend() -> None:
    """Raise :class:`UnsupportedPlatformError` when no backend is available."""
    if sys.platform != "win32":
        msg = f"hardware audit requires Windows: dxdiag is not available on {sys.platform}"
        raise UnsupportedPlatformError(msg)


def audit(*, path: Path = DEFAULT_SPEC_PATH) -> SystemSpec:
    """Run a fresh dxdiag audit, persist the result, and return it.

    Dispatches to the Windows backend, which stamps the spec with
    ``sys.platform``; other platforms raise :class:`UnsupportedPlatformError`.
    """
    _require_windows_backend()
    return windows.audit(path=path)


def load(*, refresh: bool = False, path: Path = DEFAULT_SPEC_PATH) -> SystemSpec:
    """Return the cached audit, running a fresh one only when needed.

    The cache is reused only when its ``platform`` matches the current
    ``sys.platform``; a mismatch or legacy cache without the key re-audits.
    """
    return windows.load(refresh=refresh, path=path)


def save(spec: SystemSpec, *, path: Path = DEFAULT_SPEC_PATH) -> Path:
    """Persist *spec* atomically: write a sibling temp file, then replace."""
    return windows.save(spec, path=path)


def parse_dxdiag(text: str) -> DxDiagInfo:
    """Extract CPU, RAM, GPU, and dedicated VRAM from a DxDiag report."""
    return windows.parse_dxdiag(text)
