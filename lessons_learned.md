# Hero RPG — Lessons Learned

Notes from the first implementation pass. These are retrospective observations
to apply next time, not input requirements.

## Architecture: top-down vs bottom-up

The hero_rpg was built **bottom-up**: each gamepiece manages its own movement
via a `Path2D` + `PathFollow2D` + runtime curve. The piece itself owns the
curve, sets waypoints, and emits `arrived` when done. A manager
(TurnClock/GamepieceRegistry) coordinates turns but doesn't own movement.

**Alternative — top-down:** a single game manager owns all movement. Pieces are
plain `Node2D` with a sprite. The manager computes paths, tweens positions, and
notifies pieces when they arrive. This is simpler to reason about (one place
for all movement logic) and avoids the unusual `Path2D`-as-root-node pattern.

**Lesson for next time:** decide the architecture approach upfront and document
it. The bottom-up approach works but leads to surprising node hierarchies (a
"knight" IS a Path2D, which is weird to read). Top-down would have been more
intuitive: a `Knight (Node2D)` managed by a `MovementManager` that does the
pathing and tweening.

**Main point — node identity:** identifying a gamepiece with a top node that is
a `Path2D` is very counter-intuitive. A gamepiece is conceptually a character,
not a path. The node hierarchy should reflect what the thing IS, not what
mechanism it uses internally. A more intuitive structure:

```
Knight (Node2D / CharacterBody2D)   ← this IS the piece
├── Sprite2D                         ← its appearance
├── Path2D                           ← movement mechanism (if using Path2D)
│   └── PathFollow2D
└── WeaponMarker
```

vs what we have:

```
Knight (Path2D)                      ← this IS a path???
└── PathFollow2D
    └── Sprite2D
```

If using `Path2D`/`PathFollow2D` for movement, they should be children of the
gamepiece node, not the root. If using a `Tween`, no extra nodes are needed at
all. Either way, the root node type should match the conceptual identity of the
object (`Node2D`, `CharacterBody2D`, `Area2D`), not the movement mechanism.

**Separate consideration — Path2D vs Tween:** if point-to-point grid movement is
all that's needed, a `Tween` on `position` is simpler and more readable than
`Path2D` + `PathFollow2D`. Reserve `Path2D`/`PathFollow2D` for actual curved
paths or when you need the follower's built-in features (loop, rotation, offset).
This should be an explicit design decision, not a default.

## MCP tool usage: query specs before architectural decisions

The `mcp0_get_godot_spec` tool is available and can query any Godot class's
properties, signals, and inheritance hierarchy. **Use it before choosing a node
type or architecture.**

For example, before deciding to use `Path2D` as the root node for gamepieces, I
should have queried:
- `mcp0_get_godot_spec("Path2D")` — to see it's designed for curved paths, not grid hops
- `mcp0_get_godot_spec("PathFollow2D")` — to understand it follows a curve, not a discrete path
- `mcp0_get_godot_spec("Node2D")` — to confirm a plain Node2D + Tween would suffice

**Lesson for next time:** make it a habit to query class specs before committing
to a node type. The tool exists specifically for this. Don't rely on memory
alone — Godot's API is large and some classes have surprising properties or
limitations that only surface when you read the spec.

## class_name resolution in headless validation

When you create new scripts with `class_name`, the Godot headless validator
(`--check-only`) can't resolve them until the global class cache is rebuilt.
This causes cascading "Could not find type X in the current scope" errors that
are misleading — the scripts are correct, just not cached.

**Correct solution:** run `godot --headless --import --quit` to rebuild the
class cache before validating. Do this after creating any new `class_name`
script or after renaming one. Once the cache is built, you can reference types
directly (e.g. `TileAtlas.KNIGHT`, `TileAtlas.region_for(...)`) without
`preload()` workarounds.

If you still hit resolution issues after rebuilding the cache, double-check that
the `class_name` line is at the top of the file (after any `@tool` annotation)
and that the file has no parse errors of its own.

## Scene file details

### `load_steps` is deprecated (Godot 4.6+)

The `load_steps=N` attribute in `[gd_scene]` headers was removed in Godot 4.6.
It's no longer needed — Godot computes the step count automatically. Don't
include it when writing `.tscn` files by hand. If present, Godot ignores it but
it creates unnecessary diffs in version control.

### Assign resources in the scene, not in code

