# E2E Edit-then-Validate Tests for Real Scene Fixtures

New e2e tests that verify CLI and Godot agree: parse → dump → Godot check, CLI edit operations → Godot check, and bad scenes rejected by both. Per-version, CLI-based, following the existing `real_scenes_*_vX_Y_Z_test.py` pattern.

## Context: How Validation Works Today

- **`gli tscn validate <scene> --project <dir> --godot <binary>`** — runs `godot --headless --check-only --path <dir> <scene>`. Real engine validation: Godot loads the scene and reports errors. The `--godot` flag overrides binary discovery.
- **`validate_scene()` (Python-only)** — checks parsed scenes against generated class specs (no Godot binary needed). Already used internally by operations in strict mode.
- **`gli tscn tree <scene> --json`** — prints the parsed scene tree as JSON. No Godot binary needed.
- **Current gap**: `tscn_granular_cli_test.py` and `tscn_apply_cli_test.py` test CLI mechanics on synthetic fixtures but never run Godot validation on the output. `real_scenes_godot_check_*_test.py` validates original fixtures but never edited ones. No test verifies CLI and Godot agree on bad scenes.

## CLI Changes

**No CLI changes needed.** The existing `validate` command and `tree` command are sufficient. The edit commands (`add-node`, `delete-node`, etc.) already write to disk. Tests will: copy scene to temp file in fixture dir → run CLI edit → run CLI validate (Godot) → assert pass.

## Plan

### Step 1: Add shared helpers to `tests/e2e/_helpers.py`

Add:
- `copy_scene_fixture(scenes_dir, scene_name, suffix="_test") -> Path` — copies `<scene_name>` to `<stem>_test.tscn` in the same dir, returns the path. Ensures Godot can find project.godot and resources. Cleans up the temp file after the test.
- `cleanup_test_scenes(scenes_dir)` — removes any `*_test.tscn` files left behind.

### Step 2: Add `test_stub.gd` to each fixture dir

Each `open_rpg_vX_Y_Z/` dir gets a `test_stub.gd`:
```gdscript
extends Node
```
`extends Node` is safe for any node type (everything extends Node). Godot generates the `.uid` file on import. Used by attach-script tests.

### Step 3: Create `real_scenes_edit_validate_vX_Y_Z_test.py` per version

One file per version (4.4.0, 4.4.1, 4.5.0, 4.6.0). Each file contains these test classes:

#### `TestRoundtripGodotCheck`
Verifies parse → dump preserves Godot validity, with two separate validation steps:
1. Copy scene to temp → `gli tscn add-node <temp> TempNode --type Node` → **validate with Godot** (must pass)
2. `gli tscn delete-node <temp> TempNode` → **validate with Godot** (must pass)

This proves our representation roundtrips correctly at each step.

#### `TestAddNodeGodotCheck`
For each scene: copy → `gli tscn add-node <temp> NewNode --type Node` → validate. Adding a plain `Node` child is always valid regardless of root type.

#### `TestDeleteNodeGodotCheck`
Two variants:
- **Leaf delete**: For each scene with >1 node, delete a leaf child → validate.
- **Subtree delete with collateral**: Delete a node that has children, signal connections, and exclusive sub-resource references. **Trigger.tscn is the key fixture**: deleting `Area2D` removes Area2D + CollisionShape2D (subtree), drops 2 connections (area_entered/area_exited), and orphans the RectangleShape2D sub_resource. Verify Godot accepts the result.
- **gamepiece.tscn** (4.4.1 variant): delete `Decoupler` — removes 5-node subtree.

#### `TestRenameNodeGodotCheck`
For each scene with >1 node: copy → `gli tscn rename-node <temp> <child> NewName` → validate. Verifies connection rewriting (Trigger.tscn: renaming `Area2D` rewrites 2 connection endpoints).

#### `TestMoveNodeGodotCheck`
For scenes with ≥3 nodes: copy → `gli tscn move-node <temp> <child> <new_parent>` → validate.

#### `TestUpdatePropertiesGodotCheck`
For each scene: copy → `gli tscn update-properties <temp> <node> --property <key>=<value>` → validate. Uses safe properties per scene (e.g., `position=Vector2(100, 100)` on Node2D roots, `color=Color(1, 0, 0, 1)` on ColorRect).

#### `TestComplexChangesGodotCheck`
Multi-step and multi-property operations that exercise richer Godot semantics. Each test chains CLI commands, then validates with Godot.

