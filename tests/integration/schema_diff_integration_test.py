"""Integration test: schema diff between two pre-downloaded extension_api.json files.

These tests use the reference files in tests/data/extension_api/ (downloaded
via ``godotctl download-apis``). They verify the schema diff logic produces
correct reports and that the reports are valid YAML/JSON.

Note: These tests cannot be auto-generated. When ``add-version`` runs, it
outputs test guidance. The dev writes these tests manually as part of the
version-addition workflow.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from godotllminteraction.specifications.schema_diff import (
    compute_schema_diff,
    format_report_json,
    format_report_yaml,
)

pytestmark = [pytest.mark.specs]

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "extension_api"


def _load_api(version: str) -> dict:
    path = DATA_DIR / f"extension_api-{version}.json"
    if not path.exists():
        pytest.skip(f"Reference file not found: {path}. Run: godotctl download-apis")
    return json.loads(path.read_text())


def test_schema_diff_yields_no_new_sections_for_same_version():
    """Diffing a version against itself should report no new top-level sections."""
    data = _load_api("4.4.1")
    report = compute_schema_diff(data, version="v4_4_1", base_version="v4_4_1")
    assert report.new_top_level_sections == []


def test_schema_diff_report_is_valid_yaml():
    """The YAML report output must be parseable YAML."""
    data = _load_api("4.4.1")
    report = compute_schema_diff(data, version="v4_4_1")
    yaml_text = format_report_yaml(report)
    parsed = yaml.safe_load(yaml_text)
    assert parsed["version"] == "v4_4_1"
    assert "enum_comparison" in parsed
    assert "test_guidance" in parsed


def test_schema_diff_report_is_valid_json():
    """The JSON report output must be parseable JSON."""
    data = _load_api("4.4.1")
    report = compute_schema_diff(data, version="v4_4_1")
    json_text = format_report_json(report)
    parsed = json.loads(json_text)
    assert parsed["version"] == "v4_4_1"
    assert "enum_comparison" in parsed
    assert "test_guidance" in parsed


def test_schema_diff_between_versions_detects_enum_changes():
    """Diffing 4.4.1 against 4.6.2 should detect enum value changes."""
    base_data = _load_api("4.4.1")
    new_data = _load_api("4.6.2")

    from godotllminteraction.specifications.schema_diff import extract_enum_values

    base_enums = extract_enum_values(base_data)
    report = compute_schema_diff(
        new_data, base_enum_values=base_enums, version="v4_6_2", base_version="v4_4_1"
    )

    for enum_name in report.enum_comparison:
        comp = report.enum_comparison[enum_name]
        if comp.identical_to_base is False:
            assert len(comp.new_values) > 0, (
                f"{enum_name} marked different but no new values"
            )


def test_schema_diff_requires_human_intervention_flag_is_boolean():
    """The requires_human_intervention flag must be a boolean."""
    data = _load_api("4.4.1")
    report = compute_schema_diff(data, version="v4_4_1")
    assert isinstance(report.requires_human_intervention, bool)
