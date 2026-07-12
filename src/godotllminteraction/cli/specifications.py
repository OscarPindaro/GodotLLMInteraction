from __future__ import annotations

import importlib
import json
import keyword
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

from godotllminteraction.cli._common import (
    EXIT_ERROR,
    EXIT_USAGE,
    print_error,
    print_success,
    print_text,
    print_warning,
)
from godotllminteraction.paths import GODOT_VERSIONS_FILE as _VERSIONS_FILE
from godotllminteraction.specifications.schema_diff import (
    _ENUM_NAMES,
    compute_schema_diff,
    format_report_json,
    format_report_yaml,
)

app = typer.Typer(help="Codegen utilities for versioned Godot API specifications.")

_SPECIFICATIONS_ROOT = Path(__file__).resolve().parents[1] / "specifications"
_SPEC_V4_7_0_PATH = _SPECIFICATIONS_ROOT / "v4_7_0" / "spec.py"

_VERSION_RE = re.compile(r"^v\d+(_\d+){1,2}$")
_TYPE_NAME_RE = re.compile(r"(?<!^)(?<![A-Z])(?=[A-Z][a-z])")


def _type_name_to_member(value: str) -> str:
    return _TYPE_NAME_RE.sub("_", value).upper()


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


_RESERVED_FIELD_NAMES = set(dir(BaseModel))


def _safe_field_name(name: str) -> str:
    """Godot field names that are Python keywords (e.g. 'from') or shadow a
    pydantic BaseModel attribute (e.g. 'json', 'copy') get a trailing underscore.
    """
    if keyword.iskeyword(name) or name in _RESERVED_FIELD_NAMES:
        return f"{name}_"
    return name


def _is_stale(path: Path, source: str) -> bool:
    return not path.exists() or path.read_text() != source


def _write_if_changed(path: Path, source: str) -> bool:
    """Write `source` to `path` (creating parent dirs) if it differs. Returns whether it changed."""
    changed = _is_stale(path, source)
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    return changed


def _ensure_version_package(
    version: str, specs_root: Path | None = None
) -> tuple[Path, bool]:
    """Ensure specifications/<version>/ exists with an __init__.py; return (dir, was_created)."""
    root = specs_root or _SPECIFICATIONS_ROOT
    version_dir = root / version
    created = not version_dir.exists()
    version_dir.mkdir(parents=True, exist_ok=True)
    init_path = version_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text("")
    return version_dir, created


# --- Hand-written spec.py: sync the 4.7.0-specific enum blocks ------------
#
# spec.py is partially hand-written and partially generated: the pydantic
# models are hand-written, but the five enums below (whose full value sets
# come from enumerating extension_api.json) are kept in sync between marker
# comments. This extraction is specific to the 4.7.0 API shape (unlike the
# builtin-classes/classes generators below) since it enumerates closed value
# sets that could change between Godot versions.

_OPERATOR_MEMBER_NAMES = {
    "!=": "NOT_EQUAL",
    "%": "MODULO",
    "&": "BIT_AND",
    "*": "MULTIPLY",
    "**": "POWER",
    "+": "ADD",
    "-": "SUBTRACT",
    "/": "DIVIDE",
    "<": "LESS",
    "<<": "SHIFT_LEFT",
    "<=": "LESS_EQUAL",
    "==": "EQUAL",
    ">": "GREATER",
    ">=": "GREATER_EQUAL",
    ">>": "SHIFT_RIGHT",
    "^": "BIT_XOR",
    "and": "AND",
    "in": "IN",
    "not": "NOT",
    "or": "OR",
    "unary+": "UNARY_PLUS",
    "unary-": "UNARY_MINUS",
    "xor": "XOR",
    "|": "BIT_OR",
    "~": "BIT_NOT",
}


def _operator_to_member(value: str) -> str:
    try:
        return _OPERATOR_MEMBER_NAMES[value]
    except KeyError as exc:
        raise ValueError(
            f"Unknown operator symbol {value!r}; add a member name for it to "
            f"_OPERATOR_MEMBER_NAMES in {__name__}"
        ) from exc


def _extract_type_names(data: dict) -> set[str]:
    """Every Godot type name that shows up as a return/argument/member/constant type."""
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
            if "return_type" in op:
                names.add(op["return_type"])
        for member in cls.get("members", []):
            if "type" in member:
                names.add(member["type"])
        for const in cls.get("constants", []):
            if "type" in const:
                names.add(const["type"])
        for ctor in cls.get("constructors", []):
            for arg in ctor.get("arguments", []):
                if "type" in arg:
                    names.add(arg["type"])
        for method in cls.get("methods", []):
            if "return_type" in method:
                names.add(method["return_type"])
            for arg in method.get("arguments", []):
                if "type" in arg:
                    names.add(arg["type"])
    return names


def _extract_utility_function_categories(data: dict) -> set[str]:
    return {
        fn["category"] for fn in data.get("utility_functions", []) if "category" in fn
    }


def _extract_operator_symbols(data: dict) -> set[str]:
    symbols: set[str] = set()
    for cls in data.get("builtin_classes", []):
        for op in cls.get("operators", []):
            if "name" in op:
                symbols.add(op["name"])
    return symbols


def _extract_argument_metas(data: dict) -> set[str]:
    """Native C++ type refinements ('meta') seen on class method arguments/return values."""
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
    return {cls["api_type"] for cls in data.get("classes", []) if "api_type" in cls}


def _render_enum(
    class_name: str, docstring: str | None, members: list[tuple[str, str]]
) -> str:
    # Output matches ruff format (blank line after the docstring), so the
    # generated blocks survive the pre-commit formatter unchanged.
    lines = [f"class {class_name}(str, Enum):"]
    if docstring:
        lines.append(f'    """{docstring}"""')
        lines.append("")
    if not members:
        lines.append("    pass")
    for member_name, value in members:
        lines.append(f"    {member_name} = {_quote(value)}")
    return "\n".join(lines)


def _render_type_name_block(data: dict) -> str:
    members = [(_type_name_to_member(v), v) for v in sorted(_extract_type_names(data))]
    enum_src = _render_enum(
        "GodotTypeNameEnum",
        "Name of a Godot variant/builtin type, as it shows up across return types, argument types, etc.",
        members,
    )
    return f"{enum_src}\n\n\nGodotTypeName = Union[GodotTypeNameEnum, str]"


def _render_utility_function_category_block(data: dict) -> str:
    members = [
        (v.upper(), v) for v in sorted(_extract_utility_function_categories(data))
    ]
    enum_src = _render_enum("UtilityFunctionCategoryEnum", None, members)
    return f"{enum_src}\n\n\nUtilityFunctionCategory = Union[UtilityFunctionCategoryEnum, str]"


