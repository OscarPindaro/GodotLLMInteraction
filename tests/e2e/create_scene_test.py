"""E2e tests for create_scene: build scenes and validate with Godot --check-only.

Uses the existing tests/data/scenes/open_rpg_4_7_0/ fixture project which has
project.godot + class_name scripts (e.g. gamepiece.gd with
``class_name Gamepiece extends Path2D``).

Tests skip automatically if the Godot 4.7.0 binary is not installed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from godotllminteraction.tscn import (
    ClassResolver,
    build_scene,
    dump_scene,
    parse_json,
    parse_tree,
)
from tests.e2e._helpers import check_scene, godot_binary_path

pytestmark = [pytest.mark.tscn]

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "data" / "scenes" / "open_rpg_4_7_0"

_MINIMAL_PROJECT_GODOT = """config_version=5

[application]
config/name="test"
"""


def _skip_if_no_godot():
    binary = godot_binary_path("4.7.0")
    if binary is None:
        pytest.skip("Godot 4.7.0 binary not installed")
    return binary


def _ensure_project(project_dir: Path) -> None:
    """Create a minimal project.godot if none exists (prevents project manager pop-ups)."""
    pg = project_dir / "project.godot"
    if not pg.exists():
        pg.write_text(_MINIMAL_PROJECT_GODOT, encoding="utf-8")


# ---------------------------------------------------------- Test 1: built-in types


def test_create_simple_scene_builtin_types(tmp_path: Path) -> None:
    """Simple scene with only built-in Godot types."""
    binary = _skip_if_no_godot()
    _ensure_project(tmp_path)

    tree = "Root (Node2D)\n├── Sprite (Sprite2D)\n└── Label (Label)\n"
    spec = parse_tree(tree)
    scene = build_scene(spec)
    out = tmp_path / "test_simple.tscn"
    out.write_text(dump_scene(scene))

    result = check_scene(binary, tmp_path, out.name)
    assert result.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------- Test 2: class_name


def test_create_scene_with_class_name(tmp_path: Path) -> None:
    """Scene using a user-defined class_name (Gamepiece → Path2D + script)."""
    binary = _skip_if_no_godot()

    # Copy the fixture project to tmp_path so we can write into it.
    project = tmp_path / "project"
    shutil.copytree(FIXTURE_DIR, project)

    tree = "GP (Gamepiece)\n"
    spec = parse_tree(tree)
    resolver = ClassResolver(project)
    scene = build_scene(spec, class_resolver=resolver)
    out = project / "test_class_name.tscn"
    out.write_text(dump_scene(scene))

    text = out.read_text()
    assert "res://gamepiece.gd" in text
    assert 'type="Path2D"' in text

    result = check_scene(binary, project, out.name)
    assert result.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------- Test 3: nested class_name + children


def test_create_nested_scene_class_name_and_children(tmp_path: Path) -> None:
    """Nested scene: class_name root + built-in children."""
    binary = _skip_if_no_godot()

    project = tmp_path / "project"
    shutil.copytree(FIXTURE_DIR, project)

    tree = (
        "GP (Gamepiece)\n"
        "└── Follow (PathFollow2D)\n"
        "    └── CameraAnchor (RemoteTransform2D)\n"
    )
    spec = parse_tree(tree)
    resolver = ClassResolver(project)
    scene = build_scene(spec, class_resolver=resolver)
    out = project / "test_nested.tscn"
    out.write_text(dump_scene(scene))

    text = out.read_text()
    assert 'type="Path2D"' in text
    assert 'type="PathFollow2D" parent="."' in text
    assert 'type="RemoteTransform2D" parent="Follow"' in text

    result = check_scene(binary, project, out.name)
    assert result.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------- Test 4: unique nodes


def test_create_scene_with_unique_nodes(tmp_path: Path) -> None:
    """Scene with a unique node (unique_name_in_owner = true)."""
    binary = _skip_if_no_godot()
    _ensure_project(tmp_path)

    tree = "Root (Node2D)\n└── Player (CharacterBody2D) [unique]\n"
    spec = parse_tree(tree)
    scene = build_scene(spec)
    out = tmp_path / "test_unique.tscn"
    out.write_text(dump_scene(scene))

    text = out.read_text()
    assert "unique_name_in_owner = true" in text

    result = check_scene(binary, tmp_path, out.name)
    assert result.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------- Test 5: JSON format


def test_create_scene_json_format(tmp_path: Path) -> None:
    """JSON input produces the same result as tree format for the same structure."""
    binary = _skip_if_no_godot()
    _ensure_project(tmp_path)

    data = {
        "root": {
            "name": "Root",
            "type": "Node2D",
            "children": [
                {"name": "Sprite", "type": "Sprite2D", "properties": {}},
                {"name": "Label", "type": "Label", "properties": {}},
            ],
        }
    }
    spec = parse_json(data)
    scene = build_scene(spec)
    out = tmp_path / "test_json.tscn"
    out.write_text(dump_scene(scene))

    result = check_scene(binary, tmp_path, out.name)
    assert result.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Verify it matches tree format output for the same structure.
    tree_spec = parse_tree("Root (Node2D)\n├── Sprite (Sprite2D)\n└── Label (Label)\n")
    tree_scene = build_scene(tree_spec)
    assert dump_scene(scene) == dump_scene(tree_scene)


# ---------------------------------------------------------- Test 6: ASCII tree


def test_create_scene_ascii_tree(tmp_path: Path) -> None:
    """ASCII tree characters (|, -, `) produce valid scenes too."""
    binary = _skip_if_no_godot()
    _ensure_project(tmp_path)

    tree = "Root (Node2D)\n|-- Sprite (Sprite2D)\n`-- Label (Label)\n"
    spec = parse_tree(tree)
    scene = build_scene(spec)
    out = tmp_path / "test_ascii.tscn"
    out.write_text(dump_scene(scene))

    result = check_scene(binary, tmp_path, out.name)
    assert result.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------- Test 7: properties


def test_create_scene_with_properties(tmp_path: Path) -> None:
    """Scene with property values passes Godot validation."""
    binary = _skip_if_no_godot()
    _ensure_project(tmp_path)

    tree = (
        "Root (Node2D)\n"
        "└── Label (Label)\n"
        '    [text: "Hello", position: Vector2(10, 20)]\n'
    )
    spec = parse_tree(tree)
    scene = build_scene(spec)
    out = tmp_path / "test_props.tscn"
    out.write_text(dump_scene(scene))

    text = out.read_text()
    assert 'text = "Hello"' in text
    assert "position = Vector2(10, 20)" in text

    result = check_scene(binary, tmp_path, out.name)
    assert result.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------- DFS structure tests


def test_dfs_box_drawing_tree_valid_godot(tmp_path: Path) -> None:
    """DFS example with box-drawing chars produces a valid Godot scene.

    parent → node1 → node2 → node3
    parent → node4 → node5
    """
    binary = _skip_if_no_godot()
    _ensure_project(tmp_path)

    tree = (
        "parent (Node2D)\n"
        "├── node1 (Sprite2D)\n"
        "│   └── node2 (Label)\n"
        "│       └── node3 (Camera2D)\n"
        "├── node4 (Node2D)\n"
        "│   └── node5 (Node2D)\n"
    )
    spec = parse_tree(tree)
    scene = build_scene(spec)
    out = tmp_path / "dfs_box.tscn"
    out.write_text(dump_scene(scene))

    text = out.read_text()
    assert '[node name="node4" type="Node2D" parent="."]' in text
    assert '[node name="node5" type="Node2D" parent="node4"]' in text

    result = check_scene(binary, tmp_path, out.name)
    assert result.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_dfs_ascii_tree_valid_godot(tmp_path: Path) -> None:
    """DFS example with ASCII chars produces a valid Godot scene."""
    binary = _skip_if_no_godot()
    _ensure_project(tmp_path)

    tree = (
        "parent (Node2D)\n"
        "|-- node1 (Sprite2D)\n"
        "|   `-- node2 (Label)\n"
        "|       `-- node3 (Camera2D)\n"
        "|-- node4 (Node2D)\n"
        "|   `-- node5 (Node2D)\n"
    )
    spec = parse_tree(tree)
    scene = build_scene(spec)
    out = tmp_path / "dfs_ascii.tscn"
    out.write_text(dump_scene(scene))

    result = check_scene(binary, tmp_path, out.name)
    assert result.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ============================================================ CLI e2e tests


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run gli tscn create-scene via the CLI."""
    return subprocess.run(
        ["uv", "run", "gli", "tscn", "create-scene", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cli_create_scene_tree_file(tmp_path: Path) -> None:
    """CLI: --tree-file produces a valid scene."""
    binary = _skip_if_no_godot()
    _ensure_project(tmp_path)

    tree_file = tmp_path / "input.txt"
    tree_file.write_text("Root (Node2D)\n└── Sprite (Sprite2D)\n", encoding="utf-8")
    out = tmp_path / "cli_tree.tscn"

    result = _run_cli([str(out), "--tree-file", str(tree_file)], tmp_path)
    assert result.returncode == 0, (
        f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert out.exists()

    text = out.read_text()
    assert 'type="Node2D"' in text
    assert 'type="Sprite2D" parent="."' in text

    check = check_scene(binary, tmp_path, out.name)
    assert check.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {check.stdout}\nstderr: {check.stderr}"
    )


def test_cli_create_scene_json_file(tmp_path: Path) -> None:
    """CLI: --json-file produces a valid scene."""
    binary = _skip_if_no_godot()
    _ensure_project(tmp_path)

    import json

    json_file = tmp_path / "input.json"
    json_file.write_text(
        json.dumps(
            {
                "root": {
                    "name": "Root",
                    "type": "Node2D",
                    "children": [{"name": "Label", "type": "Label"}],
                }
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "cli_json.tscn"

    result = _run_cli([str(out), "--json-file", str(json_file)], tmp_path)
    assert result.returncode == 0, (
        f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert out.exists()

    text = out.read_text()
    assert 'type="Node2D"' in text
    assert 'type="Label" parent="."' in text

    check = check_scene(binary, tmp_path, out.name)
    assert check.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {check.stdout}\nstderr: {check.stderr}"
    )


def test_cli_create_scene_with_project_and_class_name(tmp_path: Path) -> None:
    """CLI: --project with class_name resolution via fixture project."""
    binary = _skip_if_no_godot()

    project = tmp_path / "project"
    shutil.copytree(FIXTURE_DIR, project)

    tree_file = tmp_path / "input.txt"
    tree_file.write_text("GP (Gamepiece)\n", encoding="utf-8")
    out = project / "cli_class.tscn"

    result = _run_cli(
        [str(out), "--tree-file", str(tree_file), "--project", str(project)],
        tmp_path,
    )
    assert result.returncode == 0, (
        f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert out.exists()

    text = out.read_text()
    assert "res://gamepiece.gd" in text
    assert 'type="Path2D"' in text

    check = check_scene(binary, project, out.name)
    assert check.returncode == 0, (
        f"Godot --check-only failed:\nstdout: {check.stdout}\nstderr: {check.stderr}"
    )


def test_cli_create_scene_overwrite(tmp_path: Path) -> None:
    """CLI: --overwrite replaces existing file; without it, errors."""
    _skip_if_no_godot()
    _ensure_project(tmp_path)

    tree_file = tmp_path / "input.txt"
    tree_file.write_text("Root (Node2D)\n", encoding="utf-8")
    out = tmp_path / "cli_overwrite.tscn"

    # First create succeeds.
    result = _run_cli([str(out), "--tree-file", str(tree_file)], tmp_path)
    assert result.returncode == 0

    # Second without --overwrite fails.
    result = _run_cli([str(out), "--tree-file", str(tree_file)], tmp_path)
    assert result.returncode != 0
    combined = (result.stderr + result.stdout).lower()
    assert "already exists" in combined

    # With --overwrite succeeds.
    result = _run_cli(
        [str(out), "--tree-file", str(tree_file), "--overwrite"], tmp_path
    )
    assert result.returncode == 0


def test_cli_create_scene_no_input_errors(tmp_path: Path) -> None:
    """CLI: no --tree-file or --json-file errors with usage code."""
    _skip_if_no_godot()
    out = tmp_path / "cli_noinput.tscn"

    result = _run_cli([str(out)], tmp_path)
    assert result.returncode != 0
    combined = (result.stderr + result.stdout).lower()
    assert "tree-file" in combined


def test_cli_create_scene_both_inputs_error(tmp_path: Path) -> None:
    """CLI: providing both --tree-file and --json-file errors."""
    _skip_if_no_godot()
    _ensure_project(tmp_path)

    tree_file = tmp_path / "tree.txt"
    tree_file.write_text("Root (Node2D)\n", encoding="utf-8")
    json_file = tmp_path / "spec.json"
    json_file.write_text('{"name": "Root", "type": "Node2D"}', encoding="utf-8")
    out = tmp_path / "cli_both.tscn"

    result = _run_cli(
        [str(out), "--tree-file", str(tree_file), "--json-file", str(json_file)],
        tmp_path,
    )
    assert result.returncode != 0
