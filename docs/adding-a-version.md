# Adding a New Godot Version: Migration Guide

This document describes the step-by-step process for adding a new Godot version
to the multi-version specification system. It serves as a checklist for future
migrations.

## Prerequisites

- The Godot binary for the target version must be installed via `godotctl`
- The previous version must already be added to the system
- `godot-versions.txt` at the repo root lists all supported versions

## Step 1: Add the specification package

One command does everything (dump API, schema diff, generate spec.py, sync enums,
generate classes/builtins/signals):

```bash
uv run gli specifications add-version \
  --version vX_Y_Z \
  --godot-version X.Y.Z \
  --base-version vPREV_X_PREV_Y_PREV_Z
```

For the first version (no base to compare against), use `--first-version` instead
of `--base-version`:

```bash
uv run gli specifications add-version \
  --version v4_4_0 \
  --godot-version 4.4.0 \
  --first-version
```

**What happens automatically:**
1. Dumps `extension_api.json` from the Godot binary
2. Runs schema diff against the base version (or skips with `--first-version`)
3. If human intervention is needed, stops and writes a report to `schema_diff_vX_Y_Z.yaml`
4. Creates `specifications/vX_Y_Z/` package
5. Generates `spec.py` (imports enums from base if identical, otherwise generates fresh)
6. Runs `sync-enums`, `generate-builtin-classes`, `generate-global-enums`, `generate-classes`, `generate-signals`
7. Appends the version to `godot-versions.txt`
8. Outputs test guidance

**If human intervention is needed:** Read the YAML report, resolve the structural
changes (new top-level sections, type changes, required field removals), then re-run.

## Step 2: Find real scene fixtures

Scene fixtures are real `.tscn` files from open-source Godot projects, used for
e2e tests (parsing + Godot `--check-only` validation).

### Source: gdquest-demos/godot-open-rpg

The same repository has commits for different Godot versions:

```bash
git clone https://github.com/gdquest-demos/godot-open-rpg /tmp/gdquest-open-rpg
git -C /tmp/gdquest-open-rpg log --oneline | grep -i "godot\|version"
# Example commits:
#   47972ef Upgrade to Godot 4.4.1
#   7619659 Upgrade to Godot 4.5
#   b70df69 Update Godot version to 4.6.2
```

### Selecting scenes

Choose scenes with **minimal dependencies** — no audio, no textures, no external
class references. Good candidates from open-rpg:
- `CombatAI.tscn` — single Node2D with a script
- `gamepiece.tscn` — node hierarchy (Path2D > PathFollow2D > RemoteTransform2D)
- `ScreenTransition.tscn` — CanvasLayer with ColorRect child
- `Trigger.tscn` — Node2D with Area2D, signal connections, sub-resource
- `ui_damage_label.tscn` — Marker2D with theme reference

### License

The open-rpg project is **MIT licensed**. Always copy the `LICENSE` file and
create a `README.md` with source attribution.

### Preparing the fixtures

1. **Create the directory**: `tests/data/scenes/open_rpg_vX_Y_Z/`

2. **Extract files** from the appropriate commit:
   ```bash
   COMMIT=<commit-hash>
   DEST=tests/data/scenes/open_rpg_vX_Y_Z
   for f in src/combat/CombatAI.tscn src/combat/combat_ai_random.gd \
            src/field/gamepieces/gamepiece.tscn src/field/gamepieces/gamepiece.gd \
            src/common/screen_transitions/ScreenTransition.tscn src/common/screen_transitions/screen_transition.gd \
            src/field/cutscenes/Trigger.tscn src/field/cutscenes/trigger.gd \
            src/field/cutscenes/cutscene.gd \
            src/combat/ui/effect_labels/ui_damage_label.tscn src/combat/ui/effect_labels/ui_damage_label.gd; do
     git -C /tmp/gdquest-open-rpg show $COMMIT:$f > $DEST/$(basename $f)
   done
   git -C /tmp/gdquest-open-rpg show $COMMIT:LICENSE > $DEST/LICENSE
   ```

