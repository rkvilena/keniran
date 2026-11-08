"""Name-to-benchmark lookup for the vendored CPU and GPU databases.

The pipeline mirrors ``plan/benchmark-db.md`` sections 4-5: Stage 0
normalization, Stage 1 exact lookup, Stage 2 rapidfuzz token-set matching,
Stage 3 deterministic disambiguation, and Stage 4 score release.

``lookup`` receives an already-loaded database (the parsed ``cpus2a.json`` /
``gpu_db.json`` payload or its ``data`` list); loading and caching are the
caller's concern.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, Literal

from rapidfuzz import fuzz

from keniran.core.models import BenchmarkEntry, MatchResult

CONFIDENCE_GATE: Final = 0.80
MAX_ALTERNATIVES: Final = 5

_VALID_KINDS: Final[frozenset[str]] = frozenset({"cpu", "gpu"})

# Unicode hyphens/dashes are folded to "-" before punctuation stripping so
# names such as "i5\u20132300" do not collapse into an unseparated token.
_DASH_TRANSLATION: Final[dict[int, str]] = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)

_NOISE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\(\s*tm\s*\)"),
    re.compile(r"\(\s*r\s*\)"),
    re.compile(r"\bor\s+better\b"),
    re.compile(r"\bor\s+equivalent\b"),
    re.compile(r"\b(?:cpu|processor)\b"),
    re.compile(r"(?:@\s*)?\d+(?:\.\d+)?\s*(?:ghz|mhz)\b"),
)

_PUNCTUATION_RE: Final = re.compile(r"[^a-z0-9+.\-]+")
_VRAM_SUFFIX_RE: Final = re.compile(r"(?<!\d)(\d+)\s+(gb|mb|tb)\b")
_VRAM_TOKEN_RE: Final = re.compile(r"(?<!\d)\d+\s*(?:gb|mb|tb)\b")
_VRAM_CAPTURE_RE: Final = re.compile(r"(?<!\d)(\d+)\s*(gb|mb)\b")
_HYPHEN_SPACE_RE: Final = re.compile(r"\s*-\s*")
_HYPHEN_RUN_RE: Final = re.compile(r"-{2,}")
_WHITESPACE_RE: Final = re.compile(r"\s+")
_TOKEN_RE: Final = re.compile(r"[a-z0-9+]+")
_MOBILE_RE: Final = re.compile(r"\b(?:mobile|laptop(?:\s+gpu)?)\b")

# lspci/USB-style placeholder shapes: names a probe emits when it cannot
# identify the part. Real marketing names never match these shapes.
_PLACEHOLDER_NAME_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # "Device 008e", "device 0x25a2": a "device" keyword plus a hex id.
    re.compile(r"\bdevice\s+(?:0x)?[0-9a-f]+\b"),
    # Whole-name bare hex ids: "008e", "0x25a2", "0x1234". A bare token with
    # only decimal digits ("3080") stays a real shorthand model number; hex
    # letters or an "0x" prefix mark it as probe noise.
    re.compile(r"^(?:0x[0-9a-f]{4,}|(?=[0-9a-f]*[a-f])[0-9a-f]{4,})$"),
    # Failed-probe phrasing: "unknown", "unknown device", "unknown pci device".
    re.compile(r"^unknown\b"),
)

_MODEL_FEATURE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # API/interface levels: "DX11", "DirectX 12", "OpenGL 4.6", "SM 6.0".
    re.compile(r"\b(?:dx|directx|opengl|vulkan|sm|pcie|pci)\s*\d+(?:\.\d+)?\b"),
    # Instruction-set levels: "SSE2", "AVX2".
    re.compile(r"\b(?:sse|avx|mmx|neon)\d*\b"),
    # Bitness/architecture prose: "64-bit", "32 bit", "x64", "x86".
    re.compile(r"\b(?:32|64)\s*-?\s*bit\b|\bx(?:86|64)\b"),
    # Core-count prose: "quad-core", "six core", "dual-core".
    re.compile(r"\b(?:single|dual|quad|hexa|octa|deca|multi|four|six|eight)[- ]?core\b"),
    _VRAM_TOKEN_RE,
    # Resolution/refresh prose: "1080p", "1440i", "4k".
    re.compile(r"\b\d{3,4}[pi]\b|\b\d+k\b"),
    re.compile(r"\b\d+\s*fps\b"),
)

_ALIASES: Final[dict[str, str]] = {
    "gtx 1060": "geforce gtx 1060",
}

_MONTHS: Final[dict[str, int]] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass(frozen=True)
class _Candidate:
    """One database row plus its precomputed lookup key."""

    entry: BenchmarkEntry
    key: str
    raw: Mapping[str, Any]
    position: int


def normalize_name(name_text: str) -> str:
    """Stage 0: build the canonical key used for both database rows and inputs.

    Lowercases, drops punctuation except ``+ - .``, removes clock/trademark/
    qualifier noise, canonicalizes whitespace around hyphens and VRAM suffixes
    (``6 GB`` -> ``6gb``), and applies the hand-maintained vendor alias map.
    """
    text = name_text.lower().translate(_DASH_TRANSLATION)
    text = text.replace("\u00ae", " ").replace("\u2122", " ")

    for pattern in _NOISE_PATTERNS:
        text = pattern.sub(" ", text)

    text = _PUNCTUATION_RE.sub(" ", text)
    text = _VRAM_SUFFIX_RE.sub(r"\1\2", text)
    text = _HYPHEN_SPACE_RE.sub("-", text)
    text = _HYPHEN_RUN_RE.sub("-", text)
    text = _WHITESPACE_RE.sub(" ", text).strip(" -.")
    return _apply_aliases(text)


def has_model_number(name_text: str) -> bool:
    """Return whether *name_text* contains a usable model number.

    Generic requirement prose (``"2.0 GHz quad-core"``,
    ``"DX11-compatible card"``) only mentions clocks, feature levels, VRAM
    sizes, bitness, or core counts. Those tokens are stripped; a name with no
    digit left is treated as model-numberless and is never guessed.
    """
    text = normalize_name(name_text)
    for pattern in _MODEL_FEATURE_PATTERNS:
        text = pattern.sub(" ", text)
    return any(character.isdigit() for character in text)


def _is_placeholder_name(name_text: str) -> bool:
    """Return whether *name_text* is a probe placeholder, not a model name.

    Normalization runs first so trademark/clock noise (``(R)``, ``@ 2.8GHz``)
    cannot mask a placeholder shape. Shapes are lspci/USB probe artifacts:
    ``device <hex>``, a whole-name bare hex id, and ``unknown`` phrasing. A
    bare hex id must contain a hex letter (``008e``) or an ``0x`` prefix
    (``0x25a2``); pure-decimal shorthand such as ``3080`` is a real model
    number and stays scorable.
    """
    key = normalize_name(name_text)
    return any(pattern.search(key) for pattern in _PLACEHOLDER_NAME_PATTERNS)


def lookup(
    db: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    name_text: str,
    kind: Literal["cpu", "gpu"] = "cpu",
) -> MatchResult:
    """Resolve *name_text* against an already-loaded benchmark database.

    ``db`` is either the parsed JSON payload (``{"data": [...]}``) or the
    ``data`` sequence itself. ``kind`` selects the score fields: CPUs release
    ``cpumark`` as ``score`` and ``thread`` as the single-thread value; GPUs
    release ``g3d_mark`` as ``score`` and leave ``thread`` null.

    ``score_ratio`` is match confidence in ``[0, 1]``, not a performance
    ratio. ``matched_by`` is one of:

    - ``"exact"`` - Stage 1 normalized-key hit.
    - ``"fuzzy"`` - Stage 2 hit at or above :data:`CONFIDENCE_GATE`.
    - ``"best_guess"`` - Stage 2 hit below the gate but with a model number;
      callers show the confidence badge instead of prompting.
    - ``"unverified"`` - generic or placeholder-shaped text with no usable
      model number; never guessed.
    - ``"none"`` - no candidate shares a token with the input.
    """
    if kind not in _VALID_KINDS:
        msg = f"unsupported benchmark kind: {kind!r}"
        raise ValueError(msg)
    if _is_placeholder_name(name_text) or not has_model_number(name_text):
        return MatchResult(matched_by="unverified")

    key = normalize_name(name_text)
    exact, candidates = _index_candidates(db, kind)

    exact_hits = exact.get(key)
    if exact_hits:
        ordered = _disambiguate(exact_hits, kind, key)
        return MatchResult(
            best_entry=ordered[0].entry,
            score_ratio=1.0,
            alternatives=_entries(ordered[1:]),
            matched_by="exact",
        )

    matches = _fuzzy_matches(candidates, kind, key)
    if not matches:
        return MatchResult(matched_by="none")

    similarity, _shared, best = matches[0]
    alternatives = [
        candidate
        for match_similarity, _match_shared, candidate in matches[1:]
        if match_similarity >= CONFIDENCE_GATE
    ]
    return MatchResult(
        best_entry=best.entry,
        score_ratio=similarity,
        alternatives=_entries(alternatives),
        matched_by="fuzzy" if similarity >= CONFIDENCE_GATE else "best_guess",
    )


def _apply_aliases(key: str) -> str:
    """Expand a normalized key with the vendor alias map."""
    if key in _ALIASES:
        return _ALIASES[key]
    for source, target in _ALIASES.items():
        prefix = f"{source} "
        if key.startswith(prefix):
            return f"{target} {key[len(prefix) :]}"
    return key


def _records(
    db: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Return the row mappings from either a JSON payload or a bare data list."""
    if isinstance(db, Mapping):
        data = db.get("data")
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
            return []
        return [row for row in data if isinstance(row, Mapping)]
    return [row for row in db if isinstance(row, Mapping)]


