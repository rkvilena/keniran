"""Offline end-to-end tests for the ``check_game`` pipeline service.

Steam is faked either through a fake fetcher satisfying
``steam.SteamRequirements`` or through the real adapter with
``requests.get`` monkeypatched against the recorded appdetails fixture.
Hardware is injected as a crafted ``SystemSpec`` and benchmark lookups run
against the committed mini fixture database. No test touches the network or
the live vendored databases.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_type_hints

import pytest

from keniran.adapters import steam
from keniran.adapters.llm.base import RequirementExtractor
from keniran.adapters.steam import SteamRequirements
from keniran.core import scoring
from keniran.core.models import (
    ComponentName,
    GameRequirements,
    Report,
    SystemSpec,
    VerdictBand,
)
from keniran.services.check_game import NO_REQUIREMENTS_MESSAGE, check_game

FIXTURES = Path(__file__).parent / "fixtures"
BENCHMARK_DB_PATH = FIXTURES / "benchmark_mini.json"
STEAM_FIXTURE_PATH = FIXTURES / "steam" / "appdetails_minimum.json"

APP_ID = 72850
AUDITED_AT = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def benchmark_db() -> dict[str, Any]:
    return json.loads(BENCHMARK_DB_PATH.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _isolated_steam_cache() -> Iterator[None]:
    """The adapter cache is process-local, so isolate it around every test."""
    steam.clear_cache()
    yield
    steam.clear_cache()


def _system_spec(
    *,
    cpu: str = "Intel Core i7-4770",
    ram_gb: float = 16.0,
    gpu: str = "GTX 1060 6GB",
    vram_gb: float | None = 6.0,
    disk_free_gb: float = 100.0,
) -> SystemSpec:
    return SystemSpec(
        platform="win32",
        cpu_name=cpu,
        ram_gb=ram_gb,
        gpu_name=gpu,
        vram_gb=vram_gb,
        disk_free_gb=disk_free_gb,
        audited_at=AUDITED_AT,
    )


def _requirements_html(
    *,
    cpu: str = "Intel Core i5-2300",
    gpu: str = "NVIDIA GeForce GTX 650 Ti, 2 GB VRAM",
    ram: str = "8 GB",
    storage: str = "30 GB",
) -> str:
    return (
        "<strong>Minimum:</strong><br><ul>"
        f"<li><strong>Processor:</strong> {cpu}</li>"
        f"<li><strong>Memory:</strong> {ram}</li>"
        f"<li><strong>Graphics:</strong> {gpu}</li>"
        f"<li><strong>Storage:</strong> {storage}</li>"
        "</ul>"
    )


def _fetcher(
    minimum_html: str,
    *,
    name: str = "Sample Game",
) -> Callable[[int], SteamRequirements]:
    def fetch(app_id: int) -> SteamRequirements:
        return SteamRequirements(app_id=app_id, name=name, minimum_html=minimum_html)

    return fetch


def _spec_loader(
    spec: SystemSpec,
    calls: list[bool] | None = None,
) -> Callable[..., SystemSpec]:
    def load(*, refresh: bool = False) -> SystemSpec:
        if calls is not None:
            calls.append(refresh)
        return spec

    return load


def _check(
    db: dict[str, Any],
    *,
    html: str | None = None,
    spec: SystemSpec | None = None,
    fetcher: Callable[[int], SteamRequirements] | None = None,
    calls: list[bool] | None = None,
    refresh_spec: bool = False,
) -> Report:
    minimum_html = html if html is not None else _requirements_html()
    return check_game(
        APP_ID,
        refresh_spec,
        fetch_steam=fetcher if fetcher is not None else _fetcher(minimum_html),
        load_spec=_spec_loader(spec if spec is not None else _system_spec(), calls),
        cpu_db=db,
        gpu_db=db,
    )


def test_pass_case_returns_full_green_report(benchmark_db: dict[str, Any]) -> None:
    report = _check(benchmark_db)

    assert report.game_name == "Sample Game"
    assert report.app_id == APP_ID
    assert report.message is None
    assert report.verdict is not None
    assert report.verdict.band is VerdictBand.PASS
    # The RAM ratio (16/8 = 2.0) is the bottleneck, below CPU and GPU ratios.
    assert report.verdict.ratio == pytest.approx(2.0)
    assert report.verdict.display_percent == 100.0
    assert report.verdict.spec_shortfall is False
    assert report.verdict.st_warning is False

    assert [row.component for row in report.components] == [
        ComponentName.CPU,
        ComponentName.GPU,
        ComponentName.RAM,
        ComponentName.VRAM,
        ComponentName.STORAGE,
    ]
    cpu_row, gpu_row, ram_row, vram_row, storage_row = report.components
    assert cpu_row.ratio == pytest.approx(9400.0 / 3420.0)
    assert cpu_row.matched_name == "Intel Core i5-2300 @ 2.80GHz"
    assert cpu_row.confidence == 1.0
    assert cpu_row.unverified is False
    assert gpu_row.ratio == pytest.approx(11083.0 / 1873.0)
    assert gpu_row.matched_name == "NVIDIA GeForce GTX 650 Ti"
    assert gpu_row.unverified is False
    assert ram_row.ratio == pytest.approx(16.0 / 8.0)
    assert ram_row.passed is None
    assert ram_row.unverified is False
    assert vram_row.ratio == pytest.approx(6.0 / 2.0)
    assert vram_row.passed is None
    assert vram_row.unverified is False
    assert storage_row.passed is True
    assert not any(row.unverified for row in report.components)


def test_storage_shortfall_caps_verdict_at_fail_and_ram_vram_join_ratio_min(
    benchmark_db: dict[str, Any],
) -> None:
    spec = _system_spec(ram_gb=8.0, vram_gb=2.0, disk_free_gb=10.0)
    html = _requirements_html(
        ram="16 GB",
        gpu="NVIDIA GeForce GTX 650 Ti, 4 GB VRAM",
        storage="50 GB",
    )

    report = _check(benchmark_db, html=html, spec=spec)

    assert report.verdict is not None
    assert report.verdict.ratio is not None
    # RAM/VRAM ratios (0.5 each) now join the bottleneck min; the storage
    # shortfall still caps the band at FAIL regardless.
    assert report.verdict.ratio == pytest.approx(0.5)
    assert report.verdict.band is VerdictBand.FAIL
    assert report.verdict.spec_shortfall is True
    assert set(report.verdict.shortfall_components) == {
        ComponentName.STORAGE,
    }

    rows = {row.component: row for row in report.components}
    # RAM/VRAM no longer hard-check: they are ratio rows folded into the
    # bottleneck min, and only storage remains a boolean shortfall.
    assert rows[ComponentName.RAM].ratio == pytest.approx(8.0 / 16.0)
    assert rows[ComponentName.RAM].passed is None
    assert rows[ComponentName.VRAM].ratio == pytest.approx(2.0 / 4.0)
    assert rows[ComponentName.VRAM].passed is None
    assert rows[ComponentName.STORAGE].passed is False


def test_system_spec_accepts_unknown_vram() -> None:
    spec = _system_spec(vram_gb=None)

    assert spec.vram_gb is None
    assert SystemSpec.model_validate(spec.model_dump(mode="json")) == spec


def test_unknown_user_vram_is_unverified_and_not_a_shortfall(
    benchmark_db: dict[str, Any],
) -> None:
    html = _requirements_html(gpu="NVIDIA GeForce GTX 650 Ti, 4 GB VRAM")
    spec = _system_spec(vram_gb=None)

    report = _check(benchmark_db, html=html, spec=spec)

    vram_row = next(row for row in report.components if row.component is ComponentName.VRAM)
    assert vram_row.passed is None
    assert vram_row.ratio is None
    assert vram_row.unverified is True
    assert vram_row.user_value == "unverified"
    assert vram_row.required_value == "4 GB"

    assert report.verdict is not None
    assert report.verdict.band is VerdictBand.PASS
    assert report.verdict.spec_shortfall is False
    assert ComponentName.VRAM not in report.verdict.shortfall_components

    requirements = GameRequirements(vram_gb=4.0)
    assert ComponentName.VRAM not in scoring.minimum_shortfalls(spec, requirements)
    assert scoring.minimum_shortfalls(_system_spec(vram_gb=2.0), requirements) == []


def test_generic_target_gpu_row_is_unverified_but_verdict_still_produced(
    benchmark_db: dict[str, Any],
) -> None:
    html = _requirements_html(gpu="DirectX 11 compatible card with 1 GB VRAM")

    report = _check(benchmark_db, html=html, spec=_system_spec(vram_gb=6.0))

    assert report.verdict is not None
    assert report.verdict.band is VerdictBand.PASS
    gpu_row = report.components[1]
    assert gpu_row.component is ComponentName.GPU
    assert gpu_row.unverified is True
    assert gpu_row.ratio is None
    assert gpu_row.matched_name is None
    assert gpu_row.confidence is None
    assert gpu_row.required_value == "unverified"

    vram_row = report.components[3]
    assert vram_row.component is ComponentName.VRAM
    # The published generic VRAM floor is 1 GB, so the ratio is 6/1.
    assert vram_row.ratio == pytest.approx(6.0 / 1.0)
    assert vram_row.unverified is False


def test_one_sided_user_cpu_lookup_marks_row_unverified(
    benchmark_db: dict[str, Any],
) -> None:
    report = _check(benchmark_db, spec=_system_spec(cpu="Apple M3 Ultra"))

    cpu_row = report.components[0]
    assert cpu_row.component is ComponentName.CPU
    assert cpu_row.user_value == "Apple M3 Ultra"
    assert cpu_row.unverified is True
    assert cpu_row.ratio is None
    assert report.verdict is not None
    # The GPU side is still scorable, so the verdict is not UNVERIFIED;
    # the RAM ratio (16/8 = 2.0) is the bottleneck.
    assert report.verdict.ratio == pytest.approx(2.0)


def test_below_gate_target_match_surfaces_name_and_confidence(
    benchmark_db: dict[str, Any],
) -> None:
    report = _check(benchmark_db, html=_requirements_html(cpu="AMD FX-6300 Six-Core"))

    cpu_row = report.components[0]
    assert cpu_row.unverified is False
    assert cpu_row.matched_name == "AMD FX-8350 Eight-Core @ 4.00GHz"
    assert cpu_row.confidence is not None
    assert cpu_row.confidence < 0.80
    assert cpu_row.ratio == pytest.approx(9400.0 / 6300.0)
    assert report.verdict is not None
    assert report.verdict.band is VerdictBand.PASS


def test_single_thread_warning_is_forwarded_to_verdict(
    benchmark_db: dict[str, Any],
) -> None:
    # High multi-thread score with a weak single-thread score: the MT ratio
    # passes, so the scoring rule flags the informational ST warning.
    db = {
        "data": [
            *benchmark_db["data"],
            {
                "id": "9001",
                "name": "Test High MT 9000",
                "cpumark": "12000",
                "thread": "600",
                "date": "Jan 2020",
                "cat": "Desktop",
                "cpuCount": 1,
                "samples": "10",
            },
        ]
    }

    report = _check(db, spec=_system_spec(cpu="Test High MT 9000"))

    assert report.verdict is not None
    assert report.verdict.band is VerdictBand.PASS
    assert report.verdict.st_warning is True


def test_steam_cache_serves_repeat_app_id_with_single_fetch(
    benchmark_db: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(STEAM_FIXTURE_PATH.read_text(encoding="utf-8"))
    calls: list[str] = []

    class _FakeResponse:
        status_code = 200

        def json(self) -> object:
            return payload

        def raise_for_status(self) -> None:
            """The fake response always represents a successful HTTP 200."""

    def fake_get(url: str, **kwargs: object) -> _FakeResponse:
        calls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(steam.requests, "get", fake_get)

    first = check_game(
        APP_ID,
        fetch_steam=steam.fetch,
        load_spec=_spec_loader(_system_spec()),
        cpu_db=benchmark_db,
        gpu_db=benchmark_db,
    )
    second = check_game(
        APP_ID,
        fetch_steam=steam.fetch,
        load_spec=_spec_loader(_system_spec()),
        cpu_db=benchmark_db,
        gpu_db=benchmark_db,
    )

    assert len(calls) == 1
    assert first.game_name == "The Elder Scrolls V: Skyrim"
    assert first == second


def test_no_requirements_published_returns_graceful_report(
    benchmark_db: dict[str, Any],
) -> None:
    def fetch(app_id: int) -> SteamRequirements:
        raise steam.NoRequirementsPublished(app_id)

    report = check_game(
        APP_ID,
        fetch_steam=fetch,
        load_spec=_spec_loader(_system_spec()),
        cpu_db=benchmark_db,
        gpu_db=benchmark_db,
    )

    assert report.message == NO_REQUIREMENTS_MESSAGE
    assert report.verdict is None
    assert report.components == []
    assert report.game_name == f"Steam app {APP_ID}"
    assert report.app_id == APP_ID


def test_steam_app_not_found_propagates(benchmark_db: dict[str, Any]) -> None:
    def fetch(app_id: int) -> SteamRequirements:
        raise steam.SteamAppNotFound(app_id)

    with pytest.raises(steam.SteamAppNotFound):
        check_game(
            APP_ID,
            fetch_steam=fetch,
            load_spec=_spec_loader(_system_spec()),
            cpu_db=benchmark_db,
            gpu_db=benchmark_db,
        )


@pytest.mark.parametrize("refresh_spec", [False, True])
def test_hardware_loader_called_once_with_refresh_flag(
    benchmark_db: dict[str, Any],
    refresh_spec: bool,
) -> None:
    calls: list[bool] = []

    report = _check(benchmark_db, calls=calls, refresh_spec=refresh_spec)

    assert calls == [refresh_spec]
    assert report.verdict is not None


def test_not_published_ram_leaves_unverified_row_excluded_from_min(
    benchmark_db: dict[str, Any],
) -> None:
    html = (
        "<strong>Minimum:</strong><br><ul>"
        "<li><strong>Processor:</strong> Intel Core i5-2300</li>"
        "<li><strong>Graphics:</strong> NVIDIA GeForce GTX 650 Ti</li>"
        "<li><strong>Storage:</strong> 30 GB</li>"
        "</ul>"
    )

    report = _check(benchmark_db, html=html)

    ram_row = next(row for row in report.components if row.component is ComponentName.RAM)
    assert ram_row.ratio is None
    assert ram_row.passed is None
    assert ram_row.unverified is True
    assert ram_row.required_value == "not published"
    assert ram_row.user_value == "16 GB"

    assert report.verdict is not None
    # The verdict is not UNVERIFIED: the RAM ratio is simply excluded from min.
    assert report.verdict.band is VerdictBand.PASS


def test_metaphor_style_vram_shortfall_yields_poor_verdict_end_to_end(
    benchmark_db: dict[str, Any],
) -> None:
    # Metaphor-style scenario: every other component clears the minimum
    # comfortably, but the 4 GB user VRAM against the published 6 GB minimum
    # becomes the bottleneck ratio (4/6 ≈ 0.667 → Poor, ~67%).
    html = _requirements_html(gpu="NVIDIA GeForce GTX 650 Ti, 6 GB VRAM")
    spec = _system_spec(vram_gb=4.0)

    report = _check(benchmark_db, html=html, spec=spec)

    vram_row = next(row for row in report.components if row.component is ComponentName.VRAM)
    assert vram_row.ratio == pytest.approx(4.0 / 6.0)
    assert vram_row.passed is None
    assert vram_row.unverified is False

    verdict = report.verdict
    assert verdict is not None
    assert verdict.ratio == pytest.approx(4.0 / 6.0)
    assert verdict.band is VerdictBand.POOR
    assert verdict.display_percent == pytest.approx(66.0)
    assert verdict.percentage_text is not None
    assert "66% of the game's minimum requirement" in verdict.percentage_text
    assert verdict.spec_shortfall is False


def test_requirement_extractor_protocol_matches_parser_output_schema() -> None:
    hints = get_type_hints(RequirementExtractor.extract)
    assert hints["text"] is str
    assert hints["return"] is GameRequirements

    class _StubExtractor:
        def extract(self, text: str) -> GameRequirements:
            return GameRequirements()

    assert isinstance(_StubExtractor(), RequirementExtractor)
