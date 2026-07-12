"""Unit tests for the schema diff logic."""

from __future__ import annotations


from godotllminteraction.specifications.schema_diff import (
    EXPECTED_SECTIONS,
    SchemaDiffReport,
    collect_json_keys,
    collect_model_fields,
    compute_schema_diff,
    extract_enum_values,
)

_ENUM_NAMES = {
    "GodotTypeNameEnum",
    "UtilityFunctionCategoryEnum",
    "BuiltinClassOperatorNameEnum",
    "GodotArgumentMetaEnum",
    "ClassApiTypeEnum",
}


class TestCollectJsonKeys:
    def test_top_level_keys(self):
        data = {"header": {}, "classes": [], "singletons": []}
        keys = collect_json_keys(data)
        assert keys[""] == {"header", "classes", "singletons"}

    def test_nested_dict_keys(self):
        data = {"header": {"version_major": 4, "version_minor": 7}}
        keys = collect_json_keys(data)
        assert keys["header"] == {"version_major", "version_minor"}

    def test_list_of_dicts_unions_keys(self):
        data = {
            "classes": [
                {"name": "Node", "is_refcounted": True},
                {"name": "Resource", "is_instantiable": True},
            ]
        }
        keys = collect_json_keys(data)
        assert keys["classes"] == {"name", "is_refcounted", "is_instantiable"}

    def test_deeply_nested_list_keys(self):
        data = {
            "classes": [
                {"methods": [{"name": "foo", "hash": 1}]},
                {"methods": [{"name": "bar", "hash": 2, "hash_compatibility": [3]}]},
            ]
        }
        keys = collect_json_keys(data)
        assert keys["classes.methods"] == {"name", "hash", "hash_compatibility"}

    def test_empty_data(self):
        keys = collect_json_keys({})
        assert keys == {"": set()}


class TestCollectModelFields:
    def test_top_level_sections(self):
        fields = collect_model_fields()
        assert fields[""] == EXPECTED_SECTIONS

    def test_header_fields(self):
        fields = collect_model_fields()
        assert "version_major" in fields["header"]
        assert "version_minor" in fields["header"]

    def test_class_fields(self):
        fields = collect_model_fields()
        assert "name" in fields["classes"]
        assert "methods" in fields["classes"]
        assert "is_refcounted" in fields["classes"]

    def test_method_fields(self):
        fields = collect_model_fields()
        assert "hash" in fields["classes.methods"]
        assert "hash_compatibility" in fields["classes.methods"]
        assert "is_virtual" in fields["classes.methods"]

    def test_method_argument_fields(self):
        fields = collect_model_fields()
        assert "name" in fields["classes.methods.arguments"]
        assert "type" in fields["classes.methods.arguments"]
        assert "meta" in fields["classes.methods.arguments"]


class TestExtractEnumValues:
    def test_type_names(self):
        data = {
            "utility_functions": [{"return_type": "float"}],
            "builtin_classes": [
                {"members": [{"type": "Vector2"}]},
            ],
        }
        values = extract_enum_values(data)
        assert "float" in values["GodotTypeNameEnum"]
        assert "Vector2" in values["GodotTypeNameEnum"]

    def test_categories(self):
        data = {"utility_functions": [{"category": "math"}, {"category": "random"}]}
        values = extract_enum_values(data)
        assert values["UtilityFunctionCategoryEnum"] == {"math", "random"}

    def test_operators(self):
        data = {
            "builtin_classes": [{"operators": [{"name": "=="}, {"name": "unary-"}]}]
        }
        values = extract_enum_values(data)
        assert "==" in values["BuiltinClassOperatorNameEnum"]
        assert "unary-" in values["BuiltinClassOperatorNameEnum"]

    def test_metas(self):
        data = {
            "classes": [
                {
                    "methods": [
                        {"arguments": [{"meta": "int64"}]},
                    ]
                }
            ]
        }
        values = extract_enum_values(data)
        assert "int64" in values["GodotArgumentMetaEnum"]

    def test_api_types(self):
        data = {"classes": [{"api_type": "core"}, {"api_type": "editor"}]}
        values = extract_enum_values(data)
        assert values["ClassApiTypeEnum"] == {"core", "editor"}

    def test_all_five_enums_present(self):
        values = extract_enum_values({})
        assert set(values.keys()) == _ENUM_NAMES