def _render_operator_name_block(data: dict) -> str:
    members = [
        (_operator_to_member(v), v) for v in sorted(_extract_operator_symbols(data))
    ]
    enum_src = _render_enum("BuiltinClassOperatorNameEnum", None, members)
    return f"{enum_src}\n\n\nBuiltinClassOperatorName = Union[BuiltinClassOperatorNameEnum, str]"


def _render_argument_meta_block(data: dict) -> str:
    members = [(v.upper(), v) for v in sorted(_extract_argument_metas(data))]
    enum_src = _render_enum(
        "GodotArgumentMetaEnum",
        "Native C++ type refinement of an argument/return value, e.g. 'int64', 'double', 'uint8'.",
        members,
    )
    return f"{enum_src}\n\n\nGodotArgumentMeta = Union[GodotArgumentMetaEnum, str]"


def _render_api_type_block(data: dict) -> str:
    members = [(v.upper(), v) for v in sorted(_extract_class_api_types(data))]
    enum_src = _render_enum("ClassApiTypeEnum", None, members)
    return f"{enum_src}\n\n\nClassApiType = Union[ClassApiTypeEnum, str]"


_ENUM_BLOCK_RENDERERS = {
    "GodotTypeNameEnum": _render_type_name_block,
    "UtilityFunctionCategoryEnum": _render_utility_function_category_block,
    "BuiltinClassOperatorNameEnum": _render_operator_name_block,
    "GodotArgumentMetaEnum": _render_argument_meta_block,
    "ClassApiTypeEnum": _render_api_type_block,
}


def _block_pattern(
    name: str, command_str: str = "sync-enums-v4-7-0"
) -> re.Pattern[str]:
    marker = re.escape(name)
    cmd = re.escape(command_str)
    return re.compile(
        rf"(# === GENERATED: {marker} \(run: gli specifications {cmd}\) ===\n)"
        rf"(.*?)"
        rf"(\n# === END GENERATED: {marker} ===)",
        re.DOTALL,
    )


def render_spec_source(
    spec_source: str, data: dict, command_str: str = "sync-enums-v4-7-0"
) -> str:
    """Replace each generated enum block in spec.py's source with freshly derived code."""
    updated = spec_source
    for name, renderer in _ENUM_BLOCK_RENDERERS.items():
        block = renderer(data)
        pattern = _block_pattern(name, command_str)
        if not pattern.search(updated):
            # Enum is imported from a base version, not generated locally — skip.
            continue
        updated = pattern.sub(
            lambda m, block=block: m.group(1) + block + m.group(3), updated
        )
    return updated


@app.command("sync-enums")
def sync_enums(
    version: Annotated[
        str,
        typer.Option(
            "--version",
            "-v",
            help="Version package to sync, e.g. 'v4_7_0'.",
        ),
    ],
    api_json: Annotated[
        Path,
        typer.Option(
            "--api",
            "-a",
            help="Path to extension_api.json.",
            exists=True,
            dir_okay=False,
        ),
    ] = Path("extension_api.json"),
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Only check whether the generated enum blocks are up to date; don't write.",
        ),
    ] = False,
    specs_root: Annotated[
        Path | None,
        typer.Option(
            "--specs-root",
            help="Root directory for version packages. Defaults to the built-in specifications/.",
        ),
    ] = None,
) -> None:
    """Sync the generated enum blocks inside specifications/<version>/spec.py from extension_api.json."""
    if not _VERSION_RE.match(version):
        print_error(
            f"Invalid version {version!r}; expected a format like 'v4_7_0' "
            "(a valid Python identifier, 'v' + major_minor[_patch])."
        )
        raise typer.Exit(code=EXIT_USAGE)

    root = specs_root or _SPECIFICATIONS_ROOT
    spec_path = root / version / "spec.py"
    if not spec_path.exists():
        print_error(f"spec.py not found at {spec_path}.")
        raise typer.Exit(code=EXIT_ERROR)

    command_str = f"sync-enums --version {version}"
    data = json.loads(api_json.read_text())
    try:
        updated = render_spec_source(spec_path.read_text(), data, command_str)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=EXIT_ERROR) from exc

    if check:
        if _is_stale(spec_path, updated):
            print_error(
                f"Generated enum blocks in specifications/{version}/spec.py are stale. "
                f"Run `gli specifications sync-enums --version {version}` to refresh."
            )
            raise typer.Exit(code=EXIT_ERROR)
        print_success(
            f"Generated enum blocks in specifications/{version}/spec.py are up to date."
        )
        return

    if _write_if_changed(spec_path, updated):
        print_success(f"Updated {spec_path}.")
    else:
        print_text(
            f"Generated enum blocks in specifications/{version}/spec.py already up to date."
        )


@app.command("sync-enums-v4-7-0", deprecated=True)
def sync_enums_v4_7_0(
    api_json: Annotated[
        Path,
        typer.Option(
            "--api",
            "-a",
            help="Path to extension_api.json.",
            exists=True,
            dir_okay=False,
        ),
    ] = Path("extension_api.json"),
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Only check whether the generated enum blocks are up to date; don't write.",
        ),
    ] = False,
) -> None:
    """Deprecated: use `gli specifications sync-enums --version v4_7_0` instead."""
    print_warning(
        "sync-enums-v4-7-0 is deprecated. Use `gli specifications sync-enums --version v4_7_0` instead."
    )
    data = json.loads(api_json.read_text())
    try:
        updated = render_spec_source(_SPEC_V4_7_0_PATH.read_text(), data)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=EXIT_ERROR) from exc

    if check:
        if _is_stale(_SPEC_V4_7_0_PATH, updated):
            print_error(
                "Generated enum blocks in specifications/v4_7_0/spec.py are stale. "
                "Run `gli specifications sync-enums --version v4_7_0` to refresh."
            )
            raise typer.Exit(code=EXIT_ERROR)
        print_success("Generated enum blocks in spec.py are up to date.")
        return

    if _write_if_changed(_SPEC_V4_7_0_PATH, updated):
        print_success(f"Updated {_SPEC_V4_7_0_PATH}.")
    else:
        print_text("Generated enum blocks in spec.py already up to date.")


# --- Per-version builtin-class model/constant generation -------------------
#
# Unlike the enum sync above, this generator makes no assumptions specific to
# the 4.7.0 API shape: it only relies on the structural fact that a builtin
# class may have "members" (name/type pairs) and "constants" (name/type/value
# triples). It should work unmodified against a dump from a different Godot
# version; `version` is just a label for the output.

