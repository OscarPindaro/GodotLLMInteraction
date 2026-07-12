"""E2e test: add-version CLI with real Godot binary dumps.

For each installed Godot version, dumps extension_api.json and runs
``gli specifications add-version`` to verify the full workflow works
end-to-end with real API data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from godotllminteraction.cli import app

from tests.e2e._helpers import discover_all_versions, installed_godot_versions

runner = CliRunner()

pytestmark = [pytest.mark.cli, pytest.mark.specs]

COMPLETE_FAKE_API = {
    "header": {
        "version_major": 4,
        "version_minor": 4,
        "version_patch": 0,
        "version_status": "stable",
        "version_build": "official",
        "version_full_name": "Godot Engine v4.4.stable.official",
        "precision": "single",
    },
    "builtin_class_sizes": [],
    "builtin_class_member_offsets": [],
    "global_constants": [],
    "global_enums": [],
    "utility_functions": [],
    "builtin_classes": [
        {
            "name": "Vector2",
            "is_keyed": False,
            "has_destructor": False,
            "members": [
                {"name": "x", "type": "float"},
                {"name": "y", "type": "float"},
            ],
            "constants": [
                {"name": "ZERO", "type": "Vector2", "value": "Vector2(0, 0)"}
            ],
        },
    ],
    "classes": [
        {
            "name": "Object",
            "is_refcounted": True,
            "is_instantiable": True,
            "api_type": "core",
        },
        {
            "name": "Node",
            "inherits": "Object",
            "is_refcounted": True,
            "is_instantiable": True,
            "api_type": "core",
            "properties": [
                {"name": "position", "type": "Vector2", "getter": "get_position"}
            ],
        },
    ],
    "singletons": [],
    "native_structures": [],
}


@pytest.fixture
def complete_api_json_path(tmp_path: Path) -> Path:
    path = tmp_path / "extension_api.json"
    path.write_text(json.dumps(COMPLETE_FAKE_API))
    return path


@pytest.fixture
def specifications_root(tmp_path: Path):
    root = tmp_path / "specifications"
    root.mkdir()
    (root / "__init__.py").write_text("")
    return root


def test_add_version_first_version(complete_api_json_path, specifications_root):
    """add-version --first-version should create a complete, importable package."""
    result = runner.invoke(
        app,
        [
            "specifications",
            "add-version",
            "--version",
            "v4_4_0",
            "--api",
            str(complete_api_json_path),
            "--first-version",
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Version v4_4_0 added successfully" in result.output

    version_dir = specifications_root / "v4_4_0"
    assert (version_dir / "spec.py").exists()
    assert (version_dir / "__init__.py").exists()
    assert (version_dir / "builtin_classes.py").exists()
    assert (version_dir / "classes.py").exists()
    assert (version_dir / "signals.py").exists()

    spec_source = (version_dir / "spec.py").read_text()
    assert "class Specification4_4_0(BaseModel):" in spec_source
    assert "from godotllminteraction.specifications.shared.spec import (" in spec_source


def test_add_version_with_base_version(complete_api_json_path, specifications_root):
    """add-version --base-version should create a package that may import enums from base."""
    result = runner.invoke(
        app,
        [
            "specifications",
            "add-version",
            "--version",
            "v4_4_0",
            "--api",
            str(complete_api_json_path),
            "--first-version",
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app,
        [
            "specifications",
            "add-version",
            "--version",
            "v4_4_1",
            "--api",
            str(complete_api_json_path),
            "--base-version",
            "v4_4_0",
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Version v4_4_1 added successfully" in result.output

    version_dir = specifications_root / "v4_4_1"
    assert (version_dir / "spec.py").exists()
    spec_source = (version_dir / "spec.py").read_text()
    assert "class Specification4_4_1(BaseModel):" in spec_source


def test_add_version_requires_base_version_or_first(
    complete_api_json_path, specifications_root
):
    """add-version without --base-version or --first-version should error."""
    result = runner.invoke(
        app,
        [
            "specifications",
            "add-version",
            "--version",
            "v4_4_1",
            "--api",
            str(complete_api_json_path),
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert result.exit_code != 0
    assert "--base-version is required" in result.output


def test_add_version_test_guidance_output(complete_api_json_path, specifications_root):
    """add-version should output test guidance."""
    result = runner.invoke(
        app,
        [
            "specifications",
            "add-version",
            "--version",
            "v4_4_0",
            "--api",
            str(complete_api_json_path),
            "--first-version",
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Test guidance:" in result.output


_ALL_VERSIONS = discover_all_versions()
_INSTALLED = installed_godot_versions()
_TESTABLE_VERSIONS = [v for v in _ALL_VERSIONS if v in _INSTALLED]


@pytest.mark.parametrize("version", _TESTABLE_VERSIONS)
def test_add_version_with_real_godot_dump(
    godot_binary_for_version, version, tmp_path: Path
):
    """Full e2e: dump from real Godot binary, run add-version, verify importability."""
    data = godot_binary_for_version(version)
    api_path = tmp_path / "extension_api.json"
    api_path.write_text(json.dumps(data))

    specs_root = tmp_path / "specifications"
    specs_root.mkdir()
    (specs_root / "__init__.py").write_text("")

    version_pkg = "v" + version.replace(".", "_")

    result = runner.invoke(
        app,
        [
            "specifications",
            "add-version",
            "--version",
            version_pkg,
            "--api",
            str(api_path),
            "--first-version",
            "--specs-root",
            str(specs_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (specs_root / version_pkg / "spec.py").exists()
    assert (specs_root / version_pkg / "classes.py").exists()
