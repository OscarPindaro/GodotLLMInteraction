from __future__ import annotations

from pathlib import Path

import pytest

from godotllminteraction.tscn.parser import parse_scene
from godotllminteraction.tscn.specs import SpecProvider, default_provider
from godotllminteraction.tscn.validation import (
    validate_connection_signal,
    validate_node,
    validate_scene,
)

pytestmark = [pytest.mark.tscn]

_SCENES = Path(__file__).resolve().parents[2] / "tests" / "data" / "scenes"


def scene_from(text: str):
    return parse_scene(text)


def wrap(body: str) -> str:
    return f'[gd_scene format=3 uid="uid://test"]\n\n{body}\n'


class TestSpecProvider:
    def test_resolve_class_and_inheritance(self):
        provider = default_provider()
        node2d = provider.resolve_class("Node2D")
        assert node2d is not None
        assert provider.resolve_class("NotAClass") is None
        assert provider.is_subclass("Sprite2D", "Node2D") is True
        assert provider.is_subclass("Node2D", "Sprite2D") is False
        assert provider.is_subclass("Ghost", "Node2D") is None

    def test_resolve_builtin_and_scalar_width(self):
        provider = default_provider()
        vector2 = provider.resolve_builtin("Vector2")
        assert provider.scalar_width(vector2) == 2
        color = provider.resolve_builtin("Color")
        assert provider.scalar_width(color) == 4
        transform2d = provider.resolve_builtin("Transform2D")
        assert provider.scalar_width(transform2d) == 6

    def test_signals_include_inherited(self):
        provider = default_provider()
        signals = provider.signals_of("Area2D")
        assert "body_entered" in signals  # own
        assert "ready" in signals  # inherited from Node
        assert "script_changed" in signals  # inherited from Object

    def test_builtin_models_are_not_classes(self):
        # classes.py imports the builtin models; the provider must not
        # mistake them for engine classes.
        provider = default_provider()
        assert provider.resolve_class("Vector2") is None

    def test_version_agility_with_fake_module(self, load_module):
        source = "\n".join(
            [
                "from pydantic import BaseModel",
                "class Objectv9_9_9(BaseModel):",
                "    pass",
                "class Nodev9_9_9(Objectv9_9_9):",
                "    speed: float",
            ]
        )
        module = load_module(source)
        provider = SpecProvider(module, signals_table={"Node": {"ready": object()}})
        assert provider.resolve_class("Node") is module.Nodev9_9_9
        assert provider.is_subclass("Node", "Object") is True
        assert "ready" in provider.signals_of("Node")


class TestValidateNode:
    def test_valid_node_passes(self):
        scene = scene_from(
            wrap(
                '[node name="Root" type="Node2D"]\nposition = Vector2(1, 2)\nrotation = 0.5'
            )
        )
        report = validate_node(scene, scene.nodes[0])
        assert report.ok and not report.warnings

    def test_unknown_class_errors(self):
        scene = scene_from(wrap('[node name="Root" type="NotAClass"]'))
        report = validate_node(scene, scene.nodes[0])
        assert not report.ok
        assert "unknown class" in report.errors[0].message

    def test_unknown_property_errors(self):
        scene = scene_from(wrap('[node name="Root" type="Node2D"]\nwarp_factor = 9'))
        report = validate_node(scene, scene.nodes[0])
        assert not report.ok
        assert "warp_factor" in report.errors[0].message

    def test_unknown_property_with_script_warns(self):
        scene = scene_from(
            "[gd_scene format=3]\n\n"
            '[ext_resource type="Script" path="res://x.gd" id="1_x"]\n\n'
            '[node name="Root" type="Node2D"]\nscript = ExtResource("1_x")\nwarp_factor = 9\n'
        )
        report = validate_node(scene, scene.nodes[0])
        assert report.ok
        assert any("warp_factor" in w.message for w in report.warnings)

    def test_wrong_value_type_errors(self):
        scene = scene_from(wrap('[node name="Root" type="Node2D"]\nposition = 5'))
        report = validate_node(scene, scene.nodes[0])
        assert not report.ok
        assert "Vector2" in report.errors[0].message

    def test_builtin_arity_checked(self):
        scene = scene_from(
            wrap('[node name="Root" type="Node2D"]\nposition = Vector2(1, 2, 3)')
        )
        report = validate_node(scene, scene.nodes[0])
        assert not report.ok
        assert "2 scalar arguments" in report.errors[0].message

    def test_int_accepted_where_float_expected(self):
        scene = scene_from(wrap('[node name="Root" type="Node2D"]\nrotation = 1'))
        assert validate_node(scene, scene.nodes[0]).ok

    def test_metadata_keys_accepted(self):
        scene = scene_from(wrap('[node name="Root" type="Node2D"]\nmetadata/foo = 42'))
        report = validate_node(scene, scene.nodes[0])
        assert report.ok and not report.warnings

    def test_packed_array_divisibility(self):
        good = scene_from(
            wrap(
                '[node name="Root" type="CollisionPolygon2D"]\npolygon = PackedVector2Array(1, 2, 3, 4)'
            )
        )
        assert validate_node(good, good.nodes[0]).ok
        bad = scene_from(
            wrap(
                '[node name="Root" type="CollisionPolygon2D"]\npolygon = PackedVector2Array(1, 2, 3)'
            )
        )
        report = validate_node(bad, bad.nodes[0])
        assert not report.ok
        assert "multiple of the element width 2" in report.errors[0].message

    def test_resource_ref_must_resolve(self):
        scene = scene_from(
            wrap(
                '[node name="Root" type="Sprite2D"]\ntexture = ExtResource("1_missing")'
            )
        )
        report = validate_node(scene, scene.nodes[0])
        assert not report.ok
        assert "does not match any" in report.errors[0].message

    def test_resource_ref_subclass_checked(self):
        scene = scene_from(
            "[gd_scene format=3]\n\n"
            '[ext_resource type="AudioStream" path="res://a.ogg" id="1_a"]\n\n'
            '[node name="Root" type="Sprite2D"]\ntexture = ExtResource("1_a")\n'
        )
        report = validate_node(scene, scene.nodes[0])
        assert not report.ok
        assert "not a Texture2D" in report.errors[0].message

    def test_instance_node_skips_class_checks(self):
        scene = scene_from(
            "[gd_scene format=3]\n\n"
            '[ext_resource type="PackedScene" path="res://c.tscn" id="1_c"]\n\n'
            '[node name="Root" type="Node2D"]\n\n'
            '[node name="Child" parent="." instance=ExtResource("1_c")]\nanything_at_all = 7\n'
        )
        assert validate_node(scene, scene.nodes[1]).ok


