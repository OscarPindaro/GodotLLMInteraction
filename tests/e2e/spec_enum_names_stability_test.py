"""E2e test: verify the 5 enum class names are stable and enum member names are supersets across versions."""

from __future__ import annotations

import pytest

from godotllminteraction.specifications.schema_diff import extract_enum_values
from tests.e2e._helpers import discover_all_versions, installed_godot_versions

EXPECTED_ENUM_NAMES = {
    "GodotTypeNameEnum",
    "UtilityFunctionCategoryEnum",
    "BuiltinClassOperatorNameEnum",
    "GodotArgumentMetaEnum",
    "ClassApiTypeEnum",
}

_ALL_VERSIONS = discover_all_versions()
_INSTALLED = installed_godot_versions()
_TESTABLE_VERSIONS = [v for v in _ALL_VERSIONS if v in _INSTALLED]


@pytest.mark.parametrize("version", _TESTABLE_VERSIONS)
def test_enum_value_sets_are_non_empty(godot_binary_for_version, version):
    data = godot_binary_for_version(version)
    values = extract_enum_values(data)
    assert set(values.keys()) == EXPECTED_ENUM_NAMES
    for enum_name, vals in values.items():
        assert len(vals) > 0, f"{enum_name} has no values in {version}"


def test_enum_member_names_are_superset_across_versions(godot_binary_for_version):
    """Enum member names may grow between versions but should not shrink."""
    if len(_TESTABLE_VERSIONS) < 2:
        pytest.skip("Need at least 2 installed Godot versions")

    prev_values: dict[str, set[str]] | None = None
    for version in _TESTABLE_VERSIONS:
        data = godot_binary_for_version(version)
        values = extract_enum_values(data)
        if prev_values is not None:
            for enum_name in EXPECTED_ENUM_NAMES:
                assert values[enum_name] >= prev_values[enum_name], (
                    f"{enum_name} lost members between versions: "
                    f"lost {prev_values[enum_name] - values[enum_name]}"
                )
        prev_values = values
