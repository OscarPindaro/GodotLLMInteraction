# Scene Test Fixtures: open_rpg_4_4_1

These `.tscn` and `.gd` files are sourced from the
[Godot Open RPG](https://github.com/gdquest-demos/godot-open-rpg) project by
GDQuest, specifically commit
[`47972ef`](https://github.com/gdquest-demos/godot-open-rpg/commit/47972ef)
("Upgrade to Godot 4.4.1").

## License

The source project is licensed under the **MIT License**.
See [LICENSE](./LICENSE) for the full text.

## Source

- **Repository**: https://github.com/gdquest-demos/godot-open-rpg
- **Commit**: 47972ef ("Upgrade to Godot 4.4.1")
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
  `res://tests/data/scenes/open_rpg_4_4_1/` instead of the original project structure.
- `ui_combat.theme` was replaced with a minimal text-based `.tres` file
  (the original was a binary `.theme` file).
- `project.godot` was created for the test fixture directory.
