"""Unit tests for the scene_builder module (parse_tree, parse_json, build_scene)."""

from __future__ import annotations

from pathlib import Path

import pytest

from godotllminteraction.tscn import (
    NodeSpec,
    SceneBuilderError,
    build_scene,
    dump_scene,
    parse_json,
    parse_scene,
    parse_tree,
)
from godotllminteraction.tscn.class_cache import ClassResolver


# ============================================================ Tree format parsing
# ---------------------------------------------------------- box-drawing chars


def test_tree_box_drawing_basic() -> None:
    text = "Root (Node2D)\n├── Child1 (Sprite2D)\n└── Child2 (Label)\n"
    root = parse_tree(text)
    assert root.name == "Root"
    assert root.type == "Node2D"
    assert len(root.children) == 2
    assert root.children[0].name == "Child1"
    assert root.children[0].type == "Sprite2D"
    assert root.children[1].name == "Child2"
    assert root.children[1].type == "Label"


def test_tree_box_drawing_nested() -> None:
    text = (
        "Root (Node2D)\n"
        "├── Child1 (Node2D)\n"
        "│   ├── GrandChild (Sprite2D)\n"
        "│   └── GrandChild2 (Label)\n"
        "└── Child2 (Camera2D)\n"
    )
    root = parse_tree(text)
    assert len(root.children) == 2
    assert len(root.children[0].children) == 2
    assert root.children[0].children[0].name == "GrandChild"
    assert root.children[0].children[1].name == "GrandChild2"
    assert root.children[1].name == "Child2"


# ---------------------------------------------------------- ASCII chars


def test_tree_ascii_pipe_dash() -> None:
    text = "Root (Node2D)\n|-- Child1 (Sprite2D)\n`-- Child2 (Label)\n"
    root = parse_tree(text)
    assert root.name == "Root"
    assert len(root.children) == 2
    assert root.children[0].name == "Child1"
    assert root.children[1].name == "Child2"


def test_tree_ascii_dash_prefix() -> None:
    text = "Root (Node2D)\n-- Child1 (Sprite2D)\n---- GrandChild (Label)\n"
    root = parse_tree(text)
    assert len(root.children) == 1
    assert root.children[0].name == "Child1"
    assert len(root.children[0].children) == 1
    assert root.children[0].children[0].name == "GrandChild"


def test_tree_ascii_underscore_prefix() -> None:
    text = "Root (Node2D)\n__ Child1 (Sprite2D)\n____ GrandChild (Label)\n"
    root = parse_tree(text)
    assert len(root.children) == 1
    assert root.children[0].name == "Child1"
    assert len(root.children[0].children) == 1
    assert root.children[0].children[0].name == "GrandChild"


def test_tree_mixed_ascii_and_box_drawing() -> None:
    text = "Root (Node2D)\n|-- Child1 (Node2D)\n│   ├── GrandChild (Sprite2D)\n│   └── GrandChild2 (Label)\n`-- Child2 (Camera2D)\n"
    root = parse_tree(text)
    assert len(root.children) == 2
    assert root.children[0].name == "Child1"
    assert len(root.children[0].children) == 2
    assert root.children[1].name == "Child2"


# ---------------------------------------------------------- edge cases


def test_tree_root_no_prefix() -> None:
    root = parse_tree("Root (Node2D)\n")
    assert root.name == "Root"
    assert root.type == "Node2D"
    assert root.children == []


def test_tree_node_no_type() -> None:
    root = parse_tree("Root\n")
    assert root.name == "Root"
    assert root.type is None


def test_tree_node_type_only_no_props() -> None:
    root = parse_tree("Root (Sprite2D)\n")
    assert root.name == "Root"
    assert root.type == "Sprite2D"
    assert root.properties == {}


def test_tree_node_with_properties() -> None:
    root = parse_tree("Name (Sprite2D) [position: Vector2(1, 2)]\n")
    assert root.name == "Name"
    assert root.properties == {"position": "Vector2(1, 2)"}


def test_tree_node_with_unique_keyword() -> None:
    root = parse_tree("Name (Node2D) [unique]\n")
    assert root.unique is True
    assert root.properties == {}


def test_tree_node_with_properties_and_unique() -> None:
    root = parse_tree("Name (Node2D) [position: Vector2(0, 0), unique]\n")
    assert root.unique is True
    assert root.properties == {"position": "Vector2(0, 0)"}


def test_tree_empty_raises() -> None:
    with pytest.raises(Exception, match="Empty tree"):
        parse_tree("")


