---
trigger: manual
---
# Testing Godot Scenes Iteratively

When debugging or verifying a Godot scene, you cannot rely on static analysis
alone. You must run the scene, observe the output, and iterate. This document
describes the workflow for iteratively testing Godot scenes when you cannot see
the screen.

## Core Workflow

1. **Run the scene headless or windowed** using the Godot CLI:
   ```
   godot --path /path/to/project res://path/to/scene.tscn 2>&1
   ```
   Run it as a background command with a wait of 5-10 seconds so the engine
   has time to start and print initial output.

2. **Ask the user to interact** — since you cannot see the screen or send
   input, tell the user exactly what to do (e.g. "press WASD", "click on the
   monster", "walk onto the ghost"). The user plays the game; you read the
   console output.

3. **Read the console output** after the user interacts. Look for:
   - Error messages (script errors, null references, type mismatches)
   - Debug prints you added
   - Unexpected silence (a signal not firing, a function not called)

4. **Add targeted debug prints** at decision points to trace the flow:
   ```gdscript
   print("[DBG] ClassName: function_name — var1=%s var2=%s" % [var1, var2])
   ```
   Use a consistent `[DBG]` prefix and include the class/function name.
   Print the values of variables at branch points (if/else, return statements)
   to identify where logic diverges from expectations.

5. **Narrow the problem** — each debug run should answer one question:
   - Is the function called at all?
   - Are the variable values what we expect?
   - Which branch is taken?
   Move the debug print closer to the suspected root cause each iteration.

6. **Fix the root cause** — once identified, make the minimal fix. Do not
   fix symptoms. Re-run to verify.

7. **Remove debug prints** once the issue is confirmed fixed. If the user
   wants to keep them, hide them behind a boolean flag:
   ```gdscript
   const DEBUG_LOG: bool = false
   if DEBUG_LOG:
       print("[DBG] ...")
   ```

## Running Godot from the CLI

```bash
# Run a specific scene (windowed, user can interact)
godot --path /path/to/project res://examples/scenes/my_scene.tscn 2>&1

# Headless import check (no window, just checks for script errors)
godot --headless --path /path/to/project --import --quit 2>&1

# Run a specific scene headless (no window, for automated checks)
godot --headless --path /path/to/project res://examples/scenes/my_scene.tscn 2>&1
```

Always run windowed scenes as background commands with `WaitMsBeforeAsync` of
5000-10000ms so the engine starts and prints initial output before you check
status.

## Common Pitfalls

- **`_ready()` lifecycle order**: Children's `_ready()` runs before parents'.
  If a parent sets a child's position in `_ready()`, the child may have already
  snapped to `(0,0)` in its own `_ready()`. Fix by re-setting the cell and
  re-registering in the parent's `_ready()`.

- **`@export` NodePath vs Node types**: An `@export var x: Path2D` will NOT
  auto-resolve a `NodePath` value from a `.tscn` file. Use `@export var x: NodePath`
  and resolve with `get_node(x)` in `_ready()`.

- **Occupied cells block movement**: `GamepieceRegistry` blocks movement to
  occupied cells. If combat requires walking onto a monster, the move logic
  must allow occupied targets explicitly.

- **Pathfinder disabled points**: The pathfinder disables cells occupied by
  gamepieces. To path to an occupied cell (e.g. a monster for combat), pass
  `FLAG_ALLOW_TARGET_OCCUPANT`.

## Debug Print Format

Use this consistent format for all debug prints:

```
[DBG] ClassName: message — key1=%s key2=%s
```

Or with timestamps (useful for ordering issues):

```
[%.3f] ClassName: message
```

## Iteration Speed

- Keep debug prints minimal — one or two per iteration, at the key decision
  point.
- Read output quickly with `command_status` using a small `OutputCharacterCount`
  (2000-3000 is usually enough).
- Don't fix multiple issues at once — one fix, one test, one verification per
  iteration.
- If the user reports "not working" without details, add a debug print at the
  entry point of the suspected function first, then narrow down.
