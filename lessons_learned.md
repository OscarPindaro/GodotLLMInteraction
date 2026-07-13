# Hero RPG — Lessons Learned

Notes from the first implementation pass. These are retrospective observations
to apply next time, not input requirements.

## Architecture: top-down vs bottom-up

The hero_rpg was built **bottom-up**: each gamepiece manages its own movement
via a `Path2D` + `PathFollow2D` + runtime curve. The piece itself owns the
curve, sets waypoints, and emits `arrived` when done. A manager
(TurnClock/GamepieceRegistry) coordinates turns but doesn't own movement.

**Alternative — top-down:** a single game manager owns all movement. Pieces are
plain `Node2D` with a sprite. The manager computes paths, tweens positions, and
notifies pieces when they arrive. This is simpler to reason about (one place
for all movement logic) and avoids the unusual `Path2D`-as-root-node pattern.

**Lesson for next time:** decide the architecture approach upfront and document
it. The bottom-up approach works but leads to surprising node hierarchies (a
"knight" IS a Path2D, which is weird to read). Top-down would have been more
intuitive: a `Knight (Node2D)` managed by a `MovementManager` that does the
pathing and tweening.

**Main point — node identity:** identifying a gamepiece with a top node that is
a `Path2D` is very counter-intuitive. A gamepiece is conceptually a character,
not a path. The node hierarchy should reflect what the thing IS, not what
mechanism it uses internally. A more intuitive structure:

```
Knight (Node2D / CharacterBody2D)   ← this IS the piece
├── Sprite2D                         ← its appearance
├── Path2D                           ← movement mechanism (if using Path2D)
│   └── PathFollow2D
└── WeaponMarker
```

vs what we have:

```
Knight (Path2D)                      ← this IS a path???
└── PathFollow2D
    └── Sprite2D
```

If using `Path2D`/`PathFollow2D` for movement, they should be children of the
gamepiece node, not the root. If using a `Tween`, no extra nodes are needed at
all. Either way, the root node type should match the conceptual identity of the
object (`Node2D`, `CharacterBody2D`, `Area2D`), not the movement mechanism.

**Separate consideration — Path2D vs Tween:** if point-to-point grid movement is
all that's needed, a `Tween` on `position` is simpler and more readable than
`Path2D` + `PathFollow2D`. Reserve `Path2D`/`PathFollow2D` for actual curved
paths or when you need the follower's built-in features (loop, rotation, offset).
This should be an explicit design decision, not a default.

## MCP tool usage: query specs before architectural decisions

The `mcp0_get_godot_spec` tool is available and can query any Godot class's
properties, signals, and inheritance hierarchy. **Use it before choosing a node
type or architecture.**

For example, before deciding to use `Path2D` as the root node for gamepieces, I
should have queried:
- `mcp0_get_godot_spec("Path2D")` — to see it's designed for curved paths, not grid hops
- `mcp0_get_godot_spec("PathFollow2D")` — to understand it follows a curve, not a discrete path
- `mcp0_get_godot_spec("Node2D")` — to confirm a plain Node2D + Tween would suffice

**Lesson for next time:** make it a habit to query class specs before committing
to a node type. The tool exists specifically for this. Don't rely on memory
alone — Godot's API is large and some classes have surprising properties or
limitations that only surface when you read the spec.

## class_name resolution in headless validation

When you create new scripts with `class_name`, the Godot headless validator
(`--check-only`) can't resolve them until the global class cache is rebuilt.
This causes cascading "Could not find type X in the current scope" errors that
are misleading — the scripts are correct, just not cached.

**Correct solution:** run `godot --headless --import --quit` to rebuild the
class cache before validating. Do this after creating any new `class_name`
script or after renaming one. Once the cache is built, you can reference types
directly (e.g. `TileAtlas.KNIGHT`, `TileAtlas.region_for(...)`) without
`preload()` workarounds.

If you still hit resolution issues after rebuilding the cache, double-check that
the `class_name` line is at the top of the file (after any `@tool` annotation)
and that the file has no parse errors of its own.

## Scene file details

### `load_steps` is deprecated (Godot 4.6+)

The `load_steps=N` attribute in `[gd_scene]` headers was removed in Godot 4.6.
It's no longer needed — Godot computes the step count automatically. Don't
include it when writing `.tscn` files by hand. If present, Godot ignores it but
it creates unnecessary diffs in version control.

### Assign resources in the scene, not in code

When a node needs a `Resource` (like `Stats` for a monster), assign it in the
`.tscn` file as a sub_resource — don't leave it null and fall back to
`Resource.new()` in `_ready()`. The scene file is the right place for
per-instance configuration. The code fallback is a safety net, not the primary
path.

For each monster/character in a scene, create an inline `[sub_resource]` with
the Stats script and assign it:
```
[sub_resource type="Resource" id="Resource_ghost_stats"]
script = ExtResource("stats_script")
metadata/_custom_type_script = "uid://..."

[node name="Ghost" ...]
stats = SubResource("Resource_ghost_stats")
```

Or better: create separate `.tres` files (`ghost_stats.tres`, `orc_stats.tres`)
and assign them as ext_resources. This is the preferred way per the godot rules.

## Debugging workflow for runtime issues

### Setup: timestamped debug prints

When something doesn't work at runtime (clicks not registering, movement not
happening, paths returning empty), add timestamped debug prints at every step
of the flow. Use a consistent format so logs are easy to read:

```gdscript
var _start_time: float = 0.0

func _ready() -> void:
    _start_time = Time.get_ticks_msec() / 1000.0

func _dbg(msg: String) -> void:
    var t := Time.get_ticks_msec() / 1000.0 - _start_time
    print("[%.3f] ClassName: %s" % [t, msg])
```

Place prints at:
- Entry points (click handlers, input events)
- Every early return / guard clause
- Before and after calls to other objects
- Inside the called object's methods (e.g. `move_to`, `get_path_to_cell`)

Each print should include enough state to diagnose the failure: the arguments,
the relevant variables, and which branch was taken.

### Running the scene for interactive testing

Run a specific scene directly from command line (non-headless) so the user can
interact with it while logs are captured:

```bash
godot --path /path/to/project res://examples/hero_rpg/scenes/pathfinding_demo.tscn
```

The user clicks around, then closes the window. The full stdout (all debug
prints) is captured by the assistant via `run_command` (non-blocking, then
`command_status` to read output after the user says "done").

### After fixing: remove debug prints

Once the bug is found and fixed, remove all `_dbg` calls and debug `print`
statements. They should not be committed.