def _index_candidates(
    db: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    kind: str,
) -> tuple[dict[str, list[_Candidate]], list[_Candidate]]:
    """Build the Stage 1 exact index and the Stage 2 candidate list."""
    exact: dict[str, list[_Candidate]] = {}
    candidates: list[_Candidate] = []

    for position, raw in enumerate(_records(db)):
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            continue

        key = normalize_name(name)
        if not key:
            continue

        candidate = _Candidate(
            entry=_build_entry(raw, name, kind),
            key=key,
            raw=raw,
            position=position,
        )
        candidates.append(candidate)
        exact.setdefault(key, []).append(candidate)

    return exact, candidates


def _build_entry(raw: Mapping[str, Any], name: str, kind: str) -> BenchmarkEntry:
    """Coerce one database row into the Stage 4 :class:`BenchmarkEntry`."""
    if kind == "cpu":
        score = _number(raw.get("cpumark"))
        thread = _number(raw.get("thread"))
    else:
        score = _number(raw.get("g3d_mark"))
        thread = None

    identifier = raw.get("id")
    if isinstance(identifier, bool) or not isinstance(identifier, (int, str)):
        identifier = None

    href = raw.get("href")
    return BenchmarkEntry(
        id=identifier,
        name=name,
        score=score,
        thread=thread,
        samples=_integer(raw.get("samples")),
        href=href if isinstance(href, str) else None,
    )