_PRIMITIVE_FIELD_TYPES = {"float": "float", "int": "int"}


def _modeled_builtin_classes(data: dict) -> dict[str, list[tuple[str, str]]]:
    """Builtin classes that have `members`, mapped to their (name, type) pairs."""
    return {
        cls["name"]: [(m["name"], m["type"]) for m in cls["members"]]
        for cls in data.get("builtin_classes", [])
        if cls.get("members")
    }


def _topo_sort_by_dependency(
    members_by_class: dict[str, list[tuple[str, str]]],
) -> list[str]:
    """Order classes so a class referencing another modeled class comes after it.

    Uses Kahn's algorithm with alphabetical tie-breaking so the order is
    stable regardless of dict/JSON iteration order.
    """
    modeled = set(members_by_class)
    depends_on = {
        name: sorted({t for _, t in members if t in modeled and t != name})
        for name, members in members_by_class.items()
    }
    remaining = dict(depends_on)
    ordered: list[str] = []
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if not deps)
        if not ready:
            cyclic = ", ".join(sorted(remaining))
            raise ValueError(f"Cyclic dependency among builtin classes: {cyclic}")
        ordered.extend(ready)
        for name in ready:
            del remaining[name]
        for deps in remaining.values():
            deps[:] = [d for d in deps if d not in ready]
    return ordered


def _builtin_field_type(member_type: str, version: str, modeled: set[str]) -> str:
    if member_type in _PRIMITIVE_FIELD_TYPES:
        return _PRIMITIVE_FIELD_TYPES[member_type]
    if member_type in modeled:
        return f"{member_type}{version}"
    raise ValueError(
        f"Don't know how to represent member type {member_type!r} as a pydantic "
        f"field; add it to _PRIMITIVE_FIELD_TYPES in {__name__} if it's a new primitive."
    )


def render_builtin_classes_source(data: dict, version: str) -> str:
    """Render one pydantic BaseModel per builtin class that has `members`.

    Model names are `{ClassName}{version}` (e.g. 'Transform2Dv4_7_0'); a member
    whose type is itself a modeled class references that class's generated
    model rather than a bare string.
    """
    members_by_class = _modeled_builtin_classes(data)
    ordered = _topo_sort_by_dependency(members_by_class)
    modeled = set(members_by_class)

    parts = [
        '"""Auto-generated by `gli specifications generate-builtin-classes --version '
        f'{version}`. Do not edit by hand."""',
        "",
        "from __future__ import annotations",
        "",
        "from pydantic import BaseModel",
        "",
    ]
    for class_name in ordered:
        parts.append("")
        parts.append(f"class {class_name}{version}(BaseModel):")
        for member_name, member_type in members_by_class[class_name]:
            parts.append(
                f"    {_safe_field_name(member_name)}: {_builtin_field_type(member_type, version, modeled)}"
            )
    parts.append("")
    return "\n".join(parts)


def _extract_builtin_constants(data: dict) -> list[tuple[str, str, str, str]]:
    """(class_name, constant_name, type, raw_value) tuples, sorted for determinism."""
    triples = [
        (cls["name"], const["name"], const["type"], const["value"])
        for cls in data.get("builtin_classes", [])
        for const in cls.get("constants", [])
    ]
    return sorted(triples, key=lambda t: (t[0], t[1]))


def render_constants_source(data: dict) -> str:
    """Render one GodotConstant instance per builtin-class constant.

    Constant values are raw Godot constructor-expression strings (e.g.
    'Transform2D(1, 0, 0, 1, 0, 0)') and are kept as-is rather than evaluated,
    since doing so correctly would require implementing Godot's constructors.
    Python identifiers are `{CLASS_UPPER_SNAKE}_{CONST_NAME}`, disambiguating
    constant names (e.g. ZERO/IDENTITY) that repeat across classes; BY_GODOT_NAME
    maps the Godot 'ClassName.CONST_NAME' spelling to the same instance.
    """
    triples = _extract_builtin_constants(data)

    identifiers: dict[str, str] = {}
    for class_name, const_name, _, _ in triples:
        identifier = f"{_type_name_to_member(class_name)}_{const_name}"
        godot_name = f"{class_name}.{const_name}"
        if identifier in identifiers and identifiers[identifier] != godot_name:
            raise ValueError(
                f"Constant identifier collision: {identifiers[identifier]!r} and "
                f"{godot_name!r} both map to {identifier!r}"
            )
        identifiers[identifier] = godot_name

    parts = [
        '"""Auto-generated by `gli specifications generate-builtin-classes`. Do not edit by hand."""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        "",
        "@dataclass(frozen=True)",
        "class GodotConstant:",
        "    class_name: str",
        "    name: str",
        "    type: str",
        "    raw_value: str",
        "",
    ]
    for class_name, const_name, const_type, raw_value in triples:
        identifier = f"{_type_name_to_member(class_name)}_{const_name}"
        parts.append("")
        parts.append(
            f"{identifier} = GodotConstant(class_name={_quote(class_name)}, "
            f"name={_quote(const_name)}, type={_quote(const_type)}, "
            f"raw_value={_quote(raw_value)})"
        )

    parts.append("")
    parts.append("")
    parts.append("BY_GODOT_NAME = {")
    for class_name, const_name, _, _ in triples:
        identifier = f"{_type_name_to_member(class_name)}_{const_name}"
        parts.append(f"    {_quote(f'{class_name}.{const_name}')}: {identifier},")
    parts.append("}")
    parts.append("")
    return "\n".join(parts)


