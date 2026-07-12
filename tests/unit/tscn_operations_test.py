from __future__ import annotations

from pathlib import Path

import pytest

from godotllminteraction.tscn.exceptions import OperationError
from godotllminteraction.tscn.operations import (
    AddExtResource,
    AddNode,
    AttachScript,
    ConnectSignal,
    CreateSubResource,
    DeleteNode,
    DetachScript,
    DisconnectSignal,
    MoveNode,
    RenameNode,
    UpdateProperties,
    apply_operations,
)
from godotllminteraction.tscn.parser import parse_scene
from godotllminteraction.tscn.values import GInt, GString
from godotllminteraction.tscn.writer import dump_scene

pytestmark = [pytest.mark.tscn]

_SCENES = Path(__file__).resolve().parents[2] / "tests" / "data" / "scenes"


def load(fixture: str):
    return parse_scene((_SCENES / fixture).read_text())


BASIC = """[gd_scene format=3 uid="uid://basic"]

[node name="Root" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]

[node name="Sprite" type="Sprite2D" parent="Player"]

[node name="Enemy" type="Area2D" parent="."]
"""


def basic():
    return parse_scene(BASIC)


class TestAddNode:
    def test_add_child_inserted_after_parent_subtree(self):
        result = apply_operations(
            basic(),
            [AddNode(path="Player/Shape", type="CollisionShape2D")],
        )
        scene = result.scene
        assert [n.path() for n in scene.nodes] == [
            ".",
            "Player",
            "Player/Sprite",
            "Player/Shape",
            "Enemy",
        ]
        assert result.results[0].changed

    def test_add_with_properties_and_groups(self):
        result = apply_operations(
            basic(),
            [
                AddNode(
                    path="Bullet",
                    type="Node2D",
                    properties={"position": "Vector2(1, 2)", "z_index": 4},
                    groups=["projectiles"],
                )
            ],
        )
        text = dump_scene(result.scene)
        assert (
            '[node name="Bullet" type="Node2D" parent="." groups=["projectiles"]]'
            in text
        )
        assert "position = Vector2(1, 2)" in text
        assert "z_index = 4" in text

    def test_missing_parent_errors(self):
        with pytest.raises(OperationError, match="parent 'Ghost'"):
            apply_operations(basic(), [AddNode(path="Ghost/X", type="Node2D")])

    def test_unknown_type_errors(self):
        with pytest.raises(OperationError, match="unknown class"):
            apply_operations(basic(), [AddNode(path="X", type="NotAThing")])

    def test_invalid_property_errors(self):
        with pytest.raises(OperationError, match="position"):
            apply_operations(
                basic(),
                [AddNode(path="X", type="Node2D", properties={"position": "5"})],
            )

    def test_same_node_same_type_is_noop(self):
        result = apply_operations(
            basic(), [AddNode(path="Player", type="CharacterBody2D")]
        )
        assert not result.results[0].changed
        assert dump_scene(result.scene) == BASIC

    def test_same_path_different_type_conflicts(self):
        with pytest.raises(OperationError, match="already exists with type"):
            apply_operations(basic(), [AddNode(path="Player", type="Node2D")])

    def test_same_path_different_property_conflicts(self):
        with pytest.raises(OperationError, match="use update_properties"):
            apply_operations(
                basic(),
                [
                    AddNode(
                        path="Player",
                        type="CharacterBody2D",
                        properties={"position": "Vector2(9, 9)"},
                    )
                ],
            )

    def test_unique_id_never_assigned_and_existing_ones_preserved(self):
        # unique_id is Godot's own bookkeeping (assigned by the editor on
        # save); the tool never writes one for new nodes and never touches
        # existing ones on nodes it didn't add.
        scene = load("sprite_frames.tscn")  # existing nodes DO have unique_ids
        result = apply_operations(scene, [AddNode(path="Extra", type="Node2D")])
        assert "unique_id" not in result.scene.node("Extra").attributes
        assert "unique_id" in result.scene.node("AnimatedSprite2D").attributes
        assert (
            result.scene.node("AnimatedSprite2D").attributes
            == scene.node("AnimatedSprite2D").attributes
        )

    def test_add_node_has_no_unique_id_field(self):
        assert "unique_id" not in AddNode.model_fields

    def test_add_instanced_scene_node(self):
        result = apply_operations(
            basic(),
            [
                AddExtResource(type="PackedScene", path="res://bullet.tscn", id="1_b"),
                AddNode(path="Bullet", instance='ExtResource("1_b")'),
            ],
        )
        text = dump_scene(result.scene)
        assert '[node name="Bullet" parent="." instance=ExtResource("1_b")]' in text
        # idempotent
        again = apply_operations(
            result.scene, [AddNode(path="Bullet", instance='ExtResource("1_b")')]
        )
        assert not again.results[0].changed

    def test_add_instance_requires_existing_ext_resource(self):
        with pytest.raises(OperationError, match="does not match any"):
            apply_operations(
                basic(), [AddNode(path="Bullet", instance='ExtResource("1_x")')]
            )

    def test_add_node_needs_type_or_instance(self):
        with pytest.raises(OperationError, match="exactly one of"):
            apply_operations(basic(), [AddNode(path="Bullet")])

    def test_build_scene_from_empty(self):
        from godotllminteraction.tscn.scene import Scene, SceneHeader
        from godotllminteraction.tscn.values import GInt

        scene = Scene(header=SceneHeader(attributes={"format": GInt(value=3)}))
        result = apply_operations(
            scene,
            [
                AddNode(path="Root", type="Node2D"),
                AddNode(path="Child", type="Sprite2D"),
            ],
        )
        text = dump_scene(result.scene)
        assert '[node name="Root" type="Node2D"]' in text
        assert '[node name="Child" type="Sprite2D" parent="."]' in text


