from __future__ import annotations


import pytest

from godotllminteraction.mcp.tools.specs import _annotation_to_godot_type
from godotllminteraction.tscn.specs import default_provider

pytestmark = [pytest.mark.tscn]


def _spec_json(class_name: str) -> dict:
    """Call the internal spec-building logic and return parsed JSON."""
    from godotllminteraction.mcp.tools.specs import _provider_for_version

    provider = _provider_for_version(None)
    model = provider.resolve_class(class_name)
    assert model is not None, f"Unknown class: {class_name}"

    properties: list[dict] = []
    for name, field in model.model_fields.items():
        type_str = _annotation_to_godot_type(provider, field.annotation)
        properties.append(
            {"name": name, "type": type_str, "description": field.description or ""}
        )

    signals = provider.signals_of(class_name) or {}
    signals_list = [
        {
            "name": sig_name,
            "info": str(sig_info),
            "arguments": [
                {"name": arg.name, "type": arg.type} for arg in sig_info.arguments
            ],
        }
        for sig_name, sig_info in signals.items()
    ]

    inheritance: list[str] = []
    for base in model.__mro__:
        godot_name = provider.godot_name_of(base)
        if godot_name is not None:
            inheritance.append(godot_name)
    inheritance.reverse()

    return {
        "ok": True,
        "class": class_name,
        "properties": properties,
        "signals": signals_list,
        "inheritance": inheritance,
    }


def _prop(spec: dict, name: str) -> dict:
    props = {p["name"]: p for p in spec["properties"]}
    return props[name]


def _signal(spec: dict, name: str) -> dict:
    sigs = {s["name"]: s for s in spec["signals"]}
    return sigs[name]


class TestAnnotationToGodotType:
    def test_resolved_class_model(self):
        provider = default_provider()
        model = provider.resolve_class("Sprite2D")
        owner_field = model.model_fields["owner"]
        assert _annotation_to_godot_type(provider, owner_field.annotation) == "Node"

    def test_resolved_builtin_model(self):
        provider = default_provider()
        model = provider.resolve_class("Sprite2D")
        modulate_field = model.model_fields["modulate"]
        assert _annotation_to_godot_type(provider, modulate_field.annotation) == "Color"

    def test_forward_ref(self):
        provider = default_provider()
        model = provider.resolve_class("Sprite2D")
        texture_field = model.model_fields["texture"]
        assert (
            _annotation_to_godot_type(provider, texture_field.annotation) == "Texture2D"
        )

    def test_primitive_bool(self):
        provider = default_provider()
        model = provider.resolve_class("Sprite2D")
        centered_field = model.model_fields["centered"]
        assert _annotation_to_godot_type(provider, centered_field.annotation) == "bool"

    def test_primitive_int(self):
        provider = default_provider()
        model = provider.resolve_class("Sprite2D")
        hframes_field = model.model_fields["hframes"]
        assert _annotation_to_godot_type(provider, hframes_field.annotation) == "int"

    def test_primitive_float(self):
        provider = default_provider()
        model = provider.resolve_class("Sprite2D")
        rotation_field = model.model_fields["rotation"]
        assert _annotation_to_godot_type(provider, rotation_field.annotation) == "float"

    def test_any_maps_to_variant(self):
        provider = default_provider()
        model = provider.resolve_class("Sprite2D")
        material_field = model.model_fields["material"]
        assert (
            _annotation_to_godot_type(provider, material_field.annotation) == "Variant"
        )

    def test_str_maps_to_string(self):
        provider = default_provider()
        model = provider.resolve_class("Node")
        name_field = model.model_fields["name"]
        assert _annotation_to_godot_type(provider, name_field.annotation) == "String"

    def test_list_of_builtins(self):
        provider = default_provider()
        model = provider.resolve_class("Gradient")
        colors_field = model.model_fields["colors"]
        assert (
            _annotation_to_godot_type(provider, colors_field.annotation)
            == "Array[Color]"
        )

    def test_list_of_primitives(self):
        provider = default_provider()
        model = provider.resolve_class("Gradient")
        offsets_field = model.model_fields["offsets"]
        assert (
            _annotation_to_godot_type(provider, offsets_field.annotation)
            == "Array[float]"
        )

    def test_list_of_any(self):
        provider = default_provider()
        model = provider.resolve_class("PhysicsPointQueryParameters2D")
        exclude_field = model.model_fields["exclude"]
        assert (
            _annotation_to_godot_type(provider, exclude_field.annotation)
            == "Array[Variant]"
        )


class TestSpecOutput:
    def test_sprite2d_property_types(self):
        spec = _spec_json("Sprite2D")
        assert _prop(spec, "texture")["type"] == "Texture2D"
        assert _prop(spec, "modulate")["type"] == "Color"
        assert _prop(spec, "owner")["type"] == "Node"
        assert _prop(spec, "centered")["type"] == "bool"
        assert _prop(spec, "material")["type"] == "Variant"
        assert _prop(spec, "position")["type"] == "Vector2"
        assert _prop(spec, "hframes")["type"] == "int"
        assert _prop(spec, "rotation")["type"] == "float"

    def test_sprite2d_inheritance(self):
        spec = _spec_json("Sprite2D")
        assert spec["inheritance"] == [
            "Object",
            "Node",
            "CanvasItem",
            "Node2D",
            "Sprite2D",
        ]

    def test_signal_has_info_and_arguments(self):
        spec = _spec_json("Sprite2D")
        frame_changed = _signal(spec, "frame_changed")
        assert "info" in frame_changed
        assert frame_changed["arguments"] == []

    def test_signal_with_arguments(self):
        spec = _spec_json("Sprite2D")
        child_entered = _signal(spec, "child_entered_tree")
        assert "info" in child_entered
        assert child_entered["arguments"] == [{"name": "node", "type": "Node"}]

    def test_no_python_class_names_in_output(self):
        """Property types must be Godot names, not Python class reprs."""
        spec = _spec_json("Sprite2D")
        for prop in spec["properties"]:
            type_str = prop["type"]
            assert "<class" not in type_str, f"Python class repr in {prop['name']}"
            assert "ForwardRef" not in type_str, f"ForwardRef in {prop['name']}"
            assert "v4_7_0" not in type_str, f"Version suffix in {prop['name']}"