**Multi-property transforms** (set position + rotation + scale in one command):
- Trigger.tscn: `update-properties . --property position=Vector2(100,50) --property rotation=1.5708` → validate
- gamepiece.tscn: `update-properties . --property position=Vector2(200,100) --property rotation=0.5` → validate
- ScreenTransition.tscn: `update-properties ColorRect --property color=Color(1,0,0,0.5) --property offset_left=-50.0 --property offset_right=50.0` → validate
- ui_damage_label.tscn: `update-properties Label --property text="Critical!" --property theme_override_constants/outline_size=32` → validate

**PathFollow offset** (gamepiece.tscn only):
- `update-properties PathFollow2D --property offset=50.0 --property h_offset=10.0 --property v_offset=5.0` → validate

**Collision tuning** (Trigger.tscn only):
- `update-properties Area2D --property collision_layer=64 --property collision_mask=8` → validate
- `update-properties CollisionShape2D --property debug_color=Color(0,1,0,0.5)` → validate

**Sub-resource swap** (Trigger.tscn):
1. `create-sub-resource RectangleShape2D --property size=Vector2(20,20) --id new_shape` → validate
2. `update-properties CollisionShape2D --property shape=SubResource("new_shape")` → validate
3. Verify old sub-resource is now orphaned but scene still valid

