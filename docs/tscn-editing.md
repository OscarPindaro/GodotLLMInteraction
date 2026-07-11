# Editing .tscn scenes with `gli tscn`

The `godotllminteraction.tscn` package parses, edits, validates, and writes
Godot 4 scene files. The `gli tscn` commands are a thin CLI over it; the same
API can be used directly from Python (`from godotllminteraction import tscn`).

## Commands

```bash
gli tscn apply ops.yaml [--scene PATH] [--output PATH] [--dry-run] [--no-strict] [--json]
gli tscn tree scene.tscn [--detail nodes|resources|properties] [--json]
gli tscn validate res://scenes/door.tscn [--project DIR] [--godot PATH] [--json]
```

- `apply` runs a YAML operations file (below). All-or-nothing: if any
  operation fails, nothing is written.
- `tree` prints the node tree; `resources` adds each node's resource
  references, `properties` adds every set property.
- `validate` shells out to Godot (`--headless --check-only`). The executable
  is found via `--godot`, then `GODOT_BINARY`, then PATH, then common install
  locations.
- `--json` on any command prints a machine-readable result on stdout.

## Operations file

```yaml
scene: scenes/door.tscn        # file to edit (or use `create:` for a new scene)
# create: {root_name: Level, root_type: Node2D}
output: out/door_edited.tscn   # optional; default is in-place
strict: true                   # spec-validation errors abort (default)
operations:
  - op: add_ext_resource
    type: Texture2D
    path: res://asset/tilemap_packed.png
    ref: sheet                 # symbolic handle usable in later operations
  - op: create_sub_resource
    type: RectangleShape2D
    ref: shape
    properties: { size: "Vector2(16, 16)" }
  - op: add_node
    path: Door/Hinge           # nodes are addressed by scene path; "." is the root
    type: Sprite2D
    properties:
      texture: { ext_resource: sheet }
      position: "Vector2(8, 0)"
  - op: add_node
    path: Prop
    instance: { ext_resource: sheet }   # instanced scene instead of `type`
  - op: update_properties
    path: Door/Hinge
    properties: { rotation: 1.5 }
    remove: [position]
  - op: attach_script
    path: Door
    script_path: res://door.gd
  - op: connect_signal
    from: Door/Area
    to: Door
    signal: body_entered
    method: _on_body_entered
```

Property values are Godot literal syntax as strings (`"Vector2(1, 2)"`,
`'"text"'`, `"PackedVector2Array(0, 0, 16, 0)"`), or plain YAML
numbers/booleans. `{ext_resource: NAME}` / `{sub_resource: NAME}` resolve to
the id allocated by the earlier operation that declared `ref: NAME`.

The full operation set: `add_node`, `delete_node`, `update_properties`,
`rename_node`, `move_node`, `attach_script`, `detach_script`,
`add_ext_resource`, `create_sub_resource`, `connect_signal`,
`disconnect_signal`. Every field carries a description in its pydantic
model (`operations.py`) — that is the reference for exact shapes.

## Ids: which ones to touch

- **Ext/sub resource `id`** (scene-local, used by `ExtResource("...")` /
  `SubResource("...")`): free to choose. Leave unset for a generated
  Godot-shaped id, or pick readable names (`id: tile_atlas`,
  `id: player_shape`) — this is the right place for human/LLM-friendly
  naming.
- **Node `unique_id`** (integer node-heading attribute, Godot 4.6+): leave it
  alone. The editor assigns one on the next save; the tool preserves existing
  ones and only writes one if you explicitly pass `unique_id:` on `add_node`.
- **`uid` (`uid://...`)**: never written by the tool. These belong to Godot's
  asset database (.uid / .import metadata); the editor fills them in.

Scene paths (`Player/Sprite`, `.` for the root) and `res://` paths have
pathlib-style helper types in the Python API: `tscn.ScenePath` (join with
`/`, `.parent`, `.rebase()`, NodePath resolution) and `tscn.ResPath`
(`.to_filesystem(project_root)` / `.from_filesystem(...)` conversion).

## Guarantees

- **Round-trip fidelity**: parsing a scene and writing it back is
  byte-for-byte identical (tested against every scene in this repo).
- **Determinism**: no randomness anywhere. Generated resource ids are
  hash-derived, so the same operation on the same scene always produces the
  identical file.
- **Idempotency**: every operation describes a desired state. Re-applying an
  ops file is a byte-identical no-op; adding then deleting a node restores
  the original file exactly.
- **Validation**: node classes, properties (walking inheritance), value
  types, resource-reference types, and signal names are checked against the
  generated spec models in `specifications/v4_7_0/`. Properties the spec
  can't see (script-exported variables, `metadata/*`, instanced nodes)
  degrade to warnings instead of errors. `rename_node`/`move_node` rewrite
  descendant paths, connections, and relative NodePath property values
  exactly.

## Updating to a new Godot version

Dump the new API and regenerate; nothing in the tscn package needs editing:

```bash
godot --headless --dump-extension-api --quit
uv run gli specifications generate-all --version v4_8_0
```

Then build a provider from the new modules (`SpecProvider(classes, builtin_classes, signals.SIGNALS)`)
or repoint `default_provider`.

## Tests

`tests/data/scenes/` holds self-contained fixture scenes (open them in the
editor to verify them); `tests/data/tscn_scenarios/` holds YAML end-to-end
scenarios. Set `GLI_SCENARIO_OUT_DIR=out/tscn_scenarios` to dump scenario
outputs for inspection. `tests/integration/tscn_godot_check_test.py` runs
Godot's own check on everything the library produces (skipped without a
Godot binary).
