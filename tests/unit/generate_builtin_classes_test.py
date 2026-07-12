from __future__ import annotations

import pytest

from godotllminteraction.cli.specifications import (
    render_builtin_classes_source,
    render_constants_source,
)

pytestmark = [pytest.mark.specs]


def _fake_data(builtin_classes: list[dict]) -> dict:
    return {"builtin_classes": builtin_classes}


VECTOR2 = {
    "name": "Vector2",
    "members": [{"name": "x", "type": "float"}, {"name": "y", "type": "float"}],
    "constants": [{"name": "ZERO", "type": "Vector2", "value": "Vector2(0, 0)"}],
}

TRANSFORM2D = {
    "name": "Transform2D",
    "members": [
        {"name": "x", "type": "Vector2"},
        {"name": "y", "type": "Vector2"},
        {"name": "origin", "type": "Vector2"},
    ],
    "constants": [
        {
            "name": "IDENTITY",
            "type": "Transform2D",
            "value": "Transform2D(1, 0, 0, 1, 0, 0)",
        }
    ],
}

CLASS_WITHOUT_MEMBERS = {"name": "String"}


class TestRenderBuiltinModels:
    def test_is_deterministic(self):
        data = _fake_data([TRANSFORM2D, VECTOR2])
        first = render_builtin_classes_source(data, "v4_7_0")
        second = render_builtin_classes_source(data, "v4_7_0")
        assert first == second

    def test_orders_dependencies_before_dependents_regardless_of_input_order(self):
        # Transform2D is listed first in the input; Vector2 (its dependency) must
        # still be emitted first in the output so the generated code is valid Python.
        data = _fake_data([TRANSFORM2D, VECTOR2])
        source = render_builtin_classes_source(data, "v4_7_0")
        assert source.index("class Vector2v4_7_0") < source.index(
            "class Transform2Dv4_7_0"
        )

    def test_member_referencing_modeled_class_uses_versioned_model_name(self):
        data = _fake_data([VECTOR2, TRANSFORM2D])
        source = render_builtin_classes_source(data, "v4_7_0")
        assert "x: Vector2v4_7_0" in source

    def test_primitive_member_uses_plain_python_type(self):
        data = _fake_data([VECTOR2])
        source = render_builtin_classes_source(data, "v4_7_0")
        assert "x: float" in source
        assert "y: float" in source

    def test_class_without_members_is_skipped(self):
        data = _fake_data([VECTOR2, CLASS_WITHOUT_MEMBERS])
        source = render_builtin_classes_source(data, "v4_7_0")
        assert "String" not in source

    def test_version_label_is_embedded_in_model_name(self):
        data = _fake_data([VECTOR2])
        source = render_builtin_classes_source(data, "v9_9_9")
        assert "class Vector2v9_9_9(BaseModel):" in source

    def test_unknown_member_type_raises(self):
        bad_class = {
            "name": "Weird",
            "members": [{"name": "thing", "type": "SomethingUnmodeled"}],
        }
        with pytest.raises(ValueError, match="SomethingUnmodeled"):
            render_builtin_classes_source(_fake_data([bad_class]), "v4_7_0")

    def test_cyclic_dependency_raises(self):
        a = {"name": "A", "members": [{"name": "b", "type": "B"}]}
        b = {"name": "B", "members": [{"name": "a", "type": "A"}]}
        with pytest.raises(ValueError, match="Cyclic dependency"):
            render_builtin_classes_source(_fake_data([a, b]), "v4_7_0")

    def test_generated_source_is_valid_importable_python(self, load_module):
        data = _fake_data([VECTOR2, TRANSFORM2D])
        source = render_builtin_classes_source(data, "v4_7_0")
        module = load_module(source)
        vector2 = module.Vector2v4_7_0
        transform2d = module.Transform2Dv4_7_0
        instance = transform2d(
            x=vector2(x=1, y=0), y=vector2(x=0, y=1), origin=vector2(x=0, y=0)
        )
        assert instance.origin.x == 0.0


class TestRenderConstants:
    def test_is_deterministic(self):
        data = _fake_data([TRANSFORM2D, VECTOR2])
        first = render_constants_source(data)
        second = render_constants_source(data)
        assert first == second

    def test_disambiguates_same_constant_name_across_classes(self):
        data = _fake_data([VECTOR2, TRANSFORM2D])
        source = render_constants_source(data)
        assert "VECTOR2_ZERO = GodotConstant(" in source
        assert "TRANSFORM2D_IDENTITY = GodotConstant(" in source

    def test_by_godot_name_maps_dotted_syntax_to_identifier(self, load_module):
        data = _fake_data([VECTOR2, TRANSFORM2D])
        source = render_constants_source(data)
        module = load_module(source)
        assert module.BY_GODOT_NAME["Vector2.ZERO"] is module.VECTOR2_ZERO
        assert (
            module.BY_GODOT_NAME["Transform2D.IDENTITY"] is module.TRANSFORM2D_IDENTITY
        )

    def test_raw_value_is_kept_as_is_not_evaluated(self):
        data = _fake_data([VECTOR2])
        source = render_constants_source(data)
        assert 'raw_value="Vector2(0, 0)"' in source

    def test_identifier_collision_across_differently_cased_class_names_raises(self):
        clashing = {
            "name": "VECTOR2",
            "members": [],
            "constants": [
                {"name": "ZERO", "type": "VECTOR2", "value": "VECTOR2(0, 0)"}
            ],
        }
        with pytest.raises(ValueError, match="collision"):
            render_constants_source(_fake_data([VECTOR2, clashing]))
