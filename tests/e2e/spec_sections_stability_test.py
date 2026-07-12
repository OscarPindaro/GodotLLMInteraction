"""E2e test: verify all 10 top-level sections are present in extension_api.json for each installed Godot version."""

from __future__ import annotations

import pytest

from tests.e2e.conftest import discover_all_versions, installed_godot_versions

EXPECTED_SECTIONS = {
    "header",
    "builtin_class_sizes",
    "builtin_class_member_offsets",
    "global_constants",
    "global_enums",
    "utility_functions",
    "builtin_classes",
    "classes",
    "singletons",
    "native_structures",
}

_ALL_VERSIONS = discover_all_versions()
_INSTALLED = installed_godot_versions()
_TESTABLE_VERSIONS = [v for v in _ALL_VERSIONS if v in _INSTALLED]


@pytest.mark.parametrize("version", _TESTABLE_VERSIONS)
def test_all_top_level_sections_present(godot_binary_for_version, version):
    data = godot_binary_for_version(version)
    actual_sections = set(data.keys())
    missing = EXPECTED_SECTIONS - actual_sections
    assert not missing, f"Missing sections in {version}: {missing}"