When a node needs a `Resource` (like `Stats` for a monster), assign it in the
`.tscn` file as a sub_resource — don't leave it null and fall back to
`Resource.new()` in `_ready()`. The scene file is the right place for
per-instance configuration. The code fallback is a safety net, not the primary
path.

For each monster/character in a scene, create an inline `[sub_resource]` with
the Stats script and assign it:
```
[sub_resource type="Resource" id="Resource_ghost_stats"]
script = ExtResource("stats_script")
metadata/_custom_type_script = "uid://..."

[node name="Ghost" ...]
stats = SubResource("Resource_ghost_stats")
```

Or better: create separate `.tres` files (`ghost_stats.tres`, `orc_stats.tres`)
and assign them as ext_resources. This is the preferred way per the godot rules.

## Debugging workflow for runtime issues

### Setup: timestamped debug prints

When something doesn't work at runtime (clicks not registering, movement not
happening, paths returning empty), add timestamped debug prints at every step
of the flow. Use a consistent format so logs are easy to read:

```gdscript
var _start_time: float = 0.0

func _ready() -> void:
    _start_time = Time.get_ticks_msec() / 1000.0

func _dbg(msg: String) -> void:
    var t := Time.get_ticks_msec() / 1000.0 - _start_time
    print("[%.3f] ClassName: %s" % [t, msg])
```

Place prints at:
- Entry points (click handlers, input events)
- Every early return / guard clause
- Before and after calls to other objects
- Inside the called object's methods (e.g. `move_to`, `get_path_to_cell`)

Each print should include enough state to diagnose the failure: the arguments,
the relevant variables, and which branch was taken.

### Running the scene for interactive testing

Run a specific scene directly from command line (non-headless) so the user can
interact with it while logs are captured:

```bash
godot --path /path/to/project res://examples/hero_rpg/scenes/pathfinding_demo.tscn
```

The user clicks around, then closes the window. The full stdout (all debug
prints) is captured by the assistant via `run_command` (non-blocking, then
`command_status` to read output after the user says "done").

### After fixing: remove debug prints

Once the bug is found and fixed, remove all `_dbg` calls and debug `print`
statements. They should not be committed.

## Testing frameworks for Godot

There are **two main unit testing frameworks** for Godot: **GUT** (Godot Unit
Test) and **WAT** (Window/Widget Assertion Toolkit). Both let you write tests
in GDScript. They differ in syntax, feature set, and — critically — Godot 4
support.

**For our target versions (Godot 4.6 and 4.7), only GUT is viable.** WAT is
Godot-3-only and has no Godot 4 port (see the WAT section below for details).

### GUT (Godot Unit Test)

- **Repo:** https://github.com/bitwes/Gut
- **Docs:** https://gut.readthedocs.io/
- **Actively maintained:** Yes
- **Install:** Asset Library → search "GUT - Godot Unit Testing (Godot 4)", or
  clone `addons/gut` into your project and enable the plugin.

GUT is the de-facto standard for Godot 4 testing. Tests extend `GutTest`
(`res://addons/gut/test.gd`), test methods must be prefixed with `test_`, and
test files must be prefixed with `test_` by default.

#### Version mapping for Godot 4.6 and 4.7

GUT has version-specific releases matched to Godot versions. **Use the correct
branch/tag for your engine version** — mismatched versions cause subtle errors.

| Godot version | GUT version | Branch / Tag | Docs |
| --- | --- | --- | --- |
| 4.6.x | 9.6.1 | `v9.6.1` tag or `main` branch | https://gut.readthedocs.io/en/latest/ |
| 4.7.x | 9.7.1 | `godot_4_7` branch or `v9.7.1` tag | https://gut.readthedocs.io/en/v9.7.1/ |

The Asset Library only shows one GUT entry for Godot 4; it picks the version
matching your engine. If installing manually (clone/zip), select the right
branch.

#### Breaking changes and new features in 9.6.0 (Godot 4.6)

- **`assert_push_error` / `assert_engine_error` changed:** now only accept a
  string and assert a single error exists with that text. Use the new
  `assert_push_error_count` / `assert_engine_error_count` to assert counts.
  Passing a number to the old methods now fails with a message telling you to
  use the new count methods.