def test_tree_invalid_line_raises() -> None:
    with pytest.raises(Exception, match="no parent"):
        parse_tree("Root (Node2D)\n!!!bad\n")


def test_tree_dfs_structure_irregular_indentation() -> None:
    """Parser correctly handles irregular ASCII indentation depths.

    The stack-based parser uses absolute prefix length as depth and pops
    until it finds a parent with strictly less depth. This means relative
    nesting is inferred correctly regardless of the actual prefix lengths.
    """
    tree = (
        "parent (Node2D)\n"
        "├── node1 (Sprite2D)\n"
        "│   └── node2 (Label)\n"
        "│       └── node3 (Camera2D)\n"
        "├── node4 (Node2D)\n"
        "│   └── node5 (Node2D)\n"
    )
    root = parse_tree(tree)
    assert root.name == "parent"
    assert len(root.children) == 2
    # node1 is first child of parent
    n1 = root.children[0]
    assert n1.name == "node1"
    assert len(n1.children) == 1
    # node2 is child of node1, node3 is child of node2
    n2 = n1.children[0]
    assert n2.name == "node2"
    assert len(n2.children) == 1
    assert n2.children[0].name == "node3"
    assert n2.children[0].children == []
    # node4 is second child of parent, has child node5
    n4 = root.children[1]
    assert n4.name == "node4"
    assert len(n4.children) == 1
    assert n4.children[0].name == "node5"
    assert n4.children[0].children == []


def test_tree_dfs_build_scene_emits_correct_parents() -> None:
    """build_scene DFS pre-order produces correct parent paths."""
    tree = (
        "parent (Node2D)\n"
        "├── node1 (Sprite2D)\n"
        "│   └── node2 (Label)\n"
        "│       └── node3 (Camera2D)\n"
        "├── node4 (Node2D)\n"
        "│   └── node5 (Node2D)\n"
    )
    root = parse_tree(tree)
    scene = build_scene(root)
    text = dump_scene(scene)
    # Root has no parent
    assert '[node name="parent" type="Node2D"]' in text
    # node1 is child of root
    assert '[node name="node1" type="Sprite2D" parent="."]' in text
    # node2 is child of node1
    assert '[node name="node2" type="Label" parent="node1"]' in text
    # node3 is child of node1/node2
    assert '[node name="node3" type="Camera2D" parent="node1/node2"]' in text
    # node4 is child of root (sibling of node1, not child of node3!)
    assert '[node name="node4" type="Node2D" parent="."]' in text
    # node5 is child of node4
    assert '[node name="node5" type="Node2D" parent="node4"]' in text


# ============================================================ JSON format parsing


def test_json_nested_structure() -> None:
    data = {
        "root": {
            "name": "Root",
            "type": "Node2D",
            "children": [
                {"name": "Child", "type": "Sprite2D", "properties": {}},
            ],
        }
    }
    root = parse_json(data)
    assert root.name == "Root"
    assert root.type == "Node2D"
    assert len(root.children) == 1
    assert root.children[0].name == "Child"


def test_json_unique_field() -> None:
    data = {"name": "Root", "type": "Node2D", "unique": True}
    root = parse_json(data)
    assert root.unique is True


def test_json_type_null() -> None:
    data = {"name": "Root", "type": None}
    root = parse_json(data)
    assert root.type is None


# ============================================================ build_scene


def test_build_scene_builtin_types() -> None:
    spec = NodeSpec(
        name="Root",
        type="Node2D",
        children=[
            NodeSpec(name="Sprite", type="Sprite2D"),
            NodeSpec(name="Label", type="Label"),
        ],
    )
    scene = build_scene(spec)
    text = dump_scene(scene)
    assert '[node name="Root" type="Node2D"]' in text
    assert '[node name="Sprite" type="Sprite2D" parent="."]' in text
    assert '[node name="Label" type="Label" parent="."]' in text


def test_build_scene_unique_node() -> None:
    spec = NodeSpec(
        name="Root",
        type="Node2D",
        children=[
            NodeSpec(name="Player", type="CharacterBody2D", unique=True),
        ],
    )
    scene = build_scene(spec)
    text = dump_scene(scene)
    assert "unique_name_in_owner = true" in text


def test_build_scene_unique_root() -> None:
    spec = NodeSpec(name="Root", type="Node2D", unique=True)
    scene = build_scene(spec)
    text = dump_scene(scene)
    assert "unique_name_in_owner = true" in text


