"""Pydantic domain models shared across Keniran's pure core layer."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ComponentName(StrEnum):
    """Components shown as rows in the comparison report."""

    CPU = "CPU"
    GPU = "GPU"
    RAM = "RAM"
    VRAM = "VRAM"
    STORAGE = "Storage"


class VerdictBand(StrEnum):
    """Performance bands from spec §4.6, plus the shortfall cap and unverified state."""

    PASS = "Pass"
    BORDERLINE = "Borderline"
    POOR = "Poor"
    UNPLAYABLE = "Unplayable"
    FAIL = "Fail"
    UNVERIFIED = "Unverified"


class SystemSpec(BaseModel):
    """Audited local machine, persisted to ``generated/system_spec.json`` (§4.3).

    ``platform`` records the ``sys.platform`` of the audited machine so a cache
    written on another OS (e.g. Windows vs. WSL) is re-audited instead of reused.
    """

    model_config = ConfigDict(extra="forbid")

    platform: str
    cpu_name: str
    ram_gb: float = Field(ge=0)
    gpu_name: str
    vram_gb: float = Field(ge=0)
    disk_free_gb: float = Field(ge=0)
    audited_at: datetime


class GameRequirements(BaseModel):
    """Structured minimum requirements parsed from Steam text (§4.2).

    Any field the parser cannot establish with confidence stays ``None``.
    Components whose extracted name had no model number are additionally listed
    in ``unverified`` so the report can show a ⚠ badge instead of a guess.
    """

    model_config = ConfigDict(extra="forbid")

    cpu_name: str | None = None
    gpu_name: str | None = None
    ram_gb: float | None = Field(default=None, ge=0)
    vram_gb: float | None = Field(default=None, ge=0)
    storage_gb: float | None = Field(default=None, ge=0)
    target_resolution: str | None = None
    target_fps: int | None = Field(default=None, ge=0)
    unverified: set[ComponentName] = Field(default_factory=set)


class BenchmarkEntry(BaseModel):
    """A row from a vendored PassMark database, normalized by the lookup layer.

    ``score`` is the primary comparison value (``cpumark`` for CPUs,
    ``g3d_mark`` for GPUs); ``thread`` carries the CPU single-thread score and
    stays ``None`` for GPUs. Unknown database columns are preserved.
    """

    model_config = ConfigDict(extra="allow")

    id: int | str | None = None
    name: str
    score: float | None = None
    thread: float | None = None
    samples: int | None = None
    href: str | None = None


class MatchResult(BaseModel):
    """Outcome of a benchmark name lookup (§4.5).

    ``score_ratio`` is the match-confidence ratio in ``[0, 1]`` (used for the
    confidence badge and the 0.80 gate), not a performance ratio.
    """

    model_config = ConfigDict(extra="forbid")

    best_entry: BenchmarkEntry | None = None
    score_ratio: float | None = None
    alternatives: list[BenchmarkEntry] = Field(default_factory=list)
    matched_by: str | None = None


class ComponentRow(BaseModel):
    """One comparison row in the rendered report.

    CPU/GPU rows carry a performance ``ratio``; hard-checked RAM/VRAM/Storage
    rows carry a boolean ``passed`` result. Either may be ``None`` when the
    component is unverifiable.
    """

    model_config = ConfigDict(extra="forbid")

    component: ComponentName
    user_value: str
    required_value: str
    ratio: float | None = None
    passed: bool | None = None
    confidence: float | None = None
    matched_name: str | None = None
    unverified: bool = False


class Verdict(BaseModel):
    """Final bottom-line result assembled by :func:`keniran.core.scoring.build_verdict`."""

    model_config = ConfigDict(extra="forbid")

    band: VerdictBand
    ratio: float | None = None
    display_percent: float = 0.0
    percentage_text: str
    spec_shortfall: bool = False
    shortfall_components: list[ComponentName] = Field(default_factory=list)
    st_warning: bool = False


class Report(BaseModel):
    """Everything a renderer needs for one game check (§4.6).

    ``verdict`` is ``None`` only when no verdict could be produced at all;
    ``message`` carries a graceful explanation such as "No PC requirements
    published" for reports with no comparison rows.
    """

    model_config = ConfigDict(extra="forbid")

    game_name: str
    app_id: int
    components: list[ComponentRow] = Field(default_factory=list)
    verdict: Verdict | None = None
    message: str | None = None