class TestComputeSchemaDiff:
    def test_returns_pydantic_model(self):
        report = compute_schema_diff({})
        assert isinstance(report, SchemaDiffReport)

    def test_no_diff_for_matching_data(self):
        data = {
            "header": {"version_major": 4, "version_minor": 7, "version_patch": 0},
            "builtin_class_sizes": [],
            "builtin_class_member_offsets": [],
            "global_constants": [],
            "global_enums": [],
            "utility_functions": [],
            "builtin_classes": [],
            "classes": [],
            "singletons": [],
            "native_structures": [],
        }
        report = compute_schema_diff(data)
        assert not report.requires_human_intervention
        assert report.added_fields == []
        assert report.new_top_level_sections == []

    def test_new_top_level_section_detected(self):
        data = {"header": {}, "new_section": []}
        report = compute_schema_diff(data)
        assert "new_section" in report.new_top_level_sections
        assert report.requires_human_intervention

    def test_added_field_detected(self):
        data = {"classes": [{"name": "Node", "new_field": "value"}]}
        report = compute_schema_diff(data)
        added_paths = [f.path for f in report.added_fields]
        assert any("new_field" in p for p in added_paths)

    def test_removed_optional_field_no_human_intervention(self):
        data = {"classes": [{"name": "Node"}]}
        report = compute_schema_diff(data)
        removed = [f for f in report.removed_fields if "classes" in f.path]
        optional_removed = [f for f in removed if f.was_optional]
        assert all(f.action == "no_action_needed" for f in optional_removed)

    def test_enum_comparison_with_base(self):
        data = {"utility_functions": [{"category": "math"}]}
        base_enums = {
            "GodotTypeNameEnum": {"float", "int"},
            "UtilityFunctionCategoryEnum": {"math", "random"},
            "BuiltinClassOperatorNameEnum": {"=="},
            "GodotArgumentMetaEnum": {"int64"},
            "ClassApiTypeEnum": {"core"},
        }
        report = compute_schema_diff(data, base_enum_values=base_enums)
        cat_comp = report.enum_comparison["UtilityFunctionCategoryEnum"]
        assert cat_comp.identical_to_base is False
        assert "math" not in cat_comp.new_values

    def test_enum_comparison_identical(self):
        data = {"utility_functions": [{"category": "math"}, {"category": "random"}]}
        base_enums = {
            "UtilityFunctionCategoryEnum": {"math", "random"},
        }
        report = compute_schema_diff(data, base_enum_values=base_enums)
        cat_comp = report.enum_comparison["UtilityFunctionCategoryEnum"]
        assert cat_comp.identical_to_base is True
        assert cat_comp.import_from_base is True

    def test_test_guidance_has_suggestions_for_added_fields(self):
        data = {"classes": [{"name": "Node", "new_field": "value"}]}
        report = compute_schema_diff(data)
        assert len(report.test_guidance.detectable) > 0

    def test_test_guidance_generic_when_no_changes(self):
        data = {
            "header": {},
            "builtin_class_sizes": [],
            "builtin_class_member_offsets": [],
            "global_constants": [],
            "global_enums": [],
            "utility_functions": [],
            "builtin_classes": [],
            "classes": [],
            "singletons": [],
            "native_structures": [],
        }
        report = compute_schema_diff(data)
        assert (
            report.test_guidance.generic
            == "No schema changes detected. No new tests needed."
        )

    def test_version_and_base_version_in_report(self):
        report = compute_schema_diff({}, version="v4_4_1", base_version="v4_4_0")
        assert report.version == "v4_4_1"
        assert report.base_version == "v4_4_0"

    def test_report_serializes_to_json(self):
        report = compute_schema_diff({}, version="v4_4_1")
        import json

        parsed = json.loads(report.model_dump_json())
        assert parsed["version"] == "v4_4_1"
