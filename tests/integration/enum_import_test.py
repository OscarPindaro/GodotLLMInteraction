"""Integration test: enum import logic between versions.

Verifies that the enum comparison logic correctly identifies when enums
are identical (should import from base) vs different (should generate fresh).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from godotllminteraction.specifications.schema_diff import (
    extract_enum_values,
    compute_schema_diff,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "extension_api"


def _load_api(version: str) -> dict:
    path = DATA_DIR / f"extension_api-{version}.json"
    if not path.exists():
        pytest.skip(f"Reference file not found: {path}. Run: godotctl download-apis")
    return json.loads(path.read_text())


def test_enum_values_extracted_from_reference_file():
    """All 5 enum value sets should be non-empty from a real reference file."""
    data = _load_api("4.4.1")
    values = extract_enum_values(data)
    assert len(values) == 5
    for name, vals in values.items():
        assert len(vals) > 0, f"{name} is empty"


def test_enum_comparison_identical_when_same_data():
    """Comparing a version against itself should mark all enums identical."""
    data = _load_api("4.4.1")
    base_enums = extract_enum_values(data)
    report = compute_schema_diff(data, base_enum_values=base_enums, version="v4_4_1")
    for enum_name, comp in report["enum_comparison"].items():
        assert comp["identical_to_base"] is True, f"{enum_name} not identical to itself"
        assert comp["import_from_base"] is True


def test_enum_comparison_detects_new_values_between_versions():
    """Comparing 4.6.2 against 4.4.1 should detect new enum values."""
    base_data = _load_api("4.4.1")
    new_data = _load_api("4.6.2")
    base_enums = extract_enum_values(base_data)
    report = compute_schema_diff(
        new_data, base_enum_values=base_enums, version="v4_6_2"
    )

    at_least_one_different = False
    for enum_name, comp in report["enum_comparison"].items():
        if comp["identical_to_base"] is False:
            at_least_one_different = True
            assert comp["new_values"], f"{enum_name} different but no new values listed"
            assert comp["import_from_base"] is False
    # At least one enum should have grown between 4.4.1 and 4.6.2
    assert at_least_one_different, "No enum changes detected between 4.4.1 and 4.6.2"


def test_enum_comparison_new_values_are_subset_of_full_set():
    """New values reported should be a subset of the full enum value set."""
    base_data = _load_api("4.4.1")
    new_data = _load_api("4.6.2")
    base_enums = extract_enum_values(base_data)
    new_enums = extract_enum_values(new_data)
    report = compute_schema_diff(
        new_data, base_enum_values=base_enums, version="v4_6_2"
    )

    for enum_name, comp in report["enum_comparison"].items():
        if comp["new_values"]:
            new_set = set(comp["new_values"])
            assert new_set <= new_enums[enum_name], (
                f"{enum_name} new_values not in full set"
            )
            assert new_set.isdisjoint(base_enums[enum_name]), (
                f"{enum_name} new_values overlap with base"
            )