@app.command("generate-builtin-classes")
def generate_builtin_classes(
    version: Annotated[
        str,
        typer.Option(
            "--version",
            "-v",
            help="Version package to generate into, e.g. 'v4_7_0'. Created if missing.",
        ),
    ],
    api_json: Annotated[
        Path,
        typer.Option(
            "--api",
            "-a",
            help="Path to extension_api.json.",
            exists=True,
            dir_okay=False,
        ),
    ] = Path("extension_api.json"),
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Only check whether the generated files are up to date; don't write.",
        ),
    ] = False,
    specs_root: Annotated[
        Path | None,
        typer.Option(
            "--specs-root",
            help="Root directory for version packages. Defaults to the built-in specifications/.",
        ),
    ] = None,
) -> None:
    """Generate builtin_classes.py and constants.py for a specifications/<version>/ package.

    Only builtin classes with `members` get a pydantic model (named
    '{ClassName}{version}'); classes without members (String, Array, RID, ...)
    aren't referenced as member types in this API version, so they're skipped.
    This generator has no version-specific assumptions baked in, so it should
    work unmodified for other Godot versions.
    """
    if not _VERSION_RE.match(version):
        print_error(
            f"Invalid version {version!r}; expected a format like 'v4_7_0' "
            "(a valid Python identifier, 'v' + major_minor[_patch])."
        )
        raise typer.Exit(code=EXIT_USAGE)

    data = json.loads(api_json.read_text())
    try:
        models_source = render_builtin_classes_source(data, version)
        constants_source = render_constants_source(data)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=EXIT_ERROR) from exc

    root = specs_root or _SPECIFICATIONS_ROOT
    version_dir = root / version
    targets = {
        version_dir / "builtin_classes.py": models_source,
        version_dir / "constants.py": constants_source,
    }

    if check:
        if not version_dir.exists() or any(_is_stale(p, s) for p, s in targets.items()):
            print_error(
                f"specifications/{version}/ builtin classes/constants are missing or stale. "
                "Run `gli specifications generate-builtin-classes` to refresh."
            )
            raise typer.Exit(code=EXIT_ERROR)
        print_success("Generated builtin classes are up to date.")
        return

    _, created = _ensure_version_package(version, specs_root)
    if created:
        print_success(f"Created {version_dir}.")

    changed_paths = [
        path for path, source in targets.items() if _write_if_changed(path, source)
    ]
    if changed_paths:
        print_success(f"Updated {', '.join(str(p) for p in changed_paths)}.")
    else:
        print_text("Generated builtin classes already up to date.")


# --- Per-version engine-class model generation ------------------------------
#
# Mirrors the `classes` section of extension_api.json (Node/Resource/etc.),
# which is structurally different from builtin_classes: it forms a real
# single-inheritance hierarchy via `inherits`, and fields come from
# `properties` (each class only lists its own newly-declared properties, not
# inherited ones -- Python inheritance gives the rest for free). Like
# generate-builtin-classes, this has no version-specific assumptions baked in.

_CLASS_PRIMITIVE_FIELD_TYPES = {
    "bool": "bool",
    "int": "int",
    "float": "float",
    "String": "str",
    "StringName": "str",
    "NodePath": "str",
}


def _packed_array_element_types(data: dict) -> dict[str, str]:
    """Element type name for each Packed*Array builtin class.

    Godot's Packed*Array types have no `members` (so generate-builtin-classes
    doesn't model them as structs), but they're really just flat homogeneous
    arrays -- e.g. a PackedVector2Array is stored/edited as a flattened list
    of Vector2 pairs. Each Packed*Array builtin class already declares its
    element type via `indexing_return_type` (what `arr[i]` returns), so this
    is derived from the data rather than hardcoded.
    """
    return {
        cls["name"]: cls["indexing_return_type"]
        for cls in data.get("builtin_classes", [])
        if cls["name"].startswith("Packed") and "indexing_return_type" in cls
    }


def _class_parents(data: dict) -> dict[str, str | None]:
    """class_name -> parent class_name (None only for 'Object', the hierarchy root)."""
    return {cls["name"]: cls.get("inherits") for cls in data.get("classes", [])}


def _class_properties(data: dict) -> dict[str, list[tuple[str, str]]]:
    return {
        cls["name"]: [(p["name"], p["type"]) for p in cls.get("properties", [])]
        for cls in data.get("classes", [])
    }


def _topo_sort_by_parent(parent_of: dict[str, str | None]) -> list[str]:
    """Order classes so a parent is always emitted before its children.

    Stable regardless of dict/JSON iteration order (alphabetical tie-break).
    """
    ordered: list[str] = []
    resolved: set[str] = set()
    remaining = dict(parent_of)
    while remaining:
        ready = sorted(
            name
            for name, parent in remaining.items()
            if parent is None or parent in resolved
        )
        if not ready:
            raise ValueError(f"Cannot resolve class hierarchy for: {sorted(remaining)}")
        ordered.extend(ready)
        resolved.update(ready)
        for name in ready:
            del remaining[name]
    return ordered


def _class_field_type(
    prop_type: str,
    version: str,
    modeled_builtins: set[str],
    modeled_classes: set[str],
    packed_array_elements: dict[str, str],
) -> str:
    if prop_type in modeled_builtins or prop_type in modeled_classes:
        return f"{prop_type}{version}"
    if prop_type in _CLASS_PRIMITIVE_FIELD_TYPES:
        return _CLASS_PRIMITIVE_FIELD_TYPES[prop_type]
    if prop_type in packed_array_elements:
        element_name = packed_array_elements[prop_type]
        element_type = _class_field_type(
            element_name,
            version,
            modeled_builtins,
            modeled_classes,
            packed_array_elements,
        )
        return f"List[{element_type}]"
    if prop_type.startswith("typedarray::"):
        # e.g. "typedarray::PackedVector2Array" -> List[List[Vector2...]];
        # "typedarray::24/17:CompositorEffect" -> element name is after the last ':'.
        element_name = prop_type.rsplit(":", 1)[-1]
        element_type = _class_field_type(
            element_name,
            version,
            modeled_builtins,
            modeled_classes,
            packed_array_elements,
        )
        return f"List[{element_type}]"
    # Container/opaque/union-hint types (Array, Dictionary, Variant, RID,
    # "typeddictionary::...", "TypeA,TypeB", etc.) aren't modeled precisely;
    # `Any` is an honest fallback rather than guessing at a shape.
    return "Any"


