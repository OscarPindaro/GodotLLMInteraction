"""Schema diff logic for comparing extension_api.json against shared pydantic models.

This module provides the core logic for the ``gli specifications diff-schema`` CLI
command. It walks the JSON recursively, collects all keys at each dot-separated
path, and compares them against the shared pydantic model's field definitions.
The result is a typed :class:`SchemaDiffReport` (pydantic model) with actionable
test guidance.
"""

from __future__ import annotations

import typing
from typing import Any, Optional

from pydantic import BaseModel, Field

from godotllminteraction.specifications.shared.spec import (
    BuiltinClass,
    BuiltinClassMemberOffsets,
    BuiltinClassSizeType,
    GodotClass,
    GodotEnum,
    GlobalConstant,
    Header,
    NativeStructure,
    Singleton,
    UtilityFunction,
)

SECTION_MODELS: dict[str, type[BaseModel]] = {
    "header": Header,
    "builtin_class_sizes": BuiltinClassSizeType,
    "builtin_class_member_offsets": BuiltinClassMemberOffsets,
    "global_constants": GlobalConstant,
    "global_enums": GodotEnum,
    "utility_functions": UtilityFunction,
    "builtin_classes": BuiltinClass,
    "classes": GodotClass,
    "singletons": Singleton,
    "native_structures": NativeStructure,
}

EXPECTED_SECTIONS = set(SECTION_MODELS.keys())

_ENUM_NAMES = [
    "GodotTypeNameEnum",
    "UtilityFunctionCategoryEnum",
    "BuiltinClassOperatorNameEnum",
    "GodotArgumentMetaEnum",
    "ClassApiTypeEnum",
]


# --- Report models ----------------------------------------------------------


class AddedField(BaseModel):
    path: str = Field(description="Dot-separated path of the added field")
    auto_generatable: bool = Field(
        default=True, description="Whether the field can be auto-generated"
    )


class RemovedField(BaseModel):
    path: str = Field(description="Dot-separated path of the removed field")
    was_optional: bool = Field(
        description="Whether the field was Optional in the shared model"
    )
    action: str = Field(
        description="Suggested action: 'no_action_needed' or 'flag_for_human'"
    )


class EnumComparison(BaseModel):
    identical_to_base: Optional[bool] = Field(
        default=None,
        description="Whether the enum values are identical to the base version; None if no base",
    )
    import_from_base: bool = Field(
        description="Whether the enum should be imported from the base version"
    )
    new_values: list[str] = Field(
        default_factory=list,
        description="New enum values not present in the base version",
    )


class TestGuidance(BaseModel):
    detectable: list[str] = Field(
        default_factory=list,
        description="Specific, detectable test suggestions",
    )
    generic: str = Field(
        description="Generic guidance message when no specific suggestions are available"
    )


class SchemaDiffReport(BaseModel):
    version: str = Field(default="", description="The new version being diffed")
    base_version: str = Field(
        default="", description="The base version compared against"
    )
    requires_human_intervention: bool = Field(
        description="Whether structural changes require manual review"
    )
    added_fields: list[AddedField] = Field(
        default_factory=list, description="Fields present in JSON but not in the model"
    )
    removed_fields: list[RemovedField] = Field(
        default_factory=list, description="Fields in the model but absent from JSON"
    )
    type_changes: list[dict] = Field(
        default_factory=list, description="Fields whose type changed between versions"
    )
    new_top_level_sections: list[str] = Field(
        default_factory=list,
        description="New top-level sections in JSON not in the shared model",
    )
    enum_comparison: dict[str, EnumComparison] = Field(
        default_factory=dict,
        description="Per-enum comparison results",
    )
    test_guidance: TestGuidance = Field(
        description="Actionable test suggestions derived from the diff"
    )


# --- JSON key collection ----------------------------------------------------


def collect_json_keys(data: dict) -> dict[str, set[str]]:
    """Walk extension_api.json recursively, collecting all keys at each dot-separated path.

    For list fields, keys are unioned across all dict items.
    Returns ``{path: {key1, key2, ...}}``.
    """
    keys_by_path: dict[str, set[str]] = {}
    _collect_keys(data, "", keys_by_path)
    return keys_by_path


def _collect_keys(value: Any, path: str, keys_by_path: dict[str, set[str]]) -> None:
    if isinstance(value, dict):
        if path not in keys_by_path:
            keys_by_path[path] = set()
        keys_by_path[path].update(value.keys())
        for k, v in value.items():
            child_path = f"{path}.{k}" if path else k
            _collect_keys(v, child_path, keys_by_path)
    elif isinstance(value, list):
        for item in value:
            _collect_keys(item, path, keys_by_path)


