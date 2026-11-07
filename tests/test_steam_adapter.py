"""Offline tests for the Steam appdetails adapter (fetch + HTML strip).

All HTTP is monkeypatched; the fixtures are recorded appdetails payloads
(success path and "requirements absent" path). No test touches the network or
the disk cache - the adapter only has a process-local in-memory cache.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from keniran.adapters import steam

FIXTURES = Path(__file__).parent / "fixtures" / "steam"
SUCCESS_FIXTURE = FIXTURES / "appdetails_minimum.json"
MISSING_FIXTURE = FIXTURES / "appdetails_missing.json"
APP_ID = 72850
MISSING_APP_ID = 228980


class _FakeResponse:
    """Minimal stand-in for a ``requests.Response`` carrying a JSON payload."""

    status_code = 200

    def __init__(self, payload: object) -> None:
        self._payload = payload

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        """The fake response always represents a successful HTTP 200."""


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _install_response(monkeypatch: pytest.MonkeyPatch, payload: object) -> list[dict[str, Any]]:
    """Patch ``requests.get`` with a recorder and return the captured calls."""
    calls: list[dict[str, Any]] = []

    def fake_get(url: str, **kwargs: object) -> _FakeResponse:
        calls.append({"url": url, **kwargs})
        return _FakeResponse(payload)

    monkeypatch.setattr(steam.requests, "get", fake_get)
    return calls


@pytest.fixture(autouse=True)
def _isolated_cache() -> Iterator[None]:
    steam.clear_cache()
    yield
    steam.clear_cache()


def test_fetch_calls_appdetails_endpoint_with_spec_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_response(monkeypatch, _load(SUCCESS_FIXTURE))

    result = steam.fetch(APP_ID)

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://store.steampowered.com/api/appdetails"
    assert call["params"] == {"appids": str(APP_ID), "filters": "basic,pc_requirements"}
    headers = call["headers"]
    assert isinstance(headers, dict)
    assert "User-Agent" in headers
    assert result.app_id == APP_ID


def test_fetch_returns_name_and_raw_minimum_and_recommended_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load(SUCCESS_FIXTURE)
    expected = payload[str(APP_ID)]["data"]["pc_requirements"]
    _install_response(monkeypatch, payload)

    result = steam.fetch(APP_ID)

    assert result.name == "The Elder Scrolls V: Skyrim"
    assert result.minimum_html == expected["minimum"]
    assert result.recommended_html == expected["recommended"]
    assert "<strong>" in result.minimum_html


def test_fetch_caches_identical_app_id_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_response(monkeypatch, _load(SUCCESS_FIXTURE))

    first = steam.fetch(APP_ID)
    second = steam.fetch(APP_ID)

    assert first == second
    assert len(calls) == 1

    # Dropping the cache (new run) must re-fetch; nothing survives on disk.
    steam.clear_cache()
    steam.fetch(APP_ID)
    assert len(calls) == 2


def test_fetch_missing_requirements_raises_no_requirements_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_response(monkeypatch, _load(MISSING_FIXTURE))

    with pytest.raises(steam.NoRequirementsPublished) as excinfo:
        steam.fetch(MISSING_APP_ID)

    assert excinfo.value.app_id == MISSING_APP_ID


def test_fetch_unavailable_literal_raises_no_requirements_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load(SUCCESS_FIXTURE)
    payload[str(APP_ID)]["data"]["pc_requirements"]["minimum"] = "Unavailable"
    _install_response(monkeypatch, payload)

    with pytest.raises(steam.NoRequirementsPublished):
        steam.fetch(APP_ID)


def test_fetch_absent_pc_requirements_raises_no_requirements_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load(MISSING_FIXTURE)
    del payload[str(MISSING_APP_ID)]["data"]["pc_requirements"]
    _install_response(monkeypatch, payload)

    with pytest.raises(steam.NoRequirementsPublished):
        steam.fetch(MISSING_APP_ID)


def test_fetch_null_minimum_raises_no_requirements_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load(SUCCESS_FIXTURE)
    payload[str(APP_ID)]["data"]["pc_requirements"]["minimum"] = None
    _install_response(monkeypatch, payload)

    with pytest.raises(steam.NoRequirementsPublished):
        steam.fetch(APP_ID)


def test_fetch_success_false_raises_app_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_response(monkeypatch, {"999999": {"success": False}})

    with pytest.raises(steam.SteamAppNotFound):
        steam.fetch(999999)


def test_fetch_invalid_payload_raises_request_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_response(
        monkeypatch,
        {str(APP_ID): {"success": True, "data": {"pc_requirements": None}}},
    )

    with pytest.raises(steam.SteamRequestError):
        steam.fetch(APP_ID)


def test_strip_converts_br_and_li_to_line_breaks() -> None:
    html = (
        "<strong>Minimum:</strong><br>"
        "<ul><li><strong>OS:</strong> Windows 7</li>"
        "<li><strong>Processor:</strong> Intel Core i5-2300</li></ul>"
    )

    assert steam.strip_requirements_html(html) == (
        "Minimum:\nOS: Windows 7\nProcessor: Intel Core i5-2300"
    )


def test_strip_removes_nbsp_reg_and_trade_entities() -> None:
    html = "<li>NVIDIA&reg; GeForce&trade; GTX&nbsp;650 Ti</li>"

    assert steam.strip_requirements_html(html) == "NVIDIA GeForce GTX 650 Ti"


def test_strip_trims_trailing_copyright_and_legal_noise() -> None:
    payload = _load(SUCCESS_FIXTURE)
    html = payload[str(APP_ID)]["data"]["pc_requirements"]["minimum"]

    text = steam.strip_requirements_html(html)

    assert text.splitlines() == [
        "Minimum:",
        "OS: Windows 7/Vista/XP PC (32 or 64 bit)",
        "Processor: Dual Core 2.0 GHz or equivalent processor",
        "Memory: 2GB System RAM",
        "Hard Disk Space: 6GB free HDD Space",
        "Video Card: DirectX 9.0c compliant video card with 512 MB of RAM "
        "(NVIDIA GeForce 7600 GT / ATI Radeon X1600)",
        "Sound: DirectX compatible sound card",
        "Other Requirements: Internet access for Steam activation",
    ]
    assert "Bethesda" not in text
    assert "\u00a9" not in text
    assert "trademark" not in text.casefold()
    assert "&" not in text


def test_strip_trims_all_rights_reserved_trailer() -> None:
    html = "<li>Memory: 8 GB RAM</li><br>All rights reserved."

    assert steam.strip_requirements_html(html) == "Memory: 8 GB RAM"
