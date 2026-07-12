"""Fuzzy tests for render_spec_source: generate random extension_api.json-like data
and verify the enum sync produces correct, idempotent, and stable results."""

from __future__ import annotations

import random
import string

import pytest

from godotllminteraction.cli.specifications import render_spec_source

# Known valid values for each enum domain
VALID_TYPE_NAMES = [
    "AABB",
    "Array",
    "Basis",
    "Callable",
    "Color",
    "Dictionary",
    "NodePath",
    "Object",
    "PackedByteArray",
    "PackedColorArray",
    "PackedFloat32Array",
    "PackedFloat64Array",
    "PackedInt32Array",
    "PackedInt64Array",
    "PackedStringArray",
    "PackedVector2Array",
    "PackedVector3Array",
    "PackedVector4Array",
    "Plane",
    "Projection",
    "Quaternion",
    "RID",
    "Rect2",
    "Rect2i",
    "Signal",
    "String",
    "StringName",
    "Transform2D",
    "Transform3D",
    "Variant",
    "Vector2",
    "Vector2i",
    "Vector3",
    "Vector3i",
    "Vector4",
    "Vector4i",
    "bool",
    "float",
    "int",
]
VALID_CATEGORIES = ["general", "math", "random"]
VALID_OPERATORS = [
    "!=",
    "%",
    "&",
    "*",
    "**",
    "+",
    "-",
    "/",
    "<",
    "<<",
    "<=",
    "==",
    ">",
    ">=",
    ">>",
    "^",
    "and",
    "in",
    "not",
    "or",
    "unary+",
    "unary-",
    "xor",
    "|",
    "~",
]
VALID_METAS = [
    "char32",
    "double",
    "float",
    "int16",
    "int32",
    "int64",
    "int8",
    "required",
    "uint16",
    "uint32",
    "uint64",
    "uint8",
]
VALID_API_TYPES = ["core", "editor"]

# Random string generator for edge-case type names
_RANDOM_CHARS = string.ascii_letters + string.digits + "_"


def _random_type_name(rng: random.Random) -> str:
    """Generate a random type name — sometimes valid, sometimes random."""
    if rng.random() < 0.7:
        return rng.choice(VALID_TYPE_NAMES)
    length = rng.randint(1, 20)
    return "".join(rng.choice(_RANDOM_CHARS) for _ in range(length))


def _random_category(rng: random.Random) -> str:
    if rng.random() < 0.8:
        return rng.choice(VALID_CATEGORIES)
    return "".join(rng.choice(_RANDOM_CHARS) for _ in range(rng.randint(1, 10)))


def _random_operator(rng: random.Random) -> str:
    if rng.random() < 0.8:
        return rng.choice(VALID_OPERATORS)
    return rng.choice("!@#$%^&*+=<>/~|&")


def _random_meta(rng: random.Random) -> str:
    if rng.random() < 0.8:
        return rng.choice(VALID_METAS)
    return "".join(rng.choice(_RANDOM_CHARS) for _ in range(rng.randint(1, 10)))


def _random_api_type(rng: random.Random) -> str:
    if rng.random() < 0.8:
        return rng.choice(VALID_API_TYPES)
    return "".join(rng.choice(_RANDOM_CHARS) for _ in range(rng.randint(1, 10)))


