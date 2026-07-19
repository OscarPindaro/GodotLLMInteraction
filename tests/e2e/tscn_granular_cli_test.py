from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import pytest

from godotllminteraction.cli import app

_SCENES = Path(__file__).resolve().parents[2] / "tests" / "data" / "scenes"
_FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "data" / "fixtures"

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


class TestAddSpriteImage:
    def test_region_mode_creates_node_and_ext_resource(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "2",
                "1",
                "--node",
                "Tile",
                "--tile-width",
                "32",
                "--tile-height",
                "32",
            ],
        )
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert '[ext_resource type="Texture2D" path="res://tilemap.png"' in text
        assert 'name="Tile" type="Sprite2D"' in text
        assert "region_enabled = true" in text
        assert "region_rect = Rect2(64, 32, 32, 32)" in text

    def test_atlas_mode_creates_sub_resource(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "0",
                "0",
                "--node",
                "Tile",
                "--mode",
                "atlas",
                "--id",
                "atlas_tile",
            ],
        )
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert '[ext_resource type="Texture2D" path="res://tilemap.png"' in text
        assert '[sub_resource type="AtlasTexture" id="atlas_tile"]' in text
        assert "atlas = ExtResource(" in text
        assert "region = Rect2(0, 0, 16, 16)" in text
        assert 'name="Tile" type="Sprite2D"' in text
        assert "texture = SubResource(" in text

    def test_auto_creates_missing_node(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "1",
                "1",
                "--node",
                "Hero",
            ],
        )
        assert result.exit_code == 0, result.output
        assert 'name="Hero" type="Sprite2D"' in scene.read_text()

    def test_resource_only_without_node(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "0",
                "0",
                "--mode",
                "atlas",
                "--id",
                "atlas_only",
            ],
        )
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert '[ext_resource type="Texture2D" path="res://tilemap.png"' in text
        assert '[sub_resource type="AtlasTexture" id="atlas_only"]' in text
        assert "Sprite2D" not in text

    def test_dry_run(self, tmp_path):
        scene = workspace(tmp_path)
        original = scene.read_text()
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "0",
                "0",
                "--node",
                "Tile",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert scene.read_text() == original
        assert "Dry run" in result.output

    def test_json_output(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "3",
                "2",
                "--node",
                "Tile",
                "--json",
            ],
        )
        payload = json.loads(result.stdout)
        assert payload["operations"][0]["op"] == "add_sprite_image"
        assert (
            payload["operations"][0]["allocated_ids"]["region"]
            == "Rect2(48, 32, 16, 16)"
        )

    def test_texture_filter_by_name(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "0",
                "0",
                "--node",
                "Tile",
                "--texture-filter",
                "linear",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "texture_filter = 1" in scene.read_text()

    def test_margin_and_spacing(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "1",
                "1",
                "--node",
                "Tile",
                "--tile-width",
                "16",
                "--tile-height",
                "16",
                "--margin",
                "4",
                "--spacing",
                "2",
            ],
        )
        assert result.exit_code == 0, result.output
        # margin=4, spacing=2, cell(1,1): x = 4 + 1*(16+2) = 22, y = 4 + 1*(16+2) = 22
        assert "region_rect = Rect2(22, 22, 16, 16)" in scene.read_text()

    def test_dedup_reuses_ext_resource(self, tmp_path):
        scene = workspace(tmp_path)
        first = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "0",
                "0",
                "--node",
                "TileA",
            ],
        )
        assert first.exit_code == 0, first.output
        second = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "1",
                "0",
                "--node",
                "TileB",
            ],
        )
        assert second.exit_code == 0, second.output
        text = scene.read_text()
        # Only one ext_resource for the same texture path
        assert (
            text.count('[ext_resource type="Texture2D" path="res://tilemap.png"') == 1
        )

    def test_full_mode_sets_texture_without_region(self, tmp_path):
        scene = workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "0",
                "0",
                "--node",
                "Pippo",
                "--mode",
                "full",
            ],
        )
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'name="Pippo" type="Sprite2D"' in text
        assert "texture = ExtResource(" in text
        # full mode must NOT set region_enabled or region_rect
        assert "region_enabled" not in text
        assert "region_rect" not in text


