"""Unit tests for Keniran's pure domain models and scoring math."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from keniran.core import models, scoring
from keniran.core.models import (
    BenchmarkEntry,
    ComponentName,
    ComponentRow,
    GameRequirements,
    MatchResult,
    Report,
    SystemSpec,
    VerdictBand,
)


def _spec() -> SystemSpec:
    return SystemSpec(
        platform="win32",
        cpu_name="Intel Core i5-10400",
        ram_gb=8.0,
        gpu_name="NVIDIA GeForce GTX 1060 6GB",
        vram_gb=4.0,
        disk_free_gb=100.0,
        audited_at=datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
    )


def test_system_spec_exposes_section_4_3_fields() -> None:
    assert set(SystemSpec.model_fields) == {
        "platform",
        "cpu_name",
        "ram_gb",
        "gpu_name",
        "vram_gb",
        "disk_free_gb",
        "audited_at",
    }

    spec = _spec()
    assert spec.audited_at == datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    assert "2026-11-07T12:00:00" in spec.model_dump_json()
    assert SystemSpec.model_validate_json(spec.model_dump_json()) == spec


def test_game_requirements_defaults_to_null_and_tracks_unverified() -> None:
    empty = GameRequirements()
    assert empty.cpu_name is None
    assert empty.gpu_name is None
    assert empty.ram_gb is None
    assert empty.vram_gb is None
    assert empty.storage_gb is None
    assert empty.target_resolution is None
    assert empty.target_fps is None
    assert empty.unverified == set()

    parsed = GameRequirements(
        cpu_name="Intel Core i5-2300",
        ram_gb=8.0,
        storage_gb=30.0,
        target_resolution="720p",
        target_fps=30,
        unverified={ComponentName.GPU},
    )
    assert parsed.cpu_name == "Intel Core i5-2300"
    assert parsed.gpu_name is None
    assert parsed.unverified == {ComponentName.GPU}


def test_match_result_exposes_lookup_contract_fields() -> None:
    assert set(MatchResult.model_fields) == {
        "best_entry",
        "score_ratio",
        "alternatives",
        "matched_by",
    }

    best = BenchmarkEntry(id=4017, name="Intel Core i5-2300", score=3500.0, thread=1400.0)
    alternative = BenchmarkEntry(name="Intel Core i5-2320", score=3600.0)
    result = MatchResult(
        best_entry=best,
        score_ratio=0.93,
        alternatives=[alternative],
        matched_by="fuzzy",
    )

    assert result.best_entry is not None
    assert result.best_entry.name == "Intel Core i5-2300"
    assert result.best_entry.score == 3500.0
    assert result.score_ratio == pytest.approx(0.93)
    assert result.alternatives == [alternative]
    assert result.matched_by == "fuzzy"


def test_report_assembles_game_info_rows_and_verdict() -> None:
    verdict = scoring.build_verdict(1.2, 1.05)
    report = Report(
        game_name="Example Game",
        app_id=12345,
        components=[
            ComponentRow(
                component=ComponentName.CPU,
                user_value="Intel Core i5-10400",
                required_value="Intel Core i5-2300",
                ratio=1.2,
                confidence=0.95,
                matched_name="Intel Core i5-2300",
            ),
            ComponentRow(
                component=ComponentName.RAM,
                user_value="8.0 GB",
                required_value="8.0 GB",
                passed=True,
            ),
        ],
        verdict=verdict,
    )

    assert report.game_name == "Example Game"
    assert report.app_id == 12345
    assert [row.component for row in report.components] == [ComponentName.CPU, ComponentName.RAM]
    assert report.verdict is not None
    assert report.verdict.band is VerdictBand.PASS
    assert report.message is None


def test_report_supports_graceful_no_requirements_path() -> None:
    report = Report(
        game_name="Example Game",
        app_id=12345,
        message="No PC requirements published",
    )

    assert report.components == []
    assert report.verdict is None
    assert report.message == "No PC requirements published"


def test_cpu_and_gpu_ratios() -> None:
    assert scoring.cpu_ratio(12000.0, 8000.0) == pytest.approx(1.5)
    assert scoring.gpu_ratio(3000.0, 6000.0) == pytest.approx(0.5)
    assert scoring.component_ratio(9000.0, 10000.0) == pytest.approx(0.9)


def test_component_ratio_rejects_invalid_scores() -> None:
    with pytest.raises(ValueError, match="required benchmark score must be positive"):
        scoring.component_ratio(1000.0, 0.0)
    with pytest.raises(ValueError, match="user benchmark score must be non-negative"):
        scoring.component_ratio(-1.0, 1000.0)


def test_final_ratio_is_minimum_of_available_components() -> None:
    assert scoring.final_ratio(1.25, 0.8) == pytest.approx(0.8)
    assert scoring.final_ratio(0.8, 1.25) == pytest.approx(0.8)
    assert scoring.final_ratio(1.25, None) == pytest.approx(1.25)
    assert scoring.final_ratio(None, 0.8) == pytest.approx(0.8)
    assert scoring.final_ratio(None, None) is None


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (1.5, VerdictBand.PASS),
        (1.0, VerdictBand.PASS),
        (0.99, VerdictBand.BORDERLINE),
        (0.85, VerdictBand.BORDERLINE),
        (0.84, VerdictBand.POOR),
        (0.65, VerdictBand.POOR),
        (0.64, VerdictBand.UNPLAYABLE),
        (0.0, VerdictBand.UNPLAYABLE),
    ],
)
def test_status_band_boundaries(ratio: float, expected: VerdictBand) -> None:
    assert scoring.status_band(ratio) is expected


def test_display_percent_caps_at_one_hundred() -> None:
    assert scoring.display_percent(0.65) == pytest.approx(65.0)
    assert scoring.display_percent(0.84) == pytest.approx(84.0)
    assert scoring.display_percent(0.85) == pytest.approx(85.0)
    assert scoring.display_percent(0.99) == pytest.approx(99.0)
    assert scoring.display_percent(0.999) == pytest.approx(99.0)
    assert scoring.display_percent(1.0) == pytest.approx(100.0)
    assert scoring.display_percent(1.37) == pytest.approx(100.0)

    verdict = scoring.build_verdict(1.37, 2.0)
    assert verdict.band is VerdictBand.PASS
    assert verdict.display_percent == pytest.approx(100.0)
    assert verdict.percentage_text.startswith("100% of the game's minimum requirement")


def test_shortfall_caps_a_passing_verdict_at_fail() -> None:
    verdict = scoring.build_verdict(1.5, 1.25, shortfalls=[ComponentName.RAM])

    assert verdict.band is VerdictBand.FAIL
    assert verdict.spec_shortfall is True
    assert verdict.shortfall_components == [ComponentName.RAM]
    assert verdict.ratio == pytest.approx(1.25)
    assert verdict.display_percent == pytest.approx(100.0)
    assert "Fail (spec shortfall: RAM)" in verdict.percentage_text


def test_st_warning_only_when_multithread_cpu_passes() -> None:
    assert scoring.build_verdict(1.1, 1.0, st_ratio=0.69).st_warning is True
    assert scoring.build_verdict(1.1, 1.0, st_ratio=0.70).st_warning is False
    assert scoring.build_verdict(0.99, 1.0, st_ratio=0.10).st_warning is False
    assert scoring.build_verdict(1.1, 1.0, st_ratio=None).st_warning is False


def test_unverified_verdict_when_no_component_can_be_scored() -> None:
    verdict = scoring.build_verdict(None, None)

    assert verdict.band is VerdictBand.UNVERIFIED
    assert verdict.ratio is None
    assert verdict.display_percent == 0.0
    assert verdict.percentage_text == "unverified — manual review suggested"
    assert verdict.st_warning is False


def test_meets_minimum_and_minimum_shortfalls() -> None:
    assert scoring.meets_minimum(16.0, 16.0) is True
    assert scoring.meets_minimum(8.0, 16.0) is False
    assert scoring.meets_minimum(None, 16.0) is None
    assert scoring.meets_minimum(16.0, None) is None

    requirements = GameRequirements(ram_gb=16.0, vram_gb=2.0, storage_gb=150.0)
    assert scoring.minimum_shortfalls(_spec(), requirements) == [
        ComponentName.RAM,
        ComponentName.STORAGE,
    ]
    assert scoring.minimum_shortfalls(_spec(), GameRequirements()) == []


def _imported_roots(module: ModuleType) -> set[str]:
    path = module.__file__
    assert path is not None
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".")[0])
    return roots


def test_pure_modules_import_no_io_libraries() -> None:
    forbidden = {"requests", "typer", "psutil"}

    for module in (models, scoring):
        assert forbidden.isdisjoint(_imported_roots(module)), module.__name__
