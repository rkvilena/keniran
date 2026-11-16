"""Build ``src/keniran/database/gpu_db.json`` from PassMark's public GPU list.

The canonical entry point is
``https://www.videocardbenchmark.net/gpu_list.html``. As of the 2026 site
revision that URL returns 404; the live equivalent is ``gpu_list.php``. The
list page is parsed with BeautifulSoup. That page omits the sample-count/TDP
columns and a couple of hundred rows, so PassMark's own "Video Card Mega List"
dataset (``/data``, the backend for ``GPU_mega_page.html``) supplies those
fields. The combined result is written atomically to the packaged
``src/keniran/database/gpu_db.json`` (shipped as package data); the raw list
HTML is cached under ``.cache/gpu_list.html`` for offline debugging.

Run manually: ``python scripts/scrape_gpu.py``.
Offline fixture check: ``python scripts/scrape_gpu.py --dry-report``.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = REPO_ROOT / "src" / "keniran" / "database" / "gpu_db.json"
CACHE_PATH = REPO_ROOT / ".cache" / "gpu_list.html"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "gpu_list_sample.html"

SOURCE_URL = "https://www.videocardbenchmark.net/gpu_list.html"
LIST_FALLBACK_URL = "https://www.videocardbenchmark.net/gpu_list.php"
MEGA_PAGE_URL = "https://www.videocardbenchmark.net/GPU_mega_page.html"
MEGA_DATA_URL = "https://www.videocardbenchmark.net/data"

DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
JSON_ACCEPT_HEADER = "application/json, text/javascript, */*; q=0.01"

REQUEST_TIMEOUT = 30.0
MAX_ATTEMPTS = 3
MAX_PAGES = 50

NA_MARKERS = frozenset({"", "na", "n/a", "nan", "unknown", "-", "insufficient data"})
ID_RE = re.compile(r"[?&](?:amp;)?id=(\d+)")
PAGE_QUERY_RE = re.compile(r"[?&](?:amp;)?page=\d+")
INT_RE = re.compile(r"[+-]?\d+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

MEGA_MAPPED_FIELDS = frozenset({"id", "name", "g3d", "tdp", "samples", "href"})


class ScrapeError(RuntimeError):
    """Raised when the GPU list cannot be fetched or parsed."""


@dataclass
class ParseOutcome:
    """Rows parsed from one source plus the counts shown in the report."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    fetched: int = 0
    skipped: int = 0
    skip_reasons: Counter[str] = field(default_factory=Counter)


@dataclass
class ScrapeSummary:
    """End-to-end scrape counters used by the console report."""

    html_fetched: int = 0
    html_kept: int = 0
    html_skipped: int = 0
    mega_fetched: int = 0
    mega_kept: int = 0
    mega_skipped: int = 0
    duplicates: int = 0

    @property
    def fetched(self) -> int:
        return self.html_fetched + self.mega_fetched

    @property
    def kept(self) -> int:
        return self.html_kept + self.mega_kept - self.duplicates

    @property
    def skipped(self) -> int:
        return self.html_skipped + self.mega_skipped


def main(argv: Sequence[str] | None = None) -> int:
    """Run the scraper or the offline fixture report."""
    args = _parse_args(argv)

    if args.dry_report:
        return _run_dry_report(args.fixture)

    return _run_scrape(args.output)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build src/keniran/database/gpu_db.json from PassMark's GPU list.",
    )
    parser.add_argument(
        "--dry-report",
        action="store_true",
        help=(
            "Parse the committed fixture HTML offline and print the report (no network, no write)."
        ),
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=FIXTURE_PATH,
        help=f"HTML fragment used by --dry-report (default: {FIXTURE_PATH}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATABASE_PATH,
        help=f"Database path to write (default: {DATABASE_PATH}).",
    )
    return parser.parse_args(argv)


def _run_dry_report(fixture: Path) -> int:
    try:
        html_text = fixture.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read fixture {fixture}: {exc}", file=sys.stderr)
        return 1

    try:
        outcome = parse_gpu_list_html(html_text)
    except ScrapeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _print_report(
        source=str(fixture),
        fetched=outcome.fetched,
        kept=len(outcome.rows),
        skipped=outcome.skipped,
        skip_reasons=outcome.skip_reasons,
    )
    return 0