class TestClassNameResolution:
    """add-node --type <ClassName> resolves script-defined class_name to
    (base_type, script) and auto-attaches the script."""

    def _project_workspace(self, tmp_path: Path) -> Path:
        """Copy the class_name_project fixture into tmp_path so find_project_path
        discovers the project.godot and chest.gd."""
        import shutil

        fixture = _FIXTURES / "class_name_project"
        shutil.copytree(fixture, tmp_path / "project")
        scene = tmp_path / "project" / "scene.tscn"
        scene.write_text((_SCENES / "connections.tscn").read_text())
        return scene

    def test_resolves_class_name_to_base_type_and_script(self, tmp_path):
        scene = self._project_workspace(tmp_path)
        result = runner.invoke(
            app,
            ["tscn", "add-node", str(scene), "Chest", "--type", "Chest"],
        )
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        # Node created as the base type (Sprite2D), not the script class
        assert 'name="Chest" type="Sprite2D"' in text
        # Script auto-attached
        assert "script = ExtResource(" in text
        assert 'path="res://chest.gd"' in text

    def test_reports_two_operations(self, tmp_path):
        scene = self._project_workspace(tmp_path)
        result = runner.invoke(
            app,
            ["tscn", "add-node", str(scene), "Chest", "--type", "Chest", "--json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        ops = payload["operations"]
        assert len(ops) == 2
        assert ops[0]["op"] == "add_node"
        assert ops[1]["op"] == "attach_script"

    def test_builtin_class_not_affected(self, tmp_path):
        scene = self._project_workspace(tmp_path)
        result = runner.invoke(
            app,
            ["tscn", "add-node", str(scene), "Sprite", "--type", "Sprite2D"],
        )
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'name="Sprite" type="Sprite2D"' in text
        # No script attached for built-in types
        assert "script" not in text

    def test_unknown_class_without_script_still_errors(self, tmp_path):
        scene = self._project_workspace(tmp_path)
        result = runner.invoke(
            app,
            ["tscn", "add-node", str(scene), "X", "--type", "NonExistent"],
        )
        assert result.exit_code == 1
        assert "unknown class" in result.output

    def test_class_name_then_sprite_image_custom_property(self, tmp_path):
        """Full flow: add-node --type Chest, then add-sprite-image with
        Chest.closed_texture (a script-exported property)."""
        scene = self._project_workspace(tmp_path)
        # Step 1: create the node with class_name resolution
        r1 = runner.invoke(
            app,
            ["tscn", "add-node", str(scene), "Chest", "--type", "Chest"],
        )
        assert r1.exit_code == 0, r1.output
        # Step 2: set a custom property via atlas mode
        r2 = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "4",
                "0",
                "--node",
                "Chest.closed_texture",
                "--mode",
                "atlas",
                "--id",
                "chest_closed",
            ],
        )
        assert r2.exit_code == 0, r2.output
        text = scene.read_text()
        assert "closed_texture = SubResource(" in text
        assert '[sub_resource type="AtlasTexture" id="chest_closed"]' in text

    def test_custom_property_without_script_errors(self, tmp_path):
        """Setting a custom property on a plain Sprite2D (no script) should
        raise SceneValidationError."""
        scene = self._project_workspace(tmp_path)
        # Create a plain Sprite2D without any script
        r1 = runner.invoke(
            app,
            ["tscn", "add-node", str(scene), "Plain", "--type", "Sprite2D"],
        )
        assert r1.exit_code == 0, r1.output
        # Try to set a custom property — should fail
        r2 = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "0",
                "0",
                "--node",
                "Plain.closed_texture",
                "--mode",
                "atlas",
                "--id",
                "plain_closed",
            ],
        )
        assert r2.exit_code == 1
        assert "unknown property" in r2.output

    def test_sprite_image_standalone_class_name_resolution(self, tmp_path):
        """A single add-sprite-image command with --node Chest.closed_texture
        auto-creates the Chest node (with script) and sets the custom property."""
        scene = self._project_workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "4",
                "0",
                "--node",
                "Chest.closed_texture",
                "--mode",
                "atlas",
                "--id",
                "chest_closed",
            ],
        )
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        # Node auto-created as Sprite2D with script attached
        assert 'name="Chest" type="Sprite2D"' in text
        assert "script = ExtResource(" in text
        assert 'path="res://chest.gd"' in text
        # Custom property set via AtlasTexture
        assert "closed_texture = SubResource(" in text
        assert '[sub_resource type="AtlasTexture" id="chest_closed"]' in text

    def test_no_warning_for_exported_property(self, tmp_path):
        """When the property is @export-ed by the script, no warning should
        be emitted (the spec-gap is confirmed, not assumed)."""
        scene = self._project_workspace(tmp_path)
        result = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "4",
                "0",
                "--node",
                "Chest.closed_texture",
                "--mode",
                "atlas",
                "--id",
                "chest_closed",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "is not in the" not in result.output
        assert "assuming it is exported" not in result.output

    def test_sprite_image_existing_node_no_duplicate_creation(self, tmp_path):
        """If the node already exists, add-sprite-image should not try to
        re-create it or re-attach the script."""
        scene = self._project_workspace(tmp_path)
        # Pre-create the node with script
        r1 = runner.invoke(
            app,
            ["tscn", "add-node", str(scene), "Chest", "--type", "Chest"],
        )
        assert r1.exit_code == 0, r1.output
        # Now add-sprite-image should only do 1 operation (no pre-creation)
        r2 = runner.invoke(
            app,
            [
                "tscn",
                "add-sprite-image",
                str(scene),
                "res://tilemap.png",
                "4",
                "0",
                "--node",
                "Chest.closed_texture",
                "--mode",
                "atlas",
                "--id",
                "chest_closed",
                "--json",
            ],
        )
        assert r2.exit_code == 0, r2.output
        payload = json.loads(r2.stdout)
        ops = payload["operations"]
        # Only the add_sprite_image operation, no add_node/attach_script
        assert len(ops) == 1
        assert ops[0]["op"] == "add_sprite_image"


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
