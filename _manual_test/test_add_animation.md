# Manual Test: `add-sprite-frames` and `add-animation`

All commands use the scratch scene at `_manual_test/scene.tscn` (relative to repo root).

## Setup

```bash
mkdir -p _manual_test
cp tests/data/scenes/connections.tscn _manual_test/scene.tscn
```

## Commands

### 1. Create SpriteFrames (resource only, no node)

```bash
uv run gli tscn add-sprite-frames _manual_test/scene.tscn --id frames_walk
```

### 2. Create SpriteFrames with AnimatedSprite2D node and autoplay

```bash
uv run gli tscn add-sprite-frames _manual_test/scene.tscn --id frames_hero --node Hero --autoplay default
```

### 3. Add animation — atlas mode (one texture + cell coordinates)

```bash
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk default --texture res://tilemap.png --cell 0,0 --cell 1,0
```

### 4. Add animation — atlas mode with grid params and id prefix

```bash
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk walk --texture res://tilemap.png --cell 0,0 --cell 1,0 --tile-width 32 --tile-height 32 --id-prefix walk
```

### 5. Add animation — whole-image mode (separate PNG per frame)

```bash
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk idle --frame res://frame0.png --frame res://frame1.png
```

### 6. Add animation with custom durations

```bash
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk attack --texture res://tilemap.png --cell 0,0 --cell 1,0 --durations 0.5,2.0
```

### 7. Add animation with no-loop

```bash
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk die --texture res://tilemap.png --cell 0,0 --no-loop
```

### 8. Replace existing animation (same name)

```bash
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk default --texture res://tilemap.png --cell 2,0
```

After this, there should be only one animation named "default" (with cell 2,0).

### 9. Dedup check — same cell reuses AtlasTexture

```bash
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk dedup --texture res://tilemap.png --cell 0,0 --cell 0,0
```

After this, there should be only one AtlasTexture for cell 0,0.

### 10. Dry run (no file changes)

```bash
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk test --texture res://tilemap.png --cell 0,0 --dry-run
```

### 11. JSON output

```bash
uv run gli tscn add-sprite-frames _manual_test/scene.tscn --id frames_json --json
uv run gli tscn add-animation _manual_test/scene.tscn frames_json default --texture res://tilemap.png --cell 0,0 --json
```

### 12. Error cases

```bash
# Missing SpriteFrames ID with --no-auto-create
uv run gli tscn add-animation _manual_test/scene.tscn nonexistent default --texture res://tilemap.png --cell 0,0 --no-auto-create

# Durations mismatch
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk default --texture res://tilemap.png --cell 0,0 --cell 1,0 --durations 1.0

# No frames provided
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk default --texture res://tilemap.png

# Mixing --cell and --frame
uv run gli tscn add-animation _manual_test/scene.tscn frames_walk default --texture res://tilemap.png --cell 0,0 --frame res://frame.png
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