**Ext-resource swap** (ui_damage_label.tscn):
1. `add-ext-resource Theme res://ui_combat.tres --id new_theme` → validate
2. `update-properties Label --property theme=ExtResource("new_theme")` → validate
3. Verify old ext-resource is still referenced by root (not GC'd)

**Chained complex sequence** (Trigger.tscn — the richest fixture):
1. `add-node Mover --type Node2D` → validate
2. `move-node CollisionShape2D Mover` → validate
3. `update-properties Mover --property position=Vector2(50,50) --property rotation=0.785` → validate
4. `create-sub-resource CircleShape2D --property radius=10.0 --id circle` → validate
5. `update-properties Mover/CollisionShape2D --property shape=SubResource("circle")` → validate
6. `connect-signal --from Area2D --to Mover --signal area_entered --method _on_mover_area` → validate
7. `rename-node Area2D Detector` → validate (rewrites connection from-field)
8. `delete-node Detector` → validate (drops subtree + connections + orphaned sub-resources)

#### `TestAttachDetachScriptGodotCheck`
For each scene with a script on the root:
1. Copy → `gli tscn attach-script <temp> . res://test_stub.gd` → **validate** (must pass — root now has two scripts? No: attach replaces the existing script ext_resource)
2. `gli tscn detach-script <temp> .` → **validate** (must pass — script removed, ext_resource cleaned up if unreferenced)

#### `TestCreateSubResourceGodotCheck`
For each scene: copy → `gli tscn create-sub-resource <temp> RectangleShape2D --property size=Vector2(8,8) --id test_shape` → validate. The sub-resource is orphaned (no node references it) but Godot accepts that.

#### `TestConnectSignalGodotCheck`
For Trigger.tscn (has Area2D): copy → `gli tscn connect-signal <temp> --from Area2D --to . --signal body_entered --method _on_test` → validate. Adding an extra connection alongside existing ones.

#### `TestTreeCommand`
For each scene: `gli tscn tree <scene> --json` → assert JSON structure (root name, type, children count matches expected). No Godot binary needed.

#### `TestValidateCommand`
For each scene: `gli tscn validate <scene> --project <dir> --godot <binary>` → assert exit code 0. Verifies the validate CLI command itself works on valid scenes.

### Step 4: Create bad-scenes sub-project per version

Create `tests/data/scenes/bad_vX_Y_Z/` with `project.godot` and several intentionally broken `.tscn` files. Both the CLI and Godot must agree they're invalid.

**Bad scene categories:**

| File | What's wrong | CLI behavior | Godot behavior |
|------|-------------|-------------|----------------|
| `not_a_scene.tscn` | `[gd_resource type="Resource"]` — not a gd_scene | `gli tscn tree` → ParseError (exit 1) | `--check-only` → exit non-zero |
| `unknown_type.tscn` | `[node name="X" type="NotARealClass"]` | `tree` parses OK; `validate_scene()` → error "unknown class" | `--check-only` → exit non-zero |
| `missing_parent.tscn` | Node with `parent="Ghost"` where Ghost doesn't exist | `tree` parses OK; `validate_scene()` → error "parent does not exist" | `--check-only` → exit non-zero |
| `broken_connection.tscn` | `[connection from="X" to="Ghost" ...]` where Ghost doesn't exist | `tree` parses OK; `validate_scene()` → error "connection target does not exist" | `--check-only` → exit non-zero |
| `broken_subresource.tscn` | `shape = SubResource("nonexistent")` | `tree` parses OK; `validate_scene()` → error "SubResource does not match any [sub_resource]" | `--check-only` → exit non-zero |

**Test class `TestBadScenesCliGodotAgree`:**
For each bad scene:
1. **CLI side**: `gli tscn tree <bad_scene> --json` — if parse error, assert exit != 0. If parses OK, call `validate_scene(load_scene(...))` and assert `not report.ok`.
2. **Godot side**: `gli tscn validate <bad_scene> --project <bad_dir> --godot <binary>` → assert exit != 0.
3. **Agreement**: both sides reject the scene.

### Step 5: Scene-specific operation matrix

Not all operations apply to all scenes. The per-version test files parametrize over `(scene_name, operation_args)` tuples. Key differences across versions:

- **4.4.1 gamepiece.tscn**: 6 nodes (Node2D > Decoupler > Path2D > PathFollow2D > CameraAnchor + GFXAnchor) — richer subtree delete test
- **4.5.0+ gamepiece.tscn**: 3 nodes (Path2D > PathFollow2D > CameraAnchor) — simpler
- **Trigger.tscn**: identical across all versions — always the best hard-delete fixture (subtree + connections + sub_resource GC)

| Scene | Add Node | Delete Leaf | Delete Subtree | Rename | Move | Update Props | Complex Changes | Attach/Detach Script | Connect Signal |
|-------|----------|-------------|----------------|--------|------|-------------|-----------------|---------------------|----------------|
| CombatAI.tscn | `TempNode/Node` | N/A (1 node) | N/A | N/A | N/A | `position` on root | `position+rotation` on root | yes | N/A |
| gamepiece.tscn | `TempNode/Node` | delete last child | delete `PathFollow2D` (4.5+) or `Decoupler` (4.4.1) | rename child | move child to root (if ≥3) | `position` on root | `position+rotation` on root; `offset+h/v_offset` on PathFollow2D | yes | N/A |
| ScreenTransition.tscn | `TempNode/Node` | delete `ColorRect` | N/A (no multi-child subtree) | rename `ColorRect` | N/A | `color` on ColorRect | `color+offset_left/right` on ColorRect | yes | N/A |
| Trigger.tscn | `TempNode/Node` | delete `CollisionShape2D` | **delete `Area2D`** (subtree + 2 connections + sub_resource GC) | rename `Area2D` | move `CollisionShape2D` to root | `position` on root | `position+rotation`; collision tuning; **sub-resource swap**; **chained 8-step sequence** | yes | connect `body_entered` |
| ui_damage_label.tscn | `TempNode/Node` | delete `Label` | N/A | rename `Label` | N/A | `position` on root | `text+outline_size` on Label; **ext-resource swap** (theme) | yes | N/A |

### Step 6: Run tests

```bash
uv run pytest tests/e2e/real_scenes_edit_validate_4_6_0_test.py -x -v
uv run pytest tests/e2e -x -v
```

All tests skip gracefully if the Godot binary or scene fixtures are missing.

### Step 7: Update `docs/adding-a-version.md`

Add a new section after "Step 3: Write e2e tests" describing:
- The edit-validate test file pattern
- The bad-scenes sub-project
- New checklist items

## Files to Create/Modify

- **Modify**: `tests/e2e/_helpers.py` — add `copy_scene_fixture`, `cleanup_test_scenes` helpers
- **Create**: `tests/e2e/real_scenes_edit_validate_4_4_0_test.py`
- **Create**: `tests/e2e/real_scenes_edit_validate_4_4_1_test.py`
- **Create**: `tests/e2e/real_scenes_edit_validate_4_5_0_test.py`
- **Create**: `tests/e2e/real_scenes_edit_validate_4_6_0_test.py`
- **Create**: `tests/data/scenes/open_rpg_*/test_stub.gd` (per fixture dir, 4 files)
- **Create**: `tests/data/scenes/bad_v4_4_0/` (project.godot + 5 bad .tscn files)
- **Create**: `tests/data/scenes/bad_v4_4_1/` (same)
- **Create**: `tests/data/scenes/bad_v4_5_0/` (same)
- **Create**: `tests/data/scenes/bad_v4_6_0/` (same)
- **Modify**: `docs/adding-a-version.md` — add edit-validate + bad-scenes test guidance
