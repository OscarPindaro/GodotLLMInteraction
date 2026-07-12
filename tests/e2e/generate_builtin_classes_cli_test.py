from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from godotllminteraction.cli import app

runner = CliRunner()

pytestmark = [pytest.mark.cli, pytest.mark.specs]

FAKE_API = {
    "builtin_classes": [
        {
            "name": "Vector2",
            "members": [{"name": "x", "type": "float"}, {"name": "y", "type": "float"}],
            "constants": [
                {"name": "ZERO", "type": "Vector2", "value": "Vector2(0, 0)"}
            ],
        },
    ]
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


def test_rejects_invalid_version_format(api_json_path, specifications_root):
    result = runner.invoke(
        app,
        [
            "specifications",
            "generate-builtin-classes",
            "--version",
            "4_7_0",
            "--api",
            str(api_json_path),
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert result.exit_code != 0
    assert not specifications_root.exists()


def test_creates_version_directory_and_files(api_json_path, specifications_root):
    result = runner.invoke(
        app,
        [
            "specifications",
            "generate-builtin-classes",
            "--version",
            "v4_7_0",
            "--api",
            str(api_json_path),
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert result.exit_code == 0, result.output
    version_dir = specifications_root / "v4_7_0"
    assert (version_dir / "__init__.py").exists()
    assert (version_dir / "builtin_classes.py").exists()
    assert (version_dir / "constants.py").exists()
    assert "class Vector2v4_7_0" in (version_dir / "builtin_classes.py").read_text()


def test_check_fails_when_missing_then_passes_after_generation(
    api_json_path, specifications_root
):
    check_args = [
        "specifications",
        "generate-builtin-classes",
        "--version",
        "v4_7_0",
        "--api",
        str(api_json_path),
        "--check",
        "--specs-root",
        str(specifications_root),
    ]

    missing_result = runner.invoke(app, check_args)
    assert missing_result.exit_code != 0

    generate_result = runner.invoke(
        app,
        [
            "specifications",
            "generate-builtin-classes",
            "--version",
            "v4_7_0",
            "--api",
            str(api_json_path),
            "--specs-root",
            str(specifications_root),
        ],
    )
    assert generate_result.exit_code == 0, generate_result.output

    up_to_date_result = runner.invoke(app, check_args)
    assert up_to_date_result.exit_code == 0, up_to_date_result.output


def test_regenerating_is_idempotent(api_json_path, specifications_root):
    args = [
        "specifications",
        "generate-builtin-classes",
        "--version",
        "v4_7_0",
        "--api",
        str(api_json_path),
        "--specs-root",
        str(specifications_root),
    ]
    runner.invoke(app, args)
    version_dir = specifications_root / "v4_7_0"
    first_models = (version_dir / "builtin_classes.py").read_text()
    first_constants = (version_dir / "constants.py").read_text()

    second_result = runner.invoke(app, args)

    assert second_result.exit_code == 0
    assert (version_dir / "builtin_classes.py").read_text() == first_models
    assert (version_dir / "constants.py").read_text() == first_constants