def _run_scrape(output: Path) -> int:
    session = requests.Session()
    session.headers.update({"User-Agent": DESKTOP_USER_AGENT})

    try:
        pages = fetch_list_pages(session)
        html_outcome = parse_pages(pages)
        mega_outcome = fetch_mega_rows(session)
        entries, duplicates = merge_entries(html_outcome.rows, mega_outcome.rows)
        payload = build_payload(entries)
        write_db_atomic(output, payload)
    except (ScrapeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    summary = ScrapeSummary(
        html_fetched=html_outcome.fetched,
        html_kept=len(html_outcome.rows),
        html_skipped=html_outcome.skipped,
        mega_fetched=mega_outcome.fetched,
        mega_kept=len(mega_outcome.rows),
        mega_skipped=mega_outcome.skipped,
        duplicates=duplicates,
    )
    _print_report(
        source=SOURCE_URL,
        fetched=summary.fetched,
        kept=summary.kept,
        skipped=summary.skipped,
        skip_reasons=html_outcome.skip_reasons + mega_outcome.skip_reasons,
        output=output,
        details=[
            (
                f"html list: {summary.html_fetched} fetched / "
                f"{summary.html_kept} kept / {summary.html_skipped} skipped"
            ),
            (
                f"mega list: {summary.mega_fetched} fetched / "
                f"{summary.mega_kept} kept / {summary.mega_skipped} skipped"
            ),
            f"duplicate rows merged: {summary.duplicates}",
        ],
    )
    return 0


def _print_report(
    *,
    source: str,
    fetched: int,
    kept: int,
    skipped: int,
    skip_reasons: Mapping[str, int] | None = None,
    output: Path | None = None,
    details: Sequence[str] = (),
) -> None:
    print("GPU database report")
    print(f"  source: {source}")
    for detail in details:
        print(f"  note: {detail}")
    print(f"  rows fetched: {fetched}")
    print(f"  rows kept: {kept}")
    print(f"  rows skipped: {skipped}")
    if skip_reasons:
        reasons = ", ".join(
            f"{reason} ({count})" for reason, count in Counter(skip_reasons).most_common()
        )
        print(f"  skip detail: {reasons}")
    if output is not None:
        print(f"  wrote: {output}")
    sys.stdout.flush()


def _request_with_retries(
    session: requests.Session,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    attempts: int = MAX_ATTEMPTS,
    timeout: float = REQUEST_TIMEOUT,
) -> requests.Response:
    """GET *url*, retrying transient failures with exponential backoff.

    4xx responses other than 429 are returned to the caller immediately (the
    list-page fallback relies on seeing the 404).
    """
    delay = 1.0
    last_problem = "unknown error"

    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last_problem = str(exc)
        else:
            if response.status_code != 429 and response.status_code < 500:
                return response
            last_problem = f"HTTP {response.status_code}"

        if attempt < attempts:
            time.sleep(delay)
            delay *= 2

    msg = f"failed to fetch {url} after {attempts} attempts: {last_problem}"
    raise ScrapeError(msg)


def fetch_list_pages(session: requests.Session) -> list[tuple[str, str]]:
    """Fetch the GPU list and any linked pagination pages, caching the last page."""
    response = _request_with_retries(session, SOURCE_URL)
    actual_url = response.url

    if response.status_code == 404:
        print(
            f"warning: {SOURCE_URL} returned 404; using {LIST_FALLBACK_URL}",
            file=sys.stderr,
        )
        response = _request_with_retries(session, LIST_FALLBACK_URL)
        actual_url = response.url

    if response.status_code >= 400:
        msg = f"{actual_url} returned HTTP {response.status_code}"
        raise ScrapeError(msg)

    pages: list[tuple[str, str]] = [(actual_url, response.text)]
    visited = {actual_url}
    queue: deque[tuple[str, str]] = deque(pages)

    while queue and len(pages) < MAX_PAGES:
        page_url, page_html = queue.popleft()
        for link in _pagination_links(page_html, page_url):
            if link in visited or len(pages) >= MAX_PAGES:
                continue
            visited.add(link)
            follow = _request_with_retries(session, link)
            if follow.status_code >= 400:
                msg = f"pagination page {link} returned HTTP {follow.status_code}"
                raise ScrapeError(msg)
            pages.append((follow.url, follow.text))
            queue.append((follow.url, follow.text))

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(pages[-1][1], encoding="utf-8")
    return pages


def _pagination_links(html_text: str, current_url: str) -> list[str]:
    """Return same-host links carrying an explicit ``page=N`` query parameter."""
    soup = BeautifulSoup(html_text, "lxml")
    links: list[str] = []
    current_host = urlparse(current_url).netloc

    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        if not PAGE_QUERY_RE.search(href):
            continue
        absolute = urljoin(current_url, href)
        if urlparse(absolute).netloc != current_host:
            continue
        if absolute not in links:
            links.append(absolute)

    return links


def parse_pages(pages: Sequence[tuple[str, str]]) -> ParseOutcome:
    """Parse every fetched list page, dropping duplicate ids across pages."""
    combined = ParseOutcome()
    seen_ids: set[int] = set()

    for _url, html_text in pages:
        outcome = parse_gpu_list_html(html_text)
        combined.fetched += outcome.fetched
        combined.skipped += outcome.skipped
        combined.skip_reasons.update(outcome.skip_reasons)

        for row in outcome.rows:
            identifier = row["id"]
            if identifier in seen_ids:
                combined.skipped += 1
                combined.skip_reasons["duplicate id across pages"] += 1
                continue
            seen_ids.add(identifier)
            combined.rows.append(row)

    return combined


def parse_gpu_list_html(html_text: str) -> ParseOutcome:
    """BeautifulSoup the PassMark GPU table fragment into database rows."""
    soup = BeautifulSoup(html_text, "lxml")
    table = _find_gpu_table(soup)
    if table is None:
        msg = "could not locate the GPU results table (expected table#cputable)"
        raise ScrapeError(msg)

    headers = _table_headers(table)
    mapping = _header_map(headers)
    name_index = mapping["name"]
    g3d_index = mapping["g3d"]
    samples_index = mapping.get("samples")
    tdp_index = mapping.get("tdp")
    known_indices = set(mapping.values())

    outcome = ParseOutcome()

    for row in _body_rows(table):
        outcome.fetched += 1
        cells = row.find_all("td")
        if not cells:
            _skip(outcome, "missing cells")
            continue

        name = _cell_text(cells, name_index)
        if not name:
            _skip(outcome, "empty name")
            continue

        href, identifier = _extract_id(cells, name_index)
        if identifier is None:
            _skip(outcome, "missing id in href")
            continue

        g3d_raw = _cell_text(cells, g3d_index)
        g3d_mark = parse_int(g3d_raw)
        if g3d_mark is None:
            _skip(outcome, "empty/NA g3d_mark")
            continue

        tdp_raw = _cell_text(cells, tdp_index)
        samples_raw = _cell_text(cells, samples_index)
        tdp = parse_int(tdp_raw)
        samples = parse_int(samples_raw)

        entry: dict[str, Any] = {
            "id": identifier,
            "name": name,
            "g3d_mark": g3d_mark,
            "thread": None,
            "tdp": tdp,
            "samples": samples,
            "href": href,
        }

        raw = _raw_columns(cells, headers, known_indices)
        if tdp is None and _is_unparsed_marker(tdp_raw):
            raw["tdp"] = tdp_raw
        if samples is None and _is_unparsed_marker(samples_raw):
            raw["samples"] = samples_raw
        if raw:
            entry["raw"] = raw

        outcome.rows.append(entry)

    return outcome


def _find_gpu_table(soup: BeautifulSoup) -> Tag | None:
    table = soup.find("table", id="cputable")
    if isinstance(table, Tag):
        return table

    table = soup.find("table", class_="cpulist")
    if isinstance(table, Tag):
        return table

    for candidate in soup.find_all("table"):
        text = candidate.get_text(" ", strip=True).casefold()
        if "g3d mark" in text and ("videocard name" in text or "card name" in text):
            return candidate

    return None


def _table_headers(table: Tag) -> list[str]:
    header_row: Tag | None = None
    thead = table.find("thead")
    if isinstance(thead, Tag):
        candidate = thead.find("tr")
        if isinstance(candidate, Tag):
            header_row = candidate

    if header_row is None:
        for row in table.find_all("tr"):
            if row.find("th") is not None:
                header_row = row
                break

    if header_row is None:
        return []

    cells = header_row.find_all(["th", "td"])
    return [_clean_text(cell.get_text(" ", strip=True)) for cell in cells]


def _body_rows(table: Tag) -> list[Tag]:
    tbody = table.find("tbody")
    if isinstance(tbody, Tag):
        return tbody.find_all("tr")
    return [row for row in table.find_all("tr") if row.find("th") is None]


def _header_map(headers: Sequence[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}

    for index, header in enumerate(headers):
        text = header.casefold()
        if "name" not in mapping and (
            "videocard name" in text
            or "card name" in text
            or "gpu name" in text
            or "videocard" in text
        ):
            mapping["name"] = index
        elif "g3d" in text and "mark" in text and "value" not in text and "price" not in text:
            mapping.setdefault("g3d", index)
        elif "sample" in text:
            mapping.setdefault("samples", index)
        elif "tdp" in text or "thermal design" in text:
            mapping.setdefault("tdp", index)

    mapping.setdefault("name", 0)
    mapping.setdefault("g3d", 1)
    return mapping


def _cell_text(cells: Sequence[Tag], index: int | None) -> str:
    if index is None or index >= len(cells):
        return ""
    return _clean_text(cells[index].get_text(" ", strip=True))


def _extract_id(cells: Sequence[Tag], name_index: int) -> tuple[str, int | None]:
    ordered: list[Tag] = []
    if name_index < len(cells):
        ordered.append(cells[name_index])
    ordered.extend(cell for index, cell in enumerate(cells) if index != name_index)

    for cell in ordered:
        for anchor in cell.find_all("a", href=True):
            href = html_lib.unescape(str(anchor["href"]))
            match = ID_RE.search(href)
            if match:
                return href, int(match.group(1))

    return "", None


def _raw_columns(
    cells: Sequence[Tag],
    headers: Sequence[str],
    known_indices: set[int],
) -> dict[str, str]:
    raw: dict[str, str] = {}
    for index, cell in enumerate(cells):
        if index in known_indices:
            continue
        value = _clean_text(cell.get_text(" ", strip=True))
        if not value:
            continue
        key = _raw_key(headers[index]) if index < len(headers) else f"column_{index}"
        raw[_unique_key(raw, key)] = value
    return raw


def _raw_key(header: str) -> str:
    base = re.split(r"[([]", header, maxsplit=1)[0]
    key = NON_ALNUM_RE.sub("_", base.casefold()).strip("_")
    return key or "extra"


def _unique_key(mapping: Mapping[str, Any], key: str) -> str:
    if key not in mapping:
        return key
    suffix = 2
    while f"{key}_{suffix}" in mapping:
        suffix += 1
    return f"{key}_{suffix}"


def fetch_mega_rows(session: requests.Session) -> ParseOutcome:
    """Fetch the multi-column Mega List dataset used for samples/TDP columns.

    ``/data`` is the JSON backend of ``GPU_mega_page.html``. The page must be
    loaded first in the same session; a cold session receives an empty list.
    """
    warmup = _request_with_retries(session, MEGA_PAGE_URL)
    if warmup.status_code >= 400:
        msg = f"{MEGA_PAGE_URL} returned HTTP {warmup.status_code}"
        raise ScrapeError(msg)

    response = _request_with_retries(
        session,
        MEGA_DATA_URL,
        headers={
            "Accept": JSON_ACCEPT_HEADER,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": MEGA_PAGE_URL,
        },
    )
    if response.status_code >= 400:
        msg = f"{MEGA_DATA_URL} returned HTTP {response.status_code}"
        raise ScrapeError(msg)

    try:
        payload = response.json()
    except ValueError as exc:
        msg = f"{MEGA_DATA_URL} did not return JSON: {exc}"
        raise ScrapeError(msg) from exc

    rows = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        msg = f"{MEGA_DATA_URL} payload has no data list"
        raise ScrapeError(msg)

    return parse_mega_rows(rows)


def parse_mega_rows(rows: Sequence[Any]) -> ParseOutcome:
    outcome = ParseOutcome()

    for row in rows:
        outcome.fetched += 1
        if not isinstance(row, Mapping):
            _skip(outcome, "non-object mega row")
            continue

        entry, reason = _mega_entry(row)
        if entry is None:
            _skip(outcome, reason)
            continue

        outcome.rows.append(entry)

    return outcome


def _mega_entry(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    identifier = parse_int(str(row.get("id", "")))
    name = _clean_text(str(row.get("name", "")))
    g3d_mark = parse_int(str(row.get("g3d", "")))

    if identifier is None:
        return None, "missing mega id"
    if not name:
        return None, "empty mega name"
    if g3d_mark is None:
        return None, "empty/NA mega g3d_mark"

    tdp_raw = _raw_string(row.get("tdp"))
    samples_raw = _raw_string(row.get("samples"))
    tdp = parse_int(tdp_raw)
    samples = parse_int(samples_raw)

    entry: dict[str, Any] = {
        "id": identifier,
        "name": name,
        "g3d_mark": g3d_mark,
        "thread": None,
        "tdp": tdp,
        "samples": samples,
        "href": _mega_href(row.get("href")),
    }

    raw: dict[str, str] = {}
    for key, value in row.items():
        if key in MEGA_MAPPED_FIELDS or value is None or isinstance(value, bool):
            continue
        text_value = _clean_text(str(value))
        if text_value:
            raw[str(key)] = text_value
    if tdp is None and _is_unparsed_marker(tdp_raw):
        raw["tdp"] = tdp_raw
    if samples is None and _is_unparsed_marker(samples_raw):
        raw["samples"] = samples_raw
    if raw:
        entry["raw"] = raw

    return entry, ""


def _mega_href(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    href = html_lib.unescape(value)
    if href.startswith("http"):
        return href
    if "?" not in href:
        return f"gpu.php?gpu={href}"
    return href


def merge_entries(
    html_entries: Sequence[dict[str, Any]],
    mega_entries: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Merge list rows with Mega List rows, preferring list-page values."""
    merged: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    duplicates = 0

    for entry in html_entries:
        identifier = entry["id"]
        if identifier in seen_ids:
            duplicates += 1
            continue
        seen_ids.add(identifier)
        merged.append(entry)

    mega_by_id: dict[int, dict[str, Any]] = {}
    for entry in mega_entries:
        mega_by_id.setdefault(entry["id"], entry)

    for entry in merged:
        extra = mega_by_id.get(entry["id"])
        if extra is None:
            continue
        duplicates += 1
        if entry.get("samples") is None:
            entry["samples"] = extra.get("samples")
        if entry.get("tdp") is None:
            entry["tdp"] = extra.get("tdp")

        extra_raw = extra.get("raw", {})
        for column in ("samples", "tdp"):
            if entry.get(column) is None and column in extra_raw:
                entry.setdefault("raw", {})[column] = extra_raw[column]

    for entry in mega_entries:
        identifier = entry["id"]
        if identifier in seen_ids:
            continue
        seen_ids.add(identifier)
        merged.append(entry)

    merged.sort(key=lambda entry: (entry["name"].casefold(), entry["id"]))
    return merged, duplicates


def build_payload(entries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Wrap rows in the committed ``gpu_db.json`` shape from the plan."""
    return {
        "meta": {
            "source_url": SOURCE_URL,
            "scraped_at": date.today().isoformat(),
            "entry_count": len(entries),
        },
        "data": list(entries),
    }


def write_db_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON through a temp file in the target directory, then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)

    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def parse_int(value: str) -> int | None:
    """Strictly coerce a PassMark integer marker; NA/empty/garbage become None."""
    text = _clean_text(value)
    if text.casefold() in NA_MARKERS:
        return None

    text = text.replace(",", "")
    if INT_RE.fullmatch(text) is None:
        return None
    return int(text)


def _raw_string(value: object) -> str:
    if value is None or isinstance(value, bool):
        return ""
    return _clean_text(str(value))


def _is_unparsed_marker(value: str) -> bool:
    """Whether *value* is a real marker we failed to cast (not an NA/empty marker)."""
    return bool(value) and value.casefold() not in NA_MARKERS


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _skip(outcome: ParseOutcome, reason: str) -> None:
    outcome.skipped += 1
    outcome.skip_reasons[reason] += 1


if __name__ == "__main__":
    raise SystemExit(main())
