"""HON-001: placeholder-name detection and the lookup honesty gate."""

from __future__ import annotations

from typing import Any

import pytest

from keniran.adapters.benchmarks import _is_placeholder_name, has_model_number, lookup

GPU_DB: dict[str, Any] = {
    "data": [
        {
            "id": 9001,
            "name": "GeForce RTX 3080",
            "g3d_mark": 25000,
            "thread": None,
            "tdp": 320,
            "samples": 5000,
        },
        {
            # Probe-style row whose trailing "Device" token made "Device 008e"
            # a score-releasing best_guess before the honesty gate (WSL smoke).
            "id": 9002,
            "name": "AnyViewerIddDriver Device",
            "g3d_mark": 100,
            "thread": None,
            "tdp": None,
            "samples": 1,
        },
    ]
}


@pytest.mark.parametrize(
    "name",
    [
        "Device 008e",
        "device 008E",
        "Device 008e (R)",
        "008e",
        "0x25a2",
        "0x1234",
        "Unknown Device",
        "unknown",
    ],
)
def test_placeholder_shapes_are_detected(name: str) -> None:
    assert _is_placeholder_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "geforce rtx 3080",
        "ryzen 5 3600",
        "intel core i5-2300",
        "arc a380",
        "radeon rx 6600",
        "rx 6600",
        "gtx 1060 6gb",
        "3080",
    ],
)
def test_real_names_are_not_placeholders(name: str) -> None:
    assert _is_placeholder_name(name) is False


def test_placeholder_digits_still_pass_the_old_model_number_check() -> None:
    # Root-cause pin: digits alone let "Device 008e" through has_model_number,
    # so the placeholder gate must run before it inside lookup().
    assert has_model_number("Device 008e") is True


@pytest.mark.parametrize(
    "name",
    ["Device 008e", "008e", "0x25a2", "Unknown Device"],
)
def test_placeholder_names_never_release_scores(name: str) -> None:
    result = lookup(GPU_DB, name, kind="gpu")

    assert result.matched_by == "unverified"
    assert result.best_entry is None
    assert result.score_ratio is None
    assert result.alternatives == []


def test_ga102_bracket_cleanup_still_resolves_real_gpu() -> None:
    # LIN-002 cleanup output keeps resolving: only the placeholder shape is
    # gated, real digit-heavy names stay fuzzy/exact.
    result = lookup(GPU_DB, "GA102 [GeForce RTX 3080]", kind="gpu")

    assert result.matched_by in {"exact", "fuzzy"}
    assert result.best_entry is not None
    assert result.best_entry.name == "GeForce RTX 3080"
    assert result.best_entry.score == 25000.0
    assert result.score_ratio is not None