class TestValidateConnections:
    def test_known_signal_passes(self):
        scene = scene_from(wrap('[node name="Root" type="Area2D"]'))
        assert validate_connection_signal(scene, ".", "body_entered").ok

    def test_inherited_signal_passes(self):
        scene = scene_from(wrap('[node name="Root" type="Area2D"]'))
        assert validate_connection_signal(scene, ".", "ready").ok

    def test_unknown_signal_errors(self):
        scene = scene_from(wrap('[node name="Root" type="Area2D"]'))
        report = validate_connection_signal(scene, ".", "does_not_exist")
        assert not report.ok
        assert "has no signal" in report.errors[0].message

    def test_unknown_signal_with_script_warns(self):
        scene = scene_from(
            "[gd_scene format=3]\n\n"
            '[ext_resource type="Script" path="res://x.gd" id="1_x"]\n\n'
            '[node name="Root" type="Area2D"]\nscript = ExtResource("1_x")\n'
        )
        report = validate_connection_signal(scene, ".", "my_custom_signal")
        assert report.ok
        assert report.warnings

    def test_missing_source_errors(self):
        scene = scene_from(wrap('[node name="Root" type="Node2D"]'))
        assert not validate_connection_signal(scene, "Ghost", "ready").ok


class TestValidateScene:
    @pytest.mark.parametrize(
        "fixture",
        [
            "sprite_frames.tscn",
            "connections.tscn",
            "ui_and_paths.tscn",
            "instances.tscn",
        ],
    )
    def test_fixtures_validate_clean(self, fixture):
        scene = parse_scene((_SCENES / fixture).read_text())
        report = validate_scene(scene)
        assert report.ok, [str(e) for e in report.errors]

    def test_duplicate_sibling_names_error(self):
        scene = scene_from(
            wrap(
                '[node name="Root" type="Node2D"]\n\n'
                '[node name="A" type="Node2D" parent="."]\n\n'
                '[node name="A" type="Node2D" parent="."]'
            )
        )
        report = validate_scene(scene)
        assert any("duplicate node name" in e.message for e in report.errors)

    def test_missing_parent_errors(self):
        scene = scene_from(
            wrap(
                '[node name="Root" type="Node2D"]\n\n'
                '[node name="A" type="Node2D" parent="Ghost"]'
            )
        )
        report = validate_scene(scene)
        assert any("does not exist" in e.message for e in report.errors)

    def test_two_roots_error(self):
        scene = scene_from(
            wrap(
                '[node name="Root" type="Node2D"]\n\n[node name="Root2" type="Node2D"]'
            )
        )
        report = validate_scene(scene)
        assert any("exactly one root" in e.message for e in report.errors)

    def test_invalid_sub_resource_class(self):
        scene = scene_from(
            "[gd_scene format=3]\n\n"
            '[sub_resource type="Node2D" id="Node2D_x"]\n\n'
            '[node name="Root" type="Node2D"]\n'
        )
        report = validate_scene(scene)
        assert any("not a Resource subclass" in e.message for e in report.errors)
