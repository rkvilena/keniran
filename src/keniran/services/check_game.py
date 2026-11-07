"""Pipeline service: run one game check and assemble the renderer-agnostic Report.

Implements the orchestration of spec §3 steps 1-7: cached hardware audit →
Steam appdetails fetch → HTML strip → rules-only parse → CPU/GPU benchmark
lookups plus RAM/VRAM/Storage hard checks → verdict. Rendering is intentionally
absent; CLI and future UIs consume the plain :class:`~keniran.core.models.Report`
returned here.

``steam.fetch`` already caches responses in memory for the process, so two
checks of the same app id within one run perform a single HTTP request.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from keniran.adapters import benchmarks, hardware, steam
from keniran.core import requirements_parser, scoring
from keniran.core.models import (
    ComponentName,
    ComponentRow,
    MatchResult,
    Report,
    SystemSpec,
)

NO_REQUIREMENTS_MESSAGE: Final = "No PC requirements published"
UNVERIFIED_VALUE: Final = "unverified"
NOT_PUBLISHED_VALUE: Final = "not published"

_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_DEFAULT_CPU_DB_PATH: Final = _REPO_ROOT / "database" / "cpus2a.json"
_DEFAULT_GPU_DB_PATH: Final = _REPO_ROOT / "database" / "gpu_db.json"

BenchmarkDatabase = Mapping[str, Any] | Sequence[Mapping[str, Any]]


def check_game(
    app_id: int,
    refresh_spec: bool = False,
    *,
    fetch_steam: Callable[[int], steam.SteamRequirements] | None = None,
    load_spec: Callable[..., SystemSpec] | None = None,
    cpu_db: BenchmarkDatabase | None = None,
    gpu_db: BenchmarkDatabase | None = None,
) -> Report:
    """Run the full minimum-requirements pipeline for one Steam app.

    ``fetch_steam`` and ``load_spec`` are injection seams for offline tests and
    default to the production adapters. ``cpu_db``/``gpu_db`` likewise default
    to the vendored PassMark databases, loaded once per process.

    When Steam publishes no minimum requirements the run is not an error: the
    returned report carries :data:`NO_REQUIREMENTS_MESSAGE` and no verdict.
    Other Steam adapter failures (for example :class:`~keniran.adapters.steam.
    SteamAppNotFound`) propagate so the caller can surface a clear error.
    """
    spec_loader = load_spec if load_spec is not None else hardware.load
    fetcher = fetch_steam if fetch_steam is not None else steam.fetch

    system_spec = spec_loader(refresh=refresh_spec)

    try:
        game = fetcher(app_id)
    except steam.NoRequirementsPublished:
        return Report(
            game_name=f"Steam app {app_id}",
            app_id=app_id,
            message=NO_REQUIREMENTS_MESSAGE,
        )

    cleaned_text = steam.strip_requirements_html(game.minimum_html)
    requirements = requirements_parser.parse(cleaned_text)
    cpu_database, gpu_database = _resolve_benchmark_databases(cpu_db, gpu_db)

    user_cpu = benchmarks.lookup(cpu_database, system_spec.cpu_name, kind="cpu")
    user_gpu = benchmarks.lookup(gpu_database, system_spec.gpu_name, kind="gpu")
    target_cpu = (
        benchmarks.lookup(cpu_database, requirements.cpu_name, kind="cpu")
        if requirements.cpu_name is not None
        else None
    )
    target_gpu = (
        benchmarks.lookup(gpu_database, requirements.gpu_name, kind="gpu")
        if requirements.gpu_name is not None
        else None
    )

    cpu_row, cpu_ratio = _benchmark_row(
        ComponentName.CPU,
        user_name=system_spec.cpu_name,
        user_match=user_cpu,
        target_name=requirements.cpu_name,
        target_match=target_cpu,
        target_unverified=ComponentName.CPU in requirements.unverified,
    )
    gpu_row, gpu_ratio = _benchmark_row(
        ComponentName.GPU,
        user_name=system_spec.gpu_name,
        user_match=user_gpu,
        target_name=requirements.gpu_name,
        target_match=target_gpu,
        target_unverified=ComponentName.GPU in requirements.unverified,
    )
    ram_row = _hard_check_row(ComponentName.RAM, system_spec.ram_gb, requirements.ram_gb)
    vram_row = _hard_check_row(ComponentName.VRAM, system_spec.vram_gb, requirements.vram_gb)
    storage_row = _hard_check_row(
        ComponentName.STORAGE,
        system_spec.disk_free_gb,
        requirements.storage_gb,
    )

    shortfalls = scoring.minimum_shortfalls(system_spec, requirements)
    verdict = scoring.build_verdict(
        cpu_ratio,
        gpu_ratio,
        shortfalls=shortfalls,
        st_ratio=_single_thread_ratio(user_cpu, target_cpu),
    )

    return Report(
        game_name=game.name,
        app_id=app_id,
        components=[cpu_row, gpu_row, ram_row, vram_row, storage_row],
        verdict=verdict,
    )


def _benchmark_row(
    component: ComponentName,
    *,
    user_name: str,
    user_match: MatchResult,
    target_name: str | None,
    target_match: MatchResult | None,
    target_unverified: bool,
) -> tuple[ComponentRow, float | None]:
    """Build one CPU/GPU row and the performance ratio it supports.

    A ratio needs a usable score on both sides. Missing/unscorable names leave
    ``ratio``/``passed`` as ``None`` and flag the row ``unverified`` so the
    report shows ⚠ instead of inventing a comparison (§4.5).
    """
    user_score = _match_score(user_match)
    target_score = _match_score(target_match)
    ratio = (
        scoring.component_ratio(user_score, target_score)
        if user_score is not None and target_score is not None and target_score > 0
        else None
    )

    matched_name: str | None = None
    confidence: float | None = None
    if target_match is not None and target_match.best_entry is not None:
        matched_name = target_match.best_entry.name
        confidence = target_match.score_ratio

    if target_name is not None:
        required_value = target_name
    else:
        required_value = UNVERIFIED_VALUE if target_unverified else NOT_PUBLISHED_VALUE

    row = ComponentRow(
        component=component,
        user_value=user_name,
        required_value=required_value,
        ratio=ratio,
        confidence=confidence,
        matched_name=matched_name,
        unverified=ratio is None,
    )
    return row, ratio


def _hard_check_row(
    component: ComponentName,
    user_value: float,
    required_value: float | None,
) -> ComponentRow:
    """Build one RAM/VRAM/Storage row from the direct numeric minimum check."""
    passed = scoring.meets_minimum(user_value, required_value)
    return ComponentRow(
        component=component,
        user_value=_format_gigabytes(user_value),
        required_value=(
            _format_gigabytes(required_value) if required_value is not None else NOT_PUBLISHED_VALUE
        ),
        passed=passed,
        unverified=passed is None,
    )


def _match_score(match: MatchResult | None) -> float | None:
    """Return the released benchmark score of a lookup, or ``None``."""
    if match is None or match.best_entry is None:
        return None
    return match.best_entry.score


def _single_thread_ratio(
    user_match: MatchResult,
    target_match: MatchResult | None,
) -> float | None:
    """Compute the informational CPU single-thread ratio when both exist."""
    if target_match is None:
        return None
    user_thread = user_match.best_entry.thread if user_match.best_entry is not None else None
    target_thread = target_match.best_entry.thread if target_match.best_entry is not None else None
    if user_thread is None or target_thread is None or target_thread <= 0:
        return None
    return scoring.component_ratio(user_thread, target_thread)


def _format_gigabytes(value: float) -> str:
    """Render a capacity with the shared ``GB`` suffix (``16 GB``)."""
    return f"{value:g} GB"


def _resolve_benchmark_databases(
    cpu_db: BenchmarkDatabase | None,
    gpu_db: BenchmarkDatabase | None,
) -> tuple[BenchmarkDatabase, BenchmarkDatabase]:
    """Use injected databases when given, else the vendored default pair."""
    if cpu_db is not None and gpu_db is not None:
        return cpu_db, gpu_db

    default_cpu, default_gpu = _default_benchmark_databases()
    return (
        cpu_db if cpu_db is not None else default_cpu,
        gpu_db if gpu_db is not None else default_gpu,
    )


@lru_cache(maxsize=1)
def _default_benchmark_databases() -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the vendored CPU/GPU JSON payloads once per process."""
    cpu_payload: dict[str, Any] = json.loads(_DEFAULT_CPU_DB_PATH.read_text(encoding="utf-8"))
    gpu_payload: dict[str, Any] = json.loads(_DEFAULT_GPU_DB_PATH.read_text(encoding="utf-8"))
    return cpu_payload, gpu_payload
