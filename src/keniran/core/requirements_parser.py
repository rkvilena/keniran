"""Rule-based labeled-line parser for cleaned Steam minimum requirements.

Implements Step C of ``plan/detailed-flow.md``: label detection, noise
stripping, unit conversion, the GPU/VRAM tail split, optional target tokens,
and the honesty gate that refuses to guess model-numberless component names.
:func:`split_alternatives` exposes the cleaned ``"A or B"`` component names as
independently looked-up candidates without altering the parsed fields.

Everything in this module is pure: no I/O, no HTTP, no adapter imports.
:func:`parse` consumes the text produced by
:func:`keniran.adapters.steam.strip_requirements_html`.
"""

from __future__ import annotations

import re
from typing import Final

from keniran.core.models import ComponentName, GameRequirements

_WHITESPACE_RE: Final = re.compile(r"\s+")
_BULLET_RE: Final = re.compile(r"^[\s\u2022\u00b7*\-]+")
_LABEL_PAREN_RE: Final = re.compile(r"\([^)]*\)")
_TRADEMARK_RE: Final = re.compile(r"\(\s*(?:tm|r)\s*\)|[\u00ae\u2122\u00a9]", re.IGNORECASE)
_EMPTY_PARENS_RE: Final = re.compile(r"\(\s*\)")
_CLOCK_RE: Final = re.compile(r"(?:@\s*)?\d+(?:\.\d+)?\s*(?:ghz|mhz)\b", re.IGNORECASE)
_BRAND_EQUIVALENT_RE: Final = re.compile(
    r"\bor\s+(?:an?\s+)?(?:amd|nvidia|intel)\s+equivalent\b",
    re.IGNORECASE,
)
_QUALIFIER_RE: Final = re.compile(
    r"\b(?:or|and)\s+(?:better|equivalent|higher|above|later|newer|greater)\b",
    re.IGNORECASE,
)
# Every standalone ``or`` separates candidates. Qualifier prose ("or better")
# is split away here and then dropped by :func:`split_alternatives`, so a
# qualifier word can never survive as an extra candidate.
_ALTERNATIVE_SEPARATOR_RE: Final = re.compile(r"\bor\b", re.IGNORECASE)
_QUALIFIER_WORDS: Final = frozenset(
    {"better", "equivalent", "higher", "above", "later", "newer", "greater"}
)
_CPU_WORD_RE: Final = re.compile(r"\b(?:cpu|processor)\b", re.IGNORECASE)
_SIZE_RE: Final = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)\s*(gb|mb|tb)\b", re.IGNORECASE)
_VRAM_TAIL_RE: Final = re.compile(
    r"(?:,|;|\bwith\b)?\s*"
    r"(?P<sizes>\d+(?:\.\d+)?\s*(?:gb|mb)"
    r"(?:\s*/\s*\d+(?:\.\d+)?\s*(?:gb|mb))*)"
    r"\s*(?:of\s+)?(?:vram|video memory|gpu memory)\b",
    re.IGNORECASE,
)
_GPU_RAM_RE: Final = re.compile(
    r"\bwith\s+(?P<sizes>\d+(?:\.\d+)?\s*(?:gb|mb)"
    r"(?:\s*/\s*\d+(?:\.\d+)?\s*(?:gb|mb))*)\s+(?:of\s+)?(?:ram|system ram)\b",
    re.IGNORECASE,
)
_RESOLUTION_RE: Final = re.compile(
    r"(?<![\w.])(?P<resolution>\d{3,4}[pi]|[458]k)\b",
    re.IGNORECASE,
)
_FPS_RE: Final = re.compile(r"(?<!\w)(?P<fps>\d{1,3})\s*fps\b", re.IGNORECASE)

# Unicode hyphens/dashes are folded to "-" before the model-number check so
# names such as "i5\u20132300" keep their separating hyphen.
_DASH_TRANSLATION: Final = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)
_MODEL_PUNCTUATION_RE: Final = re.compile(r"[^a-z0-9+.\-]+")
_MODEL_NOISE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\(\s*tm\s*\)"),
    re.compile(r"\(\s*r\s*\)"),
    re.compile(r"\bor\s+(?:better|equivalent|higher)\b"),
    re.compile(r"\b(?:cpu|processor)\b"),
    re.compile(r"(?:@\s*)?\d+(?:\.\d+)?\s*(?:ghz|mhz)\b"),
)
# Feature-level tokens that say nothing about the model: API versions,
# instruction sets, bitness, core-count prose, VRAM sizes, display modes.
# Kept semantically in sync with ``adapters.benchmarks.has_model_number``
# without importing the adapter (core stays pure).
_MODEL_FEATURE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\b(?:dx|directx|opengl|vulkan|sm|pcie|pci)\s*\d+(?:\.\d+)?\b"),
    re.compile(r"\b(?:sse|avx|mmx|neon)\d*\b"),
    re.compile(r"\b(?:32|64)\s*-?\s*bit\b|\bx(?:86|64)\b"),
    re.compile(r"\b(?:single|dual|quad|hexa|octa|deca|multi|four|six|eight)[- ]?core\b"),
    re.compile(r"(?<!\d)\d+\s*(?:gb|mb|tb)\b"),
    re.compile(r"\b\d{3,4}[pi]\b|\b\d+k\b"),
    re.compile(r"\b\d+\s*fps\b"),
)

