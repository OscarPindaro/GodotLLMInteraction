from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import pytest

from godotllminteraction.cli import app

_SCENES = Path(__file__).resolve().parents[2] / "tests" / "data" / "scenes"

runner = CliRunner()

pytestmark = [pytest.mark.cli, pytest.mark.tscn]


def workspace(tmp_path: Path, fixture: str = "connections.tscn") -> Path:
    scene = tmp_path / "scene.tscn"
    scene.write_text((_SCENES / fixture).read_text())
    return scene


class TestAddNode:
    def test_type_writes_node(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-node",
                str(scene),
                "Sprite",
                "--type",
                "Sprite2D",
                "--property",
                "position=Vector2(3, 4)",
                "--group",
                "enemies",
            ],
        )
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert (
            '[node name="Sprite" type="Sprite2D" parent="." groups=["enemies"]]' in text
        )
        assert "position = Vector2(3, 4)" in text

    def test_instance_option(self, tmp_path):
        scene = workspace(tmp_path, "instances.tscn")
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-node",
                str(scene),
                "Actor3",
                "--instance",
                'ExtResource("1_child")',
            ],
        )
        assert result.exit_code == 0, result.output
        assert (
            'name="Actor3" parent="." instance=ExtResource("1_child")'
            in scene.read_text()
        )

    def test_missing_type_and_instance_errors(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(app, ["tscn", "add-node", str(scene), "X"])
        assert result.exit_code == 1
        assert "exactly one of" in result.output

    def test_invalid_property_pair_exits_usage(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-node",
                str(scene),
                "X",
                "--type",
                "Node2D",
                "--property",
                "nokey",
            ],
        )
        assert result.exit_code == 2

    def test_dry_run(self, tmp_path):
        scene = workspace(tmp_path)
        original = scene.read_text()
        result = runner.invoke(
            app,
            ["tscn", "add-node", str(scene), "X", "--type", "Node2D", "--dry-run"],
        )
        assert result.exit_code == 0
        assert scene.read_text() == original
        assert "Dry run" in result.output

    def test_json_output(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app, ["tscn", "add-node", str(scene), "X", "--type", "Node2D", "--json"]
        )
        payload = json.loads(result.stdout)
        assert payload["operations"][0]["op"] == "add_node"

    def test_missing_scene_exits_usage(self, tmp_path):
        result = runner.invoke(
            app,
            ["tscn", "add-node", str(tmp_path / "nope.tscn"), "X", "--type", "Node2D"],
        )
        assert result.exit_code == 2


class TestDeleteNode:
    def test_deletes_subtree(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(app, ["tscn", "delete-node", str(scene), "Button"])
        assert result.exit_code == 0, result.output
        assert 'name="Button"' not in scene.read_text()

    def test_no_recursive_with_children_errors(self, tmp_path):
        scene = workspace(tmp_path, "ui_and_paths.tscn")
        result = runner.invoke(
            app, ["tscn", "delete-node", str(scene), "PlateArea", "--no-recursive"]
        )
        assert result.exit_code == 1
        assert "has children" in result.output


class TestUpdateProperties:
    def test_set_and_remove(self, tmp_path):
        scene = workspace(tmp_path)
        runner.invoke(
            app,
            [
                "tscn",
                "update-properties",
                str(scene),
                "Timer",
                "--property",
                "wait_time=9.0",
            ],
        )
        assert "wait_time = 9.0" in scene.read_text()
        result = runner.invoke(
            app,
            ["tscn", "update-properties", str(scene), "Timer", "--remove", "wait_time"],
        )
        assert result.exit_code == 0
        assert "wait_time" not in scene.read_text()


class TestRenameMove:
    def test_rename(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app, ["tscn", "rename-node", str(scene), "Button", "Trigger"]
        )
        assert result.exit_code == 0
        text = scene.read_text()
        assert 'name="Trigger"' in text
        assert 'from="Trigger"' in text  # connection endpoint rewritten

    def test_move(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app, ["tscn", "move-node", str(scene), "Timer", "Button"]
        )
        assert result.exit_code == 0
        assert 'parent="Button"' in scene.read_text()


class TestScripts:
    def test_attach_and_detach(self, tmp_path):
        scene = workspace(tmp_path)
        runner.invoke(app, ["tscn", "attach-script", str(scene), ".", "res://door.gd"])
        assert "script = ExtResource(" in scene.read_text()
        result = runner.invoke(app, ["tscn", "detach-script", str(scene), "."])
        assert result.exit_code == 0
        assert "script" not in scene.read_text()


class TestResources:
    def test_add_ext_resource(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-ext-resource",
                str(scene),
                "Texture2D",
                "res://icon.svg",
                "--id",
                "tex",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (
            '[ext_resource type="Texture2D" path="res://icon.svg" id="tex"]'
            in scene.read_text()
        )

    def test_create_sub_resource(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "create-sub-resource",
                str(scene),
                "RectangleShape2D",
                "--property",
                "size=Vector2(8, 8)",
                "--id",
                "my_shape",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (
            '[sub_resource type="RectangleShape2D" id="my_shape"]' in scene.read_text()
        )


class TestSignals:
    def test_connect_and_disconnect(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "connect-signal",
                str(scene),
                "--from",
                "Button",
                "--to",
                ".",
                "--signal",
                "area_entered",
                "--method",
                "_on_area",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (
            '[connection signal="area_entered" from="Button" to="." method="_on_area"]'
            in scene.read_text()
        )

        result = runner.invoke(
            app,
            [
                "tscn",
                "disconnect-signal",
                str(scene),
                "--from",
                "Button",
                "--to",
                ".",
                "--signal",
                "area_entered",
                "--method",
                "_on_area",
            ],
        )
        assert result.exit_code == 0
        assert "area_entered" not in scene.read_text()

    def test_unknown_signal_errors(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "connect-signal",
                str(scene),
                "--from",
                "Button",
                "--to",
                ".",
                "--signal",
                "not_a_signal",
                "--method",
                "_on_x",
            ],
        )
        assert result.exit_code == 1
        assert "has no signal" in result.output


class TestChaining:
    def test_sequence_of_granular_commands_round_trips(self, tmp_path):
        scene = workspace(tmp_path)
        commands = [
            ["tscn", "add-node", str(scene), "Sprite", "--type", "Sprite2D"],
            ["tscn", "attach-script", str(scene), "Sprite", "res://s.gd"],
            ["tscn", "rename-node", str(scene), "Sprite", "Hero"],
            ["tscn", "move-node", str(scene), "Hero", "Button"],
            ["tscn", "detach-script", str(scene), "Button/Hero"],
            ["tscn", "delete-node", str(scene), "Button/Hero"],
        ]
        for command in commands:
            result = runner.invoke(app, command)
            assert result.exit_code == 0, (command, result.output)
        assert scene.read_text() == (_SCENES / "connections.tscn").read_text()
