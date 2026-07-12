from __future__ import annotations

import pytest

from godotllminteraction.cli.specifications import render_classes_source

pytestmark = [pytest.mark.specs]


def _fake_data(builtin_classes=None, classes=None) -> dict:
    return {"builtin_classes": builtin_classes or [], "classes": classes or []}


VECTOR2_BUILTIN = {
    "name": "Vector2",
    "members": [{"name": "x", "type": "float"}, {"name": "y", "type": "float"}],
}

PACKED_VECTOR2_ARRAY_BUILTIN = {
    "name": "PackedVector2Array",
    "indexing_return_type": "Vector2",
}
PACKED_INT32_ARRAY_BUILTIN = {"name": "PackedInt32Array", "indexing_return_type": "int"}

OBJECT_CLASS = {"name": "Object"}

NODE_CLASS = {
    "name": "Node",
    "inherits": "Object",
    "properties": [{"name": "name", "type": "String"}],
}

NODE2D_CLASS = {
    "name": "Node2D",
    "inherits": "Node",
    "properties": [{"name": "position", "type": "Vector2"}],
}


class TestRenderClasses:
    def test_is_deterministic(self):
        data = _fake_data([VECTOR2_BUILTIN], [NODE2D_CLASS, NODE_CLASS, OBJECT_CLASS])
        first = render_classes_source(data, "v4_7_0")
        second = render_classes_source(data, "v4_7_0")
        assert first == second

    def test_orders_parent_before_child_regardless_of_input_order(self):
        data = _fake_data([VECTOR2_BUILTIN], [NODE2D_CLASS, NODE_CLASS, OBJECT_CLASS])
        source = render_classes_source(data, "v4_7_0")
        assert (
            source.index("class Objectv4_7_0")
            < source.index("class Nodev4_7_0")
            < source.index("class Node2Dv4_7_0")
        )

    def test_root_class_subclasses_base_model(self):
        data = _fake_data(classes=[OBJECT_CLASS])
        source = render_classes_source(data, "v4_7_0")
        assert "class Objectv4_7_0(BaseModel):" in source

    def test_subclass_inherits_generated_parent_model(self):
        data = _fake_data(classes=[OBJECT_CLASS, NODE_CLASS])
        source = render_classes_source(data, "v4_7_0")
        assert "class Nodev4_7_0(Objectv4_7_0):" in source

    def test_own_properties_only_not_inherited(self):
        data = _fake_data([VECTOR2_BUILTIN], [OBJECT_CLASS, NODE_CLASS, NODE2D_CLASS])
        source = render_classes_source(data, "v4_7_0")
        node2d_body = source.split("class Node2Dv4_7_0")[1]
        assert "position:" in node2d_body
        assert "name:" not in node2d_body  # inherited from Node, not redeclared

    def test_property_referencing_modeled_builtin_imports_and_uses_versioned_type(self):
        data = _fake_data([VECTOR2_BUILTIN], [OBJECT_CLASS, NODE_CLASS, NODE2D_CLASS])
        source = render_classes_source(data, "v4_7_0")
        assert (
            "from godotllminteraction.specifications.v4_7_0.builtin_classes import ("
            in source
        )
        assert "Vector2v4_7_0," in source
        assert "position: Vector2v4_7_0" in source

    def test_property_referencing_another_class_uses_versioned_model_name(self):
        shape = {"name": "Shape2D", "inherits": "Resource"}
        resource = {"name": "Resource", "inherits": "Object"}
        collider = {
            "name": "CollisionShape2D",
            "inherits": "Node2D",
            "properties": [{"name": "shape", "type": "Shape2D"}],
        }
        data = _fake_data(
            classes=[OBJECT_CLASS, NODE_CLASS, NODE2D_CLASS, resource, shape, collider]
        )
        source = render_classes_source(data, "v4_7_0")
        assert "shape: Shape2Dv4_7_0" in source

    def test_primitive_properties_map_to_plain_python_types(self):
        cls = {
            "name": "Thing",
            "inherits": "Object",
            "properties": [
                {"name": "enabled", "type": "bool"},
                {"name": "count", "type": "int"},
                {"name": "ratio", "type": "float"},
                {"name": "label", "type": "String"},
                {"name": "tag", "type": "StringName"},
                {"name": "target", "type": "NodePath"},
            ],
        }
        data = _fake_data(classes=[OBJECT_CLASS, cls])
        source = render_classes_source(data, "v4_7_0")
        assert "enabled: bool" in source
        assert "count: int" in source
        assert "ratio: float" in source
        assert "label: str" in source
        assert "tag: str" in source
        assert "target: str" in source

    def test_unmodeled_property_type_falls_back_to_any(self):
        cls = {
            "name": "Thing",
            "inherits": "Object",
            "properties": [{"name": "stuff", "type": "SomeCommaHint,Union"}],
        }
        data = _fake_data(classes=[OBJECT_CLASS, cls])
        source = render_classes_source(data, "v4_7_0")
        assert "stuff: Any" in source
        assert "from typing import Any" in source

    def test_packed_array_of_primitive_element(self):
        cls = {
            "name": "Thing",
            "inherits": "Object",
            "properties": [{"name": "ids", "type": "PackedInt32Array"}],
        }
        data = _fake_data([PACKED_INT32_ARRAY_BUILTIN], [OBJECT_CLASS, cls])
        source = render_classes_source(data, "v4_7_0")
        assert "ids: List[int]" in source
        assert "from typing import List" in source

    def test_packed_array_of_modeled_builtin_element(self):
        cls = {
            "name": "ConcavePolygonShape2D",
            "inherits": "Object",
            "properties": [{"name": "segments", "type": "PackedVector2Array"}],
        }
        data = _fake_data(
            [VECTOR2_BUILTIN, PACKED_VECTOR2_ARRAY_BUILTIN], [OBJECT_CLASS, cls]
        )
        source = render_classes_source(data, "v4_7_0")
        assert "segments: List[Vector2v4_7_0]" in source
        assert "Vector2v4_7_0," in source  # imported from builtin_classes

    def test_typedarray_of_primitive_unwraps_to_list(self):
        cls = {
            "name": "Control",
            "inherits": "Object",
            "properties": [{"name": "targets", "type": "typedarray::NodePath"}],
        }
        data = _fake_data(classes=[OBJECT_CLASS, cls])
        source = render_classes_source(data, "v4_7_0")
        assert "targets: List[str]" in source

    def test_typedarray_of_packed_array_nests_two_lists(self):
        cls = {
            "name": "Thing",
            "inherits": "Object",
            "properties": [
                {"name": "polygons", "type": "typedarray::PackedVector2Array"}
            ],
        }
        data = _fake_data(
            [VECTOR2_BUILTIN, PACKED_VECTOR2_ARRAY_BUILTIN], [OBJECT_CLASS, cls]
        )
        source = render_classes_source(data, "v4_7_0")
        assert "polygons: List[List[Vector2v4_7_0]]" in source

    def test_packed_array_element_type_is_derived_not_hardcoded(self):
        # A synthetic Packed*Array whose element type doesn't match any real
        # Godot builtin, to prove this comes from `indexing_return_type` in
        # the data rather than a hardcoded name->element table.
        fake_packed = {"name": "PackedWidgetArray", "indexing_return_type": "bool"}
        cls = {
            "name": "Thing",
            "inherits": "Object",
            "properties": [{"name": "flags", "type": "PackedWidgetArray"}],
        }
        data = _fake_data([fake_packed], [OBJECT_CLASS, cls])
        source = render_classes_source(data, "v4_7_0")
        assert "flags: List[bool]" in source

    def test_typedarray_with_version_tag_prefix_extracts_trailing_name(self):
        # Real Godot quirk: "typedarray::24/17:CompositorEffect" -- the element
        # name is only the part after the last ':'.
        effect = {"name": "CompositorEffect", "inherits": "Resource"}
        resource = {"name": "Resource", "inherits": "Object"}
        cls = {
            "name": "Compositor",
            "inherits": "Object",
            "properties": [
                {
                    "name": "compositor_effects",
                    "type": "typedarray::24/17:CompositorEffect",
                }
            ],
        }
        data = _fake_data(classes=[OBJECT_CLASS, resource, effect, cls])
        source = render_classes_source(data, "v4_7_0")
        assert "compositor_effects: List[CompositorEffectv4_7_0]" in source

    def test_any_import_omitted_when_unused(self):
        data = _fake_data(classes=[OBJECT_CLASS, NODE_CLASS])
        source = render_classes_source(data, "v4_7_0")
        assert "from typing import Any" not in source

    def test_keyword_property_name_gets_safe_suffix(self):
        cls = {
            "name": "RayQuery",
            "inherits": "Object",
            "properties": [{"name": "from", "type": "float"}],
        }
        data = _fake_data(classes=[OBJECT_CLASS, cls])
        source = render_classes_source(data, "v4_7_0")
        assert "from_: float" in source
        assert "from: float" not in source

    def test_pydantic_reserved_name_gets_safe_suffix(self):
        cls = {
            "name": "Thing",
            "inherits": "Object",
            "properties": [{"name": "json", "type": "float"}],
        }
        data = _fake_data(classes=[OBJECT_CLASS, cls])
        source = render_classes_source(data, "v4_7_0")
        assert "json_: float" in source

    def test_no_properties_renders_pass_body(self):
        data = _fake_data(classes=[OBJECT_CLASS])
        source = render_classes_source(data, "v4_7_0")
        object_body = source.split("class Objectv4_7_0(BaseModel):")[1].split("class ")[
            0
        ]
        assert "pass" in object_body

    def test_unresolvable_hierarchy_raises(self):
        # 'inherits' pointing at a name that isn't itself a class in the data
        orphan = {"name": "Orphan", "inherits": "Nonexistent"}
        with pytest.raises(ValueError, match="Cannot resolve class hierarchy"):
            render_classes_source(_fake_data(classes=[orphan]), "v4_7_0")

    def test_version_label_is_embedded_in_model_names(self):
        data = _fake_data(classes=[OBJECT_CLASS, NODE_CLASS])
        source = render_classes_source(data, "v9_9_9")
        assert "class Objectv9_9_9(BaseModel):" in source
        assert "class Nodev9_9_9(Objectv9_9_9):" in source

    def test_generated_source_is_valid_importable_python(self, load_module):
        # No builtin_classes cross-import here, so this doesn't depend on
        # another generated package existing on disk.
        data = _fake_data(classes=[OBJECT_CLASS, NODE_CLASS, NODE2D_CLASS])
        # Swap the Vector2 property for a primitive so this stays import-isolated.
        node2d_primitive_only = {
            "name": "Node2D",
            "inherits": "Node",
            "properties": [{"name": "rotation", "type": "float"}],
        }
        data = _fake_data(classes=[OBJECT_CLASS, NODE_CLASS, node2d_primitive_only])
        source = render_classes_source(data, "v4_7_0")
        module = load_module(source)
        instance = module.Node2Dv4_7_0(name="n", rotation=1.5)
        assert instance.rotation == 1.5
        assert instance.name == "n"
        assert isinstance(instance, module.Nodev4_7_0)
        assert isinstance(instance, module.Objectv4_7_0)