_LABEL_FIELDS: Final[dict[str, str]] = {
    "cpu": "cpu",
    "processor": "cpu",
    "processor type": "cpu",
    "memory": "ram",
    "ram": "ram",
    "system memory": "ram",
    "graphics": "gpu",
    "graphics card": "gpu",
    "video": "gpu",
    "video card": "gpu",
    "gpu": "gpu",
    "storage": "storage",
    "hard disk": "storage",
    "hard disk space": "storage",
    "hard drive": "storage",
    "disk space": "storage",
    "free disk space": "storage",
    "vram": "vram",
    "video memory": "vram",
    "os": "os",
    "operating system": "os",
}


def parse(text: str) -> GameRequirements:
    """Parse cleaned Steam minimum-requirements text into the §4.2 schema.

    Labels are matched case-insensitively and may carry Steam's leftover
    bullet markers. The first labeled occurrence of each component wins;
    labels that are absent (or whose value cannot be established) leave the
    corresponding field ``None``. Generic, model-numberless component names
    are never guessed: their name field stays ``None`` and the component is
    added to :attr:`GameRequirements.unverified`.
    """
    cpu_name: str | None = None
    gpu_name: str | None = None
    ram_gb: float | None = None
    vram_gb: float | None = None
    storage_gb: float | None = None
    unverified: set[ComponentName] = set()
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = _BULLET_RE.sub("", raw_line)
        label, separator, value = line.partition(":")
        if not separator:
            continue

        field = _LABEL_FIELDS.get(_normalize_label(label))
        value = value.strip()
        if field is None or field == "os" or not value or field in seen:
            continue
        seen.add(field)

        if field == "cpu":
            cpu_name, is_unverified = _parse_cpu(value)
            if is_unverified:
                unverified.add(ComponentName.CPU)
        elif field == "gpu":
            gpu_name, parsed_vram, is_unverified = _parse_gpu(value)
            if parsed_vram is not None:
                vram_gb = parsed_vram
            if is_unverified:
                unverified.add(ComponentName.GPU)
        elif field == "ram":
            ram_gb = _parse_size(value)
        elif field == "vram":
            parsed_vram = _parse_size(value)
            if parsed_vram is not None:
                vram_gb = parsed_vram
        elif field == "storage":
            storage_gb = _parse_size(value)

    return GameRequirements(
        cpu_name=cpu_name,
        gpu_name=gpu_name,
        ram_gb=ram_gb,
        vram_gb=vram_gb,
        storage_gb=storage_gb,
        target_resolution=_find_resolution(text),
        target_fps=_find_fps(text),
        unverified=unverified,
    )


def split_alternatives(name_text: str) -> tuple[str, ...]:
    """Split a cleaned component name into its ``or`` alternatives.

    ``"AMD RX 570 or Nvidia GTX 1050 Ti"`` ->
    ``("AMD RX 570", "Nvidia GTX 1050 Ti")``. The separator is a standalone,
    case-insensitive ``or``; candidate casing is preserved. Whitespace and
    empty candidates are dropped, so empty input yields ``()`` and a name
    without a disjunction yields a single-element tuple. Qualifier words
    (``better``, ``equivalent``, ``higher``, …) are prose, not component
    names, so an extra candidate that is only such a word is dropped:
    ``"A or better or B"`` -> ``("A", "B")`` and
    ``"Intel Core i5-6500 or better"`` -> ``("Intel Core i5-6500",)``.
    Qualifier words are dropped only as *extra* candidates: when everything
    left after the split is a single qualifier word it is the whole value and
    stays, so an all-qualifier residue returns as a single candidate —
    ``"or better"`` -> ``("better",)`` and
    ``"or equivalent"`` -> ``("equivalent",)``.
    Candidates are trimmed of whitespace only: commas, slashes, colons,
    semicolons, and hyphens are ordinary candidate characters, so
    ``"AMD RX 470/570"`` stays one candidate and ``"/"`` is a single candidate.
    """
    candidates = [part.strip() for part in _ALTERNATIVE_SEPARATOR_RE.split(name_text)]
    candidates = [candidate for candidate in candidates if candidate]
    if len(candidates) > 1:
        candidates = [
            candidate for candidate in candidates if candidate.casefold() not in _QUALIFIER_WORDS
        ]
    return tuple(candidates)


