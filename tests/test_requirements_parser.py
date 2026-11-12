"""Offline tests for the rule-based Steam requirements parser (Step C).

The fixture files mimic the output of
:func:`keniran.adapters.steam.strip_requirements_html`: a ``Minimum:``
header, Steam's leftover bullet markers, and labeled ``Label: value`` lines.
No test touches the network, the disk cache, or an adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

from keniran.core.models import ComponentName, GameRequirements
from keniran.core.requirements_parser import parse, split_alternatives

FIXTURES = Path(__file__).parent / "fixtures" / "steam" / "requirements_text"

SPEC_4_2_EXAMPLE = """\
{
  "cpu_name": "Intel Core i5-2300",
  "gpu_name": "NVIDIA GeForce GTX 650 Ti",
  "ram_gb": 8.0,
  "vram_gb": 2.0,
  "storage_gb": 30.0,
  "target_resolution": "720p",
  "target_fps": 30
}
"""


def _fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_intel_style_fixture_matches_spec_4_2_example_verbatim() -> None:
    expected_json = json.loads(SPEC_4_2_EXAMPLE)

    parsed = parse(_fixture_text("intel_style_minimum.txt"))

    assert parsed.model_dump(mode="json", exclude={"unverified"}) == expected_json
    assert parsed == GameRequirements.model_validate_json(SPEC_4_2_EXAMPLE)


def test_amd_style_fixture_normalizes_units_and_strips_qualifiers() -> None:
    parsed = parse(_fixture_text("amd_style_minimum.txt"))

    assert parsed.model_dump() == {
        "cpu_name": "AMD FX-6300",
        "gpu_name": "AMD Radeon HD 7750",
        "ram_gb": 4.0,
        "vram_gb": 2.0,
        "storage_gb": 50.0,
        "target_resolution": None,
        "target_fps": None,
        "unverified": set(),
    }


def test_mb_units_and_compact_60fps_tokens_are_normalized() -> None:
    parsed = parse(_fixture_text("mb_units_60fps.txt"))

    assert parsed.model_dump() == {
        "cpu_name": "Intel Core 2 Duo E8400",
        "gpu_name": "NVIDIA GeForce GTX 1050 Ti",
        "ram_gb": 8.0,
        "vram_gb": 4.0,
        "storage_gb": 20.0,
        "target_resolution": "1080p",
        "target_fps": 60,
        "unverified": set(),
    }


def test_generic_descriptions_are_flagged_unverified_not_guessed() -> None:
    parsed = parse(_fixture_text("generic_description.txt"))

    assert parsed.model_dump() == {
        "cpu_name": None,
        "gpu_name": None,
        "ram_gb": 8.0,
        "vram_gb": 2.0,
        "storage_gb": 20.0,
        "target_resolution": None,
        "target_fps": None,
        "unverified": {ComponentName.CPU, ComponentName.GPU},
    }


def test_clock_and_equivalent_noise_stripped_without_unverified_flag() -> None:
    parsed = parse(
        "Processor: Intel Core i5-6500 @ 3.20 GHz or equivalent\n"
        "Graphics: NVIDIA GeForce GTX 960 or AMD equivalent\n"
    )

    assert parsed.cpu_name == "Intel Core i5-6500"
    assert parsed.gpu_name == "NVIDIA GeForce GTX 960"
    assert parsed.unverified == set()


def test_cpu_ram_video_and_storage_alias_labels_are_detected() -> None:
    parsed = parse(
        "CPU: AMD Ryzen 5 3600\n"
        "RAM: 16 GB\n"
        "Video: NVIDIA GeForce GTX 1660 Super, 6 GB VRAM\n"
        "Storage: 100 GB available space\n"
    )

    assert parsed.cpu_name == "AMD Ryzen 5 3600"
    assert parsed.ram_gb == 16.0
    assert parsed.gpu_name == "NVIDIA GeForce GTX 1660 Super"
    assert parsed.vram_gb == 6.0
    assert parsed.storage_gb == 100.0


def test_cpu_model_suffix_k_is_not_mistaken_for_a_resolution_token() -> None:
    parsed = parse("Processor: Intel Core i5-2500K\nMemory: 8 GB RAM\n")

    assert parsed.cpu_name == "Intel Core i5-2500K"
    assert parsed.target_resolution is None


def test_vram_comma_tail_with_slash_options_takes_largest_size() -> None:
    parsed = parse("Graphics: NVIDIA GeForce GTX 650 Ti, 1 GB / 2 GB VRAM")

    assert parsed.gpu_name == "NVIDIA GeForce GTX 650 Ti"
    assert parsed.vram_gb == 2.0


def test_absent_labels_leave_schema_fields_none() -> None:
    parsed = parse("OS: Windows 10 64-bit\nMemory: 16 GB RAM\n")

    assert parsed.model_dump() == {
        "cpu_name": None,
        "gpu_name": None,
        "ram_gb": 16.0,
        "vram_gb": None,
        "storage_gb": None,
        "target_resolution": None,
        "target_fps": None,
        "unverified": set(),
    }


def test_split_alternatives_splits_cpu_alternatives() -> None:
    assert split_alternatives("AMD Ryzen 5 3600 or Intel Core i7-8700K") == (
        "AMD Ryzen 5 3600",
        "Intel Core i7-8700K",
    )


def test_split_alternatives_splits_gpu_alternatives() -> None:
    assert split_alternatives("AMD RX 570 or Nvidia GTX 1050 Ti") == (
        "AMD RX 570",
        "Nvidia GTX 1050 Ti",
    )


def test_split_alternatives_separator_is_case_insensitive_and_keeps_casing() -> None:
    expected = ("AMD RX 570", "Nvidia GTX 1050 Ti")

    assert split_alternatives("AMD RX 570 OR Nvidia GTX 1050 Ti") == expected
    assert split_alternatives("AMD RX 570 oR Nvidia GTX 1050 Ti") == expected


def test_split_alternatives_returns_empty_tuple_for_empty_input() -> None:
    assert split_alternatives("") == ()
    assert split_alternatives("   ") == ()


def test_split_alternatives_returns_single_candidate_without_disjunction() -> None:
    assert split_alternatives("Intel Core i5-2300") == ("Intel Core i5-2300",)
    assert split_alternatives("  Intel Core i5-2300  ") == ("Intel Core i5-2300",)
    # A qualifier word is only discarded as an extra ``or`` candidate; alone it is the value.
    assert split_alternatives("Better") == ("Better",)


def test_split_alternatives_preserves_punctuation_and_never_splits_on_it() -> None:
    # Only a standalone ``or`` separates candidates; punctuation is content.
    assert split_alternatives("/") == ("/",)
    assert split_alternatives(",") == (",",)
    assert split_alternatives("AMD RX 470/570") == ("AMD RX 470/570",)
    assert split_alternatives("A, B or C") == ("A, B", "C")


def test_split_alternatives_drops_qualifier_words_from_raw_text() -> None:
    assert split_alternatives("Intel Core i5-6500 or better") == ("Intel Core i5-6500",)
    assert split_alternatives("AMD FX-6300 or equivalent") == ("AMD FX-6300",)
    assert split_alternatives("A or better or B") == ("A", "B")
    assert split_alternatives("AMD RX 570 or higher or Nvidia GTX 1050 Ti") == (
        "AMD RX 570",
        "Nvidia GTX 1050 Ti",
    )
    # The qualifier match is case-insensitive, like the separator.
    assert split_alternatives("Intel Core i5-6500 OR Better") == ("Intel Core i5-6500",)


def test_split_alternatives_all_qualifier_residue_stays_single_candidate() -> None:
    # v1.0.1 ruling: the qualifier is dropped only as an *extra* candidate, so
    # a residue that is nothing but a qualifier is the value and stays.
    assert split_alternatives("or better") == ("better",)
    assert split_alternatives("or equivalent") == ("equivalent",)
    assert split_alternatives("  OR Better  ") == ("Better",)


def test_cleaned_qualifiers_yield_a_single_alternative() -> None:
    parsed = parse(
        "Processor: Intel Core i5-6500 or better\n"
        "Graphics: NVIDIA GeForce GTX 960 or AMD equivalent\n"
    )

    assert parsed.cpu_name == "Intel Core i5-6500"
    assert parsed.gpu_name == "NVIDIA GeForce GTX 960"
    assert split_alternatives(parsed.cpu_name or "") == ("Intel Core i5-6500",)
    assert split_alternatives(parsed.gpu_name or "") == ("NVIDIA GeForce GTX 960",)


def test_fc27_style_lines_keep_the_full_or_expression_in_schema_fields() -> None:
    parsed = parse(
        "Processor: AMD Ryzen 5 3600 or Intel Core i7-8700K\n"
        "Graphics: AMD RX 570 or Nvidia GTX 1050 Ti\n"
    )

    assert parsed.cpu_name == "AMD Ryzen 5 3600 or Intel Core i7-8700K"
    assert parsed.gpu_name == "AMD RX 570 or Nvidia GTX 1050 Ti"
    assert parsed.unverified == set()
    assert GameRequirements.model_validate(parsed.model_dump()) == parsed
    assert split_alternatives(parsed.cpu_name or "") == (
        "AMD Ryzen 5 3600",
        "Intel Core i7-8700K",
    )
    assert split_alternatives(parsed.gpu_name or "") == (
        "AMD RX 570",
        "Nvidia GTX 1050 Ti",
    )


def test_fc27_style_graphics_vram_tail_is_split_off_before_alternatives() -> None:
    parsed = parse("Graphics: AMD RX 570 or Nvidia GTX 1050 Ti, 4 GB VRAM\n")

    assert parsed.gpu_name == "AMD RX 570 or Nvidia GTX 1050 Ti"
    assert parsed.vram_gb == 4.0
    assert split_alternatives(parsed.gpu_name or "") == (
        "AMD RX 570",
        "Nvidia GTX 1050 Ti",
    )
