from __future__ import annotations

import pytest

from godotllminteraction.cli.specifications import (
    _block_pattern,
    render_spec_source,
)

pytestmark = [pytest.mark.specs]

FAKE_DATA = {
    "utility_functions": [
        {
            "name": "sin",
            "return_type": "float",
            "category": "math",
            "is_vararg": False,
            "hash": 1,
        },
        {"name": "randomize", "category": "random", "is_vararg": False, "hash": 2},
    ],
    "builtin_classes": [
        {
            "name": "Vector2",
            "is_keyed": False,
            "operators": [
                {"name": "==", "right_type": "Vector2", "return_type": "bool"},
                {"name": "unary-", "return_type": "Vector2"},
            ],
        }
    ],
    "classes": [
        {
            "name": "Node",
            "api_type": "core",
            "methods": [
                {
                    "name": "foo",
                    "is_const": False,
                    "is_vararg": False,
                    "is_static": False,
                    "is_virtual": False,
                    "hash": 1,
                    "arguments": [{"name": "x", "type": "int", "meta": "int64"}],
                    "return_value": {"type": "float", "meta": "double"},
                }
            ],
        }
    ],
}

_SPEC_SKELETON = """from pydantic import BaseModel, Field
from typing import List, Optional, Union
from functools import cached_property
from enum import Enum


# === GENERATED: GodotTypeNameEnum (run: gli specifications sync-enums-v4-7-0) ===
class GodotTypeNameEnum(str, Enum):
    STALE = "stale"


GodotTypeName = Union[GodotTypeNameEnum, str]
# === END GENERATED: GodotTypeNameEnum ===

UtilityFunctionReturnType = GodotTypeName


# === GENERATED: UtilityFunctionCategoryEnum (run: gli specifications sync-enums-v4-7-0) ===
class UtilityFunctionCategoryEnum(str, Enum):
    STALE = "stale"


UtilityFunctionCategory = Union[UtilityFunctionCategoryEnum, str]
# === END GENERATED: UtilityFunctionCategoryEnum ===


# === GENERATED: BuiltinClassOperatorNameEnum (run: gli specifications sync-enums-v4-7-0) ===
class BuiltinClassOperatorNameEnum(str, Enum):
    STALE = "stale"


BuiltinClassOperatorName = Union[BuiltinClassOperatorNameEnum, str]
# === END GENERATED: BuiltinClassOperatorNameEnum ===


# === GENERATED: GodotArgumentMetaEnum (run: gli specifications sync-enums-v4-7-0) ===
class GodotArgumentMetaEnum(str, Enum):
    STALE = "stale"


GodotArgumentMeta = Union[GodotArgumentMetaEnum, str]
# === END GENERATED: GodotArgumentMetaEnum ===


# === GENERATED: ClassApiTypeEnum (run: gli specifications sync-enums-v4-7-0) ===
class ClassApiTypeEnum(str, Enum):
    STALE = "stale"


ClassApiType = Union[ClassApiTypeEnum, str]
# === END GENERATED: ClassApiTypeEnum ===


class Header(BaseModel):
    version_major: int = Field(default=4)
"""


