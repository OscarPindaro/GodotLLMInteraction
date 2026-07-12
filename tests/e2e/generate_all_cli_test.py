from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from godotllminteraction.cli import app

runner = CliRunner()

FAKE_API = {
    "utility_functions": [],
    "global_enums": [],
    "builtin_classes": [
        {
            "name": "Vector2",
            "members": [{"name": "x", "type": "float"}, {"name": "y", "type": "float"}],
            "constants": [
                {"name": "ZERO", "type": "Vector2", "value": "Vector2(0, 0)"}
            ],
        },
    ],
    "classes": [
        {"name": "Object", "api_type": "core"},
        {
            "name": "Node",
            "inherits": "Object",
            "api_type": "core",
            "properties": [{"name": "position", "type": "Vector2"}],
        },
    ],
}


@pytest.fixture
def api_json_path(tmp_path: Path) -> Path:
    path = tmp_path / "extension_api.json"
    path.write_text(json.dumps(FAKE_API))
    return path


@pytest.fixture
def specifications_root(tmp_path: Path):
    root = tmp_path / "specifications"
    return root


def test_generate_all_skips_enum_sync_when_spec_py_missing(
    api_json_path, specifications_root
):
    result = runner.invoke(
        app,
        [
            "specifications",
            "generate-all",
            "--version",
            "v9_9_9",
            "--api",
            str(api_json_path),
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Skipping enum sync" in result.output
    version_dir = specifications_root / "v9_9_9"
    assert (version_dir / "builtin_classes.py").exists()
    assert (version_dir / "classes.py").exists()


def test_generate_all_produces_working_package(api_json_path, specifications_root):
    result = runner.invoke(
        app,
        [
            "specifications",
            "generate-all",
            "--version",
            "v9_9_9",
            "--api",
            str(api_json_path),
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert result.exit_code == 0, result.output
    version_dir = specifications_root / "v9_9_9"
    classes_source = (version_dir / "classes.py").read_text()
    assert "class Nodev9_9_9(Objectv9_9_9):" in classes_source
    assert "position: Vector2v9_9_9" in classes_source


def test_generate_all_check_mode_reports_stale_then_passes(
    api_json_path, specifications_root
):
    check_args = [
        "specifications",
        "generate-all",
        "--version",
        "v9_9_9",
        "--api",
        str(api_json_path),
        "--check",
        "--specs-root",
        str(specifications_root),
    ]
    missing_result = runner.invoke(app, check_args)
    assert missing_result.exit_code != 0

    runner.invoke(
        app,
        [
            "specifications",
            "generate-all",
            "--version",
            "v9_9_9",
            "--api",
            str(api_json_path),
            "--specs-root",
            str(specifications_root),
        ],
    )

    up_to_date_result = runner.invoke(app, check_args)
    assert up_to_date_result.exit_code == 0, up_to_date_result.output