- **`assert_push_warning` / `assert_push_warning_count` added:** calls to
  `push_warning` no longer cause tests to fail due to unexpected errors (#775).
- **`print_tracked_errors`** added — prints all errors generated by the test.
- **Singleton doubling:** can now double Godot singletons (`Input`, `Time`,
  `OS`, etc.). See https://gut.readthedocs.io/en/latest/Doubling-Singletons.html
- **Elapsed time methods:** `get_elapsed_sec`, `get_elapsed_msec`,
  `get_elapsed_usec`, `get_elapsed_idle_frames`, `get_elapsed_process_frames`,
  `get_elapsed_physics_frames`.
- **Headless mode:** GUT automatically ignores `pause_before_teardown` and
  exits when tests finish (no need for `-gignore_pause` and `-gexit`).
- **Scene changes:** using `SceneTree.change_scene_to_file` or other
  change-scene methods in a test no longer breaks things when running from the
  editor (#780).

#### Breaking changes in 9.7.0 (Godot 4.7) — doubles return-type behavior

**This is the most important 4.7-specific gotcha.** Godot 4.7 introduced more
restrictive type checking for return values. Previously, GUT Doubles could
return `null` regardless of the declared return type. Now Doubles return a
default value for each `TYPE_` constant.

This can cause **false positives/negatives** in existing and new tests. If you
stub a method to return an invalid value, GUT generates an error but execution
continues, resulting in an engine error too:

```
[GUT ERROR]: Method [explicit_int_return] was stubbed to return invalid value [adsf].
SCRIPT ERROR: Trying to return a value of type "String" from a function whose return type is "int".
```

`stub(...).to_do_nothing()` now returns the **default value for the return
type** of the function, not `null`. See
https://gut.readthedocs.io/en/latest/Doubles.html for the complete list of
default values per type.

**Practical impact:** when upgrading a project from Godot 4.6 to 4.7, audit
all doubles and stubs. Any test that relied on a doubled method returning
`null` for a typed return will behave differently. Explicitly stub return
values that match the declared type.

**Basic structure:**

```gdscript
extends GutTest

const Player = preload("res://player.gd")

func before_all():
    gut.p("Runs once before all tests")

func before_each():
    gut.p("Runs before each test")

func after_each():
    gut.p("Runs after each test")

func after_all():
    gut.p("Runs once after all tests")

func test_player_starts_with_full_health():
    var player = Player.new()
    add_child_autofree(player)
    assert_eq(player.health, 100, "Initial health should be 100")
```

**Key assertions** (all take an optional message as last arg):

| Function | Description |
| --- | --- |
| `assert_eq(a, b, msg)` | Verify a equals b |
| `assert_ne(a, b, msg)` | Verify a does not equal b |
| `assert_true(val, msg)` | Verify val is true |
| `assert_false(val, msg)` | Verify val is false |
| `assert_null(val, msg)` | Verify val is null |
| `assert_not_null(val, msg)` | Verify val is not null |
| `assert_gt(a, b, msg)` | Verify a is greater than b |
| `assert_lt(a, b, msg)` | Verify a is less than b |
| `assert_has(container, val, msg)` | Verify container contains val |
| `assert_almost_eq(got, expected, error, msg)` | Float comparison with tolerance |
| `assert_between(got, low, high, msg)` | Verify value is within a range |
| `assert_file_exists(path, msg)` | Verify a file exists |
| `assert_no_new_orphans(msg)` | Verify no orphan nodes were leaked (call in `after_each`) |

#### Memory management: `add_child_autofree` / `add_child_autoqfree`

When you create `Node` instances in tests, you must add them to the tree (so
`_ready`, `_process`, etc. fire) and ensure they are cleaned up. GUT provides:

- `add_child_autofree(node)` — adds the node as a child of the test node and
  calls `free()` on it after the test. Use for nodes you `new()`.
- `add_child_autoqfree(node)` — same but calls `queue_free()` instead. Use when
  the node or its children might have pending deferred calls.

If you forget this, you get orphaned nodes that pollute subsequent tests. Add
`assert_no_new_orphans()` in `after_each` to catch leaks:

```gdscript
func after_each():
    assert_no_new_orphans()
```

#### Advancing frames: `simulate` vs `await wait_*`

This is the critical detail the user asked about. GUT offers two ways to test
code that depends on frame processing:

**1. `gut.simulate(obj, times, delta)` — synchronous, no real frames:**

Calls `_process` and `_physics_process` directly on the object and all its
descendants, `times` times, passing `delta`. The main loop is **not** running,
so timers, `await get_tree().create_timer(...)`, and deferred signals will
**not** fire. Use this for pure logic that lives in `_process`/`_physics_process`.

```gdscript
# Given MyObject increments a_number by 1 in _process each frame
func test_does_something_each_loop():
    var my_obj = MyObject.new()
    add_child_autofree(my_obj)
    gut.simulate(my_obj, 20, .1)
    assert_eq(my_obj.a_number, 20, 'Should be 20 after 20 simulated frames')
```

By default `simulate` ignores whether processing is enabled. Pass
`check_is_processing=true` as the 4th arg to respect `set_process(false)` /
`set_physics_process(false)`.

**2. `await wait_*` — asynchronous, real frames run:**

These pause test execution and let the actual SceneTree tick. Use these when
you need timers, signals, `call_deferred`, or any `await`-based code to run.

| Method | Description |
| --- | --- |
| `await wait_seconds(time, msg)` | Wait `time` seconds of real game time |
| `await wait_physics_frames(n, msg)` | Wait `n` physics frames (`_physics_process` ticks) |
| `await wait_idle_frames(n, msg)` | Wait `n` process/idle frames (`_process` ticks). `wait_process_frames` is an alias. |
| `await wait_for_signal(sig, max_wait, msg)` | Wait until signal emits or `max_wait` seconds. Returns `true` if emitted, `false` on timeout. |
| `await wait_until(callable, max_wait, msg)` | Wait until a `Callable` predicate returns `true` each frame, or timeout. |
| `await wait_while(callable, max_wait, msg)` | Inverse of `wait_until` — waits while callable returns `true`. |

**Match the wait method to the processing mode.** If your code runs in
`_process`, use `wait_idle_frames`. If it runs in `_physics_process`, use
`wait_physics_frames`. Mismatching causes off-by-one frame errors and flaky
tests (see GUT issue #593).

Example from GUT's own test suite — testing a node that moves in `_process`:

```gdscript
func test_illustrate_yield():
    var moving_node = MovingNode.new()
    add_child_autofree(moving_node)
    moving_node.set_position(Vector2(0, 0))

    # While the await happens, the node actually moves in _process
    await wait_seconds(2)
    assert_gt(moving_node.get_position().x, 0)
    assert_between(moving_node.get_position().x, 3.9, 4,
        'it should move almost 4 whatevers at speed 2')
```

Example from GUT's integration tests — running the full test runner and waiting
for it to finish:

```gdscript
func test_does_not_quit_when_gut_config_does_not_say_to():
    var gr = _create_runner()
    add_child_autofree(gr)
    gr.run_tests()
    await wait_physics_frames(MIN_FRAMES_TO_RUN_TESTS)
```

**Rule of thumb:** use `simulate` for deterministic `_process` logic without
side effects. Use `await wait_*` for anything involving timers, signals,
tweens, physics, or deferred calls. Never use bare `await some_node.signal` in
tests — if the signal never fires the test hangs. Always use
`wait_for_signal` with a timeout.

#### Signal testing

```gdscript
func test_assert_signal_emitted():
    var obj = SignalObject.new()
    watch_signals(obj)
    obj.emit_signal("some_signal")
    assert_signal_emitted(obj, "some_signal")

func test_assert_signal_emitted_with_parameters():
    var obj = SignalObject.new()
    watch_signals(obj)
    obj.emit_signal("some_signal", 1, 2, 3)
    obj.emit_signal("some_signal", "a", "b", "c")
    # Default checks the last emission
    assert_signal_emitted_with_parameters(obj, "some_signal", ["a", "b", "c"])
    # Check a specific emission by index
    assert_signal_emitted_with_parameters(obj, "some_signal", [1, 2, 3], 0)

func test_assert_signal_emit_count():
    var obj = SignalObject.new()
    watch_signals(obj)
    obj.emit_signal("some_signal")
    obj.emit_signal("some_signal")
    assert_signal_emit_count(obj, "some_signal", 2)
```

`wait_for_signal` internally calls `watch_signals` for you, so you can skip the
explicit `watch_signals` call when using it.

#### Doubles, stubs, and spies

```gdscript
var Foo = load("res://foo.gd")

# double() returns a LOADED class, not an instance
var double_foo = double(Foo).new()

# Stub methods to return specific values
stub(double_foo.bar).to_return(42)
stub(double_foo, "something").to_call_super()
stub(double_foo.other_thing).to_return(77).when_passed(1, 2, "c")

# Spy: assert a method was called
double_foo.bar()
assert_called(double_foo, "bar")
assert_call_count(double_foo, "bar", 1)
```

#### Parameterized tests

```gdscript
func test_addition(params = use_parameters([
    [2, 2, 4],
    [4, 4, 8],
    [5, 5, 10],
])):
    assert_eq(params[0] + params[1], params[2])
```

#### Inner test classes

Group related tests inside a single file. Class names must start with `Test`
and extend `GutTest`:

```gdscript
extends GutTest

class TestFeatureA:
    extends GutTest
    var _obj = null
    func before_each():
        _obj = MyObject.new()
    func test_something():
        assert_true(_obj.is_something_cool(), "Should be cool.")

class TestFeatureB:
    extends GutTest
    func test_foobar():
        var obj = MyObject.new()
        assert_eq(obj.foo(), "bar", "Foo should return bar")
```

#### Running tests

- **Editor:** GUT panel (bottom dock) → "Run All", or run a single script / single test method with the buttons.
- **Command line (CI/CD):**
  ```bash
  godot --headless -s addons/gut/gut_cmdln.gd -gdir=res://test/unit -gexit
  ```
  Configure directories and options via `.gutconfig.json`. Export results in
  JUnit XML format for CI integration.
- **VSCode:** GUT extension available in the marketplace.

#### GUT usage in the wild

GUT is used by its own extensive test suite (hundreds of tests across `test/unit`,
`test/integration`, `test/samples`). The `bitwes/Gut` repo itself is the best
reference for advanced patterns — see `test/samples/test_readme_examples.gd` for
signal/yield examples, `test/integration/test_gut_integration.gd` for
`add_child_autofree` + `wait_physics_frames` patterns, and
`test/unit/test_test.gd` for `assert_no_new_orphans` usage.

GDQuest does not appear to maintain a public GUT-based test suite in their main
repositories; their content focuses on design patterns and tutorials rather
than shipping test suites. The most reliable high-quality examples of GUT in
practice come from the GUT repo itself and from community guides (e.g.
UhiyamaLab's GUT tutorial, Stephan Bester's Medium series).

### WAT (Window/Widget Assertion Toolkit) — Godot 3 only, not usable on 4.6/4.7

- **Repo:** https://github.com/AlexDarigan/wat
- **Godot 4 support:** **No.** The repo explicitly states "THIS REPO IS NOT
  4.0 COMPATIBLE!" The author stated in the 6.0.1 release notes (Dec 2021):
  "There are no plans for future features. I want to make a start on WAT for
  Godot 4." No Godot 4 port was ever released.
- **Last push:** July 2023. **Latest release:** v6.0.1, Dec 2021.
- **Issue #358** (Godot 4 support, opened Nov 2022) remains open with no
  resolution.
- **Asset Library:** lists WAT 6.0.1 as "Tested with version 3.3.2" — Godot 3
  only.

**WAT is not a viable choice for Godot 4.6 or 4.7 projects.** It is documented
here for completeness and for projects still on Godot 3. If you need C# testing
on Godot 4, GUT does not support C# — but neither does WAT on Godot 4. For C#
on Godot 4, consider xUnit/NUnit directly (outside the engine) or Gadget
(another emerging option).

Tests extend `WAT.Test`, test methods must be prefixed with `test`, and test
files must use the `.test.gd` suffix by default.

**Basic structure:**

```gdscript
extends WAT.Test

func title() -> String:
    return "My Example Test"

func test_simple_example() -> void:
    describe("My Example Test Method")
    asserts.is_true(true, "optional context")

# Setup/teardown lifecycle
func start() -> void:
    # Runs once before all test methods
    pass

func pre() -> void:
    # Runs before each test method
    pass

func post() -> void:
    # Runs after each test method
    pass

func end() -> void:
    # Runs once after all test methods
    pass
```

**Key differences from GUT:**

- Assertions go through `asserts.<method>` (e.g. `asserts.is_equal(a, b)`)
  rather than bare `assert_eq(a, b)`.
- Integrated editor panel (bottom dock) rather than a separate window.
- Has a C# / Mono version.
- Cleans up after itself with regards to memory (stray nodes) — historically a
  GUT weakness, though GUT now has `add_child_autofree` and
  `assert_no_new_orphans`.
- No inner test classes; instead uses a `context` string on each assertion.
- `describe("...")` sets the display name for a test method.

**Parameterized tests:**

```gdscript
func test_parameterized_example() -> void:
    parameters([["addend", "augend", "result"],
                [2, 2, 4], [4, 4, 8], [5, 5, 10]])
    var actual = p["addend"] + p["augend"]
    asserts.is_equal(p["result"], actual,
                     "%s + %s = %s" % [p["addend"], p["augend"], p["result"]])
```

#### Yielding / frame advancement in WAT (Godot 3 syntax)

WAT uses Godot 3 `yield` syntax (not `await`). The framework provides a `YIELD`
signal on a returned yielder object:

```gdscript
func test_yield_until_timeout() -> void:
    # Wait 0.2 seconds
    yield(until_timeout(0.2), YIELD)
    asserts.auto_pass("Yielding On Timeout")

signal my_signal
func test_yield_until_signal() -> void:
    watch(self, "my_signal")
    call_deferred("emit_signal", "my_signal")
    # Wait for signal or 0.2s timeout, whichever comes first
    yield(until_signal(self, "my_signal", 0.2), YIELD)
    asserts.auto_pass("Yielding on Signal")
    asserts.signal_was_emitted(self, "my_signal")
    unwatch(self, "my_signal")
```

**Signal testing:**

```gdscript
signal my_signal

func test_signal_was_emitted() -> void:
    watch(self, "my_signal")
    emit_signal("my_signal")
    asserts.signal_was_emitted(self, "my_signal")
    unwatch(self, "my_signal")

func test_signal_was_emitted_x_times() -> void:
    watch(self, "my_signal")
    emit_signal("my_signal")
    emit_signal("my_signal")
    asserts.signal_was_emitted_x_times(self, "my_signal", 2)
    unwatch(self, "my_signal")

func test_signal_was_emitted_with_arguments() -> void:
    watch(self, "my_signal")
    emit_signal("my_signal", "Hello", "World")
    asserts.signal_was_emitted_with_arguments(self, "my_signal", ["Hello", "World"])
    unwatch(self, "my_signal")
```

Note the `watch` / `unwatch` pattern — you must explicitly unwatch after each
test to avoid leaking watchers.

### Comparison and recommendation (Godot 4.6 / 4.7)

| Feature | GUT 9.6.1 (4.6) / 9.7.1 (4.7) | WAT 6.0.1 |
| --- | --- | --- |
| Godot 4.6 support | Yes (9.6.1) | No |
| Godot 4.7 support | Yes (9.7.1) | No |
| Actively maintained | Yes | No (frozen since Dec 2021) |
| Test base class | `GutTest` | `WAT.Test` |
| Assertion style | `assert_eq(a, b)` | `asserts.is_equal(a, b)` |
| Inner test classes | Yes | No (uses context strings) |
| Doubles / stubs / spies | Yes (full + partial + singletons) | Yes (test doubles) |
| Parameterized tests | Yes (`use_parameters`) | Yes (`parameters` + `p` dict) |
| CLI / CI integration | Yes (JUnit XML export) | Yes (JUnit XML export) |
| C# / Mono support | No | Yes (Godot 3 only) |
| Memory cleanup | Manual (`add_child_autofree`) + `assert_no_new_orphans` | Automatic |
| Frame advancement | `gut.simulate` (sync) + `await wait_*` (async) | `yield(until_timeout/until_signal, YIELD)` |
| Editor integration | Dock panel | Dock panel |
| Singleton doubling | Yes (since 9.6.0) | No |
| Warning assertions | `assert_push_warning` (since 9.6.0) | No |

**Recommendation for Godot 4.6 / 4.7: use GUT.** It is the only actively
maintained option with explicit compatibility for both versions. Key points:

- **4.6 projects:** use GUT 9.6.1 (`v9.6.1` tag or `main` branch).
- **4.7 projects:** use GUT 9.7.1 (`godot_4_7` branch or `v9.7.1` tag).
- **Upgrading 4.6 → 4.7:** audit all doubles and stubs — the return-type
  behavior change in 9.7.0 is the main source of test breakage. Doubles now
  return typed defaults instead of `null`; `to_do_nothing()` returns the
  default for the return type.
- The `simulate` + `await wait_*` toolkit covers both synchronous logic testing
  and real-frame async testing. The main gotcha is memory management — always
  use `add_child_autofree` / `add_child_autoqfree` and check
  `assert_no_new_orphans` in `after_each`.