def _number(value: object) -> float | None:
    """Parse a PassMark score, mapping ``"NA"``/garbage to ``None`` (never 0)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text or text.upper() in {"NA", "N/A", "NAN", "UNKNOWN", "-"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _integer(value: object) -> int | None:
    """Parse an integer-valued database field, or ``None`` when unavailable."""
    number = _number(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _tokens(key: str) -> frozenset[str]:
    """Split a normalized key into the token set used by Stage 2."""
    return frozenset(_TOKEN_RE.findall(key))


def _fuzzy_key(key: str) -> str:
    """Drop mobile/laptop qualifiers before Stage 2 comparison."""
    return _WHITESPACE_RE.sub(" ", _MOBILE_RE.sub(" ", key)).strip()


def _vram_tokens(key: str) -> frozenset[str]:
    """Return canonical VRAM suffix tokens such as ``{"6gb"}``."""
    return frozenset(f"{size}{unit}" for size, unit in _VRAM_CAPTURE_RE.findall(key))


def _date_ordinal(value: object) -> int:
    """Convert a PassMark ``"Feb 2021"`` date to an ordinal; unknown -> 0."""
    if not isinstance(value, str):
        return 0

    parts = value.strip().split()
    if len(parts) != 2:
        return 0

    month = _MONTHS.get(parts[0][:3].lower())
    if month is None:
        return 0
    try:
        return date(int(parts[1]), month, 1).toordinal()
    except ValueError:
        return 0


def _samples(candidate: _Candidate) -> int:
    """Samples count used as the final popularity tiebreak (missing -> 0)."""
    samples = _integer(candidate.raw.get("samples"))
    return samples if samples is not None else 0


def _disambiguation_key(
    candidate: _Candidate,
    kind: str,
    input_key: str,
) -> tuple[float, ...]:
    """Stage 3 deterministic preference tuple (lower sorts first)."""
    if kind == "cpu":
        cpu_count = _integer(candidate.raw.get("cpuCount"))
        category = candidate.raw.get("cat")
        category_text = category.lower() if isinstance(category, str) else ""
        return (
            # Prefer single-socket rows, then Desktop category, then newest
            # date, then highest sample count.
            0.0 if cpu_count == 1 else 1.0,
            0.0 if "desktop" in category_text else 1.0,
            float(-_date_ordinal(candidate.raw.get("date"))),
            float(-_samples(candidate)),
            float(candidate.position),
        )

    # Prefer the variant whose VRAM suffix matches the input, else the most
    # sampled variant.
    input_vram = _vram_tokens(input_key)
    candidate_vram = _vram_tokens(candidate.key)
    vram_rank = 0.0 if input_vram and input_vram <= candidate_vram else 1.0
    return (vram_rank, float(-_samples(candidate)), float(candidate.position))


def _disambiguate(
    candidates: Sequence[_Candidate],
    kind: str,
    input_key: str,
) -> list[_Candidate]:
    """Stage 3 sort for exact-key duplicate rows."""
    return sorted(
        candidates,
        key=lambda candidate: _disambiguation_key(candidate, kind, input_key),
    )


def _fuzzy_matches(
    candidates: Sequence[_Candidate],
    kind: str,
    input_key: str,
) -> list[tuple[float, int, _Candidate]]:
    """Stage 2 ranking: token-set similarity then shared-token tiebreak.

    Candidates sharing no token with the input are not matches at all; this
    keeps character-overlap noise from inventing a best-guess. Remaining ties
    fall through to the Stage 3 preference tuple.
    """
    input_tokens = _tokens(_fuzzy_key(input_key))
    if not input_tokens:
        return []

    input_text = " ".join(sorted(input_tokens))
    scored: list[tuple[float, int, _Candidate]] = []

    for candidate in candidates:
        candidate_tokens = _tokens(_fuzzy_key(candidate.key))
        shared = len(input_tokens & candidate_tokens)
        if shared == 0:
            continue

        similarity = fuzz.token_set_ratio(input_text, " ".join(sorted(candidate_tokens))) / 100.0
        scored.append((similarity, shared, candidate))

    scored.sort(
        key=lambda match: (
            -match[0],
            -match[1],
            *_disambiguation_key(match[2], kind, input_key),
        )
    )
    return scored


def _entries(candidates: Sequence[_Candidate]) -> list[BenchmarkEntry]:
    """Convert a bounded number of candidates into public result entries."""
    return [candidate.entry for candidate in candidates[:MAX_ALTERNATIVES]]
