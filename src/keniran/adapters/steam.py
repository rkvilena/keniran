"""Steam store ``appdetails`` adapter: fetch plus HTML-to-text preparation.

Covers Step A (fetch) and Step B (strip/normalize) of
``plan/detailed-flow.md``. Responses are validated with pydantic, the minimum
requirements block is returned as raw HTML, and
:func:`strip_requirements_html` converts it into the labeled text consumed by
the rule-based parser.

Only an in-memory, per-run response cache is used - nothing is written to
disk (``plan/decisions.md`` section 6).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Final

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, RootModel, ValidationError, field_validator

STEAM_APPDETAILS_URL: Final = "https://store.steampowered.com/api/appdetails"
APPDETAILS_FILTERS: Final = "basic,pc_requirements"
REQUEST_TIMEOUT_SECONDS: Final = 10.0
RETRY_ATTEMPTS: Final = 3
RETRY_BACKOFF_SECONDS: Final = 0.5

_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
}

# BeautifulSoup already decodes entities to Unicode; the regex additionally
# catches literal entity text from double-escaped payloads.
_ENTITY_RE: Final = re.compile(r"&(?:nbsp|reg|trade|copy);", re.IGNORECASE)
_WHITESPACE_RE: Final = re.compile(r"[ \t]+")
_LEGAL_LINE_RE: Final = re.compile(
    r"^(?:\u00a9|\(c\)|copyright\b)"
    r"|\ball rights reserved\b"
    r"|\bregistered trademarks?\b"
    r"|\btrademarks? (?:and/or|or) registered trademarks?\b"
    r"|\bEULA\b"
    r"|^requires? (?:agreement|acceptance)"
    r"|^all trademarks\b",
    re.IGNORECASE,
)
_DECODED_ENTITIES: Final[dict[str, str]] = {
    "\u00a0": " ",
    "\u00ae": " ",
    "\u2122": " ",
}


class SteamAdapterError(Exception):
    """Base class for Steam adapter failures."""


class SteamRequestError(SteamAdapterError):
    """The appdetails request failed or returned an unusable payload."""


class SteamAppNotFound(SteamAdapterError):
    """Steam reported ``success: false`` for the requested app id."""

    def __init__(self, app_id: int) -> None:
        self.app_id = app_id
        super().__init__(f"Steam app {app_id} was not found")


class NoRequirementsPublished(SteamAdapterError):
    """Steam has no published minimum PC requirements (spec section 4.1).

    The service layer maps this exception to a graceful "No PC requirements
    published" message rather than treating it as a failure.
    """

    def __init__(self, app_id: int) -> None:
        self.app_id = app_id
        super().__init__(f"No PC requirements published for Steam app {app_id}")


class _PCRequirementsPayload(BaseModel):
    """The ``pc_requirements`` object of a Steam appdetails response."""

    model_config = ConfigDict(extra="ignore")

    minimum: str | None = None
    recommended: str | None = None


class _AppDataPayload(BaseModel):
    """The ``data`` object of a Steam appdetails response."""

    model_config = ConfigDict(extra="ignore")

    name: str
    pc_requirements: _PCRequirementsPayload | None = None

    @field_validator("pc_requirements", mode="before")
    @classmethod
    def _empty_list_means_missing(cls, value: object) -> object:
        """Steam sends ``[]`` instead of ``null`` when requirements are absent."""
        if isinstance(value, list) and not value:
            return None
        return value


class _AppDetailsEntry(BaseModel):
    """One app id entry: a ``success`` flag plus optional ``data``."""

    model_config = ConfigDict(extra="ignore")

    success: bool
    data: _AppDataPayload | None = None


class _AppDetailsResponse(RootModel[dict[str, _AppDetailsEntry]]):
    """Top-level appdetails payload: ``{"<appid>": {...}}``."""


@dataclass(frozen=True, slots=True)
class SteamRequirements:
    """Raw requirements payload for one Steam app.

    ``minimum_html`` and ``recommended_html`` are the HTML fragments exactly as
    Steam published them; call :func:`strip_requirements_html` before parsing.
    """

    app_id: int
    name: str
    minimum_html: str
    recommended_html: str | None = None


_FETCH_CACHE: dict[int, SteamRequirements] = {}


def clear_cache() -> None:
    """Drop the process-local appdetails cache (tests and repeat runs only)."""
    _FETCH_CACHE.clear()


def fetch(app_id: int) -> SteamRequirements:
    """Fetch a game's name and raw minimum-requirements HTML from Steam.

    Successful responses are cached in memory for the rest of the process, so
    requesting the same app id twice performs only one HTTP call and nothing
    ever touches the disk (``plan/decisions.md`` section 6).

    Raises :class:`NoRequirementsPublished` when Steam publishes no minimum
    requirements (missing block, null/empty text, or ``"Unavailable"``) so the
    service layer can render a graceful message instead of an error.
    """
    if isinstance(app_id, bool) or not isinstance(app_id, int) or app_id <= 0:
        msg = f"invalid Steam app id: {app_id!r}"
        raise ValueError(msg)

    cached = _FETCH_CACHE.get(app_id)
    if cached is not None:
        return cached

    payload = _request_json(
        STEAM_APPDETAILS_URL,
        {"appids": str(app_id), "filters": APPDETAILS_FILTERS},
    )
    entry = _parse_entry(app_id, payload)

    if not entry.success:
        raise SteamAppNotFound(app_id)
    data = entry.data
    if data is None:
        msg = f"Steam response for app {app_id} has no data"
        raise SteamRequestError(msg)

    requirements = data.pc_requirements
    minimum = requirements.minimum if requirements is not None else None
    if minimum is None or not minimum.strip() or minimum.strip().casefold() == "unavailable":
        raise NoRequirementsPublished(app_id)

    result = SteamRequirements(
        app_id=app_id,
        name=data.name,
        minimum_html=minimum,
        recommended_html=requirements.recommended if requirements is not None else None,
    )
    _FETCH_CACHE[app_id] = result
    return result


def strip_requirements_html(html_text: str) -> str:
    """Convert Steam's requirements HTML into normalized labeled text.

    ``<br>`` and ``<li>`` become line breaks, HTML entities (``&nbsp;``,
    ``&reg;``, ``&trade;``) are removed, blank lines collapse, and trailing
    copyright/legal boilerplate is dropped (Step B of ``plan/detailed-flow.md``).
    """
    soup = BeautifulSoup(html_text, "lxml")
    for tag in soup.find_all(["br", "li"]):
        tag.insert_before("\n")

    text = soup.get_text()
    text = _ENTITY_RE.sub(" ", text)
    for character, replacement in _DECODED_ENTITIES.items():
        text = text.replace(character, replacement)

    lines: list[str] = []
    for raw_line in text.splitlines():
        line = _WHITESPACE_RE.sub(" ", raw_line).strip()
        if line:
            lines.append(line)

    while lines and _LEGAL_LINE_RE.search(lines[-1]):
        lines.pop()
    return "\n".join(lines)


def _request_json(url: str, params: dict[str, str]) -> object:
    """GET *url* and decode JSON, retrying transient failures with backoff."""
    last_error: Exception | None = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=_HEADERS,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    msg = f"Steam appdetails request failed after {RETRY_ATTEMPTS} attempts"
    raise SteamRequestError(msg) from last_error


def _parse_entry(app_id: int, payload: object) -> _AppDetailsEntry:
    """Validate the appdetails payload and return the entry for *app_id*."""
    try:
        response = _AppDetailsResponse.model_validate(payload)
    except ValidationError as exc:
        msg = f"Steam returned an invalid appdetails payload for app {app_id}"
        raise SteamRequestError(msg) from exc

    entry = response.root.get(str(app_id))
    if entry is None:
        msg = f"Steam response did not contain app id {app_id}"
        raise SteamRequestError(msg)
    return entry
