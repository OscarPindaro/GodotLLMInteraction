from __future__ import annotations

from pathlib import Path

from godotllminteraction.tscn.parser import parse_scene
from godotllminteraction.tscn.tree import build_tree, render_tree

_SCENES = Path(__file__).resolve().parents[2] / "tests" / "data" / "scenes"


def load(fixture: str):
    return parse_scene((_SCENES / fixture).read_text())


class TestBuildTree:
    def test_nodes_detail(self):
        tree = build_tree(load("sprite_frames.tscn"), "nodes")
        assert tree.name == "Actor"
        assert tree.type == "Node2D"
        assert [c.name for c in tree.children] == [
            "AnimatedSprite2D",
            "CollisionPolygon2D",
        ]
        assert tree.children[0].resources == []
        assert tree.children[0].properties == {}

    def test_resources_detail(self):
        tree = build_tree(load("sprite_frames.tscn"), "resources")
        sprite = tree.children[0]
        refs = {r.property: r for r in sprite.resources}
        assert refs["sprite_frames"].kind == "sub_resource"
        assert refs["sprite_frames"].type == "SpriteFrames"
        assert sprite.properties == {}

    def test_properties_detail(self):
        tree = build_tree(load("sprite_frames.tscn"), "properties")
        sprite = tree.children[0]
        assert sprite.properties["autoplay"] == '"default"'

    def test_ext_resource_ref_resolves_path(self):
        tree = build_tree(load("ui_and_paths.tscn"), "resources")
        icon = next(c for c in tree.children[0].children if c.name == "Icon")
        texture_ref = next(r for r in icon.resources if r.property == "texture")
        assert texture_ref.kind == "ext_resource"
        assert texture_ref.path == "res://tests/data/assets/icon.png"

    def test_instance_nodes_flagged(self):
        tree = build_tree(load("instances.tscn"), "resources")
        actor = next(c for c in tree.children if c.name == "Actor")
        assert actor.instance
        instance_ref = next(r for r in actor.resources if r.property == "instance")
        assert instance_ref.path == "res://tests/data/scenes/sprite_frames.tscn"

    def test_empty_scene_returns_none(self):
        from godotllminteraction.tscn.scene import Scene

        assert build_tree(Scene(), "nodes") is None

    def test_json_serializable(self):
        tree = build_tree(load("sprite_frames.tscn"), "properties")
        data = tree.model_dump()
        assert data["children"][0]["name"] == "AnimatedSprite2D"


class TestRenderTree:
    def test_plain_text_shape(self):
        text = render_tree(build_tree(load("sprite_frames.tscn"), "nodes"))
        lines = text.splitlines()
        assert lines[0] == "Actor (Node2D)"
        assert "├─ AnimatedSprite2D (AnimatedSprite2D)" in lines[1]
        assert "└─ CollisionPolygon2D (CollisionPolygon2D)" in lines[2]

    def test_instance_label(self):
        text = render_tree(build_tree(load("instances.tscn"), "nodes"))
        assert "Actor (instance)" in text

    def test_properties_shown(self):
        text = render_tree(build_tree(load("sprite_frames.tscn"), "properties"))
        assert 'autoplay = "default"' in text
