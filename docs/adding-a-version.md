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
6. Runs `sync-enums`, `generate-builtin-classes`, `generate-classes`, `generate-signals`
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
   `class_name` and `extends`:
   ```bash
   echo 'class_name CombatAI extends Node' > $DEST/combat_ai_random.gd
   echo 'class_name Gamepiece extends Node2D' > $DEST/gamepiece.gd
   echo 'class_name Cutscene extends Node2D' > $DEST/cutscene.gd
   echo 'class_name Trigger extends Cutscene' > $DEST/trigger.gd
   ```
   Keep `screen_transition.gd` and `ui_damage_label.gd` as-is if they have no
   external dependencies.

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
- [ ] Full test suite passes
