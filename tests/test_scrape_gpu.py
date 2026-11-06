"""Offline tests for ``scripts/scrape_gpu.py`` and the committed GPU database."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from keniran.adapters.benchmarks import lookup

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "scrape_gpu.py"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "gpu_list_sample.html"
DB_PATH = ROOT / "database" / "gpu_db.json"


def _load_scraper() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scrape_gpu_under_test", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRAPER = _load_scraper()


@pytest.fixture(scope="module")
def gpu_db() -> dict[str, Any]:
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def test_fixture_extracts_three_rows_and_coerces_integers() -> None:
    outcome = SCRAPER.parse_gpu_list_html(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert outcome.fetched == 6
    assert len(outcome.rows) >= 3
    assert outcome.skipped == 2
    assert outcome.skip_reasons["empty/NA g3d_mark"] == 2

    by_id = {row["id"]: row for row in outcome.rows}
    assert set(by_id) == {3342, 3566, 4086, 7777}

    row = by_id[3342]
    assert row["name"] == "NVIDIA GeForce GTX 1060 6GB"
    assert row["g3d_mark"] == 11083
    assert isinstance(row["g3d_mark"], int)
    assert row["samples"] == 1521
    assert isinstance(row["samples"], int)
    assert row["tdp"] == 120
    assert isinstance(row["tdp"], int)
    assert row["thread"] is None
    assert "id=3342" in row["href"]
    assert row["raw"] == {"rank": "88", "price": "$299.00"}


def test_fixture_cleans_entities_and_maps_na_markers_to_none() -> None:
    outcome = SCRAPER.parse_gpu_list_html(FIXTURE_PATH.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in outcome.rows}

    row = by_id[3566]
    assert row["name"] == "GeForce GTX 1060 3GB"
    assert row["g3d_mark"] == 8857
    assert row["samples"] is None
    assert row["tdp"] is None
    assert "&id=3566" in row["href"]

    unparsed = by_id[7777]
    assert unparsed["samples"] is None
    assert unparsed["tdp"] is None
    assert unparsed["raw"]["tdp"] == "30.5"
    assert "samples" not in unparsed["raw"]


def test_merge_enriches_list_rows_and_appends_mega_only_rows() -> None:
    html_entries = [
        {
            "id": 1,
            "name": "GeForce GTX 1060",
            "g3d_mark": 10012,
            "thread": None,
            "tdp": None,
            "samples": None,
            "href": "video_lookup.php?gpu=GeForce+GTX+1060&id=1",
            "raw": {"rank": "303"},
        }
    ]
    mega_entries = [
        {
            "id": 1,
            "name": "GeForce GTX 1060",
            "g3d_mark": 10013,
            "thread": None,
            "tdp": 120,
            "samples": 303,
            "href": "gpu.php?gpu=GeForce+GTX+1060&id=1",
            "raw": {"g2d": "100"},
        },
        {
            "id": 2,
            "name": "Mega Only Card",
            "g3d_mark": 5000,
            "thread": None,
            "tdp": 60,
            "samples": 12,
            "href": "gpu.php?gpu=Mega+Only+Card&id=2",
        },
    ]

    merged, duplicates = SCRAPER.merge_entries(html_entries, mega_entries)

    assert duplicates == 1
    assert [entry["id"] for entry in merged] == [1, 2]
    assert merged[0]["g3d_mark"] == 10012  # list-page score wins
    assert merged[0]["samples"] == 303
    assert merged[0]["tdp"] == 120
    assert merged[1]["g3d_mark"] == 5000


def test_dry_report_runs_offline(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = SCRAPER.main(["--dry-report", "--fixture", str(FIXTURE_PATH)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "rows fetched: 6" in captured.out
    assert "rows kept: 4" in captured.out
    assert "rows skipped: 2" in captured.out


def test_write_db_atomic_replaces_target_and_leaves_no_temp_files(tmp_path: Path) -> None:
    target = tmp_path / "gpu_db.json"
    target.write_text("stale", encoding="utf-8")
    payload = {
        "meta": {
            "source_url": SCRAPER.SOURCE_URL,
            "scraped_at": "2026-11-07",
            "entry_count": 1,
        },
        "data": [{"id": 1, "name": "Card", "g3d_mark": 100, "thread": None}],
    }

    SCRAPER.write_db_atomic(target, payload)

    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert list(tmp_path.iterdir()) == [target]


def test_committed_database_has_full_catalog(gpu_db: dict[str, Any]) -> None:
    meta = gpu_db["meta"]
    data = gpu_db["data"]

    assert meta["source_url"] == SCRAPER.SOURCE_URL
    assert meta["scraped_at"]
    assert meta["entry_count"] == len(data)
    assert meta["entry_count"] >= 3000
    assert all(isinstance(row["g3d_mark"], int) and row["g3d_mark"] > 0 for row in data)
    assert all(row["thread"] is None for row in data)


@pytest.mark.parametrize(
    ("name", "expected_fragment"),
    [
        ("NVIDIA GeForce GTX 1060 6GB", "1060"),
        ("AMD Radeon RX 580 8GB", "RX 580"),
    ],
)
def test_committed_database_passes_lookup_spot_checks(
    gpu_db: dict[str, Any],
    name: str,
    expected_fragment: str,
) -> None:
    result = lookup(gpu_db, name, kind="gpu")

    assert result.matched_by in {"exact", "fuzzy"}
    assert result.best_entry is not None
    assert result.best_entry.score is not None
    assert result.best_entry.score > 0
    assert expected_fragment.casefold() in result.best_entry.name.casefold()
