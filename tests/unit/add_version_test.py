"""Unit tests for the add-version CLI logic."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from godotllminteraction.cli import app
from godotllminteraction.cli.specifications import (
    _read_godot_versions,
    _render_spec_py_template,
    _version_to_class_suffix,
    _version_to_pkg,
)

runner = CliRunner()


class TestVersionToPkg:
    def test_basic(self):
        assert _version_to_pkg("4.4.0") == "v4_4_0"

    def test_patch_version(self):
        assert _version_to_pkg("4.6.2") == "v4_6_2"


class TestVersionToClassSuffix:
    def test_basic(self):
        assert _version_to_class_suffix("v4_4_0") == "4_4_0"

    def test_without_v_prefix(self):
        assert _version_to_class_suffix("4_4_0") == "4_4_0"


class TestRenderSpecPyTemplate:
    def test_generates_valid_python(self):
        source = _render_spec_py_template("v4_4_0", None, None)
        assert "class Specification4_4_0(BaseModel):" in source
        assert "from godotllminteraction.specifications.shared.spec import (" in source
        assert "header: Header = Field" in source

    def test_generates_enum_marker_blocks_without_base(self):
        source = _render_spec_py_template("v4_4_0", None, None)
        assert "sync-enums --version v4_4_0" in source
        assert "PLACEHOLDER" in source
        assert "class GodotTypeNameEnum(str, Enum):" in source

    def test_imports_enums_from_base_when_identical(self):
        enum_comparison = {
            "GodotTypeNameEnum": {"identical_to_base": True, "import_from_base": True},
            "UtilityFunctionCategoryEnum": {
                "identical_to_base": True,
                "import_from_base": True,
            },
            "BuiltinClassOperatorNameEnum": {
                "identical_to_base": True,
                "import_from_base": True,
            },
            "GodotArgumentMetaEnum": {
                "identical_to_base": True,
                "import_from_base": True,
            },
            "ClassApiTypeEnum": {"identical_to_base": True, "import_from_base": True},
        }
        source = _render_spec_py_template("v4_4_1", "v4_4_0", enum_comparison)
        assert "from godotllminteraction.specifications.v4_4_0.spec import (" in source
        assert "GodotTypeNameEnum," in source
        assert "GodotTypeName," in source
        assert "PLACEHOLDER" not in source

    def test_generates_fresh_enums_when_different(self):
        enum_comparison = {
            "GodotTypeNameEnum": {
                "identical_to_base": False,
                "import_from_base": False,
            },
            "UtilityFunctionCategoryEnum": {
                "identical_to_base": True,
                "import_from_base": True,
            },
            "BuiltinClassOperatorNameEnum": {
                "identical_to_base": True,
                "import_from_base": True,
            },
            "GodotArgumentMetaEnum": {
                "identical_to_base": True,
                "import_from_base": True,
            },
            "ClassApiTypeEnum": {"identical_to_base": True, "import_from_base": True},
        }
        source = _render_spec_py_template("v4_5_0", "v4_4_1", enum_comparison)
        assert "class GodotTypeNameEnum(str, Enum):" in source
        assert "PLACEHOLDER" in source
        assert "from godotllminteraction.specifications.v4_4_1.spec import (" in source
        assert "UtilityFunctionCategoryEnum," in source

    def test_specification_class_has_all_sections(self):
        source = _render_spec_py_template("v4_4_0", None, None)
        for section in [
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
        ]:
            assert section in source

    def test_specification_class_has_cached_properties(self):
        source = _render_spec_py_template("v4_4_0", None, None)
        assert "class_names" in source
        assert "builtin_class_names" in source


class TestAddVersionCliValidation:
    """Unit tests for CLI argument validation (no real generation)."""

    def test_requires_base_version_or_first_version(self, tmp_path):
        api_path = tmp_path / "extension_api.json"
        api_path.write_text("{}")
        result = runner.invoke(
            app,
            [
                "specifications",
                "add-version",
                "--version",
                "v4_4_1",
                "--api",
                str(api_path),
                "--specs-root",
                str(tmp_path / "specs"),
            ],
        )
        assert result.exit_code != 0
        assert "--base-version is required" in result.output

    def test_first_version_skips_base_requirement(self, tmp_path):
        api_path = tmp_path / "extension_api.json"
        api_path.write_text("{}")
        result = runner.invoke(
            app,
            [
                "specifications",
                "add-version",
                "--version",
                "v4_4_0",
                "--api",
                str(api_path),
                "--first-version",
                "--specs-root",
                str(tmp_path / "specs"),
            ],
        )
        # Will fail later (no complete API data) but should pass the base-version check
        assert "--base-version is required" not in result.output

    def test_invalid_version_format_rejected(self, tmp_path):
        api_path = tmp_path / "extension_api.json"
        api_path.write_text("{}")
        result = runner.invoke(
            app,
            [
                "specifications",
                "add-version",
                "--version",
                "invalid",
                "--api",
                str(api_path),
                "--first-version",
                "--specs-root",
                str(tmp_path / "specs"),
            ],
        )
        assert result.exit_code != 0
        assert "Invalid version" in result.output

    def test_invalid_base_version_format_rejected(self, tmp_path):
        api_path = tmp_path / "extension_api.json"
        api_path.write_text("{}")
        result = runner.invoke(
            app,
            [
                "specifications",
                "add-version",
                "--version",
                "v4_4_1",
                "--api",
                str(api_path),
                "--base-version",
                "invalid",
                "--specs-root",
                str(tmp_path / "specs"),
            ],
        )
        assert result.exit_code != 0
        assert "Invalid base version" in result.output


class TestReadGodotVersions:
    def test_reads_versions_file(self):
        fake_content = "4.4.0\n4.4.1\n4.5.0\n"
        with patch(
            "godotllminteraction.cli.specifications._VERSIONS_FILE"
        ) as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = fake_content
            versions = _read_godot_versions()
            assert versions == ["4.4.0", "4.4.1", "4.5.0"]

    def test_skips_comments_and_blank_lines(self):
        fake_content = "# comment\n4.4.0\n\n  \n4.4.1\n"
        with patch(
            "godotllminteraction.cli.specifications._VERSIONS_FILE"
        ) as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = fake_content
            versions = _read_godot_versions()
            assert versions == ["4.4.0", "4.4.1"]

    def test_returns_empty_list_when_file_missing(self):
        with patch(
            "godotllminteraction.cli.specifications._VERSIONS_FILE"
        ) as mock_path:
            mock_path.exists.return_value = False
            assert _read_godot_versions() == []