class TestDeleteNode:
    def test_delete_subtree_and_connections(self):
        scene = load("connections.tscn")
        result = apply_operations(scene, [DeleteNode(path="Button")])
        assert result.scene.node("Button") is None
        assert all(
            c.from_path != "Button" and c.to_path != "Button"
            for c in result.scene.connections
        )
        assert len(result.scene.connections) == 1  # only Timer->root remains

    def test_delete_missing_is_noop(self):
        result = apply_operations(basic(), [DeleteNode(path="Ghost")])
        assert not result.results[0].changed

    def test_non_recursive_with_children_errors(self):
        with pytest.raises(OperationError, match="has children"):
            apply_operations(basic(), [DeleteNode(path="Player", recursive=False)])

    def test_delete_root_errors(self):
        with pytest.raises(OperationError, match="root"):
            apply_operations(basic(), [DeleteNode(path=".")])

    def test_delete_gcs_transitively_orphaned_sub_resources(self):
        # AnimatedSprite2D -> SpriteFrames_walk -> AtlasTexture_frame_{0,1};
        # deleting the only node referencing SpriteFrames_walk should also
        # drop the AtlasTextures it alone referenced.
        scene = load("sprite_frames.tscn")
        result = apply_operations(scene, [DeleteNode(path="AnimatedSprite2D")])
        ids = {sub.id for sub in result.scene.sub_resources}
        assert ids == set()
        # the ext_resource (a different kind) is untouched
        assert len(result.scene.ext_resources) == 1

    def test_delete_keeps_sub_resource_still_referenced_by_a_sibling(self):
        scene = load("sprite_frames.tscn")
        result = apply_operations(
            scene,
            [
                AddNode(
                    path="Other",
                    type="Sprite2D",
                    properties={"texture": 'SubResource("AtlasTexture_frame_0")'},
                ),
                DeleteNode(path="AnimatedSprite2D"),
            ],
        )
        ids = {sub.id for sub in result.scene.sub_resources}
        # SpriteFrames_walk and AtlasTexture_frame_1 are gone (only reachable
        # via the deleted node); AtlasTexture_frame_0 survives via "Other".
        assert ids == {"AtlasTexture_frame_0"}

    def test_delete_leaves_preexisting_orphan_untouched(self):
        scene = load("sprite_frames.tscn")
        # A resource nothing in the scene references, present before any op.
        first = scene.sub_resources[0]
        orphan = first.model_copy(
            update={
                "attributes": {
                    **first.attributes,
                    "id": GString(value="PreexistingOrphan"),
                }
            }
        )
        scene.sub_resources.append(orphan)
        result = apply_operations(scene, [DeleteNode(path="CollisionPolygon2D")])
        ids = {sub.id for sub in result.scene.sub_resources}
        assert "PreexistingOrphan" in ids

    def test_delete_gc_recomputes_load_steps_when_present(self):
        scene = load("sprite_frames.tscn")
        scene.header.attributes["load_steps"] = GInt(value=5)
        result = apply_operations(scene, [DeleteNode(path="AnimatedSprite2D")])
        text = dump_scene(result.scene)
        # 1 (base) + 1 ext_resource + 0 sub_resources
        assert "load_steps=2" in text


