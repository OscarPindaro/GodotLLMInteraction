from __future__ import annotations

from pathlib import Path

import pytest

from godotllminteraction.tscn.exceptions import OperationError
from godotllminteraction.tscn.operations import (
    AddAnimation,
    AddExtResource,
    AddNode,
    AddSpriteFrames,
    AddSpriteImage,
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

    def test_add_sprite_image_then_delete_removes_node_and_sub_resource(self):
        # delete_node GCs sub_resources orphaned by the deletion, but never
        # touches ext_resources (same contract as every other op) — so the
        # texture ext_resource is expected to remain afterwards.
        added = apply_operations(
            basic(),
            [
                AddSpriteImage(
                    texture="res://tests/data/assets/atlas.png",
                    cell=(1, 8),
                    node="Knight",
                    mode="atlas",
                )
            ],
        )
        assert len(added.scene.sub_resources) == 1
        deleted = apply_operations(added.scene, [DeleteNode(path="Knight")])
        assert deleted.scene.node("Knight") is None
        assert deleted.scene.sub_resources == []
        assert len(deleted.scene.ext_resources) == 1


class TestAddSpriteImage:
    TEXTURE = "res://tests/data/assets/atlas.png"

    def test_region_mode_sets_region_rect_and_texture(self):
        result = apply_operations(
            basic(),
            [
                AddSpriteImage(
                    texture=self.TEXTURE, cell=(1, 8), node="Knight", texture_filter=0
                )
            ],
        )
        node = result.scene.node("Knight")
        assert node is not None
        assert node.type == "Sprite2D"
        text = dump_scene(result.scene)
        assert "region_enabled = true" in text
        assert "region_rect = Rect2(16, 128, 16, 16)" in text
        assert "texture_filter = 0" in text
        assert "sub_resource" not in text

    def test_atlas_mode_creates_sub_resource_and_wires(self):
        result = apply_operations(
            basic(),
            [
                AddSpriteImage(
                    texture=self.TEXTURE, cell=(1, 8), node="Knight", mode="atlas"
                )
            ],
        )
        node = result.scene.node("Knight")
        assert node is not None
        assert len(result.scene.sub_resources) == 1
        sub = result.scene.sub_resources[0]
        assert sub.type == "AtlasTexture"
        text = dump_scene(result.scene)
        assert f'texture = SubResource("{sub.id}")' in text
        assert "region = Rect2(16, 128, 16, 16)" in text

    def test_node_none_creates_resource_only(self):
        scene = basic()
        before_nodes = len(scene.nodes)
        result = apply_operations(
            scene,
            [AddSpriteImage(texture=self.TEXTURE, cell=(1, 8), mode="atlas")],
        )
        assert len(result.scene.nodes) == before_nodes
        assert len(result.scene.sub_resources) == 1

    def test_auto_create_sprite2d_if_missing(self):
        result = apply_operations(
            basic(),
            [AddSpriteImage(texture=self.TEXTURE, cell=(0, 0), node="Knight")],
        )
        node = result.scene.node("Knight")
        assert node is not None
        assert node.type == "Sprite2D"
        assert node.parent == "."

    def test_auto_create_sets_texture_filter_nearest(self):
        result = apply_operations(
            basic(),
            [
                AddSpriteImage(
                    texture=self.TEXTURE, cell=(0, 0), node="Knight", texture_filter=0
                )
            ],
        )
        assert "texture_filter = 0" in dump_scene(result.scene)

    def test_texture_filter_string_mapped(self):
        result = apply_operations(
            basic(),
            [
                AddSpriteImage(
                    texture=self.TEXTURE,
                    cell=(0, 0),
                    node="Knight",
                    texture_filter="linear",
                )
            ],
        )
        assert "texture_filter = 1" in dump_scene(result.scene)

    def test_texture_filter_int_passthrough(self):
        result = apply_operations(
            basic(),
            [
                AddSpriteImage(
                    texture=self.TEXTURE, cell=(0, 0), node="Knight", texture_filter=2
                )
            ],
        )
        assert "texture_filter = 2" in dump_scene(result.scene)

    def test_texture_filter_unknown_string_errors(self):
        with pytest.raises(OperationError, match="unknown texture_filter"):
            apply_operations(
                basic(),
                [
                    AddSpriteImage(
                        texture=self.TEXTURE,
                        cell=(0, 0),
                        node="Knight",
                        texture_filter="bogus",
                    )
                ],
            )

    def test_dedup_reuses_existing_atlas_texture(self):
        op = AddSpriteImage(texture=self.TEXTURE, cell=(1, 8), mode="atlas")
        first = apply_operations(basic(), [op])
        rid = first.results[0].allocated_ids["sub_resource_id"]
        again = apply_operations(first.scene, [op])
        assert not again.results[0].changed
        assert again.results[0].allocated_ids["sub_resource_id"] == rid
        assert len(again.scene.sub_resources) == 1

    def test_dedup_different_region_creates_new(self):
        scene = basic()
        result = apply_operations(
            scene,
            [
                AddSpriteImage(texture=self.TEXTURE, cell=(1, 8), mode="atlas"),
                AddSpriteImage(texture=self.TEXTURE, cell=(2, 8), mode="atlas"),
            ],
        )
        assert len(result.scene.sub_resources) == 2

    def test_dedup_with_readable_id(self):
        first = apply_operations(
            basic(),
            [
                AddSpriteImage(
                    texture=self.TEXTURE, cell=(1, 8), mode="atlas", id="knight"
                )
            ],
        )
        again = apply_operations(
            first.scene,
            [AddSpriteImage(texture=self.TEXTURE, cell=(1, 8), mode="atlas")],
        )
        assert not again.results[0].changed
        assert again.results[0].allocated_ids["sub_resource_id"] == "knight"

    def test_ext_resource_dedup_by_path(self):
        result = apply_operations(
            basic(),
            [
                AddSpriteImage(texture=self.TEXTURE, cell=(1, 8), node="A"),
                AddSpriteImage(texture=self.TEXTURE, cell=(2, 8), node="B"),
            ],
        )
        assert len(result.scene.ext_resources) == 1

    def test_custom_texture_type(self):
        result = apply_operations(
            basic(),
            [
                AddSpriteImage(
                    texture="res://custom/my_texture.tres",
                    cell=(0, 0),
                    mode="atlas",
                    texture_type="MyCustomTexture",
                )
            ],
        )
        assert result.scene.ext_resources[0].type == "MyCustomTexture"

    def test_node_property_encoding(self):
        scene = basic()
        # Create a Chest node and attach a script so the custom property
        # 'closed_texture' is accepted as script-exported.
        prepared = apply_operations(
            scene,
            [
                AddNode(path="Chest", type="Sprite2D"),
                AttachScript(path="Chest", script_path="res://chest.gd"),
            ],
        )
        result = apply_operations(
            prepared.scene,
            [
                AddSpriteImage(
                    texture=self.TEXTURE,
                    cell=(1, 8),
                    node="Chest.closed_texture",
                    mode="atlas",
                )
            ],
        )
        node = result.scene.node("Chest")
        assert node is not None
        sub_id = result.scene.sub_resources[0].id
        assert node.properties["closed_texture"].args[0].value == sub_id

    def test_smart_node_lookup_by_name_unique(self):
        result = apply_operations(
            basic(),
            [AddSpriteImage(texture=self.TEXTURE, cell=(1, 8), node="Sprite")],
        )
        node = result.scene.node("Player/Sprite")
        assert node is not None
        assert "texture" in node.properties

    def test_smart_node_lookup_ambiguous_errors(self):
        scene = basic()
        prepared = apply_operations(
            scene,
            [
                AddNode(path="Other", type="Node2D"),
                AddNode(path="Other/Sprite", type="Sprite2D"),
            ],
        )
        with pytest.raises(OperationError, match="ambiguous"):
            apply_operations(
                prepared.scene,
                [AddSpriteImage(texture=self.TEXTURE, cell=(1, 8), node="Sprite")],
            )

    def test_region_mode_requires_node(self):
        with pytest.raises(OperationError, match="requires 'node'"):
            apply_operations(
                basic(),
                [AddSpriteImage(texture=self.TEXTURE, cell=(1, 8), node=None)],
            )

    def test_region_mode_property_encoding_errors(self):
        with pytest.raises(OperationError, match="only supports the built-in"):
            apply_operations(
                basic(),
                [
                    AddSpriteImage(
                        texture=self.TEXTURE,
                        cell=(1, 8),
                        node="Knight.other_texture",
                    )
                ],
            )

    def test_margin_and_spacing_in_region(self):
        result = apply_operations(
            basic(),
            [
                AddSpriteImage(
                    texture=self.TEXTURE,
                    cell=(1, 1),
                    node="Knight",
                    margin=2,
                    spacing=1,
                )
            ],
        )
        assert "region_rect = Rect2(19, 19, 16, 16)" in dump_scene(result.scene)

    def test_apply_twice_byte_identical_region_mode(self):
        op = AddSpriteImage(texture=self.TEXTURE, cell=(1, 8), node="Knight")
        first = apply_operations(basic(), [op])
        second = apply_operations(first.scene, [op])
        assert dump_scene(second.scene) == dump_scene(first.scene)
        assert all(not r.changed for r in second.results)

    def test_apply_twice_byte_identical_atlas_mode(self):
        op = AddSpriteImage(
            texture=self.TEXTURE, cell=(1, 8), node="Knight", mode="atlas"
        )
        first = apply_operations(basic(), [op])
        second = apply_operations(first.scene, [op])
        assert dump_scene(second.scene) == dump_scene(first.scene)
        assert all(not r.changed for r in second.results)


class TestAddSpriteFrames:
    TEXTURE = "res://tests/data/assets/atlas.png"

    def test_creates_sprite_frames_with_empty_animations(self):
        result = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        text = dump_scene(result.scene)
        assert '[sub_resource type="SpriteFrames" id="frames_walk"]' in text
        assert "animations = []" in text
        assert result.results[0].changed

    def test_with_node_auto_creates_animated_sprite_2d(self):
        result = apply_operations(
            basic(),
            [AddSpriteFrames(id="frames_walk", node="Hero")],
        )
        node = result.scene.node("Hero")
        assert node is not None
        assert node.type == "AnimatedSprite2D"
        text = dump_scene(result.scene)
        assert 'sprite_frames = SubResource("frames_walk")' in text

    def test_with_autoplay_sets_autoplay(self):
        result = apply_operations(
            basic(),
            [AddSpriteFrames(id="frames_walk", node="Hero", autoplay="default")],
        )
        node = result.scene.node("Hero")
        assert node is not None
        text = dump_scene(result.scene)
        assert 'autoplay = "default"' in text

    def test_autoplay_without_node_ignored(self):
        result = apply_operations(
            basic(),
            [AddSpriteFrames(id="frames_walk", autoplay="default")],
        )
        text = dump_scene(result.scene)
        assert "autoplay" not in text

    def test_idempotent(self):
        op = AddSpriteFrames(id="frames_walk", node="Hero")
        first = apply_operations(basic(), [op])
        second = apply_operations(first.scene, [op])
        assert dump_scene(second.scene) == dump_scene(first.scene)
        assert all(not r.changed for r in second.results)

    def test_existing_node_wires_sprite_frames(self):
        scene = basic()
        prepared = apply_operations(
            scene, [AddNode(path="Hero", type="AnimatedSprite2D")]
        )
        result = apply_operations(
            prepared.scene, [AddSpriteFrames(id="frames_walk", node="Hero")]
        )
        node = result.scene.node("Hero")
        assert node is not None
        text = dump_scene(result.scene)
        assert 'sprite_frames = SubResource("frames_walk")' in text


class TestAddAnimation:
    TEXTURE = "res://tests/data/assets/atlas.png"

    def test_atlas_mode_adds_animation(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        result = apply_operations(
            prepared.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="default",
                    texture=self.TEXTURE,
                    frames=[[0, 0], [1, 0]],
                )
            ],
        )
        text = dump_scene(result.scene)
        assert '"name": &"default"' in text
        assert "SubResource(" in text
        assert "AtlasTexture" in text
        assert '"speed": 5.0' in text
        assert '"loop": 1' in text

    def test_atlas_mode_creates_atlas_textures(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        result = apply_operations(
            prepared.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="default",
                    texture=self.TEXTURE,
                    frames=[[0, 0], [1, 0]],
                )
            ],
        )
        atlas_subs = [s for s in result.scene.sub_resources if s.type == "AtlasTexture"]
        assert len(atlas_subs) == 2

    def test_atlas_mode_dedup_reuses_atlas_texture(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        result = apply_operations(
            prepared.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="default",
                    texture=self.TEXTURE,
                    frames=[[0, 0], [0, 0]],
                )
            ],
        )
        atlas_subs = [s for s in result.scene.sub_resources if s.type == "AtlasTexture"]
        assert len(atlas_subs) == 1

    def test_atlas_mode_with_id_prefix(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        result = apply_operations(
            prepared.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="default",
                    texture=self.TEXTURE,
                    frames=[[0, 0], [1, 0]],
                    id_prefix="walk",
                )
            ],
        )
        text = dump_scene(result.scene)
        assert 'id="walk_0_0"' in text
        assert 'id="walk_1_0"' in text

    def test_whole_image_mode_adds_animation(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        result = apply_operations(
            prepared.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="idle",
                    texture=None,
                    frames=["res://frame0.png", "res://frame1.png"],
                )
            ],
        )
        text = dump_scene(result.scene)
        assert '"name": &"idle"' in text
        assert "ExtResource(" in text
        # No AtlasTexture in whole-image mode
        assert "AtlasTexture" not in text

    def test_whole_image_mode_creates_ext_resources(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        result = apply_operations(
            prepared.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="idle",
                    texture=None,
                    frames=["res://frame0.png", "res://frame1.png"],
                )
            ],
        )
        ext_paths = {e.path for e in result.scene.ext_resources}
        assert "res://frame0.png" in ext_paths
        assert "res://frame1.png" in ext_paths

    def test_replaces_animation_with_same_name(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        first = apply_operations(
            prepared.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="default",
                    texture=self.TEXTURE,
                    frames=[[0, 0]],
                )
            ],
        )
        second = apply_operations(
            first.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="default",
                    texture=self.TEXTURE,
                    frames=[[1, 0]],
                )
            ],
        )
        text = dump_scene(second.scene)
        # Should have only one animation named "default"
        assert text.count('&"default"') == 1

    def test_durations_mismatch_errors(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        with pytest.raises(OperationError, match="durations has"):
            apply_operations(
                prepared.scene,
                [
                    AddAnimation(
                        sprite_frames_id="frames_walk",
                        name="default",
                        texture=self.TEXTURE,
                        frames=[[0, 0], [1, 0]],
                        durations=[1.0],
                    )
                ],
            )

    def test_missing_sprite_frames_id_errors(self):
        with pytest.raises(OperationError, match="not found"):
            apply_operations(
                basic(),
                [
                    AddAnimation(
                        sprite_frames_id="nonexistent",
                        name="default",
                        texture=self.TEXTURE,
                        frames=[[0, 0]],
                        auto_create=False,
                    )
                ],
            )

    def test_auto_create_creates_sprite_frames(self):
        result = apply_operations(
            basic(),
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="default",
                    texture=self.TEXTURE,
                    frames=[[0, 0]],
                    auto_create=True,
                )
            ],
        )
        text = dump_scene(result.scene)
        assert '[sub_resource type="SpriteFrames" id="frames_walk"]' in text
        assert '"name": &"default"' in text

    def test_auto_create_idempotent(self):
        op = AddAnimation(
            sprite_frames_id="frames_walk",
            name="default",
            texture=self.TEXTURE,
            frames=[[0, 0], [1, 0]],
            auto_create=True,
        )
        first = apply_operations(basic(), [op])
        second = apply_operations(first.scene, [op])
        assert dump_scene(second.scene) == dump_scene(first.scene)
        assert all(not r.changed for r in second.results)

    def test_idempotent_same_animation(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        op = AddAnimation(
            sprite_frames_id="frames_walk",
            name="default",
            texture=self.TEXTURE,
            frames=[[0, 0], [1, 0]],
        )
        first = apply_operations(prepared.scene, [op])
        second = apply_operations(first.scene, [op])
        assert dump_scene(second.scene) == dump_scene(first.scene)
        assert all(not r.changed for r in second.results)

    def test_durations_applied(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        result = apply_operations(
            prepared.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="default",
                    texture=self.TEXTURE,
                    frames=[[0, 0], [1, 0]],
                    durations=[0.5, 2.0],
                )
            ],
        )
        text = dump_scene(result.scene)
        assert '"duration": 0.5' in text
        assert '"duration": 2.0' in text

    def test_no_loop(self):
        prepared = apply_operations(basic(), [AddSpriteFrames(id="frames_walk")])
        result = apply_operations(
            prepared.scene,
            [
                AddAnimation(
                    sprite_frames_id="frames_walk",
                    name="default",
                    texture=self.TEXTURE,
                    frames=[[0, 0]],
                    loop=False,
                )
            ],
        )
        text = dump_scene(result.scene)
        assert '"loop": 0' in text