def test_build_scene_with_class_name(tmp_path: Path) -> None:
    (tmp_path / "gamepiece.gd").write_text(
        "class_name Gamepiece extends Path2D\n", encoding="utf-8"
    )
    resolver = ClassResolver(tmp_path)
    spec = NodeSpec(name="GP", type="Gamepiece")
    scene = build_scene(spec, class_resolver=resolver)
    text = dump_scene(scene)
    assert '[node name="GP" type="Path2D"]' in text
    assert "res://gamepiece.gd" in text
    assert "Script" in text


def test_build_scene_class_name_with_children(tmp_path: Path) -> None:
    (tmp_path / "gamepiece.gd").write_text(
        "class_name Gamepiece extends Path2D\n", encoding="utf-8"
    )
    resolver = ClassResolver(tmp_path)
    spec = NodeSpec(
        name="GP",
        type="Gamepiece",
        children=[
            NodeSpec(name="Follow", type="PathFollow2D"),
        ],
    )
    scene = build_scene(spec, class_resolver=resolver)
    text = dump_scene(scene)
    assert 'type="Path2D"' in text
    assert 'type="PathFollow2D" parent="."' in text


def test_build_scene_class_name_deleted_errors(tmp_path: Path) -> None:
    """If a .gd file is deleted after caching, build_scene errors clearly."""
    gd = tmp_path / "gamepiece.gd"
    gd.write_text("class_name Gamepiece extends Path2D\n", encoding="utf-8")
    resolver = ClassResolver(tmp_path)
    # Trigger initial scan.
    assert resolver.resolve("Gamepiece") is not None
    # Delete the file.
    gd.unlink()
    # Rescan on miss (ask for a different class) drops the deleted class.
    assert resolver.resolve("SomeOther") is None
    # Now Gamepiece is gone from the cache too.
    assert resolver.resolve("Gamepiece") is None
    # build_scene should error.
    spec = NodeSpec(name="GP", type="Gamepiece")
    with pytest.raises((SceneBuilderError, Exception)):
        build_scene(spec, class_resolver=resolver)


def test_build_scene_idempotent() -> None:
    spec = NodeSpec(
        name="Root",
        type="Node2D",
        children=[NodeSpec(name="Child", type="Sprite2D")],
    )
    scene1 = build_scene(spec)
    scene2 = build_scene(spec)
    assert dump_scene(scene1) == dump_scene(scene2)


def test_build_scene_roundtrip_stable() -> None:
    spec = NodeSpec(
        name="Root",
        type="Node2D",
        children=[NodeSpec(name="Child", type="Label")],
    )
    scene = build_scene(spec)
    text1 = dump_scene(scene)
    # Parse it back and re-dump.
    scene2 = parse_scene(text1)
    text2 = dump_scene(scene2)
    assert text1 == text2


def test_build_scene_error_unknown_type_no_script() -> None:
    spec = NodeSpec(name="X", type="NonExistentClass")
    with pytest.raises((SceneBuilderError, Exception)):
        build_scene(spec)


def test_build_scene_error_no_type_no_script() -> None:
    spec = NodeSpec(name="X")
    with pytest.raises((SceneBuilderError, Exception)):
        build_scene(spec)


def test_build_scene_nested_paths() -> None:
    spec = NodeSpec(
        name="Root",
        type="Node2D",
        children=[
            NodeSpec(
                name="Mid",
                type="Node2D",
                children=[NodeSpec(name="Leaf", type="Sprite2D")],
            ),
        ],
    )
    scene = build_scene(spec)
    text = dump_scene(scene)
    assert 'parent="."' in text  # Mid is child of root
    assert 'parent="Mid"' in text  # Leaf is child of Mid


def test_build_scene_with_properties() -> None:
    spec = NodeSpec(
        name="Root",
        type="Node2D",
        properties={"position": "Vector2(100, 200)"},
    )
    scene = build_scene(spec)
    text = dump_scene(scene)
    assert "position = Vector2(100, 200)" in text


def test_build_scene_script_only_no_type(tmp_path: Path) -> None:
    """A node with script but no type should default to Node base."""
    (tmp_path / "custom.gd").write_text(
        "extends Node\nclass_name Custom\n", encoding="utf-8"
    )
    spec = NodeSpec(name="X", script="res://custom.gd")
    scene = build_scene(spec)
    text = dump_scene(scene)
    assert 'type="Node"' in text
    assert "res://custom.gd" in text
