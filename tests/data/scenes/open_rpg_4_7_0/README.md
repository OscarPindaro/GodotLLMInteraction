# Scene Test Fixtures: open_rpg_4_7_0

These `.tscn` and `.gd` files are sourced from the
[Godot Open RPG](https://github.com/gdquest-demos/godot-open-rpg) project by
GDQuest. The open-rpg project has not been updated to Godot 4.7, so the
scenes are identical to the 4.6.2 fixtures (commit
[`b70df69`](https://github.com/gdquest-demos/godot-open-rpg/commit/b70df69)),
with only `project.godot` updated to target Godot 4.7.

## License

The source project is licensed under the **MIT License**.
See [LICENSE](./LICENSE) for the full text.

## Source

- **Repository**: https://github.com/gdquest-demos/godot-open-rpg
- **Commit**: b70df69 ("Update Godot version to 4.6.2") — no 4.7 commit exists
- **Author**: GDQuest (Nathan Lovato et al.)
- **License**: MIT

## Files

The following files were copied and adapted (resource paths rewritten to
match the test fixture directory structure):

| File | Original path |
|------|--------------|
| `CombatAI.tscn` | `src/combat/CombatAI.tscn` |
| `combat_ai_random.gd` | `src/combat/combat_ai_random.gd` |
| `gamepiece.tscn` | `src/field/gamepieces/gamepiece.tscn` |
| `gamepiece.gd` | `src/field/gamepieces/gamepiece.gd` |
| `ScreenTransition.tscn` | `src/common/screen_transitions/ScreenTransition.tscn` |
| `screen_transition.gd` | `src/common/screen_transitions/screen_transition.gd` |
| `Trigger.tscn` | `src/field/cutscenes/Trigger.tscn` |
| `trigger.gd` | `src/field/cutscenes/trigger.gd` |
| `cutscene.gd` | `src/field/cutscenes/cutscene.gd` |
| `ui_damage_label.tscn` | `src/combat/ui/effect_labels/ui_damage_label.tscn` |
| `ui_damage_label.gd` | `src/combat/ui/effect_labels/ui_damage_label.gd` |
| `ui_combat.tres` | `src/combat/ui/ui_combat.theme` (replaced binary with text `.tres`) |

## Modifications

- `res://` paths in `.tscn` files were rewritten to point to
  `res://tests/data/scenes/open_rpg_4_7_0/` instead of the original project structure.
- `ui_combat.theme` was replaced with a minimal text-based `.tres` file
  (the original was a binary `.theme` file).
- `project.godot` was created for the test fixture directory.

## Differences from 4.6.2 fixtures

The `.tscn` scene files are identical to the 4.6.2 fixtures — the open-rpg
project has not been updated to Godot 4.7. The only change is:
- `project.godot` updated to target Godot 4.7 (`config/features=PackedStringArray("4.7", ...)`)