def render_classes_source(data: dict, version: str) -> str:
    """Render one pydantic BaseModel per entry in `classes`, mirroring Godot's inheritance.

    Model names are `{ClassName}{version}`; each model subclasses its parent's
    generated model (Object's model subclasses BaseModel directly) and declares
    only its own `properties` as fields -- inherited properties come from the
    Python base class. Property types that reference a generate-builtin-classes
    model or another `classes` entry point at that generated model; primitives
    map to plain Python types; anything else (containers, unions, Variant, ...)
    falls back to `Any`.
    """
    parent_of = _class_parents(data)
    properties = _class_properties(data)
    ordered = _topo_sort_by_parent(parent_of)

    modeled_builtins = set(_modeled_builtin_classes(data))
    modeled_classes = set(parent_of)
    packed_array_elements = _packed_array_element_types(data)

    field_types: dict[str, list[tuple[str, str]]] = {}
    for name in ordered:
        field_types[name] = [
            (
                prop_name,
                _class_field_type(
                    prop_type,
                    version,
                    modeled_builtins,
                    modeled_classes,
                    packed_array_elements,
                ),
            )
            for prop_name, prop_type in properties.get(name, [])
        ]

    all_field_types = [ft for fields in field_types.values() for _, ft in fields]
    # Derived from the resolved field-type strings (not the raw property
    # types), since a Packed*Array/typedarray:: property resolves to
    # 'List[Vector2v4_7_0]' etc. without 'Vector2' ever being its own type.
    joined_field_types = "\n".join(all_field_types)
    used_builtins = sorted(
        b for b in modeled_builtins if f"{b}{version}" in joined_field_types
    )
    uses_any = any("Any" in ft for ft in all_field_types)
    uses_list = any(ft.startswith("List[") for ft in all_field_types)

    parts = [
        '"""Auto-generated by `gli specifications generate-classes --version '
        f'{version}`. Do not edit by hand."""',
        "",
        "from __future__ import annotations",
        "",
    ]
    typing_imports = [
        name for name, used in (("Any", uses_any), ("List", uses_list)) if used
    ]
    if typing_imports:
        parts.append(f"from typing import {', '.join(typing_imports)}")
        parts.append("")
    parts.append("from pydantic import BaseModel")
    if used_builtins:
        parts.append("")
        parts.append(
            f"from godotllminteraction.specifications.{version}.builtin_classes import ("
        )
        for name in used_builtins:
            parts.append(f"    {name}{version},")
        parts.append(")")
    parts.append("")

    for name in ordered:
        parent = parent_of[name]
        base = "BaseModel" if parent is None else f"{parent}{version}"
        parts.append("")
        parts.append(f"class {name}{version}({base}):")
        fields = field_types[name]
        if not fields:
            parts.append("    pass")
        else:
            for prop_name, field_type in fields:
                parts.append(f"    {_safe_field_name(prop_name)}: {field_type}")
    parts.append("")
    return "\n".join(parts)


@app.command("generate-classes")
def generate_classes(
    version: Annotated[
        str,
        typer.Option(
            "--version",
            "-v",
            help="Version package to generate into, e.g. 'v4_7_0'. Created if missing.",
        ),
    ],
    api_json: Annotated[
        Path,
        typer.Option(
            "--api",
            "-a",
            help="Path to extension_api.json.",
            exists=True,
            dir_okay=False,
        ),
    ] = Path("extension_api.json"),
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Only check whether the generated file is up to date; don't write.",
        ),
    ] = False,
    specs_root: Annotated[
        Path | None,
        typer.Option(
            "--specs-root",
            help="Root directory for version packages. Defaults to the built-in specifications/.",
        ),
    ] = None,
) -> None:
    """Generate classes.py for a specifications/<version>/ package.

    One pydantic model per entry in the `classes` section (Node, Resource,
    CollisionShape2D, ...), mirroring Godot's inheritance hierarchy via Python
    subclassing. Only `properties` become fields; methods/signals/constants
    are out of scope for now. References generate-builtin-classes models for
    builtin-typed properties (Vector2, Color, ...); falls back to `Any` for
    containers/unions/Variant that aren't modeled precisely.
    """
    if not _VERSION_RE.match(version):
        print_error(
            f"Invalid version {version!r}; expected a format like 'v4_7_0' "
            "(a valid Python identifier, 'v' + major_minor[_patch])."
        )
        raise typer.Exit(code=EXIT_USAGE)

    data = json.loads(api_json.read_text())
    try:
        source = render_classes_source(data, version)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=EXIT_ERROR) from exc

    root = specs_root or _SPECIFICATIONS_ROOT
    version_dir = root / version
    classes_path = version_dir / "classes.py"

    if check:
        if not version_dir.exists() or _is_stale(classes_path, source):
            print_error(
                f"specifications/{version}/classes.py is missing or stale. "
                "Run `gli specifications generate-classes` to refresh."
            )
            raise typer.Exit(code=EXIT_ERROR)
        print_success("Generated classes.py is up to date.")
        return

    _, created = _ensure_version_package(version, specs_root)
    if created:
        print_success(f"Created {version_dir}.")

    if _write_if_changed(classes_path, source):
        print_success(f"Updated {classes_path}.")
    else:
        print_text("Generated classes.py already up to date.")


# --- Per-version signal table generation ------------------------------------
#
# Mirrors the `signals` arrays of the `classes` section. Like the class models,
# each class only lists its own newly-declared signals; inherited signals are
# resolved by consumers walking the generated class models' MRO (classes.py
# mirrors Godot's inheritance via Python subclassing). No version-specific
# assumptions baked in.


def _extract_class_signals(
    data: dict,
) -> dict[str, list[tuple[str, list[tuple[str, str]]]]]:
    """class_name -> [(signal_name, [(arg_name, arg_type), ...]), ...] for classes with signals.

    A signal without an `arguments` key is a zero-argument signal.
    """
    return {
        cls["name"]: [
            (
                sig["name"],
                [(arg["name"], arg["type"]) for arg in sig.get("arguments", [])],
            )
            for sig in cls["signals"]
        ]
        for cls in data.get("classes", [])
        if cls.get("signals")
    }


def render_signals_source(data: dict, version: str) -> str:
    """Render frozen pydantic signal models plus a per-class own-signal table.

    `SIGNALS` maps class name -> {signal name -> GodotSignal} and contains only
    each class's own signals, not inherited ones; classes without signals are
    omitted entirely. Classes and signals are sorted alphabetically so output
    is stable regardless of JSON iteration order.
    """
    signals_by_class = _extract_class_signals(data)

    parts = [
        '"""Auto-generated by `gli specifications generate-signals --version '
        f'{version}`. Do not edit by hand."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Dict, Tuple",
        "",
        "from pydantic import BaseModel, ConfigDict",
        "",
        "",
        "class SignalArgument(BaseModel):",
        "    model_config = ConfigDict(frozen=True)",
        "",
        "    name: str",
        "    type: str",
        "",
        "",
        "class GodotSignal(BaseModel):",
        "    model_config = ConfigDict(frozen=True)",
        "",
        "    name: str",
        "    arguments: Tuple[SignalArgument, ...] = ()",
        "",
        "",
        "SIGNALS: Dict[str, Dict[str, GodotSignal]] = {",
    ]
    for class_name in sorted(signals_by_class):
        parts.append(f"    {_quote(class_name)}: {{")
        for sig_name, args in sorted(signals_by_class[class_name]):
            if args:
                args_src = ", ".join(
                    f"SignalArgument(name={_quote(n)}, type={_quote(t)})"
                    for n, t in args
                )
                sig_src = (
                    f"GodotSignal(name={_quote(sig_name)}, arguments=({args_src},))"
                )
            else:
                sig_src = f"GodotSignal(name={_quote(sig_name)})"
            parts.append(f"        {_quote(sig_name)}: {sig_src},")
        parts.append("    },")
    parts.append("}")
    parts.append("")
    return "\n".join(parts)


