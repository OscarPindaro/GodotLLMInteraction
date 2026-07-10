# Creating AnimatedSprite2D Scenes in Godot

This guide collects the conventions and workflow used when creating `.tscn` scenes with `AnimatedSprite2D` nodes in this project.

---

## 1. Use the `godotllminteraction` CLI to inspect tilemaps

Before writing `.tscn` files by hand, use the project CLI to get the exact numbers from the source image:

```bash
uv run godotllminteraction info asset/tilemap_packed.png
uv run godotllminteraction tiles asset/tilemap_packed.png
uv run godotllminteraction region asset/tilemap_packed.png <col> <row>
```

The `region` command prints the ready-to-paste `Rect2(x, y, width, height)` value for any tile index.

---

## 2. Scene structure

A typical animated scene uses this hierarchy:

```text
Node2D                       <- root node, named after the entity ("Door", "Player", ...)
└── AnimatedSprite2D         <- the visible animated part
```

This keeps the root as a plain container and the animation logic in a child `AnimatedSprite2D`.

---

## 3. Naming convention

### Root node
Use the PascalCase name of the entity:

- `Door`
- `ManualDoor`
- `Chest`

### Sub-resource IDs
Give every sub-resource a **human-readable, semantically meaningful ID**. This makes the `.tscn` diff-friendly and easy to inspect.

| Type | Bad ID | Good ID |
|------|--------|---------|
| External texture | `1_cuq2a` | `1_tilemap` |
| AtlasTexture | `AtlasTexture_8jjlj` | `AtlasTexture_door_0` |
| SpriteFrames | `SpriteFrames_10sb8` | `SpriteFrames_door` |

For animation frames, number them from `0` and prefix with the entity name:

```text
AtlasTexture_door_0
AtlasTexture_door_1
AtlasTexture_door_2
AtlasTexture_door_3
```

Do not let Godot's auto-generated IDs sit in committed `.tscn` files.

---

## 4. Ordering of sub-resources

Keep the order natural to the animation timeline:

1. `ext_resource` for the atlas texture
2. `AtlasTexture` sub-resources in frame order
3. `SpriteFrames` sub-resource that references them
4. `node` blocks

This makes the file easier to read and keeps diffs predictable.

---

## 5. AtlasTexture regions

Every `AtlasTexture` must declare a `region` in `Rect2(x, y, width, height)` form.

For a tilemap with `tile_width` and `tile_height` in pixels, the tile at column `c` and row `r` has:

```text
Rect2(c * tile_width, r * tile_height, tile_width, tile_height)
```

Verify the tile size first with the CLI or by dividing image dimensions by tile count.

Example (16×16 tilemap, column 9, rows 0-3):

```
[sub_resource type="AtlasTexture" id="AtlasTexture_door_0"]
atlas = ExtResource("1_tilemap")
region = Rect2(144, 0, 16, 16)
```

---

## 6. SpriteFrames definition

One animation per sequence. Use `"loop": 1` (or `true`) for repeating animations, `"loop": 0` (or `false`) for one-shot.

The default animation name should be `&"default"`. Set `"autoplay": "default"` on the `AnimatedSprite2D` to start it automatically.

```
[sub_resource type="SpriteFrames" id="SpriteFrames_door"]
animations = [{
"frames": [{
"duration": 1.0,
"texture": SubResource("AtlasTexture_door_0")
}, {
"duration": 1.0,
"texture": SubResource("AtlasTexture_door_1")
}, {
"duration": 1.0,
"texture": SubResource("AtlasTexture_door_2")
}, {
"duration": 1.0,
"texture": SubResource("AtlasTexture_door_3")
}],
"loop": 1,
"name": &"default",
"speed": 5.0
}]
```

Keep all durations equal for simple frames unless a specific timing is intended.

---

## 7. Node block

```
[node name="Door" type="Node2D"]

[node name="AnimatedSprite2D" type="AnimatedSprite2D" parent="."]
sprite_frames = SubResource("SpriteFrames_door")
animation = &"default"
autoplay = "default"
```

- `animation` points to the animation name.
- `autoplay` starts the animation when the scene loads.

If `autoplay` is omitted, the first frame of the default animation is shown but the animation does not play until `play()` is called from code.

---

## 8. Avoid committing editor-captured state

After opening a scene in the Godot editor, fields like `frame_progress`, `unique_id`, and `metadata/_edit_group_` may appear. Do not commit these unless they are necessary:

- `frame_progress` is a runtime/editor capture.
- `unique_id` is random per node and changes on re-save.
- `uid` values on `ext_resource` are assigned by Godot; do not invent random ones.

For hand-written scenes, leave the `uid` on `[gd_scene]` and `ext_resource` absent unless Godot has already imported them. Godot will assign consistent UIDs when the project loads.

---

## 9. Full minimal example

`scenes/door.tscn`:

```
[gd_scene format=3]

[ext_resource type="Texture2D" path="res://asset/tilemap_packed.png" id="1_tilemap"]

[sub_resource type="AtlasTexture" id="AtlasTexture_door_0"]
atlas = ExtResource("1_tilemap")
region = Rect2(144, 0, 16, 16)

[sub_resource type="AtlasTexture" id="AtlasTexture_door_1"]
atlas = ExtResource("1_tilemap")
region = Rect2(144, 16, 16, 16)

[sub_resource type="AtlasTexture" id="AtlasTexture_door_2"]
atlas = ExtResource("1_tilemap")
region = Rect2(144, 32, 16, 16)

[sub_resource type="AtlasTexture" id="AtlasTexture_door_3"]
atlas = ExtResource("1_tilemap")
region = Rect2(144, 48, 16, 16)

[sub_resource type="SpriteFrames" id="SpriteFrames_door"]
animations = [{
"frames": [{
"duration": 1.0,
"texture": SubResource("AtlasTexture_door_0")
}, {
"duration": 1.0,
"texture": SubResource("AtlasTexture_door_1")
}, {
"duration": 1.0,
"texture": SubResource("AtlasTexture_door_2")
}, {
"duration": 1.0,
"texture": SubResource("AtlasTexture_door_3")
}],
"loop": 1,
"name": &"default",
"speed": 5.0
}]

[node name="Door" type="Node2D"]

[node name="AnimatedSprite2D" type="AnimatedSprite2D" parent="."]
sprite_frames = SubResource("SpriteFrames_door")
animation = &"default"
autoplay = "default"
```

---

## 10. Checklist

- [ ] Tile size verified (use `godotllminteraction tiles`)
- [ ] Frames are ordered correctly
- [ ] `Rect2` regions are exact (use `godotllminteraction region`)
- [ ] Sub-resource IDs are human-readable
- [ ] Root node is `Node2D` and named after the entity
- [ ] `AnimatedSprite2D` is a child with `autoplay = "default"` when needed
- [ ] No random/editor-generated UIDs or unique IDs invented by hand