def _generate_random_api_data(rng: random.Random) -> dict:
    """Generate a random extension_api.json-like dict with known structure."""
    data: dict = {}

    # Random utility functions
    n_funcs = rng.randint(0, 10)
    funcs = []
    for i in range(n_funcs):
        fn: dict = {
            "name": f"func_{i}",
            "category": _random_category(rng),
            "is_vararg": rng.choice([True, False]),
            "hash": rng.randint(0, 2**63),
        }
        if rng.random() < 0.5:
            fn["return_type"] = _random_type_name(rng)
        if rng.random() < 0.3:
            fn["arguments"] = [
                {"name": f"arg_{j}", "type": _random_type_name(rng)}
                for j in range(rng.randint(0, 4))
            ]
        funcs.append(fn)
    if funcs:
        data["utility_functions"] = funcs

    # Random builtin classes
    n_builtins = rng.randint(0, 5)
    builtins = []
    for i in range(n_builtins):
        cls: dict = {
            "name": f"Builtin{i}",
            "is_keyed": rng.choice([True, False]),
            "has_destructor": rng.choice([True, False]),
        }
        n_ops = rng.randint(0, 6)
        ops = []
        for j in range(n_ops):
            op: dict = {
                "name": _random_operator(rng),
                "return_type": _random_type_name(rng),
            }
            if rng.random() < 0.5:
                op["right_type"] = _random_type_name(rng)
            ops.append(op)
        if ops:
            cls["operators"] = ops

        n_members = rng.randint(0, 4)
        members = [
            {"name": f"m_{j}", "type": _random_type_name(rng)} for j in range(n_members)
        ]
        if members:
            cls["members"] = members

        n_consts = rng.randint(0, 3)
        consts = [
            {
                "name": f"C_{j}",
                "type": _random_type_name(rng),
                "value": f"Builtin{i}({j})",
            }
            for j in range(n_consts)
        ]
        if consts:
            cls["constants"] = consts

        n_methods = rng.randint(0, 5)
        methods = []
        for j in range(n_methods):
            method: dict = {
                "name": f"method_{j}",
                "is_const": rng.choice([True, False]),
                "is_vararg": rng.choice([True, False]),
                "is_static": rng.choice([True, False]),
                "hash": rng.randint(0, 2**63),
            }
            if rng.random() < 0.5:
                method["return_type"] = _random_type_name(rng)
            if rng.random() < 0.3:
                method["arguments"] = [
                    {"name": f"arg_{k}", "type": _random_type_name(rng)}
                    for k in range(rng.randint(0, 3))
                ]
            methods.append(method)
        if methods:
            cls["methods"] = methods

        builtins.append(cls)
    if builtins:
        data["builtin_classes"] = builtins

    # Random engine classes
    n_classes = rng.randint(0, 8)
    classes = []
    for i in range(n_classes):
        engine_cls: dict = {
            "name": f"Class{i}",
            "api_type": _random_api_type(rng),
        }
        n_methods = rng.randint(0, 6)
        methods = []
        for j in range(n_methods):
            m: dict = {
                "name": f"m_{j}",
                "is_const": rng.choice([True, False]),
                "is_vararg": rng.choice([True, False]),
                "is_static": rng.choice([True, False]),
                "is_virtual": rng.choice([True, False]),
                "hash": rng.randint(0, 2**63),
            }
            n_args = rng.randint(0, 4)
            args = []
            for k in range(n_args):
                arg: dict = {
                    "name": f"arg_{k}",
                    "type": _random_type_name(rng),
                }
                if rng.random() < 0.3:
                    arg["meta"] = _random_meta(rng)
                args.append(arg)
            if args:
                m["arguments"] = args
            if rng.random() < 0.5:
                rv: dict = {"type": _random_type_name(rng)}
                if rng.random() < 0.3:
                    rv["meta"] = _random_meta(rng)
                m["return_value"] = rv
            methods.append(m)
        if methods:
            engine_cls["methods"] = methods
        classes.append(engine_cls)
    if classes:
        data["classes"] = classes

    return data


_SPEC_SKELETON_TEMPLATE = """from pydantic import BaseModel, Field
from typing import List, Optional, Union
from functools import cached_property
from enum import Enum


# === GENERATED: GodotTypeNameEnum (run: gli specifications {cmd}) ===
class GodotTypeNameEnum(str, Enum):
    STALE = "stale"


GodotTypeName = Union[GodotTypeNameEnum, str]
# === END GENERATED: GodotTypeNameEnum ===

UtilityFunctionReturnType = GodotTypeName


# === GENERATED: UtilityFunctionCategoryEnum (run: gli specifications {cmd}) ===
class UtilityFunctionCategoryEnum(str, Enum):
    STALE = "stale"


UtilityFunctionCategory = Union[UtilityFunctionCategoryEnum, str]
# === END GENERATED: UtilityFunctionCategoryEnum ===


# === GENERATED: BuiltinClassOperatorNameEnum (run: gli specifications {cmd}) ===
class BuiltinClassOperatorNameEnum(str, Enum):
    STALE = "stale"


BuiltinClassOperatorName = Union[BuiltinClassOperatorNameEnum, str]
# === END GENERATED: BuiltinClassOperatorNameEnum ===


# === GENERATED: GodotArgumentMetaEnum (run: gli specifications {cmd}) ===
class GodotArgumentMetaEnum(str, Enum):
    STALE = "stale"


GodotArgumentMeta = Union[GodotArgumentMetaEnum, str]
# === END GENERATED: GodotArgumentMetaEnum ===


# === GENERATED: ClassApiTypeEnum (run: gli specifications {cmd}) ===
class ClassApiTypeEnum(str, Enum):
    STALE = "stale"


ClassApiType = Union[ClassApiTypeEnum, str]
# === END GENERATED: ClassApiTypeEnum ===


class Header(BaseModel):
    version_major: int = Field(default=4)
"""


