# Validating `.tscn` Scene Files

Godot can validate `.tscn` files from the command line using the editor executable.

## Single scene check

The fastest way to validate one scene is with `--check-only` and `--quit`:

```bash
godot --headless --check-only --quit --path . res://scenes/door.tscn
```

Output on success:

```text
Godot Engine v4.7.stable.official.5b4e0cb0f - https://godotengine.org
```

Output on failure (missing resource, parse error, etc.):

```text
ERROR: Resource file not found: res://asset/does_not_exist.png (expected type: Texture2D)
   at: _load (core/io/resource_loader.cpp:325)
ERROR: res://scenes/broken_door.tscn:6 - Parse Error: [ext_resource] referenced non-existent resource at: res://asset/does_not_exist.png.
   at: _printerr (scene/resources/resource_format_text.cpp:41)
ERROR: Failed loading scene: res://scenes/broken_door.tscn.
   at: start (main/main.cpp:4763)
```

## Full project check

To import all resources and catch broader project-level issues:

```bash
godot --headless --import --quit --path . project.godot
```

This is slower but more thorough. It is useful in CI or before a commit.

## Notes

- `godot` must be in the `PATH` or called with the full binary path.
- `--path .` points to the project directory that contains `project.godot`.
- `--quit` stops the editor after validation instead of running the game.