@app.command("generate-signals")
def generate_signals(
    version: Annotated[
        str,
        typer.Option(
            "--version",
            "-v",
            help="Version package to generate into, e.g. 'v4_7_0'. Created if missing.",
        ),
    ],
    api_json: Annotated[
        Path,
        typer.Option(
            "--api",
            "-a",
            help="Path to extension_api.json.",
            exists=True,
            dir_okay=False,
        ),
    ] = Path("extension_api.json"),
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Only check whether the generated file is up to date; don't write.",
        ),
    ] = False,
    specs_root: Annotated[
        Path | None,
        typer.Option(
            "--specs-root",
            help="Root directory for version packages. Defaults to the built-in specifications/.",
        ),
    ] = None,
) -> None:
    """Generate signals.py for a specifications/<version>/ package.

    A `SIGNALS` table mapping each class name to its own (non-inherited)
    signals as frozen GodotSignal models. Consumers union signals along the
    inheritance chain via the classes.py models' MRO.
    """
    if not _VERSION_RE.match(version):
        print_error(
            f"Invalid version {version!r}; expected a format like 'v4_7_0' "
            "(a valid Python identifier, 'v' + major_minor[_patch])."
        )
        raise typer.Exit(code=EXIT_USAGE)

    data = json.loads(api_json.read_text())
    source = render_signals_source(data, version)

    root = specs_root or _SPECIFICATIONS_ROOT
    version_dir = root / version
    signals_path = version_dir / "signals.py"

    if check:
        if not version_dir.exists() or _is_stale(signals_path, source):
            print_error(
                f"specifications/{version}/signals.py is missing or stale. "
                "Run `gli specifications generate-signals` to refresh."
            )
            raise typer.Exit(code=EXIT_ERROR)
        print_success("Generated signals.py is up to date.")
        return

    _, created = _ensure_version_package(version, specs_root)
    if created:
        print_success(f"Created {version_dir}.")

    if _write_if_changed(signals_path, source):
        print_success(f"Updated {signals_path}.")
    else:
        print_text("Generated signals.py already up to date.")


@app.command("generate-all")
def generate_all(
    version: Annotated[
        str,
        typer.Option(
            "--version",
            "-v",
            help="Version package to generate into, e.g. 'v4_7_0'. Created if missing.",
        ),
    ],
    api_json: Annotated[
        Path,
        typer.Option(
            "--api",
            "-a",
            help="Path to extension_api.json.",
            exists=True,
            dir_okay=False,
        ),
    ] = Path("extension_api.json"),
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Only check whether everything is up to date; don't write.",
        ),
    ] = False,
    specs_root: Annotated[
        Path | None,
        typer.Option(
            "--specs-root",
            help="Root directory for version packages. Defaults to the built-in specifications/.",
        ),
    ] = None,
) -> None:
    """Run every codegen step for a specifications/<version>/ package.

    Runs sync-enums (spec.py), then generate-builtin-classes, then
    generate-classes, then generate-signals. Skips enum sync if spec.py
    doesn't exist yet (use ``add-version`` to create it).
    """
    root = specs_root or _SPECIFICATIONS_ROOT
    spec_path = root / version / "spec.py"
    if spec_path.exists():
        sync_enums(
            version=version, api_json=api_json, check=check, specs_root=specs_root
        )
    else:
        print_warning(
            f"Skipping enum sync: {spec_path} not found. "
            "Use 'gli specifications add-version' to create it."
        )
    generate_builtin_classes(
        version=version, api_json=api_json, check=check, specs_root=specs_root
    )
    generate_classes(
        version=version, api_json=api_json, check=check, specs_root=specs_root
    )
    generate_signals(
        version=version, api_json=api_json, check=check, specs_root=specs_root
    )

    if check:
        print_success(f"Everything for {version} is up to date.")
    else:
        print_success(f"Everything for {version} is generated.")


# --- Schema diff and add-version -------------------------------------------