3. **Rewrite `res://` paths** to be relative to the fixture project dir:
   ```bash
   sed -i 's|res://src/combat/combat_ai_random.gd|res://combat_ai_random.gd|g' $DEST/CombatAI.tscn
   sed -i 's|res://src/field/gamepieces/gamepiece.gd|res://gamepiece.gd|g' $DEST/gamepiece.tscn
   # ... etc for each scene
   ```
   The `res://` paths must be relative to the fixture's `project.godot` location,
   NOT to the main repo root.

4. **Replace scripts with stubs**: The original scripts reference types from the
   full project (Battler, Gameboard, Cutscene, FieldEvents, etc.) that don't exist
   in the test fixtures. Replace them with minimal stubs that keep the same
   `class_name` and `extends`.

   **Important:** Do not blindly copy `extends` from the previous version's stubs.
   Scene structure can change between versions (e.g. in 4.5.0 `gamepiece.tscn`
   changed its root node from `Node2D` to `Path2D`). Always check the root node
   type in the extracted `.tscn` file and match the `extends` clause accordingly:
   ```bash
   # Check the root node type in each scene
   grep '^\[node ' $DEST/*.tscn | head -5
   ```
   Then write stubs matching the actual node types:
   ```bash
   echo 'class_name CombatAI extends Node' > $DEST/combat_ai_random.gd
   echo 'class_name Gamepiece extends Node2D' > $DEST/gamepiece.gd  # 4.4.x
   # echo 'class_name Gamepiece extends Path2D' > $DEST/gamepiece.gd  # 4.5.0+
   echo 'class_name Cutscene extends Node2D' > $DEST/cutscene.gd
   echo 'class_name Trigger extends Cutscene' > $DEST/trigger.gd
   ```

   **Checking for external dependencies:** Before keeping a script as-is, verify
   it has no external references:
   ```bash
   git -C /tmp/gdquest-open-rpg show $COMMIT:src/path/to/script.gd | grep -n 'preload\|load\|const\|import'
   ```
   If the output references project-internal types (Battler, Gameboard, etc.),
   replace with a stub. If it only references engine builtins (Color, Tween,
   etc.), it is safe to keep.

5. **Rename `.theme` to `.tres`**: Godot expects `.theme` files to be binary.
   If the original theme is text-based, rename it to `.tres`:
   ```bash
   mv $DEST/ui_combat.theme $DEST/ui_combat.tres
   sed -i 's|ui_combat.theme|ui_combat.tres|g' $DEST/*.tscn
   ```

6. **Create `project.godot`**:
   ```ini
   config_version=5
   [application]
   config/name="open_rpg_vX_Y_Z_test_fixtures"
   config/features=PackedStringArray("X.Y", "GL Compatibility")
   [display]
   window/size/viewport_width=1920
   window/size/viewport_height=1080
   window/stretch/mode="canvas_items"
   window/stretch/aspect="expand"
   [filesystem]
   import/blender/enabled=false
   import/fbx/enabled=false
   ```

7. **Create `README.md`** with source, commit, license, file list, and modifications.

8. **Verify scenes load cleanly**:
   ```bash
   godot-X.Y.Z-stable --headless --import --quit --path tests/data/scenes/open_rpg_vX_Y_Z
   for f in *.tscn; do
     godot-X.Y.Z-stable --headless --check-only --quit --path tests/data/scenes/open_rpg_vX_Y_Z "$f"
     echo "$f: exit $?"
   done
   ```
   All scenes should exit 0 with no ERROR or SCRIPT ERROR lines.

## Step 3: Write e2e tests

Create two test files per version:

### `tests/e2e/real_scenes_parse_vX_Y_Z_test.py`

Tests that our Python parser can parse the scenes without errors. Check:
- Each scene parses without raising
- Root node type matches expected
- Ext resource count, node count
- Signal connections (Trigger.tscn)
- Sub-resources (Trigger.tscn)
- Node hierarchy (gamepiece.tscn)
- All scenes have `format=3` and `uid` attribute