# --- Model field collection -------------------------------------------------


def _unwrap_annotation(annotation: Any) -> tuple[type[BaseModel] | None, bool]:
    """Unwrap Optional and List wrappers to find the inner BaseModel type.

    Returns (inner_type, is_list). inner_type is None if not a BaseModel.
    """
    inner = annotation
    origin = typing.get_origin(inner)
    if origin is typing.Union:
        args = typing.get_args(inner)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            inner = non_none[0]
    origin = typing.get_origin(inner)
    is_list = origin is list
    if is_list:
        args = typing.get_args(inner)
        if args:
            inner = args[0]
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return inner, is_list
    return None, is_list


def collect_model_fields() -> dict[str, set[str]]:
    """Collect all field names at each dot-separated path from the shared models.

    Returns ``{path: {field1, field2, ...}}``.
    """
    fields_by_path: dict[str, set[str]] = {"": set(SECTION_MODELS.keys())}
    for section_name, model in SECTION_MODELS.items():
        _collect_model_fields(model, section_name, fields_by_path)
    return fields_by_path


def _collect_model_fields(
    model: type[BaseModel], path: str, fields_by_path: dict[str, set[str]]
) -> None:
    if path in fields_by_path:
        return
    fields_by_path[path] = set(model.model_fields.keys())
    for field_name, field_info in model.model_fields.items():
        inner, _is_list = _unwrap_annotation(field_info.annotation)
        if inner is not None:
            child_path = f"{path}.{field_name}" if path else field_name
            _collect_model_fields(inner, child_path, fields_by_path)


# --- Enum value extraction --------------------------------------------------


def extract_enum_values(data: dict) -> dict[str, set[str]]:
    """Extract all 5 enum value sets from extension_api.json data."""
    return {
        "GodotTypeNameEnum": _extract_type_names(data),
        "UtilityFunctionCategoryEnum": _extract_utility_function_categories(data),
        "BuiltinClassOperatorNameEnum": _extract_operator_symbols(data),
        "GodotArgumentMetaEnum": _extract_argument_metas(data),
        "ClassApiTypeEnum": _extract_class_api_types(data),
    }


def _extract_type_names(data: dict) -> set[str]:
    names: set[str] = set()
    for fn in data.get("utility_functions", []):
        if "return_type" in fn:
            names.add(fn["return_type"])
    for cls in data.get("builtin_classes", []):
        if "indexing_return_type" in cls:
            names.add(cls["indexing_return_type"])
        for op in cls.get("operators", []):
            if "right_type" in op:
                names.add(op["right_type"])
            names.add(op["return_type"])
        for member in cls.get("members", []):
            names.add(member["type"])
        for const in cls.get("constants", []):
            names.add(const["type"])
        for ctor in cls.get("constructors", []):
            for arg in ctor.get("arguments", []):
                names.add(arg["type"])
        for method in cls.get("methods", []):
            if "return_type" in method:
                names.add(method["return_type"])
            for arg in method.get("arguments", []):
                names.add(arg["type"])
    return names


def _extract_utility_function_categories(data: dict) -> set[str]:
    return {fn["category"] for fn in data.get("utility_functions", [])}


def _extract_operator_symbols(data: dict) -> set[str]:
    symbols: set[str] = set()
    for cls in data.get("builtin_classes", []):
        for op in cls.get("operators", []):
            symbols.add(op["name"])
    return symbols


def _extract_argument_metas(data: dict) -> set[str]:
    metas: set[str] = set()
    for cls in data.get("classes", []):
        for method in cls.get("methods", []):
            for arg in method.get("arguments", []):
                if "meta" in arg:
                    metas.add(arg["meta"])
            if "meta" in method.get("return_value", {}):
                metas.add(method["return_value"]["meta"])
    return metas


def _extract_class_api_types(data: dict) -> set[str]:
    return {cls["api_type"] for cls in data.get("classes", [])}


# --- Diff computation -------------------------------------------------------