def _read_godot_versions() -> list[str]:
    """Read godot-versions.txt, returning a list of version strings like ['4.4.0', ...]."""
    if not _VERSIONS_FILE.exists():
        return []
    return [
        line.strip()
        for line in _VERSIONS_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _version_to_pkg(version: str) -> str:
    """Convert '4.4.0' to 'v4_4_0'."""
    return "v" + version.replace(".", "_")


def _version_to_class_suffix(version_pkg: str) -> str:
    """Convert 'v4_4_0' to '4_4_0'."""
    return version_pkg[1:] if version_pkg.startswith("v") else version_pkg


def _get_enum_values_from_module(version_pkg: str) -> dict[str, set[str]]:
    """Import a version's spec module and extract enum values from the 5 enum classes."""
    module = importlib.import_module(
        f"godotllminteraction.specifications.{version_pkg}.spec"
    )
    result: dict[str, set[str]] = {}
    for enum_name in _ENUM_NAMES:
        enum_class = getattr(module, enum_name, None)
        if enum_class is not None:
            result[enum_name] = {member.value for member in enum_class}
    return result


def _render_spec_py_template(
    version_pkg: str,
    base_version_pkg: str | None,
    enum_comparison: dict[str, dict] | None,
) -> str:
    """Generate the spec.py source for a new version package.

    Enums identical to the base version are imported from it; others get
    placeholder marker blocks for sync-enums to fill in.
    """
    suffix = _version_to_class_suffix(version_pkg)
    class_name = f"Specification{suffix}"

    imports_from_shared = [
        "BuiltinClass",
        "BuiltinClassArgument",
        "BuiltinClassConstructor",
        "BuiltinClassConstant",
        "BuiltinClassEnum",
        "BuiltinClassMember",
        "BuiltinClassMemberOffsets",
        "BuiltinClassMethod",
        "BuiltinClassOperator",
        "BuiltinClassSizeType",
        "BuiltinClassesList",
        "ClassConstant",
        "ClassMember",
        "ClassMemeberOffset",
        "ClassMethod",
        "ClassMethodArgument",
        "ClassMethodReturnValue",
        "ClassProperty",
        "ClassSignal",
        "ClassSignalArgument",
        "ClassSize",
        "ClassesList",
        "GlobalConstant",
        "GlobalConstantsList",
        "GlobalEnumsList",
        "GodotClass",
        "GodotEnum",
        "GodotEnumValues",
        "Header",
        "NativeStructure",
        "NativeStructuresList",
        "Singleton",
        "SingletonsList",
        "UtilityFunction",
        "UtilityFunctionArgument",
        "UtilityFunctionsList",
    ]

    lines = [
        '"""Auto-generated spec for Godot ' + version_pkg + '. Do not edit by hand."""',
        "",
        "from __future__ import annotations",
        "",
        "from enum import Enum",
        "from functools import cached_property",
        "from typing import List, Optional, Union",
        "",
        "from pydantic import BaseModel, Field",
        "",
        "from godotllminteraction.specifications.shared.spec import (",
    ]
    for name in imports_from_shared:
        lines.append(f"    {name},")
    lines.append(")")
    lines.append("")

    enum_blocks = {
        "GodotTypeNameEnum": (
            "GodotTypeName",
            "UtilityFunctionReturnType = GodotTypeName",
        ),
        "UtilityFunctionCategoryEnum": ("UtilityFunctionCategory", None),
        "BuiltinClassOperatorNameEnum": ("BuiltinClassOperatorName", None),
        "GodotArgumentMetaEnum": ("GodotArgumentMeta", None),
        "ClassApiTypeEnum": ("ClassApiType", None),
    }

    enum_imports: list[str] = []
    for enum_name, (alias_name, extra_alias) in enum_blocks.items():
        entry = enum_comparison.get(enum_name) if enum_comparison else None
        identical = getattr(entry, "identical_to_base", None) if entry else None
        if entry and isinstance(entry, dict):
            identical = entry.get("identical_to_base")
        should_import = base_version_pkg is not None and identical is True
        if should_import:
            enum_imports.append(enum_name)
            enum_imports.append(alias_name)
        else:
            lines.append("")
            lines.append(
                f"# === GENERATED: {enum_name} "
                f"(run: gli specifications sync-enums --version {version_pkg}) ==="
            )
            lines.append(f"class {enum_name}(str, Enum):")
            lines.append('    PLACEHOLDER = "placeholder"')
            lines.append("")
            lines.append("")
            lines.append(f"{alias_name} = Union[{enum_name}, str]")
            lines.append(f"# === END GENERATED: {enum_name} ===")
            if extra_alias:
                lines.append("")
                lines.append(extra_alias)

    if enum_imports:
        lines.append("")
        lines.append(
            f"from godotllminteraction.specifications.{base_version_pkg}.spec import ("
        )
        for name in enum_imports:
            lines.append(f"    {name},")
        lines.append(")")

    lines.append("")
    lines.append("")
    lines.append(f"class {class_name}(BaseModel):")
    lines.append(
        f'    """Full Godot {version_pkg} GDExtension API dump, '
        'mirroring the top-level sections of extension_api.json."""'
    )
    lines.append("")
    lines.append(
        '    header: Header = Field(description="Engine version and build metadata")'
    )
    lines.append("    builtin_class_sizes: List[BuiltinClassSizeType] = Field(")
    lines.append(
        '        description="Byte sizes of builtin classes, per build configuration"'
    )
    lines.append("    )")
    lines.append(
        "    builtin_class_member_offsets: List[BuiltinClassMemberOffsets] = Field("
    )
    lines.append(
        '        description="Member offsets within builtin classes, per build configuration"'
    )
    lines.append("    )")
    lines.append("    global_constants: GlobalConstantsList = Field(")
    lines.append('        description="Engine-wide global constants"')
    lines.append("    )")
    lines.append(
        '    global_enums: GlobalEnumsList = Field(description="Engine-wide global enums")'
    )
    lines.append("    utility_functions: UtilityFunctionsList = Field(")
    lines.append(
        '        description="Global utility functions (math, random, general)"'
    )
    lines.append("    )")
    lines.append("    builtin_classes: BuiltinClassesList = Field(")
    lines.append(
        '        description="Builtin variant types such as Vector2, Color, Array"'
    )
    lines.append("    )")
    lines.append("    classes: ClassesList = Field(")
    lines.append(
        '        description="Engine class hierarchy such as Object, Node, Resource"'
    )
    lines.append("    )")
    lines.append("    singletons: SingletonsList = Field(")
    lines.append('        description="Globally accessible singleton instances"')
    lines.append("    )")
    lines.append("    native_structures: NativeStructuresList = Field(")
    lines.append('        description="Native C++ structs exposed to extensions"')
    lines.append("    )")
    lines.append("")
    lines.append("    @cached_property")
    lines.append("    def class_names(self):")
    lines.append("        return [cls.name for cls in self.classes]")
    lines.append("")
    lines.append("    @cached_property")
    lines.append("    def builtin_class_names(self):")
    lines.append("        return [cls.name for cls in self.builtin_classes]")
    lines.append("")

    return "\n".join(lines)


@app.command("diff-schema")
def diff_schema(
    version: Annotated[
        str,
        typer.Option(
            "--version",
            "-v",
            help="Version package to diff, e.g. 'v4_4_1'.",
        ),
    ],
    api_json: Annotated[
        Path,
        typer.Option(
            "--api",
            "-a",
            help="Path to extension_api.json.",
            exists=True,
            dir_okay=False,
        ),
    ] = Path("extension_api.json"),
    base_version: Annotated[
        str | None,
        typer.Option(
            "--base-version",
            help="Base version package to compare against, e.g. 'v4_4_0'. "
            "Required unless --first-version is set.",
        ),
    ] = None,
    first_version: Annotated[
        bool,
        typer.Option(
            "--first-version",
            help="Skip base version comparison (for the first version added).",
        ),
    ] = False,
    report_path: Annotated[
        Path | None,
        typer.Option(
            "--report",
            help="Path to write the diff report. Default: schema_diff_<version>.yaml",
        ),
    ] = None,
    report_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Report format: 'yaml' (default) or 'json'.",
        ),
    ] = "yaml",
) -> None:
    """Compute the schema diff between extension_api.json and the shared pydantic models."""
    if not _VERSION_RE.match(version):
        print_error(f"Invalid version {version!r}; expected a format like 'v4_4_0'.")
        raise typer.Exit(code=EXIT_USAGE)

    if base_version is None and not first_version:
        print_error(
            "--base-version is required (or use --first-version for the first version)."
        )
        raise typer.Exit(code=EXIT_USAGE)

    if base_version is not None and not _VERSION_RE.match(base_version):
        print_error(
            f"Invalid base version {base_version!r}; expected a format like 'v4_4_0'."
        )
        raise typer.Exit(code=EXIT_USAGE)

    data = json.loads(api_json.read_text())

    base_enum_values: dict[str, set[str]] | None = None
    if base_version is not None:
        try:
            base_enum_values = _get_enum_values_from_module(base_version)
        except ImportError as exc:
            print_error(f"Could not import base version {base_version}: {exc}")
            raise typer.Exit(code=EXIT_ERROR) from exc

    report = compute_schema_diff(
        data,
        base_enum_values=base_enum_values,
        version=version,
        base_version=base_version or "",
    )

    if report_path is None:
        ext = "yaml" if report_format == "yaml" else "json"
        report_path = Path(f"schema_diff_{version}.{ext}")

    if report_format == "json":
        report_text = format_report_json(report)
    else:
        report_text = format_report_yaml(report)

    report_path.write_text(report_text)
    print_success(f"Schema diff report written to {report_path}.")

    if report.requires_human_intervention:
        print_error("Human intervention required. Review the report for details.")
        raise typer.Exit(code=EXIT_ERROR)

    print_text("No human intervention required.")


