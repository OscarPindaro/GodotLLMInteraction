"""E2e edit-then-validate tests for real scene fixtures (Godot 4.4.0).

For each real scene: copy → CLI edit operation → validate with both
``gli tscn validate`` (CLI) and Godot ``--check-only`` → assert both agree.

Also tests bad scenes that CLI and Godot must both reject.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.e2e._helpers import (
    cleanup_test_scenes,
    godot_binary_path,
    output_scene_path,
    run_cli_edit,
    validate_both,
)

VERSION = "4.4.0"
SCENES_DIR = Path(__file__).resolve().parents[1] / "data" / "scenes" / "open_rpg_4_4_0"
BAD_SCENES_DIR = Path(__file__).resolve().parents[1] / "data" / "scenes" / "bad_4_4_0"

SCENE_NAMES = [
    "CombatAI.tscn",
    "exported_props.tscn",
    "gamepiece.tscn",
    "ScreenTransition.tscn",
    "Trigger.tscn",
    "ui_damage_label.tscn",
]

MULTI_NODE_SCENES = [
    "gamepiece.tscn",
    "ScreenTransition.tscn",
    "Trigger.tscn",
    "ui_damage_label.tscn",
]

MOVE_SCENES = ["gamepiece.tscn", "Trigger.tscn"]


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    cleanup_test_scenes(SCENES_DIR)


def _require_binary():
    binary = godot_binary_path(VERSION)
    if binary is None:
        pytest.skip(f"Godot {VERSION} binary not installed")
    return binary


def _require_scene(scene_name: str) -> Path:
    p = SCENES_DIR / scene_name
    if not p.exists():
        pytest.skip(f"Scene fixture not found: {p}")
    return p


def _edit_and_validate(scene_name: str, edit_args: list[str]) -> tuple[int, int]:
    """Apply CLI edit with ``--output`` to a temp file, then validate.

    ``edit_args`` uses ``"{scene}"`` as a placeholder for the *source* scene
    path; it is replaced with the actual fixture path.  ``--output <tmp>``
    is appended automatically so the original fixture is never modified.
    """
    binary = _require_binary()
    src = _require_scene(scene_name)
    tmp = output_scene_path(SCENES_DIR, scene_name)
    resolved = [str(src) if a == "{scene}" else a for a in edit_args]
    resolved += ["--output", str(tmp)]
    result = run_cli_edit(resolved)
    assert result.exit_code == 0, f"CLI edit failed: {result.output}"
    return validate_both(tmp, SCENES_DIR, binary)


# ── TestRoundtripGodotCheck ─────────────────────────────────────────────


class TestRoundtripGodotCheck:
    """Parse → dump preserves Godot validity at each step."""

    @pytest.mark.parametrize("scene_name", SCENE_NAMES)
    def test_add_then_delete_roundtrip(self, scene_name):
        binary = _require_binary()
        src = _require_scene(scene_name)
        tmp = output_scene_path(SCENES_DIR, scene_name)

        r = run_cli_edit(
            ["add-node", str(src), "TempNode", "--type", "Node", "--output", str(tmp)]
        )
        assert r.exit_code == 0, r.output
        cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
        assert cli_exit == 0, f"CLI validate failed after add: {scene_name}"
        assert godot_exit == 0, f"Godot check failed after add: {scene_name}"

        r = run_cli_edit(["delete-node", str(tmp), "TempNode"])
        assert r.exit_code == 0, r.output
        cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
        assert cli_exit == 0, f"CLI validate failed after delete: {scene_name}"
        assert godot_exit == 0, f"Godot check failed after delete: {scene_name}"


# ── TestAddNodeGodotCheck ───────────────────────────────────────────────


class TestAddNodeGodotCheck:
    @pytest.mark.parametrize("scene_name", SCENE_NAMES)
    def test_add_plain_node(self, scene_name):
        cli_exit, godot_exit = _edit_and_validate(
            scene_name, ["add-node", "{scene}", "TempNode", "--type", "Node"]
        )
        assert cli_exit == 0, f"CLI validate failed: {scene_name}"
        assert godot_exit == 0, f"Godot check failed: {scene_name}"


# ── TestDeleteNodeGodotCheck ────────────────────────────────────────────


class TestDeleteNodeGodotCheck:
    @pytest.mark.parametrize("scene_name", MULTI_NODE_SCENES)
    def test_delete_leaf(self, scene_name):
        leaf = {
            "gamepiece.tscn": "PathFollow2D/CameraAnchor",
            "ScreenTransition.tscn": "ColorRect",
            "Trigger.tscn": "Area2D/CollisionShape2D",
            "ui_damage_label.tscn": "Label",
        }[scene_name]
        cli_exit, godot_exit = _edit_and_validate(
            scene_name, ["delete-node", "{scene}", leaf]
        )
        assert cli_exit == 0, f"CLI validate failed: {scene_name}"
        assert godot_exit == 0, f"Godot check failed: {scene_name}"

    def test_delete_subtree_trigger(self):
        """Delete Area2D: removes subtree + 2 connections + orphans sub_resource."""
        cli_exit, godot_exit = _edit_and_validate(
            "Trigger.tscn", ["delete-node", "{scene}", "Area2D"]
        )
        assert cli_exit == 0, "CLI validate failed: Trigger subtree delete"
        assert godot_exit == 0, "Godot check failed: Trigger subtree delete"

    def test_delete_subtree_gamepiece(self):
        """Delete PathFollow2D (contains CameraAnchor)."""
        cli_exit, godot_exit = _edit_and_validate(
            "gamepiece.tscn", ["delete-node", "{scene}", "PathFollow2D"]
        )
        assert cli_exit == 0, "CLI validate failed: gamepiece subtree delete"
        assert godot_exit == 0, "Godot check failed: gamepiece subtree delete"


# ── TestRenameNodeGodotCheck ────────────────────────────────────────────


class TestRenameNodeGodotCheck:
    @pytest.mark.parametrize("scene_name", MULTI_NODE_SCENES)
    def test_rename_child(self, scene_name):
        child = {
            "gamepiece.tscn": "PathFollow2D",
            "ScreenTransition.tscn": "ColorRect",
            "Trigger.tscn": "Area2D",
            "ui_damage_label.tscn": "Label",
        }[scene_name]
        cli_exit, godot_exit = _edit_and_validate(
            scene_name, ["rename-node", "{scene}", child, "RenamedChild"]
        )
        assert cli_exit == 0, f"CLI validate failed: {scene_name}"
        assert godot_exit == 0, f"Godot check failed: {scene_name}"


# ── TestMoveNodeGodotCheck ──────────────────────────────────────────────


class TestMoveNodeGodotCheck:
    @pytest.mark.parametrize("scene_name", MOVE_SCENES)
    def test_move_child_to_root(self, scene_name):
        child = {
            "gamepiece.tscn": "PathFollow2D",
            "Trigger.tscn": "Area2D/CollisionShape2D",
        }[scene_name]
        cli_exit, godot_exit = _edit_and_validate(
            scene_name, ["move-node", "{scene}", child, "."]
        )
        assert cli_exit == 0, f"CLI validate failed: {scene_name}"
        assert godot_exit == 0, f"Godot check failed: {scene_name}"


# ── TestUpdatePropertiesGodotCheck ──────────────────────────────────────


class TestUpdatePropertiesGodotCheck:
    @pytest.mark.parametrize(
        "scene_name,node,props",
        [
            ("CombatAI.tscn", ".", ["position=Vector2(100, 100)"]),
            ("gamepiece.tscn", ".", ["position=Vector2(100, 100)"]),
            ("ScreenTransition.tscn", "ColorRect", ["color=Color(1, 0, 0, 1)"]),
            ("Trigger.tscn", ".", ["position=Vector2(100, 100)"]),
            ("ui_damage_label.tscn", ".", ["position=Vector2(50, 50)"]),
        ],
    )
    def test_update_safe_property(self, scene_name, node, props):
        args = ["update-properties", "{scene}", node]
        for p in props:
            args += ["--property", p]
        cli_exit, godot_exit = _edit_and_validate(scene_name, args)
        assert cli_exit == 0, f"CLI validate failed: {scene_name}"
        assert godot_exit == 0, f"Godot check failed: {scene_name}"


# ── TestComplexChangesGodotCheck ────────────────────────────────────────


class TestComplexChangesGodotCheck:
    def test_multi_property_transform_trigger(self):
        cli_exit, godot_exit = _edit_and_validate(
            "Trigger.tscn",
            [
                "update-properties",
                "{scene}",
                ".",
                "--property",
                "position=Vector2(100,50)",
                "--property",
                "rotation=1.5708",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_multi_property_transform_gamepiece(self):
        cli_exit, godot_exit = _edit_and_validate(
            "gamepiece.tscn",
            [
                "update-properties",
                "{scene}",
                ".",
                "--property",
                "position=Vector2(200,100)",
                "--property",
                "rotation=0.5",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_multi_property_transform_screen_transition(self):
        cli_exit, godot_exit = _edit_and_validate(
            "ScreenTransition.tscn",
            [
                "update-properties",
                "{scene}",
                "ColorRect",
                "--property",
                "color=Color(1,0,0,0.5)",
                "--property",
                "offset_left=-50.0",
                "--property",
                "offset_right=50.0",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_multi_property_transform_ui_damage_label(self):
        cli_exit, godot_exit = _edit_and_validate(
            "ui_damage_label.tscn",
            [
                "update-properties",
                "{scene}",
                "Label",
                "--property",
                'text="Critical!"',
                "--property",
                "theme_override_constants/outline_size=32",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_pathfollow_progress_gamepiece(self):
        cli_exit, godot_exit = _edit_and_validate(
            "gamepiece.tscn",
            [
                "update-properties",
                "{scene}",
                "PathFollow2D",
                "--property",
                "progress=50.0",
                "--property",
                "h_offset=10.0",
                "--property",
                "v_offset=5.0",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_collision_tuning_trigger(self):
        cli_exit, godot_exit = _edit_and_validate(
            "Trigger.tscn",
            [
                "update-properties",
                "{scene}",
                "Area2D",
                "--property",
                "collision_layer=64",
                "--property",
                "collision_mask=8",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_collision_shape_debug_color_trigger(self):
        cli_exit, godot_exit = _edit_and_validate(
            "Trigger.tscn",
            [
                "update-properties",
                "{scene}",
                "Area2D/CollisionShape2D",
                "--property",
                "debug_color=Color(0,1,0,0.5)",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_sub_resource_swap_trigger(self):
        """Create new shape, swap reference, verify scene still valid."""
        binary = _require_binary()
        src = _require_scene("Trigger.tscn")
        tmp = output_scene_path(SCENES_DIR, "Trigger.tscn")

        r = run_cli_edit(
            [
                "create-sub-resource",
                str(src),
                "RectangleShape2D",
                "--property",
                "size=Vector2(20,20)",
                "--id",
                "new_shape",
                "--output",
                str(tmp),
            ],
        )
        assert r.exit_code == 0, r.output
        cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
        assert cli_exit == 0 and godot_exit == 0

        r = run_cli_edit(
            [
                "update-properties",
                str(tmp),
                "Area2D/CollisionShape2D",
                "--property",
                'shape=SubResource("new_shape")',
            ],
        )
        assert r.exit_code == 0, r.output
        cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
        assert cli_exit == 0 and godot_exit == 0

    def test_ext_resource_swap_ui_damage_label(self):
        """Add new theme ext-resource, swap reference on Label."""
        binary = _require_binary()
        src = _require_scene("ui_damage_label.tscn")
        tmp = output_scene_path(SCENES_DIR, "ui_damage_label.tscn")

        r = run_cli_edit(
            [
                "add-ext-resource",
                str(src),
                "Theme",
                "res://test_theme.tres",
                "--id",
                "new_theme",
                "--output",
                str(tmp),
            ],
        )
        assert r.exit_code == 0, r.output
        cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
        assert cli_exit == 0 and godot_exit == 0

        r = run_cli_edit(
            [
                "update-properties",
                str(tmp),
                "Label",
                "--property",
                'theme=ExtResource("new_theme")',
            ],
        )
        assert r.exit_code == 0, r.output
        cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
        assert cli_exit == 0 and godot_exit == 0

    def test_chained_complex_sequence_trigger(self):
        """8-step chained sequence on Trigger.tscn — the richest fixture."""
        binary = _require_binary()
        src = _require_scene("Trigger.tscn")
        tmp = output_scene_path(SCENES_DIR, "Trigger.tscn")

        steps: list[list[str]] = [
            ["add-node", str(src), "Mover", "--type", "Node2D", "--output", str(tmp)],
            ["move-node", str(tmp), "Area2D/CollisionShape2D", "Mover"],
            [
                "update-properties",
                str(tmp),
                "Mover",
                "--property",
                "position=Vector2(50,50)",
                "--property",
                "rotation=0.785",
            ],
            [
                "create-sub-resource",
                str(tmp),
                "CircleShape2D",
                "--property",
                "radius=10.0",
                "--id",
                "circle",
            ],
            [
                "update-properties",
                str(tmp),
                "Mover/CollisionShape2D",
                "--property",
                'shape=SubResource("circle")',
            ],
            [
                "connect-signal",
                str(tmp),
                "--from",
                "Area2D",
                "--to",
                "Mover",
                "--signal",
                "area_entered",
                "--method",
                "_on_mover_area",
            ],
            ["rename-node", str(tmp), "Area2D", "Detector"],
            ["delete-node", str(tmp), "Detector"],
        ]

        for i, step in enumerate(steps):
            r = run_cli_edit(step)
            assert r.exit_code == 0, f"Step {i + 1} failed: {r.output}"
            cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
            assert cli_exit == 0, f"CLI validate failed at step {i + 1}"
            assert godot_exit == 0, f"Godot check failed at step {i + 1}"


# ── TestExportedPropertiesGodotCheck ────────────────────────────────────


class TestExportedPropertiesGodotCheck:
    """Tests for @export GDScript properties stored in .tscn files.

    exported_props.gd defines @export var max_speed, damage, is_active, label,
    tint, spawn_position.  The scene overrides max_speed=350, damage=25,
    is_active=false (non-default values stored in the .tscn).  Properties
    matching defaults (label, tint, spawn_position) are NOT in the scene file.
    """

    def test_update_existing_exported_float(self):
        cli_exit, godot_exit = _edit_and_validate(
            "exported_props.tscn",
            ["update-properties", "{scene}", ".", "--property", "max_speed=500.0"],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_update_existing_exported_int(self):
        cli_exit, godot_exit = _edit_and_validate(
            "exported_props.tscn",
            ["update-properties", "{scene}", ".", "--property", "damage=50"],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_update_existing_exported_bool(self):
        cli_exit, godot_exit = _edit_and_validate(
            "exported_props.tscn",
            ["update-properties", "{scene}", ".", "--property", "is_active=true"],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_add_exported_string_not_in_scene(self):
        cli_exit, godot_exit = _edit_and_validate(
            "exported_props.tscn",
            ["update-properties", "{scene}", ".", "--property", 'label="Boss"'],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_add_exported_color_not_in_scene(self):
        cli_exit, godot_exit = _edit_and_validate(
            "exported_props.tscn",
            [
                "update-properties",
                "{scene}",
                ".",
                "--property",
                "tint=Color(0, 1, 0, 1)",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_add_exported_vector2_not_in_scene(self):
        cli_exit, godot_exit = _edit_and_validate(
            "exported_props.tscn",
            [
                "update-properties",
                "{scene}",
                ".",
                "--property",
                "spawn_position=Vector2(100, 200)",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_multi_exported_property_update(self):
        cli_exit, godot_exit = _edit_and_validate(
            "exported_props.tscn",
            [
                "update-properties",
                "{scene}",
                ".",
                "--property",
                "max_speed=400.0",
                "--property",
                "damage=99",
                "--property",
                'label="Mini Boss"',
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0

    def test_exported_properties_roundtrip(self):
        binary = _require_binary()
        src = _require_scene("exported_props.tscn")
        tmp = output_scene_path(SCENES_DIR, "exported_props.tscn")

        props = [
            "max_speed=600.0",
            "damage=100",
            "is_active=true",
            'label="Final Boss"',
            "tint=Color(0.5, 0.2, 0.8, 1)",
            "spawn_position=Vector2(256, 128)",
        ]
        args = ["update-properties", str(src), "."]
        for p in props:
            args += ["--property", p]
        args += ["--output", str(tmp)]
        r = run_cli_edit(args)
        assert r.exit_code == 0, r.output
        cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
        assert cli_exit == 0, "CLI validate failed after multi-export update"
        assert godot_exit == 0, "Godot check failed after multi-export update"


# ── TestAttachDetachScriptGodotCheck ────────────────────────────────────


class TestAttachDetachScriptGodotCheck:
    @pytest.mark.parametrize("scene_name", SCENE_NAMES)
    def test_attach_then_detach_script(self, scene_name):
        binary = _require_binary()
        src = _require_scene(scene_name)
        tmp = output_scene_path(SCENES_DIR, scene_name)

        r = run_cli_edit(
            ["attach-script", str(src), ".", "res://test_stub.gd", "--output", str(tmp)]
        )
        assert r.exit_code == 0, f"Attach failed: {r.output}"
        cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
        assert cli_exit == 0, f"CLI validate failed after attach: {scene_name}"
        assert godot_exit == 0, f"Godot check failed after attach: {scene_name}"

        r = run_cli_edit(["detach-script", str(tmp), "."])
        assert r.exit_code == 0, f"Detach failed: {r.output}"
        cli_exit, godot_exit = validate_both(tmp, SCENES_DIR, binary)
        assert cli_exit == 0, f"CLI validate failed after detach: {scene_name}"
        assert godot_exit == 0, f"Godot check failed after detach: {scene_name}"


# ── TestCreateSubResourceGodotCheck ─────────────────────────────────────


class TestCreateSubResourceGodotCheck:
    @pytest.mark.parametrize("scene_name", SCENE_NAMES)
    def test_create_orphan_sub_resource(self, scene_name):
        cli_exit, godot_exit = _edit_and_validate(
            scene_name,
            [
                "create-sub-resource",
                "{scene}",
                "RectangleShape2D",
                "--property",
                "size=Vector2(8,8)",
                "--id",
                "test_shape",
            ],
        )
        assert cli_exit == 0, f"CLI validate failed: {scene_name}"
        assert godot_exit == 0, f"Godot check failed: {scene_name}"


# ── TestConnectSignalGodotCheck ─────────────────────────────────────────


class TestConnectSignalGodotCheck:
    def test_connect_body_entered_trigger(self):
        cli_exit, godot_exit = _edit_and_validate(
            "Trigger.tscn",
            [
                "connect-signal",
                "{scene}",
                "--from",
                "Area2D",
                "--to",
                ".",
                "--signal",
                "body_entered",
                "--method",
                "_on_test",
            ],
        )
        assert cli_exit == 0
        assert godot_exit == 0


# ── TestTreeCommand ─────────────────────────────────────────────────────


class TestTreeCommand:
    @pytest.mark.parametrize("scene_name", SCENE_NAMES)
    def test_tree_json_structure(self, scene_name):
        _require_scene(scene_name)
        r = run_cli_edit(["tree", str(SCENES_DIR / scene_name), "--json"])
        assert r.exit_code == 0, r.output
        payload = json.loads(r.stdout)
        assert "name" in payload
        assert "type" in payload

    def test_tree_json_trigger(self):
        _require_scene("Trigger.tscn")
        r = run_cli_edit(["tree", str(SCENES_DIR / "Trigger.tscn"), "--json"])
        assert r.exit_code == 0
        payload = json.loads(r.stdout)
        assert payload["name"] == "Trigger"
        assert payload["type"] == "Node2D"
        children = payload.get("children", [])
        assert len(children) == 1
        assert children[0]["name"] == "Area2D"


# ── TestValidateCommand ─────────────────────────────────────────────────


class TestValidateCommand:
    @pytest.mark.parametrize("scene_name", SCENE_NAMES)
    def test_validate_original_scene(self, scene_name):
        binary = _require_binary()
        _require_scene(scene_name)
        r = run_cli_edit(
            [
                "validate",
                str(SCENES_DIR / scene_name),
                "--project",
                str(SCENES_DIR),
                "--godot",
                binary,
            ],
        )
        assert r.exit_code == 0, f"Validate failed: {scene_name}\n{r.output}"


# ── TestBadScenesCliGodotAgree ──────────────────────────────────────────


BAD_SCENES = [
    "not_a_scene.tscn",
    "missing_parent.tscn",
    "broken_connection.tscn",
    "broken_subresource.tscn",
]


class TestBadScenesCliGodotAgree:
    @pytest.mark.parametrize("scene_name", BAD_SCENES)
    def test_both_reject_bad_scene(self, scene_name):
        binary = _require_binary()
        scene_path = BAD_SCENES_DIR / scene_name
        if not scene_path.exists():
            pytest.skip(f"Bad scene fixture not found: {scene_path}")

        tree_result = run_cli_edit(["tree", str(scene_path), "--json"])
        validate_result = run_cli_edit(
            [
                "validate",
                str(scene_path),
                "--project",
                str(BAD_SCENES_DIR),
                "--godot",
                binary,
            ],
        )

        from tests.e2e._helpers import check_scene

        godot_result = check_scene(binary, BAD_SCENES_DIR, scene_name)

        cli_rejected = validate_result.exit_code != 0 or tree_result.exit_code != 0
        godot_rejected = godot_result.returncode != 0

        assert cli_rejected == godot_rejected, (
            f"CLI and Godot disagree on {scene_name}: "
            f"cli_rejected={cli_rejected} (tree={tree_result.exit_code}, "
            f"validate={validate_result.exit_code}), "
            f"godot_rejected={godot_rejected} (exit={godot_result.returncode})\n"
            f"{godot_result.stdout}\n{godot_result.stderr}"
        )