def compute_schema_diff(
    data: dict,
    base_enum_values: dict[str, set[str]] | None = None,
    version: str = "",
    base_version: str = "",
) -> SchemaDiffReport:
    """Compute the schema diff between JSON data and shared models.

    Args:
        data: Parsed extension_api.json dict.
        base_enum_values: Enum values from the base version, if comparing.
        version: The new version string (e.g. "v4_4_1").
        base_version: The base version string (e.g. "v4_4_0").

    Returns a :class:`SchemaDiffReport`.
    """
    json_keys = collect_json_keys(data)
    model_fields = collect_model_fields()

    added_fields: list[AddedField] = []
    removed_fields: list[RemovedField] = []
    new_sections: list[str] = []

    all_paths = set(json_keys.keys()) | set(model_fields.keys())
    for path in sorted(all_paths):
        json_k = json_keys.get(path, set())
        model_k = model_fields.get(path, set())

        for key in sorted(json_k - model_k):
            if path == "":
                new_sections.append(key)
            else:
                added_fields.append(
                    AddedField(path=f"{path}.{key}", auto_generatable=True)
                )

        for key in sorted(model_k - json_k):
            field_path = f"{path}.{key}" if path else key
            model = _get_model_for_path(path)
            is_optional = False
            if model is not None and key in model.model_fields:
                field_info = model.model_fields[key]
                is_optional = not field_info.is_required()
            removed_fields.append(
                RemovedField(
                    path=field_path,
                    was_optional=is_optional,
                    action="no_action_needed" if is_optional else "flag_for_human",
                )
            )

    requires_human = bool(new_sections) or any(
        f.action == "flag_for_human" for f in removed_fields
    )

    enum_comparison = _compute_enum_comparison(data, base_enum_values)
    test_guidance = _build_test_guidance(added_fields, new_sections, enum_comparison)

    return SchemaDiffReport(
        version=version,
        base_version=base_version,
        requires_human_intervention=requires_human,
        added_fields=added_fields,
        removed_fields=removed_fields,
        type_changes=[],
        new_top_level_sections=new_sections,
        enum_comparison=enum_comparison,
        test_guidance=test_guidance,
    )


def _compute_enum_comparison(
    data: dict, base_enum_values: dict[str, set[str]] | None
) -> dict[str, EnumComparison]:
    new_enum_values = extract_enum_values(data)
    result: dict[str, EnumComparison] = {}
    for enum_name in _ENUM_NAMES:
        new_vals = new_enum_values.get(enum_name, set())
        if base_enum_values and enum_name in base_enum_values:
            base_vals = base_enum_values[enum_name]
            identical = new_vals == base_vals
            result[enum_name] = EnumComparison(
                identical_to_base=identical,
                import_from_base=identical,
                new_values=sorted(new_vals - base_vals) if not identical else [],
            )
        else:
            result[enum_name] = EnumComparison(
                identical_to_base=None,
                import_from_base=False,
                new_values=sorted(new_vals),
            )
    return result


def _build_test_guidance(
    added_fields: list[AddedField],
    new_sections: list[str],
    enum_comparison: dict[str, EnumComparison],
) -> TestGuidance:
    detectable: list[str] = []

    for field in added_fields:
        detectable.append(
            f"Added field {field.path}: write a unit test asserting the field "
            f"is Optional and defaults to None"
        )

    for section in new_sections:
        detectable.append(
            f"New top-level section {section}: write an integration test asserting "
            f"the Specification model can parse it"
        )

    for enum_name, info in enum_comparison.items():
        if info.identical_to_base is False and info.new_values:
            detectable.append(
                f"Enum {enum_name} differs from base: write an integration test "
                f"asserting new enum members are present"
            )

    generic = (
        "Some schema changes were detected that may require version-specific "
        "test assertions. Review the diff report and add tests as needed."
        if detectable
        else "No schema changes detected. No new tests needed."
    )

    return TestGuidance(detectable=detectable, generic=generic)


def _get_model_for_path(path: str) -> type[BaseModel] | None:
    """Find the pydantic model class for a given dot-separated path."""
    if path in SECTION_MODELS:
        return SECTION_MODELS[path]
    parts = path.split(".")
    if not parts:
        return None
    root_model = SECTION_MODELS.get(parts[0])
    if root_model is None:
        return None
    current = root_model
    for part in parts[1:]:
        found = False
        for field_name, field_info in current.model_fields.items():
            if field_name == part:
                inner, _ = _unwrap_annotation(field_info.annotation)
                if (
                    inner is not None
                    and isinstance(inner, type)
                    and issubclass(inner, BaseModel)
                ):
                    current = inner
                    found = True
                    break
        if not found:
            return None
    return current


# --- Report formatting ------------------------------------------------------


def format_report_yaml(report: SchemaDiffReport) -> str:
    """Format the diff report as a YAML string."""
    import yaml

    return yaml.dump(
        report.model_dump(mode="json"), default_flow_style=False, sort_keys=False
    )


def format_report_json(report: SchemaDiffReport) -> str:
    """Format the diff report as a JSON string."""
    return report.model_dump_json(indent=2)