class TestRenderSpecSource:
    def test_is_deterministic(self):
        first = render_spec_source(_SPEC_SKELETON, FAKE_DATA)
        second = render_spec_source(_SPEC_SKELETON, FAKE_DATA)
        assert first == second

    def test_replaces_stale_type_name_enum(self):
        updated = render_spec_source(_SPEC_SKELETON, FAKE_DATA)
        assert (
            'STALE = "stale"'
            not in updated.split("# === END GENERATED: ClassApiTypeEnum ===")[0]
        )
        assert 'VECTOR2 = "Vector2"' in updated
        assert 'FLOAT = "float"' in updated

    def test_replaces_category_enum(self):
        updated = render_spec_source(_SPEC_SKELETON, FAKE_DATA)
        assert 'MATH = "math"' in updated
        assert 'RANDOM = "random"' in updated

    def test_replaces_operator_enum(self):
        updated = render_spec_source(_SPEC_SKELETON, FAKE_DATA)
        assert 'EQUAL = "=="' in updated
        assert 'UNARY_MINUS = "unary-"' in updated

    def test_replaces_argument_meta_enum(self):
        updated = render_spec_source(_SPEC_SKELETON, FAKE_DATA)
        assert 'DOUBLE = "double"' in updated
        assert 'INT64 = "int64"' in updated

    def test_replaces_api_type_enum(self):
        updated = render_spec_source(_SPEC_SKELETON, FAKE_DATA)
        assert 'CORE = "core"' in updated

    def test_preserves_hand_written_code_outside_markers(self):
        updated = render_spec_source(_SPEC_SKELETON, FAKE_DATA)
        assert "class Header(BaseModel):" in updated
        assert "version_major: int = Field(default=4)" in updated

    def test_missing_marker_skips_enum_silently(self):
        """When a marker block is missing (enum imported from base), it should be skipped."""
        broken = _SPEC_SKELETON.replace(
            "# === END GENERATED: ClassApiTypeEnum ===", "# oops, marker gone"
        )
        # Should not raise — just skips the enum whose markers are missing
        updated = render_spec_source(broken, FAKE_DATA)
        assert "class Header(BaseModel):" in updated

    def test_missing_marker_does_not_skip_other_enums(self):
        """A missing marker for one enum must not prevent the others from being updated."""
        broken = _SPEC_SKELETON.replace(
            "# === END GENERATED: ClassApiTypeEnum ===", "# oops, marker gone"
        )
        updated = render_spec_source(broken, FAKE_DATA)
        # The 4 enums with intact markers should still be refreshed
        assert 'VECTOR2 = "Vector2"' in updated
        assert 'MATH = "math"' in updated
        assert 'EQUAL = "=="' in updated
        assert 'DOUBLE = "double"' in updated
        # The broken enum's stale content should be left untouched (not deleted)
        broken_section = updated.split("class Header")[0]
        assert (
            'STALE = "stale"'
            in broken_section.split("# === GENERATED: ClassApiTypeEnum")[1]
        )

    def test_running_twice_is_idempotent(self):
        once = render_spec_source(_SPEC_SKELETON, FAKE_DATA)
        twice = render_spec_source(once, FAKE_DATA)
        assert once == twice


class TestBlockPatternVersioned:
    def test_default_pattern_matches_old_marker(self):
        pattern = _block_pattern("GodotTypeNameEnum")
        text = "# === GENERATED: GodotTypeNameEnum (run: gli specifications sync-enums-v4-7-0) ===\nclass X:\n    pass\n# === END GENERATED: GodotTypeNameEnum ==="
        assert pattern.search(text) is not None

    def test_versioned_pattern_matches_new_marker(self):
        pattern = _block_pattern("GodotTypeNameEnum", "sync-enums --version v4_4_0")
        text = "# === GENERATED: GodotTypeNameEnum (run: gli specifications sync-enums --version v4_4_0) ===\nclass X:\n    pass\n# === END GENERATED: GodotTypeNameEnum ==="
        assert pattern.search(text) is not None

    def test_versioned_pattern_does_not_match_old_marker(self):
        pattern = _block_pattern("GodotTypeNameEnum", "sync-enums --version v4_4_0")
        text = "# === GENERATED: GodotTypeNameEnum (run: gli specifications sync-enums-v4-7-0) ===\nclass X:\n    pass\n# === END GENERATED: GodotTypeNameEnum ==="
        assert pattern.search(text) is None

    def test_render_spec_source_with_versioned_command(self):
        skeleton = _SPEC_SKELETON.replace(
            "sync-enums-v4-7-0", "sync-enums --version v4_4_0"
        )
        updated = render_spec_source(skeleton, FAKE_DATA, "sync-enums --version v4_4_0")
        assert 'VECTOR2 = "Vector2"' in updated
        assert 'FLOAT = "float"' in updated
