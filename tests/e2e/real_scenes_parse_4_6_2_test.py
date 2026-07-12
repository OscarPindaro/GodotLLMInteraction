"""E2e test: parse real .tscn files from the open-rpg 4.6.2 project.

These scenes are from gdquest-demos/godot-open-rpg at commit b70df69
("Update Godot version to 4.6.2"), MIT licensed. They are
real-world scenes with scripts, sub-resources, signals, and various node types.

The test verifies that our tscn parser can parse them without errors.
It does NOT verify Godot-level correctness (that would require running
the Godot binary with --check-only).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from godotllminteraction.tscn import load_scene

SCENES_DIR = Path(__file__).resolve().parents[1] / "data" / "scenes" / "open_rpg_4_6_2"

# (filename, expected_root_node_type, expected_ext_resource_count, expected_node_count)
SCENE_FIXTURES = [
    ("CombatAI.tscn", "Node2D", 1, 1),
    ("gamepiece.tscn", "Path2D", 1, 3),
    ("ScreenTransition.tscn", "CanvasLayer", 1, 2),
    ("Trigger.tscn", "Node2D", 1, 3),
    ("ui_damage_label.tscn", "Marker2D", 2, 2),
]


def _scene_path(name: str) -> Path:
    path = SCENES_DIR / name
    if not path.exists():
        pytest.skip(f"Scene fixture not found: {path}")
    return path


@pytest.mark.parametrize("filename,root_type,n_ext,n_nodes", SCENE_FIXTURES)
def test_parse_real_scene_without_errors(filename, root_type, n_ext, n_nodes):
    """Each real-world .tscn file should parse without raising ParseError."""
    scene = load_scene(_scene_path(filename))
    assert scene.header is not None
    assert len(scene.ext_resources) == n_ext
    assert len(scene.nodes) == n_nodes


@pytest.mark.parametrize("filename,root_type,n_ext,n_nodes", SCENE_FIXTURES)
def test_real_scene_root_node_type(filename, root_type, n_ext, n_nodes):
    """The root node should have the expected type."""
    scene = load_scene(_scene_path(filename))
    root = scene.nodes[0]
    assert root.parent is None
    assert root.type == root_type


def test_trigger_scene_has_signal_connections():
    """Trigger.tscn should have signal connections (area_entered, area_exited)."""
    scene = load_scene(_scene_path("Trigger.tscn"))
    assert len(scene.connections) == 2
    signals = {c.signal for c in scene.connections}
    assert "area_entered" in signals
    assert "area_exited" in signals


def test_trigger_scene_has_sub_resource():
    """Trigger.tscn should have a RectangleShape2D sub-resource."""
    scene = load_scene(_scene_path("Trigger.tscn"))
    assert len(scene.sub_resources) == 1
    sub = scene.sub_resources[0]
    assert sub.attributes.get("type").value == "RectangleShape2D"


def test_gamepiece_scene_has_node_hierarchy():
    """gamepiece.tscn should have a Path2D > PathFollow2D > RemoteTransform2D hierarchy."""
    scene = load_scene(_scene_path("gamepiece.tscn"))
    assert scene.nodes[0].type == "Path2D"
    assert scene.nodes[0].name == "Gamepiece"
    assert scene.nodes[1].type == "PathFollow2D"
    assert scene.nodes[1].name == "PathFollow2D"
    assert scene.nodes[2].type == "RemoteTransform2D"
    assert scene.nodes[2].name == "CameraAnchor"


def test_screen_transition_has_colorrect_child():
    """ScreenTransition.tscn should have a ColorRect child with a color property."""
    scene = load_scene(_scene_path("ScreenTransition.tscn"))
    color_rect = scene.nodes[1]
    assert color_rect.type == "ColorRect"
    assert "color" in color_rect.properties


def test_all_scenes_have_format_3():
    """All scenes should use format=3 (Godot 4.x)."""
    scene_files = sorted(SCENES_DIR.glob("*.tscn"))
    assert len(scene_files) >= 1, "No .tscn files found in fixtures directory"
    for path in scene_files:
        scene = load_scene(path)
        assert scene.header.attributes.get("format").value == 3, (
            f"{path.name} is not format=3"
        )


def test_all_scenes_have_uid():
    """All scenes should have a uid attribute (Godot 4.4+ feature)."""
    scene_files = sorted(SCENES_DIR.glob("*.tscn"))
    for path in scene_files:
        scene = load_scene(path)
        assert "uid" in scene.header.attributes, f"{path.name} has no uid"