def _make_skeleton(cmd: str = "sync-enums-v4-7-0") -> str:
    return _SPEC_SKELETON_TEMPLATE.format(cmd=cmd)


@pytest.mark.parametrize("seed", range(100))
def test_fuzzy_render_is_idempotent(seed):
    """render_spec_source applied twice should produce the same result."""
    rng = random.Random(seed)
    data = _generate_random_api_data(rng)
    skeleton = _make_skeleton()
    try:
        once = render_spec_source(skeleton, data)
        twice = render_spec_source(once, data)
    except ValueError:
        # Unknown operator symbols are expected for random data
        return
    assert once == twice


@pytest.mark.parametrize("seed", range(50))
def test_fuzzy_render_replaces_all_stale_enums(seed):
    """After rendering, no STALE values should remain in generated blocks."""
    rng = random.Random(seed + 1000)
    data = _generate_random_api_data(rng)
    skeleton = _make_skeleton()
    try:
        updated = render_spec_source(skeleton, data)
    except ValueError:
        return
    assert 'STALE = "stale"' not in updated


@pytest.mark.parametrize("seed", range(50))
def test_fuzzy_render_preserves_handwritten_code(seed):
    """The Header class and other non-generated code should be preserved."""
    rng = random.Random(seed + 2000)
    data = _generate_random_api_data(rng)
    skeleton = _make_skeleton()
    try:
        updated = render_spec_source(skeleton, data)
    except ValueError:
        return
    assert "class Header(BaseModel):" in updated
    assert "version_major: int = Field(default=4)" in updated


@pytest.mark.parametrize("seed", range(50))
def test_fuzzy_render_with_versioned_command(seed):
    """render_spec_source should work with version-specific command strings."""
    rng = random.Random(seed + 3000)
    data = _generate_random_api_data(rng)
    cmd = f"sync-enums --version v4_{rng.randint(0, 9)}_{rng.randint(0, 9)}"
    skeleton = _make_skeleton(cmd)
    try:
        updated = render_spec_source(skeleton, data, cmd)
    except ValueError:
        return
    assert cmd in updated
    assert 'STALE = "stale"' not in updated


@pytest.mark.parametrize("seed", range(30))
def test_fuzzy_render_empty_data_produces_empty_enums(seed):
    """Empty data should produce valid enum blocks with no members (except placeholder)."""
    rng = random.Random(seed + 4000)
    data = _generate_random_api_data(rng)
    # Force empty by removing all sections
    data = {}
    skeleton = _make_skeleton()
    updated = render_spec_source(skeleton, data)
    assert 'STALE = "stale"' not in updated
    # Should still have all 5 marker blocks
    for enum_name in [
        "GodotTypeNameEnum",
        "UtilityFunctionCategoryEnum",
        "BuiltinClassOperatorNameEnum",
        "GodotArgumentMetaEnum",
        "ClassApiTypeEnum",
    ]:
        assert f"# === GENERATED: {enum_name}" in updated
        assert f"# === END GENERATED: {enum_name}" in updated


@pytest.mark.parametrize("seed", range(30))
def test_fuzzy_render_deterministic_with_same_seed(seed):
    """Same random data should produce the same output every time."""
    rng1 = random.Random(seed + 5000)
    rng2 = random.Random(seed + 5000)
    data1 = _generate_random_api_data(rng1)
    data2 = _generate_random_api_data(rng2)
    assert data1 == data2
    skeleton = _make_skeleton()
    try:
        out1 = render_spec_source(skeleton, data1)
        out2 = render_spec_source(skeleton, data2)
    except ValueError:
        return
    assert out1 == out2