def _normalize_label(label: str) -> str:
    """Lowercase a label and collapse punctuation used for parenthetical hints."""
    text = _LABEL_PAREN_RE.sub(" ", label.casefold())
    return " ".join(text.replace("/", " ").replace("&", " ").split())


def _parse_cpu(value: str) -> tuple[str | None, bool]:
    """Return ``(cpu_name, unverified)`` for a ``Processor``/``CPU`` value."""
    name = _clean_name(value)
    if not name:
        return None, False
    if not _has_model_number(name):
        return None, True
    return name, False


def _parse_gpu(value: str) -> tuple[str | None, float | None, bool]:
    """Return ``(gpu_name, vram_gb, unverified)`` for a graphics value."""
    name, vram_gb = _split_vram_tail(value)
    name = _clean_name(name)
    if not name:
        return None, vram_gb, False
    if not _has_model_number(name):
        return None, vram_gb, True
    return name, vram_gb, False


def _clean_name(value: str) -> str:
    """Strip trademark, qualifier, and clock noise from a component name."""
    name = _TRADEMARK_RE.sub(" ", value)
    name = _BRAND_EQUIVALENT_RE.sub(" ", name)
    name = _QUALIFIER_RE.sub(" ", name)
    name = _CLOCK_RE.sub(" ", name)
    name = _CPU_WORD_RE.sub(" ", name)
    name = _EMPTY_PARENS_RE.sub(" ", name)
    return _WHITESPACE_RE.sub(" ", name).strip(" \t,;:/-")


def _split_vram_tail(value: str) -> tuple[str, float | None]:
    """Split a comma/``with`` VRAM tail off a graphics value.

    ``"GTX 650 Ti, 2 GB VRAM"`` -> ``("GTX 650 Ti", 2.0)``. When the tail
    lists alternatives (``"1 GB / 2 GB VRAM"``), the largest size wins.
    """
    sizes: list[float] = []

    def capture(match: re.Match[str]) -> str:
        sizes.extend(_sizes_from(match.group("sizes")))
        return " "

    name = _GPU_RAM_RE.sub(capture, value)
    name = _VRAM_TAIL_RE.sub(capture, name)
    return name, max(sizes) if sizes else None


def _sizes_from(text: str) -> list[float]:
    """Convert every ``<number> <unit>`` pair in *text* to gigabytes."""
    return [_to_gb(float(amount), unit) for amount, unit in _SIZE_RE.findall(text)]


def _parse_size(value: str) -> float | None:
    """Return the first capacity mentioned in *value* as gigabytes."""
    match = _SIZE_RE.search(value)
    if match is None:
        return None
    return _to_gb(float(match.group(1)), match.group(2))


def _to_gb(amount: float, unit: str) -> float:
    """Convert a capacity in GB/MB/TB to gigabytes."""
    unit_casefold = unit.casefold()
    if unit_casefold == "mb":
        return round(amount / 1024.0, 3)
    if unit_casefold == "tb":
        return round(amount * 1024.0, 3)
    return round(amount, 3)


def _has_model_number(name: str) -> bool:
    """Return whether *name* keeps a model number after feature-token stripping.

    Generic prose such as ``"2.0 GHz quad-core"`` or ``"DX11-compatible
    card"`` only mentions clocks, API levels, bitness, or core counts; it must
    never be guessed into a benchmark target.
    """
    text = name.casefold().translate(_DASH_TRANSLATION)
    text = text.replace("\u00ae", " ").replace("\u2122", " ")
    for noise_pattern in _MODEL_NOISE_PATTERNS:
        text = noise_pattern.sub(" ", text)
    text = _MODEL_PUNCTUATION_RE.sub(" ", text)
    for feature_pattern in _MODEL_FEATURE_PATTERNS:
        text = feature_pattern.sub(" ", text)
    return any(character.isdigit() for character in text)


def _find_resolution(text: str) -> str | None:
    """Return the first trivially present resolution token (``720p``, ``4k``)."""
    match = _RESOLUTION_RE.search(text)
    return match.group("resolution").casefold() if match else None


def _find_fps(text: str) -> int | None:
    """Return the first trivially present FPS token (``30 FPS``, ``60FPS``)."""
    match = _FPS_RE.search(text)
    return int(match.group("fps")) if match else None
