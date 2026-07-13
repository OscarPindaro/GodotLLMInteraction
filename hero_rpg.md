Ok my friend, let's implement a simple game.
In assets we have a tilemap_packed.png
you will find some light terrain at position (4,0). 4 is a row index, while 0 is column index. remeber that X positions reflect columns, while Y positions reflex rows.
Then we have:
- knight: (8,1)
- orc: (9,1)
- ghost: (10,1)
- table: (6, 0)
- chair: (6,1)
- chest:
  - closed: (7,5)
  - half close: (7,6)
  - open: (7,7)
  - open with a mimic: (8,8)
- selection sprite (it's squared, used to probably highlight a cell): (5,0)
- selection sprite with diagonal full lines: i guess when we select, (5,1)
- sword, vertical: (8,8)
- shield: (8,5), centered.
- big axe: (9,10)
- light terrain: (4,0)
- wall (for atlas):
  - center wall: (3,4), used for piece near terrain or not at an edge of a wall
  - right edge: (4,11)
  - left edge: (4,9)
- graveyard cross: (5,5)
- blue potion: (9,8)
- door (animated):
  - open door: (9,0)
  - starting to close (9,1)
  - almost closed (9,2)
  - closed (9,2), of course if you registere in the animation in the opposite direction, it opens
- key: (10,10)
The sprites are 16x16
ok let's create a game.
the protagonist is a knight. at the beginning they have to look for the sword.
They go around this dungeon with some rooms. some rooms don't have doors, other have doors. it's a 2d game, so it's like we are seeing the worl from uptop.
it's a discrete world, meaning that movements are wasd or arrows and just move from one tile to the next, if possible.
this means that there is a sort of clock,. managed by a game managers, that coordinates the moovements of everyone.
the player moves, then the monster moves, than if there are some  special events they can happen.
There are two monsters: ghosts -> they patrol areas, following a path.
Orcs: they stand still, with a vision "cone", and the vision cone moves around (up, left, down, right). If the hero enters the vision cone, than the orc starts to approach the hero. Consider using an Area2D with a cone-shaped collision shape for detection instead of manual cell-based checks — this is more idiomatic Godot and leverages the physics engine. The choice of collision object type for gamepieces is not imposed:
- If gamepieces are Area2D: the orc's vision cone Area2D detects them via the area_entered signal. Each gamepiece needs a CollisionShape2D child. Use monitoring (observer) on the cone and monitorable (observable) on the gamepieces to control who detects whom.
- If gamepieces are PhysicsBody2D (CharacterBody2D, RigidBody2D, etc.): the orc's vision cone Area2D detects them via the body_entered signal. Each gamepiece needs a CollisionShape2D child. Same monitoring/monitorable flags apply.
Either way, no manual distance/direction math is needed — the physics engine handles overlap detection.

### Combat (autobattler)

When the hero and a monster end up on the same tile, the game transitions to a separate battle view. The main game freezes — the clock stops, no one moves on the map. The battle takes place in a different space: a full-screen view with a solid color background (configurable, since there is no art for it yet).

The battle is automatic — the player does not choose actions. The two fighters take turns attacking each other:
1. The hero lunges toward the enemy sprite, then returns to position.
2. If the attack lands, the enemy flashes and shakes (tremor). A damage number pops up above the enemy and floats away.
3. If the enemy dodges, a "MISS" text appears instead.
4. The enemy then does the same to the hero.
5. This repeats until one fighter's HP reaches zero.

The sprites should be displayed much larger than on the map, so the player can clearly see the action. Each fighter has:
- A name displayed above them
- An HP bar showing current / max HP as both a bar and a number
- A crit hit shows a bigger, red damage number with an exclamation mark

When the battle ends, the view fades and the game returns to the map. If the hero won, the monster is removed. If the hero lost, it's game over.

really thing hard about this, look online how people do this type of stuff.

the player has hp, attack and defense. same for monsters. when fgightning, the damage is done like dhis: hp_diff = (attack - defese). there is also a crit change that double the damage.
very easy, very simple.
when picking up a weapon, the hero now has a weapon moving with it.
position of where the weapon is should configurable with a marker, you will put under it the object representing the weapon. there will be two markers, one for shield, on for weapon. orcs also have an axe. ghosts don't have a weapon, but they have a dodge change.
you win if you go out of the dungeon.

first let's create all the components of this game. let's also create an algorithm that creates procedurally rooms. I will manage putting the  potions, weapons and suff like that in the map.
the game can be also controlled with mouse. a player clicks, and the grid of the tiles is visible only in a circle around the  the mouse, the further the more transparent it is. use the marker for before clicking and when clicked to select stuff.
Of course you need to compute the best path to go there, use A*. wall block a*. close doors block a*. chest block A*. in order to open a chest, you need to be on a tile defined by the chest, can be easility configured.
You will provide to me all these scenes, and since you are not able to see the screen, you can make tentative positioning of stuff, but I want it to be configurable. for example, vision cone radius and angle should be configurable.
Objects on the floor should have particles that go up and shirnk or pulsate. create a circle for the particle, with transparency changing linearly fron center to radius. the lmits should be configurable. they should be at most 8x8 pixels. let's create mimics, if you open a mimic, it will start a fight.
when you reach the goal the game ends.

regarding how to implement
use the gli MCP to interact with the tscn files.
when you create a scene, you can create it from scratch, but then use the tools to add, move, remove nodes or resources, since it makes a lot of validation. while you use a tool, if you are stuck on something or something is not working, write on new_tools.md proposal for new tools that you would enjoy. tools are useful because they are deterministic and know well godot conventions.
use the kb search in the planning phase to see if there are already good examples.


GODOT is version 4.7, non negotiable

## Implementation decisions

Everything goes under a single `examples/hero_rpg/` folder with subfolders (scenes, scripts, resources, autoloads, assets). No shared lib, no flat structure.

Each building block should be standalone and testable on its own with a tiny demo scene to verify it. Plus one minimal integration level that wires everything together so you can see movement+combat end-to-end.

All blocks are in scope for the first pass:
- Core grid + movement + turn clock (tilemap layers, gameboard, gamepiece registry, turn clock/game manager, WASD/arrows discrete movement)
- A* pathfinding + mouse select (pathfinder wrapper, mouse-click pathing with radial grid highlight + selection markers)
- Monsters AI (ghost patrol-path behavior + orc vision-cone detection/chase, all configurable)
- Combat autobattler + items + particles + dungeon gen (battle scene, stats/damage/crit, weapon/shield markers, floor-item particles, chest/mimic, procedural rooms)

### class_name resolution in headless validation

When you create new scripts with `class_name`, the Godot headless validator (`--check-only`) can't resolve them until the global class cache is rebuilt. This causes cascading "Could not find type X in the current scope" errors that are misleading — the scripts are correct, just not cached.

**Correct solution:** run `godot --headless --import --quit` to rebuild the class cache before validating. Do this after creating any new `class_name` script or after renaming one. Once the cache is built, you can reference types directly (e.g. `TileAtlas.KNIGHT`, `TileAtlas.region_for(...)`) without `preload()` workarounds.

If you still hit resolution issues after rebuilding the cache, double-check that the `class_name` line is at the top of the file (after any `@tool` annotation) and that the file has no parse errors of its own.