class TestUpdateProperties:
    def test_set_and_remove(self):
        result = apply_operations(
            basic(),
            [
                UpdateProperties(
                    path="Player/Sprite",
                    properties={"position": "Vector2(3, 4)", "flip_h": True},
                )
            ],
        )
        sprite = result.scene.node("Player/Sprite")
        assert "position" in sprite.properties
        removed = apply_operations(
            result.scene,
            [UpdateProperties(path="Player/Sprite", remove=["position", "flip_h"])],
        )
        assert removed.scene.node("Player/Sprite").properties == {}

    def test_missing_node_errors(self):
        with pytest.raises(OperationError, match="does not exist"):
            apply_operations(
                basic(), [UpdateProperties(path="Ghost", properties={"visible": False})]
            )

    def test_setting_same_value_is_noop(self):
        first = apply_operations(
            basic(),
            [UpdateProperties(path="Player", properties={"position": "Vector2(1, 2)"})],
        )
        second = apply_operations(
            first.scene,
            [UpdateProperties(path="Player", properties={"position": "Vector2(1, 2)"})],
        )
        assert not second.results[0].changed

    def test_unknown_property_errors_strict(self):
        with pytest.raises(OperationError, match="warp_factor"):
            apply_operations(
                basic(),
                [UpdateProperties(path="Player", properties={"warp_factor": 1})],
            )


class TestRenameAndMove:
    def test_rename_rewrites_children_connections_and_nodepaths(self):
        scene = load("ui_and_paths.tscn")
        result = apply_operations(
            scene, [RenameNode(path="PlateArea", new_name="Plate")]
        )
        out = result.scene
        assert out.node("Plate/Icon") is not None
        label = out.node("Label")
        assert label.properties["area"].value == "../Plate"

    def test_rename_to_same_name_is_noop(self):
        result = apply_operations(
            basic(), [RenameNode(path="Player", new_name="Player")]
        )
        assert not result.results[0].changed

    def test_rename_collision_errors(self):
        with pytest.raises(OperationError, match="already exists"):
            apply_operations(basic(), [RenameNode(path="Player", new_name="Enemy")])

    def test_rename_root_keeps_paths(self):
        result = apply_operations(basic(), [RenameNode(path=".", new_name="Level")])
        assert result.scene.root().name == "Level"
        assert result.scene.node("Player/Sprite") is not None

    def test_move_reparents_subtree(self):
        result = apply_operations(
            basic(), [MoveNode(path="Player/Sprite", new_parent="Enemy")]
        )
        assert result.scene.node("Enemy/Sprite") is not None
        assert result.scene.node("Player/Sprite") is None

    def test_move_rewrites_connections(self):
        scene = load("connections.tscn")
        result = apply_operations(
            scene,
            [
                AddNode(path="Holder", type="Node2D"),
                MoveNode(path="Button", new_parent="Holder"),
            ],
        )
        assert any(c.from_path == "Holder/Button" for c in result.scene.connections)

    def test_move_into_own_subtree_errors(self):
        with pytest.raises(OperationError, match="own subtree"):
            apply_operations(
                basic(), [MoveNode(path="Player", new_parent="Player/Sprite")]
            )

    def test_move_to_current_parent_is_noop(self):
        result = apply_operations(basic(), [MoveNode(path="Player", new_parent=".")])
        assert not result.results[0].changed

    def test_move_root_errors(self):
        with pytest.raises(OperationError, match="root"):
            apply_operations(basic(), [MoveNode(path=".", new_parent="Player")])

    def test_move_nodepath_rewritten_when_owner_moves(self):
        scene = load("ui_and_paths.tscn")
        result = apply_operations(
            scene, [MoveNode(path="Label", new_parent="PlateArea")]
        )
        label = result.scene.node("PlateArea/Label")
        assert label.properties["area"].value == ".."


