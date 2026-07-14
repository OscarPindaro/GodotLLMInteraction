---
trigger: always
---
# Using the gli MCP Server

The `gli` MCP server exposes tools for creating, inspecting, and editing
Godot scenes and resources. Prefer these tools over hand-writing `.tscn`
files or raw CLI calls — they validate against the Godot spec and guarantee
round-trip fidelity.

## Setup

Call `set_godot_version` once at the start of a session (e.g. `4.7.0`) so
spec queries resolve correctly. Call `set_project` if doing KB operations
on a project other than the workspace root.

## Creating Scenes

Always use `create_scene` to make a new `.tscn` file. It accepts a tree
format (indentation-based) or JSON spec, validates node types and
properties, and produces a correct file. Never hand-write a `.tscn` from
scratch — `create_scene` guarantees the header, resource format, and node
structure are valid.

## Inspecting Scenes

Use `tree` to read a scene's node hierarchy. Pass `detail: "properties"`
when you need to see every set property, or `detail: "resources"` to trace
resource references. This is the read path — use it before editing to
understand the current structure.

## Editing Scenes

Use the granular editing tools for single changes:

- `add_node` / `delete_node` / `move_node` / `rename_node` — node tree
  manipulation. Paths are scene paths (`Player/Sprite`, `.` for root).
- `update_properties` — set or remove properties on a node. Values use
  Godot literal syntax (`"Vector2(8, 0)"`, `"Color(1, 0, 0)"`).
- `attach_script` / `detach_script` — bind a `.gd` script to a node.
- `add_ext_resource` / `create_sub_resource` — declare external file
  references or embed sub-resources (shapes, atlases, etc.).
- `connect_signal` / `disconnect_signal` — wire signals between nodes.

For **batch edits** (especially when creating a resource and referencing
it in the same operation), write a YAML ops file and use `apply_ops_file`.
It is all-or-nothing and idempotent — re-applying is a safe no-op.

## Querying the Godot API

Use `get_godot_spec` to look up a class's properties, signals, and
inheritance chain before setting properties or connecting signals. This
avoids guessing property names or types. Always check the spec when unsure
whether a property exists or what type it expects.

## Images and Tilemaps

- `image_info` — get dimensions, format, and mode of an image file.
- `tile_grid` — compute columns/rows/total tiles for a tilemap image.
- `tile_region` — compute the pixel `Rect2` for a specific tile.

Use these before assigning atlas regions or configuring TileMapLayers.

## Validation

Use `validate` to run Godot's own `--check-only` on a scene or
`project.godot`. Do this after non-trivial edits to catch errors the
spec validation may not cover (script load failures, broken references).

## Knowledge Base

The KB tools (`kb_register`, `kb_search`, `kb_list`, `kb_remove`) store
question-linked answers (text, files, folders, GitHub URLs) for the
project. Use `kb_search` to find prior solutions before re-deriving them.
