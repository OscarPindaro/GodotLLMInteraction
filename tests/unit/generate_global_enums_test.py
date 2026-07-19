"""Unit tests for the generate-global-enums codegen step."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from godotllminteraction.cli import app
from godotllminteraction.cli.specifications import (
    _extract_global_enums,
    _flatten_enum_class_name,
    render_global_enums_source,
)

runner = CliRunner()

pytestmark = [pytest.mark.specs, pytest.mark.cli]


# --- Pure function tests ----------------------------------------------------


class TestFlattenEnumClassName:
    def test_simple_name(self):
        assert _flatten_enum_class_name("Key") == "Key"

    def test_dotted_name(self):
        assert _flatten_enum_class_name("Variant.Type") == "VariantType"

    def test_another_dotted_name(self):
        assert _flatten_enum_class_name("Variant.Operator") == "VariantOperator"


class TestExtractGlobalEnums:
    def test_empty(self):
        assert _extract_global_enums({}) == []

    def test_single_enum(self):
        data = {
            "global_enums": [
                {
                    "name": "Key",
                    "is_bitfield": False,
                    "values": [
                        {"name": "KEY_A", "value": 65},
                        {"name": "KEY_B", "value": 66},
                    ],
                }
            ]
        }
        result = _extract_global_enums(data)
        assert len(result) == 1
        name, is_bitfield, values = result[0]
        assert name == "Key"
        assert is_bitfield is False
        assert values == [("KEY_A", 65), ("KEY_B", 66)]

    def test_sorted_by_enum_name(self):
        data = {
            "global_enums": [
                {"name": "Zoo", "values": [{"name": "Z", "value": 0}]},
                {"name": "Apple", "values": [{"name": "A", "value": 0}]},
            ]
        }
        result = _extract_global_enums(data)
        assert result[0][0] == "Apple"
        assert result[1][0] == "Zoo"

    def test_values_sorted_by_name(self):
        data = {
            "global_enums": [
                {
                    "name": "Key",
                    "values": [
                        {"name": "KEY_Z", "value": 3},
                        {"name": "KEY_A", "value": 1},
                        {"name": "KEY_M", "value": 2},
                    ],
                }
            ]
        }
        result = _extract_global_enums(data)
        _, _, values = result[0]
        assert [v[0] for v in values] == ["KEY_A", "KEY_M", "KEY_Z"]

    def test_negative_values(self):
        data = {
            "global_enums": [
                {
                    "name": "JoyButton",
                    "values": [{"name": "JOY_BUTTON_INVALID", "value": -1}],
                }
            ]
        }
        result = _extract_global_enums(data)
        _, _, values = result[0]
        assert values == [("JOY_BUTTON_INVALID", -1)]


class TestRenderGlobalEnumsSource:
    def test_basic_enum(self, load_module):
        data = {
            "global_enums": [
                {
                    "name": "Key",
                    "is_bitfield": False,
                    "values": [
                        {"name": "KEY_A", "value": 65},
                        {"name": "KEY_B", "value": 66},
                    ],
                }
            ]
        }
        source = render_global_enums_source(data, "v9_9_9")
        assert "class Key(IntEnum):" in source
        assert "KEY_A = 65" in source
        assert "KEY_B = 66" in source

        mod = load_module(source)
        assert mod.Key.KEY_A == 65
        assert mod.Key.KEY_B == 66

    def test_dotted_name_flattened(self, load_module):
        data = {
            "global_enums": [
                {
                    "name": "Variant.Type",
                    "is_bitfield": False,
                    "values": [{"name": "TYPE_NIL", "value": 0}],
                }
            ]
        }
        source = render_global_enums_source(data, "v9_9_9")
        assert "class VariantType(IntEnum):" in source
        assert "class Variant.Type(IntEnum):" not in source

        mod = load_module(source)
        assert mod.VariantType.TYPE_NIL == 0

    def test_by_name_dict(self, load_module):
        data = {
            "global_enums": [
                {
                    "name": "Key",
                    "values": [{"name": "KEY_A", "value": 65}],
                },
                {
                    "name": "Variant.Type",
                    "values": [{"name": "TYPE_NIL", "value": 0}],
                },
            ]
        }
        source = render_global_enums_source(data, "v9_9_9")
        mod = load_module(source)
        assert "Key" in mod.BY_NAME
        assert "Variant.Type" in mod.BY_NAME
        assert mod.BY_NAME["Key"] is mod.Key
        assert mod.BY_NAME["Variant.Type"] is mod.VariantType

    def test_empty_enums_section(self, load_module):
        source = render_global_enums_source({}, "v9_9_9")
        mod = load_module(source)
        assert mod.BY_NAME == {}

    def test_empty_enum_has_pass(self):
        data = {
            "global_enums": [
                {"name": "Empty", "values": []},
            ]
        }
        source = render_global_enums_source(data, "v9_9_9")
        assert "class Empty(IntEnum):" in source
        assert "pass" in source

    def test_version_in_docstring(self):
        data = {"global_enums": []}
        source = render_global_enums_source(data, "v4_7_0")
        assert "v4_7_0" in source


# --- CLI command tests ------------------------------------------------------


class TestGenerateGlobalEnumsCli:
    @pytest.fixture
    def api_json_path(self, tmp_path: Path) -> Path:
        path = tmp_path / "extension_api.json"
        path.write_text(
            json.dumps(
                {
                    "global_enums": [
                        {
                            "name": "Key",
                            "values": [
                                {"name": "KEY_A", "value": 65},
                                {"name": "KEY_ESCAPE", "value": 4194305},
                            ],
                        }
                    ]
                }
            )
        )
        return path

    def test_generates_file(self, api_json_path, tmp_path):
        specs_root = tmp_path / "specs"
        result = runner.invoke(
            app,
            [
                "specifications",
                "generate-global-enums",
                "--version",
                "v9_9_9",
                "--api",
                str(api_json_path),
                "--specs-root",
                str(specs_root),
            ],
        )
        assert result.exit_code == 0, result.output
        enums_path = specs_root / "v9_9_9" / "global_enums.py"
        assert enums_path.exists()
        content = enums_path.read_text()
        assert "class Key(IntEnum):" in content
        assert "KEY_A = 65" in content

    def test_check_mode_reports_stale(self, api_json_path, tmp_path):
        specs_root = tmp_path / "specs"
        check_args = [
            "specifications",
            "generate-global-enums",
            "--version",
            "v9_9_9",
            "--api",
            str(api_json_path),
            "--check",
            "--specs-root",
            str(specs_root),
        ]
        stale_result = runner.invoke(app, check_args)
        assert stale_result.exit_code != 0
        assert "stale" in stale_result.output.lower()

    def test_check_mode_passes_after_generation(self, api_json_path, tmp_path):
        specs_root = tmp_path / "specs"
        gen_args = [
            "specifications",
            "generate-global-enums",
            "--version",
            "v9_9_9",
            "--api",
            str(api_json_path),
            "--specs-root",
            str(specs_root),
        ]
        check_args = [*gen_args, "--check"]

        runner.invoke(app, gen_args)
        up_to_date = runner.invoke(app, check_args)
        assert up_to_date.exit_code == 0, up_to_date.output

    def test_invalid_version_rejected(self, api_json_path, tmp_path):
        result = runner.invoke(
            app,
            [
                "specifications",
                "generate-global-enums",
                "--version",
                "invalid",
                "--api",
                str(api_json_path),
                "--specs-root",
                str(tmp_path / "specs"),
            ],
        )
        assert result.exit_code != 0
        assert "Invalid version" in result.output
