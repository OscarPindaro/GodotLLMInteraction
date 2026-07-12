# Scene Test Fixtures: open_rpg_4_5_0

These `.tscn` and `.gd` files are sourced from the
[Godot Open RPG](https://github.com/gdquest-demos/godot-open-rpg) project by
GDQuest, specifically commit
[`7619659`](https://github.com/gdquest-demos/godot-open-rpg/commit/7619659)
("Upgrade to Godot 4.5 & fix Dialogic portraits").

## License

The source project is licensed under the **MIT License**.
See [LICENSE](./LICENSE) for the full text.

## Source

- **Repository**: https://github.com/gdquest-demos/godot-open-rpg
- **Commit**: 7619659 ("Upgrade to Godot 4.5 & fix Dialogic portraits")
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
  `res://tests/data/scenes/open_rpg_4_5_0/` instead of the original project structure.
- `ui_combat.theme` was replaced with a minimal text-based `.tres` file
  (the original was a binary `.theme` file).
- `project.godot` was created for the test fixture directory.

## Differences from 4.4.1 fixtures

The `gamepiece.tscn` scene was refactored in the 4.5 commit:
- Root node changed from `Node2D` to `Path2D` (the Gamepiece script now extends Path2D)
- The `Decoupler` intermediate node was removed
- The node hierarchy is now `Path2D > PathFollow2D > RemoteTransform2D` (3 nodes)
  instead of `Node2D > Decoupler > Path2D > PathFollow2D > RemoteTransform2D × 2` (6 nodes)
- The `GFXAnchor` RemoteTransform2D was removed
