"""Pure scoring math: benchmark ratios, hard checks, status bands, and verdicts.

This module is part of the pure ``core`` layer: it performs no I/O and imports
no network, CLI, or hardware libraries.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from keniran.core.models import (
    ComponentName,
    GameRequirements,
    SystemSpec,
    Verdict,
    VerdictBand,
)

PASS_RATIO: Final = 1.0
BORDERLINE_RATIO: Final = 0.85
POOR_RATIO: Final = 0.65
ST_WARNING_RATIO: Final = 0.70
DISPLAY_CAP_PERCENT: Final = 100.0

_BAND_PHRASES: Final[dict[VerdictBand, str]] = {
    VerdictBand.PASS: "meets requirement",
    VerdictBand.BORDERLINE: "playable on low settings",
    VerdictBand.POOR: "low FPS expected",
    VerdictBand.UNPLAYABLE: "below minimum requirements",
    VerdictBand.FAIL: "spec shortfall",
    VerdictBand.UNVERIFIED: "manual review suggested",
}


def component_ratio(user_score: float, required_score: float) -> float:
    """Return ``user_score / required_score`` (used for both CPU and GPU)."""
    if required_score <= 0:
        msg = "required benchmark score must be positive"
        raise ValueError(msg)
    if user_score < 0:
        msg = "user benchmark score must be non-negative"
        raise ValueError(msg)
    return user_score / required_score


def cpu_ratio(user_cpumark: float, target_cpumark: float) -> float:
    """Multi-thread CPU ratio (primary CPU comparison per §4.5)."""
    return component_ratio(user_cpumark, target_cpumark)


def gpu_ratio(user_g3d_mark: float, target_g3d_mark: float) -> float:
    """GPU ratio based on PassMark G3D marks."""
    return component_ratio(user_g3d_mark, target_g3d_mark)


def final_ratio(cpu_ratio_value: float | None, gpu_ratio_value: float | None) -> float | None:
    """Bottleneck ratio: ``min`` of the available CPU/GPU ratios.

    ``None`` components are treated as unverified and ignored; ``None`` is
    returned only when neither component could be scored.
    """
    available = [ratio for ratio in (cpu_ratio_value, gpu_ratio_value) if ratio is not None]
    return min(available) if available else None


def status_band(ratio: float) -> VerdictBand:
    """Map a performance ratio to its §4.6 band (boundaries are inclusive)."""
    if ratio >= PASS_RATIO:
        return VerdictBand.PASS
    if ratio >= BORDERLINE_RATIO:
        return VerdictBand.BORDERLINE
    if ratio >= POOR_RATIO:
        return VerdictBand.POOR
    return VerdictBand.UNPLAYABLE


def display_percent(ratio: float) -> float:
    """Human-facing percentage for a ratio, capped at 100% per §4.6.

    Values are floored so a sub-1.0 ratio can never render as ``100%``; the
    small epsilon only absorbs binary floating-point representation noise.
    """
    if ratio <= 0:
        return 0.0
    capped = min(ratio, PASS_RATIO) * DISPLAY_CAP_PERCENT
    return float(math.floor(capped + 1e-9))


def meets_minimum(user_value: float | None, required_value: float | None) -> bool | None:
    """Direct numeric minimum check for RAM/VRAM/Storage.

    Returns ``None`` when either side is unknown, so callers never mistake
    missing data for a failed check.
    """
    if user_value is None or required_value is None:
        return None
    return user_value >= required_value


def minimum_shortfalls(spec: SystemSpec, requirements: GameRequirements) -> list[ComponentName]:
    """Return the hard-checked components below the published minimum."""
    checks: tuple[tuple[ComponentName, float, float | None], ...] = (
        (ComponentName.RAM, spec.ram_gb, requirements.ram_gb),
        (ComponentName.VRAM, spec.vram_gb, requirements.vram_gb),
        (ComponentName.STORAGE, spec.disk_free_gb, requirements.storage_gb),
    )
    return [
        component
        for component, user_value, required_value in checks
        if meets_minimum(user_value, required_value) is False
    ]


def st_warning(cpu_ratio_value: float | None, st_ratio: float | None) -> bool:
    """True when multi-thread CPU passes but single-thread is below 0.70."""
    if cpu_ratio_value is None or st_ratio is None:
        return False
    return cpu_ratio_value >= PASS_RATIO and st_ratio < ST_WARNING_RATIO


def build_verdict(
    cpu_ratio: float | None,
    gpu_ratio: float | None,
    *,
    shortfalls: Sequence[ComponentName] = (),
    st_ratio: float | None = None,
) -> Verdict:
    """Assemble the final verdict from component ratios and hard checks.

    Any RAM/VRAM/Storage shortfall caps the band at :attr:`VerdictBand.FAIL`
    regardless of the benchmark ratio; otherwise the band follows
    :func:`status_band`. A passing CPU with ST ratio below 0.70 raises the
    informational ``st_warning`` flag.
    """
    ratio = final_ratio(cpu_ratio, gpu_ratio)
    shortfall_list = list(shortfalls)

    if shortfall_list:
        band = VerdictBand.FAIL
    elif ratio is None:
        band = VerdictBand.UNVERIFIED
    else:
        band = status_band(ratio)

    percent = display_percent(ratio) if ratio is not None else 0.0
    return Verdict(
        band=band,
        ratio=ratio,
        display_percent=percent,
        percentage_text=_percentage_text(band, percent, shortfall_list),
        spec_shortfall=bool(shortfall_list),
        shortfall_components=shortfall_list,
        st_warning=st_warning(cpu_ratio, st_ratio),
    )


def _percentage_text(band: VerdictBand, percent: float, shortfalls: Sequence[ComponentName]) -> str:
    """Build the one-line verdict text rendered by the CLI."""
    if band is VerdictBand.UNVERIFIED:
        return "unverified — manual review suggested"

    summary = f"{percent:.0f}% of the game's minimum requirement"
    if band is VerdictBand.FAIL:
        names = ", ".join(component.value for component in shortfalls)
        return f"{summary} — Fail (spec shortfall: {names})"
    return f"{summary} ({band.value} — {_BAND_PHRASES[band]})"
