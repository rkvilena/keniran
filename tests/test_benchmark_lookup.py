"""Unit tests for the Stage 0-4 benchmark lookup pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pytest

from keniran.adapters.benchmarks import (
    CONFIDENCE_GATE,
    has_model_number,
    lookup,
    normalize_name,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "benchmark_mini.json"


@pytest.fixture(scope="module")
def db() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_normalize_name_applies_stage_zero_rules() -> None:
    assert normalize_name("Intel(R) Core(TM) i5-2300 CPU @ 2.80GHz") == "intel core i5-2300"
    assert normalize_name("NVIDIA GeForce GTX 1060 6 GB") == "nvidia geforce gtx 1060 6gb"
    assert normalize_name("GTX 1060 6GB") == "geforce gtx 1060 6gb"
    assert normalize_name("AMD Radeon R9 280X or better") == "amd radeon r9 280x"
    assert normalize_name("AMD Radeon R9 280X or equivalent") == "amd radeon r9 280x"
    assert normalize_name("AMD 7900XTX+ 24GB") == "amd 7900xtx+ 24gb"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Intel Core i5-2300", True),
        ("NVIDIA GeForce GTX 1060 6GB", True),
        ("2.0 GHz quad-core", False),
        ("DX11-compatible card", False),
        ("64-bit quad-core processor", False),
    ],
)
def test_has_model_number_rule(name: str, expected: bool) -> None:
    assert has_model_number(name) is expected


def test_exact_hit_releases_cpu_scores(db: dict[str, Any]) -> None:
    result = lookup(db, "Intel Core i5-2300", kind="cpu")

    assert result.matched_by == "exact"
    assert result.score_ratio == 1.0
    assert result.best_entry is not None
    assert result.best_entry.name == "Intel Core i5-2300 @ 2.80GHz"
    assert result.best_entry.score == 3420.0
    assert result.best_entry.thread == 1428.0


def test_exact_hit_ignores_noise_tokens(db: dict[str, Any]) -> None:
    result = lookup(db, "Intel(R) Core(TM) i5-2300 CPU @ 2.80GHz", kind="cpu")

    assert result.matched_by == "exact"
    assert result.best_entry is not None
    assert result.best_entry.id == "788"


def test_fuzzy_hit_uses_shared_token_tiebreak(db: dict[str, Any]) -> None:
    # Both "GTX 650" (5000 samples) and "GTX 650 Ti Boost" (100 samples) are
    # token-set subsets of the input, so both score 1.0. The shared-token
    # tiebreak must beat the higher-sample Stage 3 fallback.
    result = lookup(db, "NVIDIA GeForce GTX 650 Ti Boost OC Edition", kind="gpu")

    assert result.matched_by == "fuzzy"
    assert result.score_ratio == 1.0
    assert result.best_entry is not None
    assert result.best_entry.name == "NVIDIA GeForce GTX 650 Ti Boost"
    assert result.best_entry.samples == 100


def test_exact_duplicate_prefers_single_socket_cpu(db: dict[str, Any]) -> None:
    result = lookup(db, "Intel Xeon E5-2670", kind="cpu")

    assert result.matched_by == "exact"
    assert result.best_entry is not None
    assert result.best_entry.id == "5002"
    assert result.best_entry.score == 8500.0
    assert [entry.score for entry in result.alternatives] == [12000.0]


def test_cpu_disambiguation_prefers_desktop_newest_and_samples(db: dict[str, Any]) -> None:
    # Rows: cpuCount==2 Desktop 2014, cpuCount==1 Laptop 2021,
    # cpuCount==1 Desktop 2013, and two cpuCount==1 Desktop Feb 2014 rows
    # (300 vs 2000 samples). Only the full Stage 3 order reaches 6005.
    result = lookup(db, "Intel Core i7-4770", kind="cpu")

    assert result.best_entry is not None
    assert result.best_entry.id == "6005"
    assert result.best_entry.score == 9400.0


def test_gpu_vram_suffix_selects_gtx_1060_variant(db: dict[str, Any]) -> None:
    six_gb = lookup(db, "GTX 1060 6GB", kind="gpu")
    assert six_gb.best_entry is not None
    assert six_gb.best_entry.name == "NVIDIA GeForce GTX 1060 6GB"
    assert six_gb.best_entry.score == 11083.0
    assert six_gb.best_entry.thread is None

    three_gb = lookup(db, "GTX 1060 3GB", kind="gpu")
    assert three_gb.best_entry is not None
    assert three_gb.best_entry.name == "NVIDIA GeForce GTX 1060 3GB"
    assert three_gb.best_entry.score == 8857.0


def test_gpu_without_vram_suffix_uses_highest_samples(db: dict[str, Any]) -> None:
    result = lookup(db, "GTX 1060", kind="gpu")

    assert result.best_entry is not None
    assert result.best_entry.name == "NVIDIA GeForce GTX 1060 6GB"


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("2.0 GHz quad-core", "cpu"),
        ("DX11-compatible card", "gpu"),
    ],
)
def test_generic_text_is_unverified(
    db: dict[str, Any],
    name: str,
    kind: Literal["cpu", "gpu"],
) -> None:
    result = lookup(db, name, kind=kind)

    assert result.best_entry is None
    assert result.score_ratio is None
    assert result.alternatives == []
    assert result.matched_by == "unverified"


def test_below_gate_target_returns_best_guess_with_confidence(db: dict[str, Any]) -> None:
    result = lookup(db, "AMD FX-6300 Six-Core", kind="cpu")

    assert result.best_entry is not None
    assert result.best_entry.name == "AMD FX-8350 Eight-Core @ 4.00GHz"
    assert result.score_ratio is not None
    assert 0.0 < result.score_ratio < CONFIDENCE_GATE
    assert result.matched_by == "best_guess"


def test_no_match_returns_null_score(db: dict[str, Any]) -> None:
    result = lookup(db, "Apple M3 Ultra", kind="cpu")

    assert result.best_entry is None
    assert result.score_ratio is None
    assert result.alternatives == []
    assert result.matched_by == "none"


def test_na_benchmark_values_release_as_null_never_zero(db: dict[str, Any]) -> None:
    result = lookup(db, "Intel Xeon E-2288G ES", kind="cpu")

    assert result.matched_by == "exact"
    assert result.best_entry is not None
    assert result.best_entry.score is None
    assert result.best_entry.thread is None
    assert result.best_entry.samples is None