class TestResources:
    def test_add_ext_resource_deterministic_and_idempotent(self):
        op = AddExtResource(type="Texture2D", path="res://icon.svg")
        first = apply_operations(basic(), [op])
        second = apply_operations(basic(), [op])
        assert dump_scene(first.scene) == dump_scene(second.scene)
        rid = first.results[0].allocated_ids["id"]
        assert rid.startswith("1_") and len(rid) == 7
        again = apply_operations(first.scene, [op])
        assert not again.results[0].changed
        assert again.results[0].allocated_ids["id"] == rid

    def test_add_ext_resource_explicit_id_conflict(self):
        first = apply_operations(
            basic(), [AddExtResource(type="Texture2D", path="res://icon.svg", id="1_x")]
        )
        with pytest.raises(OperationError, match="already taken"):
            apply_operations(
                first.scene,
                [AddExtResource(type="Texture2D", path="res://other.svg", id="1_x")],
            )

    def test_create_sub_resource_idempotent_by_content(self):
        op = CreateSubResource(
            type="RectangleShape2D", properties={"size": "Vector2(16, 16)"}
        )
        first = apply_operations(basic(), [op])
        rid = first.results[0].allocated_ids["id"]
        assert rid.startswith("RectangleShape2D_")
        again = apply_operations(first.scene, [op])
        assert not again.results[0].changed
        assert again.results[0].allocated_ids["id"] == rid

    def test_create_sub_resource_non_resource_type_errors(self):
        with pytest.raises(OperationError, match="not a Resource subclass"):
            apply_operations(basic(), [CreateSubResource(type="Node2D")])

    def test_load_steps_recomputed_only_when_present(self):
        with_steps = parse_scene(
            "[gd_scene load_steps=2 format=3]\n\n"
            '[ext_resource type="Texture2D" path="res://a.png" id="1_a"]\n\n'
            '[node name="Root" type="Node2D"]\n'
        )
        result = apply_operations(
            with_steps, [AddExtResource(type="Texture2D", path="res://b.png")]
        )
        assert "load_steps=3" in dump_scene(result.scene)
        without = apply_operations(
            basic(), [AddExtResource(type="Texture2D", path="res://b.png")]
        )
        assert "load_steps" not in dump_scene(without.scene)


class TestScripts:
    def test_attach_creates_ext_resource_and_sets_property(self):
        result = apply_operations(
            basic(), [AttachScript(path="Player", script_path="res://player.gd")]
        )
        text = dump_scene(result.scene)
        assert '[ext_resource type="Script" path="res://player.gd"' in text
        assert "script = ExtResource(" in text

    def test_attach_twice_is_noop(self):
        op = AttachScript(path="Player", script_path="res://player.gd")
        first = apply_operations(basic(), [op])
        second = apply_operations(first.scene, [op])
        assert not second.results[0].changed

    def test_detach_removes_property_and_orphan_resource(self):
        attached = apply_operations(
            basic(), [AttachScript(path="Player", script_path="res://player.gd")]
        )
        detached = apply_operations(attached.scene, [DetachScript(path="Player")])
        assert dump_scene(detached.scene) == BASIC

    def test_detach_keeps_shared_script_resource(self):
        both = apply_operations(
            basic(),
            [
                AttachScript(path="Player", script_path="res://x.gd"),
                AttachScript(path="Enemy", script_path="res://x.gd"),
            ],
        )
        one_detached = apply_operations(both.scene, [DetachScript(path="Player")])
        assert len(one_detached.scene.ext_resources) == 1

    def test_detach_without_script_is_noop(self):
        result = apply_operations(basic(), [DetachScript(path="Player")])
        assert not result.results[0].changed


