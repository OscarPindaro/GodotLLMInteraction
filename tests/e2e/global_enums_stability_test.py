"""E2e test: verify generated global_enums.py is stable and correct across versions.

For each installed Godot version, dumps the real extension_api.json, generates
global_enums.py, and checks that key enums (Key, MouseButton, JoyButton) have
the expected values. Also verifies the generated file imports cleanly.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from godotllminteraction.cli import app
from tests.e2e._helpers import discover_all_versions, installed_godot_versions

runner = CliRunner()

pytestmark = [pytest.mark.specs]

_ALL_VERSIONS = discover_all_versions()
_INSTALLED = installed_godot_versions()
_TESTABLE_VERSIONS = [v for v in _ALL_VERSIONS if v in _INSTALLED]


def _version_to_pkg(version: str) -> str:
    return "v" + version.replace(".", "_")


# Well-known keycode values that should be stable across all Godot 4.x versions.
_EXPECTED_KEY_VALUES = {
    "KEY_NONE": 0,
    "KEY_A": 65,
    "KEY_ESCAPE": 4194305,
    "KEY_TAB": 4194306,
    "KEY_ENTER": 4194309,
    "KEY_LEFT": 4194319,
    "KEY_UP": 4194320,
    "KEY_RIGHT": 4194321,
    "KEY_DOWN": 4194322,
    "KEY_SPACE": 32,
}

_EXPECTED_MOUSE_VALUES = {
    "MOUSE_BUTTON_NONE": 0,
    "MOUSE_BUTTON_LEFT": 1,
    "MOUSE_BUTTON_RIGHT": 2,
    "MOUSE_BUTTON_MIDDLE": 3,
}

_EXPECTED_JOY_VALUES = {
    "JOY_BUTTON_INVALID": -1,
    "JOY_BUTTON_A": 0,
    "JOY_BUTTON_B": 1,
    "JOY_BUTTON_X": 2,
    "JOY_BUTTON_Y": 3,
}


@pytest.mark.parametrize("version", _TESTABLE_VERSIONS)
def test_global_enums_import_cleanly(version):
    """The generated global_enums.py for each checked-in version imports without error."""
    version_pkg = _version_to_pkg(version)
    mod = importlib.import_module(
        f"godotllminteraction.specifications.{version_pkg}.global_enums"
    )
    assert hasattr(mod, "BY_NAME")
    assert len(mod.BY_NAME) > 0


@pytest.mark.parametrize("version", _TESTABLE_VERSIONS)
def test_key_enum_has_expected_values(version):
    version_pkg = _version_to_pkg(version)
    mod = importlib.import_module(
        f"godotllminteraction.specifications.{version_pkg}.global_enums"
    )
    key = mod.Key
    for name, expected in _EXPECTED_KEY_VALUES.items():
        assert hasattr(key, name), f"{version_pkg}: Key missing {name}"
        assert getattr(key, name) == expected, (
            f"{version_pkg}: Key.{name} = {getattr(key, name)}, expected {expected}"
        )


@pytest.mark.parametrize("version", _TESTABLE_VERSIONS)
def test_mouse_button_enum_has_expected_values(version):
    version_pkg = _version_to_pkg(version)
    mod = importlib.import_module(
        f"godotllminteraction.specifications.{version_pkg}.global_enums"
    )
    mouse = mod.MouseButton
    for name, expected in _EXPECTED_MOUSE_VALUES.items():
        assert hasattr(mouse, name), f"{version_pkg}: MouseButton missing {name}"
        assert getattr(mouse, name) == expected


@pytest.mark.parametrize("version", _TESTABLE_VERSIONS)
def test_joy_button_enum_has_expected_values(version):
    version_pkg = _version_to_pkg(version)
    mod = importlib.import_module(
        f"godotllminteraction.specifications.{version_pkg}.global_enums"
    )
    joy = mod.JoyButton
    for name, expected in _EXPECTED_JOY_VALUES.items():
        assert hasattr(joy, name), f"{version_pkg}: JoyButton missing {name}"
        assert getattr(joy, name) == expected


@pytest.mark.parametrize("version", _TESTABLE_VERSIONS)
def test_by_name_maps_dotted_enums(version):
    version_pkg = _version_to_pkg(version)
    mod = importlib.import_module(
        f"godotllminteraction.specifications.{version_pkg}.global_enums"
    )
    assert "Variant.Type" in mod.BY_NAME
    assert "Variant.Operator" in mod.BY_NAME
    assert mod.BY_NAME["Variant.Type"] is mod.VariantType


@pytest.mark.parametrize("version", _TESTABLE_VERSIONS)
def test_generated_matches_dumped_api(
    godot_binary_for_version, version, tmp_path: Path
):
    """Generating from a freshly-dumped API produces the same file that's checked in."""
    data = godot_binary_for_version(version)
    version_pkg = _version_to_pkg(version)

    # Write the dumped API to a temp file and generate into a temp specs root
    api_path = tmp_path / "extension_api.json"
    api_path.write_text(json.dumps(data))
    specs_root = tmp_path / "specs"

    result = runner.invoke(
        app,
        [
            "specifications",
            "generate-global-enums",
            "--version",
            version_pkg,
            "--api",
            str(api_path),
            "--specs-root",
            str(specs_root),
        ],
    )
    assert result.exit_code == 0, result.output

    generated = (specs_root / version_pkg / "global_enums.py").read_text()
    checked_in = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "godotllminteraction"
        / "specifications"
        / version_pkg
        / "global_enums.py"
    ).read_text()
    assert generated == checked_in, (
        f"{version_pkg}: generated global_enums.py differs from checked-in version. "
        "Run `gli specifications generate-global-enums` to refresh."
    )