**Important:** The `SCENE_FIXTURES` table (root node type, ext resource count,
node count) and the node hierarchy test must be adapted per version. Scene
structure can change between Godot versions — for example, `gamepiece.tscn`
had 6 nodes with a `Node2D > Decoupler > Path2D > PathFollow2D > RemoteTransform2D`
hierarchy in 4.4.1, but was refactored to 3 nodes with
`Path2D > PathFollow2D > RemoteTransform2D` in 4.5.0. Always diff the scenes
against the previous version's fixtures and update the test assertions:
```bash
diff <(git -C /tmp/gdquest-open-rpg show $PREV_COMMIT:src/field/gamepieces/gamepiece.tscn) \
     <(git -C /tmp/gdquest-open-rpg show $COMMIT:src/field/gamepieces/gamepiece.tscn)
```

### `tests/e2e/real_scenes_godot_check_vX_Y_Z_test.py`

Tests that Godot's `--check-only` passes on each scene. Uses the `check_scene`
helper from `tests/e2e/_helpers.py` which auto-imports the project on first run
(no manual Godot editor opening needed):

```python
from tests.e2e._helpers import check_scene, godot_binary_path

result = check_scene(binary, SCENES_DIR, scene_path.name)
assert result.returncode == 0
```

## Step 4: Run the full test suite

```bash
uv run pytest tests/unit tests/integration tests/e2e -x -q
```

All tests should pass. The e2e tests will auto-import the Godot project on first
run (creating `.godot/` cache, which is gitignored).

## Step 3b: Write edit-validate e2e tests

Create `tests/e2e/real_scenes_edit_validate_vX_Y_Z_test.py`. This file verifies
that CLI edit operations produce scenes Godot accepts, by running both
`gli tscn validate` (CLI) and Godot `--check-only` on every edited scene.

### Test classes

Each file contains these test classes:

- **`TestRoundtripGodotCheck`** — add then delete a TempNode, validate both steps
- **`TestAddNodeGodotCheck`** — add a plain `Node` child to each scene
- **`TestDeleteNodeGodotCheck`** — leaf delete + subtree delete (Trigger Area2D)
- **`TestRenameNodeGodotCheck`** — rename child nodes (connection rewriting)
- **`TestMoveNodeGodotCheck`** — move child to root for scenes with ≥3 nodes
- **`TestUpdatePropertiesGodotCheck`** — safe property per scene
- **`TestComplexChangesGodotCheck`** — multi-property transforms, sub-resource swap,
  ext-resource swap, chained 8-step sequence on Trigger.tscn
- **`TestAttachDetachScriptGodotCheck`** — attach `test_stub.gd` then detach
- **`TestCreateSubResourceGodotCheck`** — create orphaned RectangleShape2D
- **`TestConnectSignalGodotCheck`** — connect `body_entered` on Trigger.tscn
- **`TestTreeCommand`** — `gli tscn tree --json` structure assertions (no Godot needed)
- **`TestValidateCommand`** — `gli tscn validate` on original scenes
- **`TestExportedPropertiesGodotCheck`** — update/add `@export` properties on `exported_props.tscn`
- **`TestBadScenesCliGodotAgree`** — CLI and Godot must agree on bad scenes (both reject or both accept)

### Helpers

Use the shared helpers from `tests/e2e/_helpers.py`:

- `output_scene_path(scenes_dir, scene_name)` — returns a temp path `<stem>_e2e.tscn`
  inside the fixture dir (no file copy needed; the CLI `--output` flag writes there)
- `cleanup_test_scenes(scenes_dir)` — removes `*_e2e.tscn` files after each test
- `run_cli_edit(args)` — invokes `gli tscn <args>` via CliRunner
- `validate_both(scene_path, scenes_dir, binary)` — runs both CLI validate and
  Godot check, returns `(cli_exit, godot_exit)` for agreement assertion

