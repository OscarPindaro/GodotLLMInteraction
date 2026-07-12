from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import pytest

from godotllminteraction.cli import app

_SCENES = Path(__file__).resolve().parents[2] / "tests" / "data" / "scenes"

runner = CliRunner()

pytestmark = [pytest.mark.cli, pytest.mark.tscn]

OPS = """
version: 1
operations:
  - op: add_node
    path: Sprite
    type: Sprite2D
    properties:
      position: "Vector2(1, 2)"
"""


def write_workspace(tmp_path: Path, ops_text: str = OPS) -> tuple[Path, Path]:
    scene = tmp_path / "scene.tscn"
    scene.write_text((_SCENES / "minimal.tscn").read_text())
    ops = tmp_path / "ops.yaml"
    ops.write_text(ops_text)
    return scene, ops


class TestApply:
    def test_apply_in_place(self, tmp_path):
        scene, ops = write_workspace(tmp_path)
        result = runner.invoke(app, ["tscn", "apply", str(ops), "--scene", str(scene)])
        assert result.exit_code == 0, result.output
        assert 'name="Sprite"' in scene.read_text()

    def test_apply_to_output(self, tmp_path):
        scene, ops = write_workspace(tmp_path)
        out = tmp_path / "out.tscn"
        result = runner.invoke(
            app,
            ["tscn", "apply", str(ops), "--scene", str(scene), "--output", str(out)],
        )
        assert result.exit_code == 0
        assert out.exists()
        assert scene.read_text() == (_SCENES / "minimal.tscn").read_text()

    def test_dry_run_writes_nothing_and_shows_diff(self, tmp_path):
        scene, ops = write_workspace(tmp_path)
        original = scene.read_text()
        result = runner.invoke(
            app, ["tscn", "apply", str(ops), "--scene", str(scene), "--dry-run"]
        )
        assert result.exit_code == 0
        assert scene.read_text() == original
        assert '+[node name="Sprite"' in result.output

    def test_global_dry_run_flag(self, tmp_path):
        scene, ops = write_workspace(tmp_path)
        original = scene.read_text()
        result = runner.invoke(
            app, ["--dry-run", "tscn", "apply", str(ops), "--scene", str(scene)]
        )
        assert result.exit_code == 0
        assert scene.read_text() == original

    def test_json_output(self, tmp_path):
        scene, ops = write_workspace(tmp_path)
        result = runner.invoke(
            app, ["tscn", "apply", str(ops), "--scene", str(scene), "--json"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["changed"] is True
        assert payload["operations"][0]["op"] == "add_node"
        assert payload["operations"][0]["affected_paths"] == ["Sprite"]

    def test_failing_op_exits_one_and_writes_nothing(self, tmp_path):
        bad = OPS.replace("Sprite2D", "NotAClass")
        scene, ops = write_workspace(tmp_path, bad)
        original = scene.read_text()
        result = runner.invoke(app, ["tscn", "apply", str(ops), "--scene", str(scene)])
        assert result.exit_code == 1
        assert "unknown class" in result.output
        assert scene.read_text() == original

    def test_no_strict_downgrades_spec_errors(self, tmp_path):
        bad = OPS.replace("Sprite2D", "NotAClass")
        scene, ops = write_workspace(tmp_path, bad)
        result = runner.invoke(
            app, ["tscn", "apply", str(ops), "--scene", str(scene), "--no-strict"]
        )
        assert result.exit_code == 0
        assert 'type="NotAClass"' in scene.read_text()

    def test_malformed_ops_file_exits_usage(self, tmp_path):
        scene, ops = write_workspace(tmp_path, "operations: [{op: not_an_op}]")
        result = runner.invoke(app, ["tscn", "apply", str(ops), "--scene", str(scene)])
        assert result.exit_code == 1

    def test_create_new_scene(self, tmp_path):
        ops = tmp_path / "ops.yaml"
        out = tmp_path / "new.tscn"
        ops.write_text(
            "create:\n  root_name: Level\n  root_type: Node2D\n"
            f"output: {out}\n"
            "operations:\n  - op: add_node\n    path: Player\n    type: CharacterBody2D\n"
        )
        result = runner.invoke(app, ["tscn", "apply", str(ops)])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert '[node name="Level" type="Node2D"]' in text
        assert '[node name="Player" type="CharacterBody2D" parent="."]' in text

    def test_reapply_is_noop(self, tmp_path):
        scene, ops = write_workspace(tmp_path)
        runner.invoke(app, ["tscn", "apply", str(ops), "--scene", str(scene)])
        first = scene.read_text()
        result = runner.invoke(app, ["tscn", "apply", str(ops), "--scene", str(scene)])
        assert result.exit_code == 0
        assert "already satisfied" in result.output
        assert scene.read_text() == first


class TestTree:
    def test_tree_text(self):
        result = runner.invoke(
            app, ["tscn", "tree", str(_SCENES / "sprite_frames.tscn")]
        )
        assert result.exit_code == 0
        assert "Actor (Node2D)" in result.stdout

    def test_tree_json(self):
        result = runner.invoke(
            app,
            [
                "tscn",
                "tree",
                str(_SCENES / "sprite_frames.tscn"),
                "--detail",
                "properties",
                "--json",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["name"] == "Actor"

    def test_invalid_detail_exits_usage(self):
        result = runner.invoke(
            app,
            ["tscn", "tree", str(_SCENES / "minimal.tscn"), "--detail", "everything"],
        )
        assert result.exit_code == 2


class TestValidate:
    def test_missing_godot_fails_clearly(self, tmp_path, monkeypatch):
        result = runner.invoke(
            app,
            [
                "tscn",
                "validate",
                "res://x.tscn",
                "--project",
                str(tmp_path),
                "--godot",
                str(tmp_path / "nope"),
            ],
        )
        assert result.exit_code == 2
        assert "Could not find a Godot executable" in result.output