class TestSignals:
    def test_connect_and_disconnect(self):
        connected = apply_operations(
            basic(),
            [
                ConnectSignal(
                    **{
                        "from": "Enemy",
                        "to": ".",
                        "signal": "body_entered",
                        "method": "_on_body",
                    }
                )
            ],
        )
        assert len(connected.scene.connections) == 1
        assert (
            '[connection signal="body_entered" from="Enemy" to="." method="_on_body"]'
            in dump_scene(connected.scene)
        )
        disconnected = apply_operations(
            connected.scene,
            [
                DisconnectSignal(
                    **{
                        "from": "Enemy",
                        "to": ".",
                        "signal": "body_entered",
                        "method": "_on_body",
                    }
                )
            ],
        )
        assert dump_scene(disconnected.scene) == BASIC

    def test_connect_duplicate_is_noop(self):
        op = ConnectSignal(
            **{
                "from": "Enemy",
                "to": ".",
                "signal": "body_entered",
                "method": "_on_body",
            }
        )
        first = apply_operations(basic(), [op])
        second = apply_operations(first.scene, [op])
        assert not second.results[0].changed

    def test_connect_unknown_signal_errors(self):
        with pytest.raises(OperationError, match="has no signal"):
            apply_operations(
                basic(),
                [
                    ConnectSignal(
                        **{"from": "Enemy", "to": ".", "signal": "nope", "method": "_m"}
                    )
                ],
            )

    def test_disconnect_missing_is_noop(self):
        result = apply_operations(
            basic(),
            [
                DisconnectSignal(
                    **{
                        "from": "Enemy",
                        "to": ".",
                        "signal": "body_entered",
                        "method": "_m",
                    }
                )
            ],
        )
        assert not result.results[0].changed


class TestInvariants:
    """The determinism and idempotency contracts from the design doc."""

    @pytest.mark.parametrize(
        "fixture", ["sprite_frames.tscn", "ui_and_paths.tscn", "connections.tscn"]
    )
    def test_add_then_delete_restores_original_bytes(self, fixture):
        original = (_SCENES / fixture).read_text()
        scene = parse_scene(original)
        added = apply_operations(
            scene,
            [
                AddNode(
                    path="TempNode",
                    type="Node2D",
                    properties={"position": "Vector2(5, 5)"},
                )
            ],
        )
        deleted = apply_operations(added.scene, [DeleteNode(path="TempNode")])
        assert dump_scene(deleted.scene) == original

    def test_apply_same_ops_twice_is_byte_identical_and_all_noops(self):
        ops = [
            AddExtResource(type="Texture2D", path="res://icon.svg"),
            AddNode(path="Turret", type="Node2D", properties={"z_index": 2}),
            AddNode(path="Turret/Shape", type="CollisionShape2D"),
            UpdateProperties(path="Player", properties={"position": "Vector2(7, 8)"}),
            AttachScript(path="Turret", script_path="res://turret.gd"),
            ConnectSignal(
                **{
                    "from": "Enemy",
                    "to": ".",
                    "signal": "body_entered",
                    "method": "_on_body",
                }
            ),
        ]
        first = apply_operations(basic(), ops)
        second = apply_operations(first.scene, ops)
        assert dump_scene(second.scene) == dump_scene(first.scene)
        assert all(not r.changed for r in second.results)

    def test_failed_batch_leaves_input_scene_untouched(self):
        scene = basic()
        before = dump_scene(scene)
        with pytest.raises(OperationError, match="operation 2"):
            apply_operations(
                scene,
                [
                    AddNode(path="Ok", type="Node2D"),
                    AddNode(path="Ghost/Child", type="Node2D"),
                ],
            )
        assert dump_scene(scene) == before

    def test_attach_then_detach_restores_original_bytes(self):
        original = (_SCENES / "connections.tscn").read_text()
        scene = parse_scene(original)
        attached = apply_operations(
            scene, [AttachScript(path="Button", script_path="res://b.gd")]
        )
        detached = apply_operations(attached.scene, [DetachScript(path="Button")])
        assert dump_scene(detached.scene) == original
