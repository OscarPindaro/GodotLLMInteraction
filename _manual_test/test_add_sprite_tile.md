# Manual Test: `add-sprite-image`

All commands use the scratch scene at `_manual_test/scene.tscn` (relative to repo root).

## Setup

```bash
mkdir -p _manual_test
cp tests/data/scenes/connections.tscn _manual_test/scene.tscn
```

## Commands

### 1. Region mode (default) — auto-creates a Sprite2D node

```bash
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 2 1 --node Hero --tile-width 32 --tile-height 32
```

### 2. Region mode with named texture filter

```bash
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 0 0 --node Enemy --texture-filter linear
```

### 3. Atlas mode — creates a shareable AtlasTexture sub_resource

```bash
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 3 0 --node Chest --mode atlas --id chest_atlas
```

### 4. Atlas mode targeting a custom property (e.g. `closed_texture`)

`chest.gd` defines `class_name Chest extends Sprite2D` with `@export var closed_texture`.
`--type Chest` auto-resolves to `Sprite2D` + script attachment:

```bash
uv run gli tscn add-node _manual_test/scene.tscn Chest --type Chest
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 4 0 --node Chest.closed_texture --mode atlas --id chest_closed
```

### 5. Resource-only (no node) — atlas mode

```bash
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 0 0 --mode atlas --id standalone_atlas
```

### 6. Dedup check — second op on same texture reuses the ext_resource

```bash
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 0 0 --node Tile1
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 1 1 --node Tile2
```

After both, there should be only one `ext_resource` for `res://tilemap.png`.

### 7. Margin and spacing

```bash
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 2 2 --node Spaced --margin 4 --spacing 2
```

### 8. Dry run (no file changes)

```bash
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 0 0 --node Ghost --dry-run
```

### 9. JSON output

```bash
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 5 5 --node JsonTile --json
```

### 10. Error cases

```bash
# Region mode without --node (should error)
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 0 0

# Invalid mode
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 0 0 --node X --mode foo

# Bad texture filter name
uv run gli tscn add-sprite-image _manual_test/scene.tscn res://tilemap.png 0 0 --node X --texture-filter bogus
```

## Inspecting results

After each command, check the scene:

```bash
cat _manual_test/scene.tscn
```

## Reset

```bash
cp tests/data/scenes/connections.tscn _manual_test/scene.tscn
```

## Cleanup

```bash
rm -rf _manual_test
```