### `--output` pattern

Tests use the CLI's `--output` flag to write edited scenes to `*_e2e.tscn` temp
files instead of copying fixtures. The `_edit_and_validate` helper appends
`--output <tmp>` automatically. Chained tests use `--output` on the first edit
(reading from the source fixture), then edit in-place on the temp file for
subsequent steps. Original fixtures are never modified.

### `test_stub.gd`

Add a `test_stub.gd` file to the fixture dir (`extends Node`) for attach-script
tests. Godot generates the `.uid` file on import.

### `exported_props.gd` and `exported_props.tscn`

Add an `exported_props.gd` script and `exported_props.tscn` scene to the fixture
dir for `TestExportedPropertiesGodotCheck`. The script defines `@export`
properties of various types (float, int, bool, String, Color, Vector2); the
scene overrides some non-default values. This verifies that CLI property
updates on exported variables produce Godot-valid scenes.

```gdscript
# exported_props.gd
extends Node2D
class_name ExportTest

@export var max_speed: float = 200.0
@export var damage: int = 10
@export var is_active: bool = true
@export var label: String = "Enemy"
@export var tint: Color = Color(1, 0, 0, 1)
@export var spawn_position: Vector2 = Vector2(0, 0)
```

The scene stores only non-default values (max_speed=350, damage=25,
is_active=false). Properties matching defaults are not in the .tscn file.

### `test_theme.tres`

Add a `test_theme.tres` file to the fixture dir for `TestComplexChangesGodotCheck`
(ext-resource swap test). It's a minimal empty Theme resource:

```
[gd_resource type="Theme" format=3]

[resource]
```

### Bad-scenes sub-project

Create `tests/data/scenes/bad_vX_Y_Z/` with `project.godot` and 4 intentionally
broken `.tscn` files:

| File | What's wrong |
|------|-------------|
| `not_a_scene.tscn` | `[gd_resource]` not `[gd_scene]` |
| `missing_parent.tscn` | `parent="Ghost"` (nonexistent) |
| `broken_connection.tscn` | connection to nonexistent node |
| `broken_subresource.tscn` | `SubResource("nonexistent")` |

The test asserts CLI and Godot **agree** on each scene's validity (both reject
or both accept). Neither the CLI parser nor Godot's `--check-only` mode validates
node types, so `unknown_type.tscn` was removed — both accept it, which is
correct behavior.

### Version-specific differences

Adapt the test file for scene structure changes across versions. For example,
4.4.1 `gamepiece.tscn` has 6 nodes (Node2D > Decoupler > Path2D > PathFollow2D >
CameraAnchor + GFXAnchor), while 4.5.0+ has 3 nodes (Path2D > PathFollow2D >
CameraAnchor). Always check the actual scene structure and update paths accordingly.

## Checklist

- [ ] `gli specifications add-version --version vX_Y_Z --godot-version X.Y.Z --base-version vPREV`
- [ ] No human intervention required (or resolved if flagged)
- [ ] Scene fixtures extracted from open-rpg at the correct commit
- [ ] `res://` paths rewritten to be relative to fixture project dir
- [ ] Scripts with external dependencies replaced with stubs
- [ ] `.theme` files renamed to `.tres` if text-based
- [ ] `project.godot` created for the fixture dir
- [ ] `README.md` with source, commit, license, file list
- [ ] `LICENSE` file copied
- [ ] All scenes pass `--check-only` with no errors
- [ ] `real_scenes_parse_vX_Y_Z_test.py` created
- [ ] `real_scenes_godot_check_vX_Y_Z_test.py` created
- [ ] `test_stub.gd` added to the fixture dir
- [ ] `exported_props.gd` and `exported_props.tscn` added to the fixture dir
- [ ] `test_theme.tres` added to the fixture dir
- [ ] `real_scenes_edit_validate_vX_Y_Z_test.py` created
- [ ] `bad_vX_Y_Z/` sub-project created with 4 bad scenes
- [ ] Full test suite passes