@app.command("add-version")
def add_version(
    version: Annotated[
        str,
        typer.Option(
            "--version",
            "-v",
            help="Version package to create, e.g. 'v4_4_1'.",
        ),
    ],
    api_json: Annotated[
        Path | None,
        typer.Option(
            "--api",
            "-a",
            help="Path to extension_api.json. If omitted, --godot-version must be set.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    godot_version: Annotated[
        str | None,
        typer.Option(
            "--godot-version",
            help="Godot version to dump from (e.g. '4.5.0'). Uses godotctl to find the binary. "
            "If set, --api is not needed.",
        ),
    ] = None,
    base_version: Annotated[
        str | None,
        typer.Option(
            "--base-version",
            help="Base version package to compare against, e.g. 'v4_4_0'. "
            "Required unless --first-version is set.",
        ),
    ] = None,
    first_version: Annotated[
        bool,
        typer.Option(
            "--first-version",
            help="Skip base version comparison (for the first version added).",
        ),
    ] = False,
    specs_root: Annotated[
        Path | None,
        typer.Option(
            "--specs-root",
            help="Root directory for version packages. Defaults to the built-in specifications/.",
        ),
    ] = None,
) -> None:
    """Orchestrate the full version-addition workflow: dump API (optional), diff, generate spec.py, sync enums, generate code."""
    if not _VERSION_RE.match(version):
        print_error(f"Invalid version {version!r}; expected a format like 'v4_4_0'.")
        raise typer.Exit(code=EXIT_USAGE)

    if base_version is None and not first_version:
        print_error(
            "--base-version is required (or use --first-version for the first version)."
        )
        raise typer.Exit(code=EXIT_USAGE)

    if base_version is not None and not _VERSION_RE.match(base_version):
        print_error(
            f"Invalid base version {base_version!r}; expected a format like 'v4_4_0'."
        )
        raise typer.Exit(code=EXIT_USAGE)

    if api_json is None and godot_version is None:
        print_error("Either --api or --godot-version must be provided.")
        raise typer.Exit(code=EXIT_USAGE)

    if api_json is not None and godot_version is not None:
        print_error("--api and --godot-version are mutually exclusive.")
        raise typer.Exit(code=EXIT_USAGE)

    if godot_version is not None:
        binary_name = f"godot-{godot_version}-stable"
        binary = shutil.which(binary_name)
        if binary is None:
            print_error(
                f"Could not find Godot binary {binary_name!r} on PATH. "
                "Install it with godotctl or pass --api with a pre-dumped JSON."
            )
            raise typer.Exit(code=EXIT_ERROR)

        print_text(f"Dumping extension_api.json from {binary}...")
        tmpdir = tempfile.mkdtemp()
        result = subprocess.run(
            [binary, "--headless", "--dump-extension-api", "--quit"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        dump_path = Path(tmpdir) / "extension_api.json"
        if result.returncode != 0 or not dump_path.exists():
            print_error(
                f"Godot failed to dump extension_api.json (exit {result.returncode}):\n"
                f"{result.stderr}"
            )
            raise typer.Exit(code=EXIT_ERROR)
        api_json = dump_path

    data = json.loads(api_json.read_text())  # type: ignore[union-attr]

    base_enum_values: dict[str, set[str]] | None = None
    if base_version is not None:
        try:
            base_enum_values = _get_enum_values_from_module(base_version)
        except ImportError as exc:
            print_error(f"Could not import base version {base_version}: {exc}")
            raise typer.Exit(code=EXIT_ERROR) from exc

    report = compute_schema_diff(
        data,
        base_enum_values=base_enum_values,
        version=version,
        base_version=base_version or "",
    )

    if report.requires_human_intervention:
        report_path = Path(f"schema_diff_{version}.yaml")
        report_path.write_text(format_report_yaml(report))
        print_error(
            f"Human intervention required. Report written to {report_path}. "
            "Resolve the issues and re-run."
        )
        raise typer.Exit(code=EXIT_ERROR)

    version_dir, created = _ensure_version_package(version, specs_root)
    if created:
        print_success(f"Created {version_dir}.")

    spec_path = version_dir / "spec.py"
    spec_source = _render_spec_py_template(
        version, base_version if not first_version else None, report.enum_comparison
    )
    _write_if_changed(spec_path, spec_source)
    print_success(f"Generated {spec_path}.")

    sync_enums(version=version, api_json=api_json, specs_root=specs_root)
    generate_builtin_classes(version=version, api_json=api_json, specs_root=specs_root)
    generate_classes(version=version, api_json=api_json, specs_root=specs_root)
    generate_signals(version=version, api_json=api_json, specs_root=specs_root)

    init_path = version_dir / "__init__.py"
    suffix = _version_to_class_suffix(version)
    class_name = f"Specification{suffix}"
    init_source = (
        f"from godotllminteraction.specifications.{version}.spec import {class_name}\n\n"
        f'__all__ = ["{class_name}"]\n'
    )
    _write_if_changed(init_path, init_source)
    print_success(f"Generated {init_path}.")

    if _VERSIONS_FILE.exists():
        existing = _read_godot_versions()
        version_dot = (
            version[1:].replace("_", ".") if version.startswith("v") else version
        )
        if version_dot not in existing:
            existing.append(version_dot)
            existing.sort(key=lambda v: [int(x) for x in v.split(".")])
            _VERSIONS_FILE.write_text("\n".join(existing) + "\n")
            print_success(f"Appended {version_dot} to {_VERSIONS_FILE}.")

    print_success(f"Version {version} added successfully.")

    guidance = report.test_guidance
    if guidance.detectable:
        print_text("\nTest guidance:")
        for suggestion in guidance.detectable:
            print_text(f"  - {suggestion}")
    else:
        print_text(f"\nTest guidance: {guidance.generic}")
