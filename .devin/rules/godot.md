---
trigger: manual
---
# GDScript Language Reference for Code Generation

GDScript is a high-level, object-oriented, imperative, and gradually typed programming language built for the Godot game engine. It uses indentation-based syntax similar to Python but is entirely independent from Python. Key differences from Python are called out throughout this document.

## Example Script

```gdscript
# A file is a class. Every .gd file implicitly defines one class.

class_name MyClass
extends BaseClass

# Member variables
var a = 5
var s = "Hello"
var arr = [1, 2, 3]
var dict = {"key": "value", 2: 3}
var typed_var: int
var inferred_type := "String"

# Constants
const ANSWER = 42
const THE_NAME = "Charly"

# Enums
enum {UNIT_NEUTRAL, UNIT_ENEMY, UNIT_ALLY}
enum Named {THING_1, THING_2, ANOTHER_THING = -1}

# Built-in vector types
var v2 = Vector2(1, 2)
var v3 = Vector3(1, 2, 3)

func some_function(param1, param2, param3 = 123):
    const local_const = 5

    if param1 < local_const:
        print(param1)
    elif param2 > 5:
        print(param2)
    else:
        print("Fail!")

    for i in range(20):
        print(i)

    while param2 != 0:
        param2 -= 1

    match param3:
        3:
            print("param3 is 3!")
        _:
            print("param3 is not 3!")

    var local_var = param1 + 3
    return local_var

func something(p1, p2):
    super(p1, p2)

func other_something(p1, p2):
    super.something(p1, p2)

class Something:
    var a = 10

func _init():
    print("Constructed!")
    var lv = Something.new()
    print(lv.a)
```

---

## Operators (Selected)

**Attribute reference:** `x.attribute` accesses a member of an object.

**Await:** `await x` pauses execution until a signal is emitted or a coroutine finishes.

**Type checking:** `x is Node` returns `true` if `x` is of that type. `x is not Node` returns `true` if it is not. For dynamic type checks, use `is_instance_of(value, type)` which accepts `Variant.Type` constants, engine classes, or scripts (including inner classes).

**Bitwise operations:** `~x` (NOT), `x & y` (AND), `x | y` (OR), `x ^ y` (XOR), `x << y` and `x >> y` (shift).

**Inclusion checking:** `x in y` tests membership in strings, arrays, dictionaries, ranges, or nodes. Used with `for`, it iterates instead.

**Ternary expression:** `value_if_true if condition else value_if_false` (right-associative).

**Assignment operators:**
`x = y`, `x += y`, `x -= y`, `x *= y`, `x /= y`, `x **= y`, `x %= y`, `x &= y`, `x |= y`, `x ^= y`, `x <<= y`, `x >>= y`. Assignment cannot be used inside an expression.

**Important notes on division and modulo:**
- If both operands of `/` are `int`, integer division is performed: `5 / 2 == 2`, not `2.5`. Use a float literal (`x / 2.0`) or cast (`float(x) / y`) to get fractional results.
- `%` works only on ints; use `fmod()` for floats. Both use truncation, not floor division. Use `posmod()` / `fposmod()` for mathematical remainder.
- For float comparison, use `is_equal_approx()` and `is_zero_approx()` instead of `==`.

---

## Literals

**Numbers:** integers can be written in base 10 (`45`), hexadecimal (`0x8f51`), or binary (`0b101010`). Floats use decimal notation (`3.14`, `58.1e-10`). Use `_` separators for readability: `12_345_678`, `3.141_592_7`, `0x8080_0000_ffff`.

**Booleans:** `true` and `false` (lowercase, unlike Python's `True`/`False`).

**Null:** the empty type is `null`, not `None` (different from Python).

**Strings:** `"Hello"` or `'Hi'`. Triple-quoted: `"""Hello"""` or `'''Hi'''`. Raw strings: `r"Hello"` (no escape processing). Triple-quoted raw: `r"""Hello"""`.

**StringName:** `&"name"` — an immutable, interned string optimized for fast comparison. Good for dictionary keys and signal names.

**NodePath:** `^"Node/Label"` — a pre-parsed path to a node or property, useful with tweens and tree access.

### Node Access Shorthands

- `$NodePath` is shorthand for `get_node("NodePath")`. Example: `$Player/Sprite2D`.
- `%UniqueNode` is shorthand for `get_node("%UniqueNode")`. This accesses a **scene unique node** — a node marked with "Access as Unique Name" in the editor (a `%` appears before its name in the scene tree). Unique nodes are cached and fast to retrieve, but they only resolve within the same scene owner. Use them for stable internal nodes like UI elements and spawn points; do not rely on them for nodes that cross scene boundaries or are created dynamically.

---

## Annotations

Annotations start with `@` and modify declarations or scripts. Key annotations:

### `@onready`

Defers a member variable's initialization until `_ready()` is called:

```gdscript
@onready var my_label = get_node("MyLabel")
# Equivalent to assigning in _ready(), but more concise.
```

**Critical rule:** `@onready` and `@export` must NOT be used together on the same variable. `@onready` overrides the exported value when `_ready()` runs, which produces unexpected behavior. This generates a warning treated as an error by default. When using `@export`, always provide a sensible default value instead of relying on `@onready`.

### `@export` annotations

Exported variables are saved with the resource, visible in the inspector, and transferred over RPCs. An exported variable must be initialized to a constant expression or have a type specifier.

```gdscript
@export var speed: float = 200.0
@export var health: int = 100
```

**Basic exports with types:**
```gdscript
@export var number: int = 5
@export var resource: Resource
@export var node: Node
```

**Grouping in the inspector:**
```gdscript
@export_group("Movement")
@export var speed: float = 200.0
@export var acceleration: float = 50.0

@export_subgroup("Advanced")
@export var friction: float = 0.1

@export_category("Combat")
@export var damage: int = 10
```

**Strings as paths:**
```gdscript
@export_file var f                          # Any file
@export_file("*.txt") var f                 # Filtered by extension
@export_dir var f                           # Directory
@export_multiline var text                  # Large text field
```

**Numeric ranges:**
```gdscript
@export_range(0, 100) var health: int = 100
@export_range(-10, 20, 0.2) var k: float    # With step
@export_range(0, 100, 1, "or_less", "or_greater") var flexible: int
@export_range(0, 100000, 0.01, "exp") var exponential: float
@export_range(0, 100, 1, "suffix:m") var distance: int
@export_range(0, 360, 0.1, "radians_as_degrees") var angle: float
```

**Easing curves:**
```gdscript
@export_exp_easing var transition_speed
```

**Colors:**
```gdscript
@export var col: Color
@export_color_no_alpha var col: Color
```

**Nodes (direct reference, preferred over NodePath):**
```gdscript
@export var player: Node
@export var some_button: BaseButton
```

**Enums:**
```gdscript
enum NamedEnum {THING_1, THING_2, ANOTHER_THING = -1}
@export var x: NamedEnum

@export_enum("Warrior", "Magician", "Thief") var character_class: int
@export_enum("Slow:30", "Average:60", "Very Fast:200") var character_speed: int
@export_enum("Rebecca", "Mary", "Leah") var character_name: String = "Rebecca"
```

**Bit flags:**
```gdscript
@export_flags("Fire", "Water", "Earth", "Wind") var spell_elements = 0
@export_flags_2d_physics var layers_2d_physics
@export_flags_3d_render var layers_3d_render
```

**Arrays:**
```gdscript
@export var ints: Array[int] = [1, 2, 3]
@export var scenes: Array[PackedScene] = []
@export_range(-360, 360, 0.001, "degrees") var laser_angles: Array[float] = []
```

**Curves (for value-over-variable relationships):**

A `Curve` resource maps an input in the range `[0, 1]` to an output value along a designer-editable curve. This is extremely useful for any property that depends on a continuous variable — damage falloff over distance, speed over time, opacity over health percentage, audio volume over proximity, etc. The inspector shows a visual curve editor where users can add points and adjust tangents.

```gdscript
## How damage scales with distance (0 = point blank, 1 = max range).
## Designers can shape this curve in the inspector.
@export var damage_curve: Curve

func calculate_damage(base_damage: float, distance: float, max_range: float) -> float:
    var t = clampf(distance / max_range, 0.0, 1.0)
    return base_damage * damage_curve.sample_baked(t)
```

Key methods:
- `sample(offset: float) -> float` — evaluates the curve at the given X position (0.0–1.0).
- `sample_baked(offset: float) -> float` — same but uses a baked/cached version (faster, preferred at runtime).

Use `Curve` whenever a property changes based on a variable and you want designers to be able to tweak the relationship visually. Do NOT use `Curve2D` or `Curve3D` for this — those are spatial path curves for movement, not value mapping.

**Storage-only (serialized but hidden from inspector):**
```gdscript
@export_storage var internal_state: int
```

**Tool buttons (for `@tool` scripts):**
```gdscript
@export_tool_button("Hello", "Callable") var hello_action = hello
func hello():
    print("Hello world!")
```

**Important:** reading an exported variable in `_init()` returns the default value, not the inspector-set value. Read exported values in `_ready()` or in a setter.

---

## Comments

`#` starts a single-line comment. The editor highlights special keywords in comments (case-sensitive, must be uppercase):
- **Red:** `ALERT`, `ATTENTION`, `CAUTION`, `CRITICAL`, `DANGER`, `SECURITY`
- **Yellow:** `BUG`, `DEPRECATED`, `FIXME`, `HACK`, `TASK`, `TBD`, `TODO`, `WARNING`
- **Green:** `INFO`, `NOTE`, `NOTICE`, `TEST`, `TESTING`

### Documentation Comments

Use `##` (double hash) for documentation comments. These appear in the script documentation and as inspector tooltips for exported variables. Place them directly above the documented item or at the top of a file:

```gdscript
## The maximum speed of the character in pixels per second.
@export var max_speed: float = 300.0

## Current health points. When this reaches zero, the character dies.
var health: int = 100
```

Always write documentation comments above exported variables and important class members.

### Code Regions

Use `#region` and `#endregion` to create foldable sections in the editor:

```gdscript
#region Terrain generation
func generate_lakes():
    pass

func generate_hills():
    pass
#endregion

#region Terrain population
func place_vegetation():
    pass
#endregion
```

Use code regions in files with many functions (more than ~10). If a file has only a few small functions, do not bother with regions.

---

## Line Continuation

A backslash `\` at the end of a line continues it on the next. By default, avoid using line continuation; restructure the code instead.

---

## Built-in Types

### Basic Types

- `null` — empty type, only valid for Object-derived types. Not `None`.
- `bool` — `true` or `false`.
- `int` — 64-bit signed integer.
- `float` — 64-bit double-precision floating point.
- `String` — Unicode character sequence.
- `StringName` — immutable interned string, fast to compare. Use for dictionary keys and signal names.
- `NodePath` — pre-parsed path to a node or property.

### Vector Types

**`Vector2`** — 2D vector with `x` and `y` float components.
- `Vector2(x, y)` constructor. Also `Vector2.ZERO`, `Vector2.ONE`, `Vector2.UP`, `Vector2.DOWN`, `Vector2.LEFT`, `Vector2.RIGHT`.
- `length() -> float` — returns the magnitude.
- `length_squared() -> float` — returns squared magnitude (faster, use for comparisons).
- `normalized() -> Vector2` — returns a unit-length vector (length = 1) pointing in the same direction.
- `is_normalized() -> bool` — checks if already unit length.
- `distance_to(to: Vector2) -> float` — distance to another point.
- `dot(with: Vector2) -> float` — dot product.
- `angle() -> float` — angle in radians relative to the X axis.
- `rotated(angle: float) -> Vector2` — returns the vector rotated by the given angle in radians.
- `lerp(to: Vector2, weight: float) -> Vector2` — linear interpolation.

**`Vector2i`** — 2D vector with `int` components. Use for grid coordinates, tile positions, and pixel-exact work. Use `Vector2` for physics, movement, and any continuous math. Convert with `Vector2(vec2i)` or `Vector2i(vec2)`.

**`Vector3`** — 3D vector with `x`, `y`, `z` float components.
- Same core methods as `Vector2`: `length()`, `length_squared()`, `normalized()`, `is_normalized()`, `distance_to()`, `dot()`, `lerp()`.
- `cross(with: Vector3) -> Vector3` — cross product (gives a perpendicular vector).
- `rotated(axis: Vector3, angle: float) -> Vector3` — rotates around an axis.

**`Vector3i`** — 3D vector with `int` components. Use for 3D grids and voxel indexing.

**`Rect2`** — 2D rectangle with `position` and `size` (both `Vector2`). Has `end` = `position + size`.

**`Transform2D`** — 3×2 matrix for 2D transforms (position, rotation, scale). Contains columns `x`, `y` (basis), and `origin` (position).
- `Transform2D(rotation: float, position: Vector2)` — common constructor.
- `affine_inverse() -> Transform2D` — returns the inverse transform.
- `rotated(angle: float) -> Transform2D` — returns a rotated copy.
- `scaled(scale: Vector2) -> Transform2D` — returns a scaled copy.
- `translated(offset: Vector2) -> Transform2D` — returns a translated copy.

**Other spatial types:** `Plane`, `Quaternion` (3D rotation), `AABB` (3D bounding box), `Basis` (3×3 rotation/scale matrix), `Transform3D` (full 3D transform with `basis` and `origin`).

### Color

`Color` stores RGBA as floats (0.0–1.0). Fields: `r`, `g`, `b`, `a` (also accessible as `h`, `s`, `v`).

**Constructors (prefer hex strings):**
```gdscript
var c1 = Color("#ff6600")              # Hex RGB (preferred)
var c2 = Color("#80ff6600")            # Hex ARGB (with alpha)
var c3 = Color(1.0, 0.4, 0.0)         # Float RGB
var c4 = Color(1.0, 0.4, 0.0, 0.5)    # Float RGBA
var c5 = Color("orange")              # Named color (case-insensitive)
var c6 = Color8(255, 102, 0, 255)     # Byte values 0-255
var c7 = Color.from_hsv(0.07, 1.0, 1.0) # HSV
```

**Common named constants:** `Color.WHITE`, `Color.BLACK`, `Color.RED`, `Color.GREEN`, `Color.BLUE`, `Color.TRANSPARENT`.

**Common operations:**
```gdscript
color.lerp(other_color, 0.5)   # Blend two colors
color.lightened(0.2)            # Make lighter
color.darkened(0.2)             # Make darker
color.inverted()                # Invert
color.to_html()                 # Convert to hex string
color.get_luminance()           # Light intensity (0.0–1.0)
```

### Arrays

Generic ordered collection, indexed from 0. Negative indices count from the end. Arrays are **passed by reference**.

```gdscript
var arr = []
arr = [1, 2, 3]
var b = arr[1]            # 2
var c = arr[-1]           # 3 (last element)
arr[0] = "Hi!"            # Replace element
arr.append(4)             # Add to end
arr.size()                # Length
arr.has(2)                # Contains check
arr.find(3)               # Index of element (-1 if not found)
arr.remove_at(0)          # Remove by index
arr.erase(4)              # Remove first occurrence of value
arr.insert(1, "mid")      # Insert at index
arr.pop_back()            # Remove and return last
arr.pop_front()           # Remove and return first
arr.sort()                # Sort in place
arr.reverse()             # Reverse in place
arr.map(func(x): return x * 2)    # Functional map
arr.filter(func(x): return x > 1) # Functional filter
arr.any(func(x): return x > 5)    # Any match
arr.all(func(x): return x > 0)    # All match
```

**Typed arrays** restrict element types. Nested typed arrays (`Array[Array[int]]`) are NOT supported:

```gdscript
var a: Array[int] = [1, 2, 3]
var b: Array[Node] = []
var c: Array[MyClass] = []
```

You cannot assign an array with a different element type directly, even if it's a subtype. Use `assign()` to copy contents:

```gdscript
var nodes_2d: Array[Node2D] = [Node2D.new()]
var nodes: Array[Node] = []
nodes.assign(nodes_2d)  # Copies contents, not reference
```

### Packed Arrays

Use packed arrays when storing large amounts (tens of thousands) of uniform data — they are faster to iterate and use less memory than typed arrays. Available types: `PackedByteArray`, `PackedInt32Array`, `PackedInt64Array`, `PackedFloat32Array`, `PackedFloat64Array`, `PackedStringArray`, `PackedVector2Array`, `PackedVector3Array`, `PackedVector4Array`, `PackedColorArray`.

For smaller arrays or when you need convenience methods like `map()`, `filter()`, use regular typed arrays.

### Dictionaries

Associative key-value containers:

```gdscript
var d = {4: 5, "key": "value", 28: [1, 2, 3]}
d["new_key"] = 42           # Add or update a key
d[4]                         # Access by key
d.has("key")                 # Check key existence
d.keys()                     # Array of all keys
d.values()                   # Array of all values
d.erase("key")               # Remove a key
d.get("missing", "default")  # Get with fallback
d.size()                     # Number of entries
```

**NEVER use dot syntax to add dictionary keys** (e.g. `d.waiting = 14`). Always use bracket syntax: `d["waiting"] = 14`. Dot syntax is ambiguous with property access and leads to confusion.

**Typed dictionaries** (Godot 4.4+) restrict key and value types. Nested typed collections are NOT supported:

```gdscript
var a: Dictionary[String, int] = {}
var b: Dictionary[Vector2i, MyClass] = {}
var c: Dictionary[String, Variant] = {}  # String keys, any value type
```

---

## Signals

Signals are messages emitted by objects that other objects can listen to. They are the primary decoupling mechanism in Godot (the Observer pattern). Use signals to keep code flexible and avoid tight references between nodes.

### Declaring Signals

```gdscript
signal health_depleted
signal health_changed(old_value, new_value)
```

Argument names in the declaration are for documentation purposes; they appear in the editor's Signals dock.

### Emitting Signals

```gdscript
func take_damage(amount: int) -> void:
    var old_health = health
    health -= amount
    health_changed.emit(old_health, health)
    if health <= 0:
        health_depleted.emit()
```

### Connecting Signals in Code (Preferred Method)

Always use the `Signal.connect()` method with callable references (not string-based `Object.connect()`):

```gdscript
func _ready() -> void:
    # Preferred: direct signal reference + callable
    $Button.pressed.connect(_on_button_pressed)

    # With bound parameters
    var player = get_node("Player")
    player.hit.connect(_on_player_hit.bind("sword", 100))

func _on_button_pressed() -> void:
    print("Button pressed!")

# Bound arguments come after emitted arguments
func _on_player_hit(hit_by: String, level: int, weapon: String, damage: int) -> void:
    print("%s hit by %s" % [weapon, hit_by])
```

**Parameter order when binding:** emitted arguments come first, then bound arguments.

### Disconnecting Signals

```gdscript
if player.hit.is_connected(_on_player_hit):
    player.hit.disconnect(_on_player_hit)
```

### Signal Connection Flags

```gdscript
signal.connect(callable, CONNECT_ONE_SHOT)   # Auto-disconnect after first emission
signal.connect(callable, CONNECT_DEFERRED)   # Call on next idle frame
```

### The Signal Type

Signals are first-class values:
```gdscript
var my_signal: Signal = $Button.pressed
my_signal.connect(_on_pressed)
my_signal.has_connections()  # true/false
my_signal.get_name()         # StringName
my_signal.get_object()       # The emitting object
```

---

## Callables

A `Callable` wraps an object and a method. Obtained by referencing a method by name without calling it:

```gdscript
var c: Callable = $Sprite2D.rotate
c.call(PI)  # Must use .call(), not ()

# Binding arguments
var bound = _on_hit.bind("extra_arg")
bound.call()
```

Callables are used for signal connections, `Array.map()`, `Array.filter()`, `Array.sort_custom()`, and more.

---

## Variables

Variables are declared with `var`. They can be typed:

```gdscript
var a                        # Untyped, defaults to null
var b = 5                    # Inferred as int-ish (Variant)
var c: int = 5               # Explicitly typed
var d: Vector2 = Vector2.ZERO
var e := Vector2.ZERO        # Type inferred from right side (static type)
var my_node: Node = Sprite2D.new()
var my_sprite := Sprite2D.new()  # Inferred as Sprite2D
```

Always use `var` for local and member variables. Prefer typed variables (`:` or `:=`) for clarity and better editor support.

### Initialization Order

Member variables are initialized in this order — this is critical to understand:

1. Variables get their **type default** (`null` for objects, `0` for `int`, `false` for `bool`, etc.).
2. **Specified values** are assigned top-to-bottom in script order.
   - Variables with `@onready` are deferred to step 5.
3. `_init()` is called.
4. **Exported values** from the scene/resource file are assigned.
5. `@onready` variables are initialized (Node-derived classes only).
6. `_ready()` is called (Node-derived classes only).

This means: `@export` values override script defaults (step 4 after step 2), and `@onready` values override everything (step 5 after step 4) — which is why combining `@export` and `@onready` on the same variable is forbidden.

### Node Lifecycle Order

When a scene tree loads, Godot calls lifecycle methods in a specific order:

- **`_enter_tree`** runs **top-down**: parent first, then children.
- **`_ready`** runs **bottom-up**: children first, then parent.

This means a parent's `_ready()` runs **after** all its children are ready. A child cannot rely on setup done in its parent's `_ready()` — the parent hasn't run yet when the child's `_ready()` executes. If a child needs data from the parent, the parent must set it before the tree enters (e.g. via exported properties in the scene file) or the child must `await` a signal.

### Static Variables

Avoid static variables unless specifically needed. They belong to the class, not instances, and prevent scripts from being unloaded (memory leak risk). If you must use them, add `@static_unload` at the top of the script to allow cleanup:

```gdscript
@static_unload
class_name MyClass
extends Node

static var instance_count: int = 0
```

---

## Casting

Use `as` to cast values. For objects, returns `null` if the cast fails (no error). For built-in types, forces conversion or raises an error:

```gdscript
var sprite := $Character as Sprite2D  # null if not a Sprite2D
($AnimPlayer as AnimationPlayer).play("walk")  # Fails clearly if wrong type

var my_int: int = "123" as int  # String to int conversion
```

---

## Constants

Declared with `const`. Must be compile-time constant expressions:

```gdscript
const MAX_HEALTH = 100
const SPAWN_POS: Vector2 = Vector2(20, 30)
const H = A + 20          # Valid if A is also const
```

---

## Enums

Enums are shorthand for consecutive integer constants:

```gdscript
# Anonymous enum — values are global to the script
enum {TILE_BRICK, TILE_FLOOR, TILE_SPIKE}
# TILE_BRICK = 0, TILE_FLOOR = 1, TILE_SPIKE = 2

# Named enum — values accessed via Name.KEY
enum State {IDLE, JUMP = 5, SHOOT}
# State.IDLE = 0, State.JUMP = 5, State.SHOOT = 6

# Named enums are dictionaries, so you can use:
State.keys()    # ["IDLE", "JUMP", "SHOOT"]
State.values()  # [0, 5, 6]
```

Enums can be exported (see `@export` section above). Named enum keys must be accessed with the enum prefix: `State.IDLE`, not just `IDLE`.

---

## Functions

Functions belong to a class. They can have typed parameters and return types. **GDScript does NOT support named arguments** — all arguments must be passed positionally:

```gdscript
func my_function(a: int, b: String = "default") -> int:
    print(b)
    return a + 1

# Single-line functions
func square(a: float) -> float: return a * a

# Void return type
func do_something() -> void:
    print("done")
    return  # Cannot return a value

# Calling — arguments are positional only:
my_function(5, "hello")  # Correct
# my_function(a=5, b="hello")  # NOT SUPPORTED
```

Non-void functions must return a value on all code paths.

### Lambda Functions

Anonymous functions that capture their surrounding scope:

```gdscript
var double = func(x: int) -> int: return x * 2
print(double.call(5))  # 10

# Multi-line lambda
var greet = func(name: String) -> void:
    print("Hello, " + name)

# Named lambda (for debugging)
var process = func my_processor(data: Array) -> Array:
    return data.map(func(x): return x * 2)

# Lambdas MUST use .call()
greet.call("World")
```

**Capture rules:** lambdas capture local variables **by value at creation time**. Reassigning the outer variable later does not update the lambda's copy. However, mutations on reference types (arrays, dictionaries, objects) are shared.

```gdscript
var x = 42
var f = func(): print(x)
x = 99
f.call()  # Prints 42, not 99

var arr = []
var g = func(): arr.append(1)
g.call()
print(arr)  # [1] — mutations are shared
```

### Static Functions

Static functions have no access to instance members or `self`. Use them for utility/helper functions:

```gdscript
static func sum2(a: float, b: float) -> float:
    return a + b
```

### Variadic Functions

Use the rest parameter `...args` to accept a variable number of arguments. It must be the last parameter:

```gdscript
func my_func(a, b = 0, ...args):
    prints(a, b, args)
```

---

## Abstract Classes and Methods

Use the `@abstract` annotation to define classes that cannot be instantiated and methods that must be implemented by subclasses:

```gdscript
@abstract
class_name Shape
extends Node2D

@abstract func draw_shape() -> void

func get_info() -> String:
    return "I am a shape"
```

```gdscript
class_name Circle
extends Shape

func draw_shape() -> void:
    # Must implement this — Shape is abstract
    draw_arc(Vector2.ZERO, radius, 0, TAU, 32, color)
```

If a class has any unimplemented abstract methods, it must also be marked `@abstract`. An abstract class cannot be attached to a node.

---

## Iteration (for, while, range)

```gdscript
# Iterate over an array
for x in [5, 7, 11]:
    print(x)

# Typed loop variable
for name: String in ["John", "Marta"]:
    print(name)

# Iterate dictionary keys
var dict = {"a": 0, "b": 1, "c": 2}
for key in dict:
    print(dict[key])

# Range-based iteration
for i in range(3):         # 0, 1, 2
    print(i)
for i in range(1, 5):      # 1, 2, 3, 4
    print(i)
for i in range(2, 10, 2):  # 2, 4, 6, 8
    print(i)
for i in range(8, 2, -2):  # 8, 6, 4
    print(i)

# Shorthand
for i in 3:                # Same as range(3)
    print(i)

# Iterate string characters
for c in "Hello":
    print(c)

# Modify array elements by index (loop variable is local, assigning to it doesn't change the array)
for i in array.size():
    array[i] = "modified"

# While loop
while condition:
    do_something()
    # Use `break` to exit, `continue` to skip to next iteration
```

---

## Match Statement

Similar to `switch` in other languages. Patterns are matched top to bottom; first match executes, then continues below. Avoid `match` when simple `if/elif` would be clearer:

```gdscript
match value:
    1:
        print("One")
    2, 3:
        print("Two or three")  # Multiple patterns
    "test":
        print("String match")
    [1, var second, _]:
        print("Array pattern, second element: ", second)
    {"name": "Dennis", "age": var age}:
        print("Dict pattern, age: ", age)
    var other:
        print("Binding pattern: ", other)  # Like default
    _:
        print("Wildcard — matches everything")
```

**Pattern guards** with `when`:
```gdscript
match point:
    [var x, var y] when y == x:
        print("On y = x line")
    [var x, var y]:
        print("Point (%s, %s)" % [x, y])
```

Note: `match` is more type-strict than `==`. For example, `1` will not match `1.0`.

---

## Classes

### Class Names and Inheritance

Always give classes a name using `class_name`. Keep `class_name` and `extends` on separate lines:

```gdscript
class_name Character
extends CharacterBody2D
```

This registers the class globally — it can be used anywhere without `load()` or `preload()`:

```gdscript
var player = Character.new()
```

Add an `@icon` annotation only if explicitly requested:
```gdscript
@icon("res://icons/character.svg")
class_name Character
extends CharacterBody2D
```

If no `extends` is specified, the class implicitly inherits `RefCounted`.

### Inheritance and `super`

Use `super` to call the parent class's implementation. **By default, overriding a method does NOT call the parent.** Decide based on the specification whether the parent should be called:

```gdscript
# Full replacement — parent is NOT called
func _process(delta: float) -> void:
    position += velocity * delta

# Extension — parent IS called
func _ready() -> void:
    super()  # Calls parent's _ready()
    setup_custom_stuff()

# Call a different parent method
func overriding() -> int:
    return 0  # Completely replaces parent's version

func dont_override() -> int:
    return super.overriding()  # Explicitly calls parent's version
```

**Rule of thumb:** when a function completely changes behavior, do not call `super`. When it extends or adds to existing behavior, call `super()` first or last as appropriate. In lifecycle methods like `_ready()` and `_enter_tree()`, call `super()` to preserve parent setup.

Do NOT override non-virtual engine methods (`get_class()`, `queue_free()`, etc.) — this is unsupported and will cause issues.

### Class Constructor (`_init`)

Called when instantiating with `.new()`. Use `super()` to pass arguments to the parent constructor:

```gdscript
class_name Character
extends Node2D

var name: String
var health: int

func _init(p_name: String, p_health: int = 100) -> void:
    name = p_name
    health = p_health
```

When instantiating from another script:
```gdscript
var hero = Character.new("Hero", 150)
```

If the parent class has a constructor with required arguments, the child must pass them via `super()`:

```gdscript
class_name Warrior
extends Character

func _init(p_name: String) -> void:
    super(p_name, 200)  # Pass to Character._init
```

### Inner Classes

Define classes inside a script using `class`. Use inner classes when manipulating structured data instead of dictionaries — they provide named fields, type safety, and better readability:

```gdscript
class DamageEvent:
    var source: Node
    var amount: int
    var type: String

    func _init(p_source: Node, p_amount: int, p_type: String) -> void:
        source = p_source
        amount = p_amount
        type = p_type

# Usage
var event = DamageEvent.new(self, 25, "fire")
print(event.amount)  # Much clearer than event["amount"]
```

Prefer inner classes over dictionaries for structured data. Use dictionaries only for truly dynamic key-value data.

#### Dataclass pattern for fixed-key dictionaries

Whenever a dictionary has a fixed set of keys — whether stored in an array, returned from a function, passed between functions, or used as a local variable — **always** define an inner class (or standalone `class_name`) instead. Dictionaries with fixed keys lose type safety, autocomplete, and are error-prone (typos in string keys silently fail). This is the GDScript equivalent of a dataclass.

This applies to:
- `Array[Dictionary]` collections where all items share the same keys (e.g. a pending-move queue, event queue, list of spawn requests)
- Functions that return a `Dictionary` with a known shape, when that dictionary is consumed by other code
- Local variables or member variables that hold a `Dictionary` with fixed keys

**Bad:**
```gdscript
var _pending_moves: Array[Dictionary] = []

func request_move(actor: Node, target: Vector2i) -> bool:
    _pending_moves.append({"actor": actor, "target": target_cell})
    return true

# Later: no autocomplete, no type checking, typo-prone
var move = _pending_moves[0]
move.actpr  # Silent failure — key doesn't exist
```

```gdscript
# Also bad: function returns a fixed-shape dictionary
func roll_damage_against(defender: Stats) -> Dictionary:
    return {"damage": dmg, "crit": is_crit, "dodged": false}

# Caller has no type info, no autocomplete
var result = roll_damage_against(stats)
result.damge  # Silent failure
```

**Good:**
```gdscript
class PendingMove:
    var actor: Node
    var target: Vector2i

    func _init(p_actor: Node, p_target: Vector2i) -> void:
        actor = p_actor
        target = p_target

var _pending_moves: Array[PendingMove] = []

func request_move(actor: Node, target: Vector2i) -> bool:
    _pending_moves.append(PendingMove.new(actor, target))
    return true

# Later: full autocomplete and type checking
var move = _pending_moves[0]
move.actor  # Autocompletes, type-checked as Node
move.actpr  # Compile error — catches the typo
```

```gdscript
# Also good: function returns a typed object
class DamageResult:
    var damage: int
    var crit: bool
    var dodged: bool

    func _init(p_damage: int, p_crit: bool, p_dodged: bool) -> void:
        damage = p_damage
        crit = p_crit
        dodged = p_dodged

func roll_damage_against(defender: Stats) -> DamageResult:
    return DamageResult.new(dmg, is_crit, false)

# Caller gets full type info and autocomplete
var result = roll_damage_against(stats)
result.damage  # Autocompletes, type-checked as int
result.damge   # Compile error
```

**Rules:**
- If a dictionary has a known, fixed set of keys → use a class instead.
- If the data structure is internal to a single class or very tightly coupled to it (e.g. only that class creates and consumes it) → use an **inner class** (`class Foo:` inside the script).
- If the data structure is used by more than one script, returned from public APIs, or could reasonably be reused → put it in a **standalone `class_name` file** under a `dataclasses/` folder in the project. This makes it importable, autocompletes across files, and keeps the parent script focused.
- If keys vary per item or are truly dynamic (e.g. a lookup table, JSON from external source, arbitrary metadata) → use `Dictionary`.

#### Resources vs inner classes vs dictionaries

When you need a structured data container, choose based on **mutability**, **sharing**, and **persistence**:

| Need | Use | Why |
|------|-----|-----|
| Mutable, non-shared, internal data (action queues, pending moves, combat results) | **Inner class** | Lightweight, no file overhead, each instance is independent. Not shared by reference. |
| Designer-editable data saved as `.tres`, shared between nodes, or passed as a value | **Custom `Resource`** | Inspector-editable, serializable, `@export` + `@tool` pattern. |
| Truly dynamic key-value data | **`Dictionary`** | Only when keys are not fixed/known at compile time. |

**Custom `Resource` (`extends Resource`):**
- Use when data needs to be saved as `.tres` files, shared between nodes, edited in the inspector, or passed around as a value type.
- A `.tres` file is a **single instance** loaded once and shared by reference. If multiple nodes reference the same `.tres`, they all see the same data — mutating it affects everyone.
- To have separate data per node, either:
  - Create a new `Resource` instance in code every time (`Stats.new()`) and be careful about ownership, or
  - Create multiple `.tres` files (e.g. `knight_stats.tres`, `orc_stats.tres`) and assign them in the `.tscn`. (preferred way)
- If you need per-node copies of a shared resource at runtime, add a `clone()` method that creates a new instance with copied fields. This avoids mutating the shared `.tres`:

```gdscript
func clone() -> Stats:
    var s := Stats.new()
    s.max_hp = max_hp
    s.hp = hp
    s.attack = attack
    s.defense = defense
    return s

## Or with modifications:
func clone_modified(atk: int = 0, hp: int = 0) -> Stats:
    var s := clone()
    s.attack += atk
    s.max_hp += hp
    s.hp = s.max_hp
    return s
```

- Use `@tool` + `@export` so the resource is editable in the inspector and updates live in the editor.

```gdscript
@tool
class_name Stats
extends Resource

@export var max_hp: int = 100
@export var attack: int = 10
@export var defense: int = 5
```

**Inner class (mutable, non-shared):**
- Use for data that is created at runtime, mutated independently per instance,and that's more intuitive to "create" wrt to resources.
- Perfect for action queues, pending moves, combat results — each instance owns its own copy.

```gdscript
class PendingMove:
    var actor: Node
    var target: Vector2i

    func _init(p_actor: Node, p_target: Vector2i) -> void:
        actor = p_actor
        target = p_target

var _pending_moves: Array[PendingMove] = []
```

**Decision rule:** if you need it in the inspector or saved to disk → `Resource`. If it's internal, mutable, and non-shared → inner class. If keys are dynamic → `Dictionary`.

---

## Scene File Format (`.tscn`)

When writing `.tscn` files by hand or via tools:

- **`load_steps` is deprecated** (Godot 4.6+). Do not include `load_steps=N` in the `[gd_scene]` header. Godot computes it automatically. Including it creates unnecessary diffs.
- The header should be: `[gd_scene format=3 uid="uid://..."]` (or without `uid` if letting Godot generate it).
- Assign resources (like `Stats`) in the scene file as sub_resources, not via `Resource.new()` in code. The scene is the right place for per-instance configuration.
- **Z-ordering:** children render in tree order — later children render on top. Position nodes in the scene tree so that backgrounds/tiles come first and entities come after. If nodes are added at runtime via `add_child()` and end up on top, use `move_child(node, index)` to reorder them. Alternatively, use `z_index` or `CanvasLayer` for explicit control.

---

## Autoloads (Global Singletons)

Autoloads are scripts that load automatically when the game starts and persist across all scene changes. They are the Godot equivalent of singletons — accessible globally by name from any script.

### Creating an Autoload

**Step 1: Write the script.** Place it in an `autoloads/` folder. The script can extend `Node` (non-UI) or `CanvasLayer` (UI overlay). Avoid using `class_name` in autoload scripts — the autoload name already registers the class globally, so adding `class_name` with the same name triggers a "hides a global script class" warning. If you do use `class_name`, make sure it differs from the autoload name (but this creates two global identifiers for one thing, which is confusing):

```gdscript
## Global event bus for cross-scene communication.
extends Node

signal combat_triggered(enemy: Node)
signal combat_finished(player_won: bool)
signal item_picked_up(item: Node)

func _ready() -> void:
    # Autoload _ready runs once at startup, before any scene loads.
    pass
```

**Step 2: Register in `project.godot`.** Add an entry under `[autoload]`:

```ini
[autoload]

EventBus="*res://examples/hero_rpg/autoloads/event_bus.gd"
TurnClock="*res://examples/hero_rpg/autoloads/turn_clock.gd"
```

- The `*` prefix means the autoload is **enabled**. Without `*`, it's registered but disabled.
- The name on the left (`EventBus`) becomes the global singleton name.
- The path on the right is the `res://` path to the script.

**Step 3: Use it anywhere.** No `preload`, no `load`, no `get_node` — just use the name directly:

```gdscript
func _on_combat_triggered(enemy: Node) -> void:
    EventBus.combat_triggered.emit(enemy)

# Connect to autoload signals:
func _ready() -> void:
    EventBus.combat_finished.connect(_on_battle_end)
```

### When to Use Autoloads

- **Signal buses** — decouple emitters from listeners across scenes (e.g. `EventBus`, `FieldEvents`)
- **Global state** — player party, inventory, game phase (e.g. `Player`, `TurnClock`)
- **Registry/lookup** — bidirectional mappings that multiple scenes need (e.g. `GamepieceRegistry`)
- **Manager services** — audio, save/load, transitions that persist across scenes

### When NOT to Use Autoloads

- **Scene-specific logic** — if it only matters in one scene, use a regular node in that scene
- **Per-instance data** — autoloads are singletons; all scenes share the same instance
- **Avoid god objects** — keep autoloads focused on one responsibility. Split into multiple autoloads rather than cramming everything into one.

### Autoload Lifecycle

- Autoloads load **before** the first scene, in the order listed in `project.godot`.
- Their `_ready()` runs once at startup.
- They are never freed — they persist for the entire game session.
- They are accessible from any scene via their global name.
- If an autoload extends `CanvasLayer`, it renders on top of (or below, depending on `layer`) the main scene.

### Autoloads vs Static Classes

Autoloads are preferred over static classes/variables for global access because:
- They have a `_ready()` lifecycle (can connect signals, initialize state)
- They can hold references to nodes and resources
- They participate in the scene tree (can receive `_process`, `_input`, etc.)
- Static variables prevent script unloading and have no lifecycle

---

## Properties (Setters and Getters)

Setters and getters are always called (even from within the class), unlike Godot 3's `setget`.

**Inline style** — use when the logic is simple:

```gdscript
var health: int = 100:
    get:
        return health
    set(value):
        health = clampi(value, 0, max_health)
        health_changed.emit(health)
```

**Separate function style** — use when the logic is complex. Put it on the line after the variable, not inline:

```gdscript
var health: int = 100:
    get = get_health, set = set_health

func get_health() -> int:
    return health

func set_health(value: int) -> void:
    health = clampi(value, 0, max_health)
    health_changed.emit(health)
```

### When Setters/Getters Are NOT Called

- **Initialization:** the initial value is written directly, bypassing the setter. This includes `@onready` initialization.
- **Self-reference inside own setter/getter:** using the variable's own name inside its setter/getter accesses the backing value directly (no infinite recursion):

```gdscript
signal changed(new_value)
var warns_when_changed = "some value":
    get:
        return warns_when_changed      # Direct access, no recursion
    set(value):
        changed.emit(value)
        warns_when_changed = value     # Direct access, no recursion
```

**This is critical for `@tool` scripts:** when a tool script loads, exported values are assigned but the setter is not called during initialization. If your tool script relies on side effects in a setter (like updating visuals), you may need to manually trigger the update in `_ready()`.

**Warning:** the no-recursion exception only applies to the setter/getter function itself, NOT to other functions called from within it:

```gdscript
var my_prop:
    set(value):
        set_my_prop(value)  # This calls the function below

func set_my_prop(value):
    my_prop = value  # INFINITE RECURSION — this triggers the setter again
```

---

## Tool Mode (`@tool`)

Add `@tool` at the top of a script to run it inside the editor. Use `Engine.is_editor_hint()` to separate editor code from game code:

```gdscript
@tool
extends Sprite2D

@export var speed: float = 1.0:
    set(new_speed):
        speed = new_speed
        rotation = 0

func _process(delta: float) -> void:
    if Engine.is_editor_hint():
        rotation += PI * delta * speed  # Runs in editor
    else:
        rotation -= PI * delta * speed  # Runs in game
```

**Critical rules for `@tool` scripts:**
- Any GDScript that a tool script references must also be `@tool` (except for static methods, constants, and enums).
- Extending a `@tool` script does NOT automatically make the child `@tool`.
- Be cautious with `queue_free()` and `free()` — freeing the script's own node can crash the editor.
- When setters rely on side effects (updating visuals, notifying children), remember that the setter is NOT called during initialization. Handle this in `_ready()`.

### Configuration Warnings

In `@tool` scripts, implement `_get_configuration_warnings()` to show yellow warning icons in the Scene dock when a node is misconfigured. **By default, always implement configuration warnings** when a node has required properties, dependencies, or constraints that could be set up incorrectly. Warn when something is missing, has an invalid value, or would cause runtime errors:

```gdscript
@export var title: String = "":
    set(p_title):
        if p_title != title:
            title = p_title
            update_configuration_warnings()

func _get_configuration_warnings() -> PackedStringArray:
    var warnings: PackedStringArray = []
    if title == "":
        warnings.append("Please set 'title' to a non-empty value.")
    return warnings
```

### Resource Change Notifications

To react to changes on an exported resource's properties in the editor, connect to the resource's `changed` signal:

```gdscript
@export var resource: MyResource:
    set(new_resource):
        if resource != null:
            resource.changed.disconnect(_on_resource_changed)
        resource = new_resource
        if resource != null:
            resource.changed.connect(_on_resource_changed)

func _on_resource_changed() -> void:
    # React to property changes on the resource
    queue_redraw()
```

The resource class must also be `@tool` and emit `changed` from its setters:

```gdscript
@tool
class_name MyResource
extends Resource

@export var property: int = 1:
    set(value):
        property = value
        changed.emit()
```

---

## Awaiting Signals and Coroutines

`await` pauses execution until a signal is emitted or a coroutine finishes. **Avoid using `await` and coroutines unless there is no other way** — they complicate control flow. Prefer signals and callbacks.

When you must use `await`:

```gdscript
func wait_for_confirmation() -> bool:
    await $Button.button_up
    return true

# Caller must also await
func request_confirmation() -> void:
    var confirmed = await wait_for_confirmation()
    if confirmed:
        print("Confirmed")
```

If you call a coroutine without `await`, it runs asynchronously and you cannot get its return value.

---

## Assert

Use `assert` to enforce preconditions in important functions. Assertions are ignored in release builds (no runtime cost). Use them when consistency between calls matters, but not for trivial or straightforward functions:

```gdscript
func apply_damage(target: Node, amount: int) -> void:
    assert(target != null, "Target must not be null")
    assert(amount >= 0, "Damage amount must be non-negative")
    target.health -= amount
```

---

## Format Strings

```gdscript
# % operator with placeholders
var text = "Player %s has %d HP" % [name, health]

# Common specifiers: %s (string), %d (decimal int), %f (float), %x (hex)
# Padding: %10d (pad to 10 chars), %010d (pad with zeros)
# Precision: %.2f (2 decimal places)

# String.format() method
var text = "Hello {name}, level {level}".format({"name": "Hero", "level": 5})
var text = "Values: {0}, {1}".format([42, "test"])
```

---

## Memory Management

Godot uses reference counting, not garbage collection. Classes extending `RefCounted` (and `Resource`) are freed automatically when no references remain. Classes extending `Node` or `Object` must be freed manually with `free()` or `queue_free()`. Deleting a node with `free()`/`queue_free()` also deletes all its children recursively.

Use `weakref()` to avoid reference cycles with RefCounted objects. Use `is_instance_valid(instance)` to check if an Object has been freed.

---

## Custom Drawing (`_draw`)

Any node inheriting from `CanvasItem` (which includes `Node2D` and `Control`) can override `_draw()` to render custom shapes. Drawing is primarily used for **debugging and visualization** — showing collision areas, velocity arrows, detection ranges, paths, AI states, etc.

### How It Works

Override `_draw()` in your script. It is called once and cached. To trigger a redraw, call `queue_redraw()`. Drawing uses the node's local coordinate system.

```gdscript
extends Node2D

func _draw() -> void:
    draw_circle(Vector2.ZERO, 50.0, Color.RED)

# Call queue_redraw() whenever something changes that affects drawing.
# To draw every frame (e.g. for continuously changing debug info):
func _process(_delta: float) -> void:
    queue_redraw()
```

### Available Draw Methods

```gdscript
# Lines
draw_line(from: Vector2, to: Vector2, color: Color, width: float = -1.0, antialiased: bool = false)
draw_dashed_line(from: Vector2, to: Vector2, color: Color, width: float = -1.0, dash: float = 2.0, aligned: bool = true, antialiased: bool = false)
draw_polyline(points: PackedVector2Array, color: Color, width: float = -1.0, antialiased: bool = false)
draw_multiline(points: PackedVector2Array, color: Color, width: float = -1.0, antialiased: bool = false)

# Shapes
draw_circle(position: Vector2, radius: float, color: Color, filled: bool = true, width: float = -1.0, antialiased: bool = false)
draw_arc(center: Vector2, radius: float, start_angle: float, end_angle: float, point_count: int, color: Color, width: float = -1.0, antialiased: bool = false)
draw_rect(rect: Rect2, color: Color, filled: bool = true, width: float = -1.0, antialiased: bool = false)
draw_polygon(points: PackedVector2Array, colors: PackedColorArray)
draw_colored_polygon(points: PackedVector2Array, color: Color)

# Text and textures
draw_string(font: Font, pos: Vector2, text: String, alignment: int = HORIZONTAL_ALIGNMENT_LEFT, width: float = -1, font_size: int = 16, modulate: Color = Color.WHITE)
draw_texture(texture: Texture2D, position: Vector2, modulate: Color = Color.WHITE)

# Transform (affects subsequent draw calls within the same _draw)
draw_set_transform(position: Vector2, rotation: float = 0.0, scale: Vector2 = Vector2.ONE)
```

### Debug Drawing Pattern

Debug draws should always be togglable via an `@export` variable. This is the standard pattern:

```gdscript
extends CharacterBody2D

@export var debug_draw: bool = false

var _velocity: Vector2 = Vector2.ZERO
var _detection_radius: float = 200.0
var _target_position: Vector2 = Vector2.ZERO

func _process(delta: float) -> void:
    # ... game logic ...
    if debug_draw:
        queue_redraw()

func _draw() -> void:
    if not debug_draw:
        return

    # Draw velocity arrow
    _draw_arrow(Vector2.ZERO, _velocity.normalized() * 60.0, Color.GREEN)

    # Draw detection radius
    draw_arc(Vector2.ZERO, _detection_radius, 0, TAU, 64, Color("#80ffff00"), 1.0)

    # Draw target direction
    if _target_position != Vector2.ZERO:
        var local_target = to_local(_target_position)
        _draw_arrow(Vector2.ZERO, local_target.normalized() * 80.0, Color.RED)

    # Draw a region/area
    var region = Rect2(-50, -50, 100, 100)
    draw_rect(region, Color("#3300ff00"), true)   # Filled, semi-transparent
    draw_rect(region, Color.GREEN, false, 2.0)     # Outline


## Draws an arrow from `from` to `to` with an arrowhead.
func _draw_arrow(from: Vector2, to: Vector2, color: Color, width: float = 2.0) -> void:
    var direction = (to - from).normalized()
    var arrow_size = 10.0
    var perpendicular = Vector2(-direction.y, direction.x)

    draw_line(from, to, color, width)
    draw_line(to, to - direction * arrow_size + perpendicular * arrow_size * 0.5, color, width)
    draw_line(to, to - direction * arrow_size - perpendicular * arrow_size * 0.5, color, width)
```

### Common Debug Draw Helpers

When writing debug drawing code, implement reusable helper methods for common shapes:

- **Arrow** (direction/velocity): line with an arrowhead, as shown above.
- **Circle** (radius/range): `draw_arc(center, radius, 0, TAU, 64, color, width)` for an unfilled circle, or `draw_circle()` for filled.
- **Region/Area** (rectangular zones): `draw_rect()` with a semi-transparent fill and a solid outline.
- **Cross/Point** (marking positions): two short perpendicular lines at the target point.
- **Path** (waypoints): `draw_polyline()` connecting an array of points.
- **Label** (state/values): `draw_string()` with the default font from `ThemeDB.fallback_font`.

```gdscript
## Draws a cross marker at a position.
func _draw_cross(pos: Vector2, size: float, color: Color, width: float = 1.0) -> void:
    draw_line(pos - Vector2(size, 0), pos + Vector2(size, 0), color, width)
    draw_line(pos - Vector2(0, size), pos + Vector2(0, size), color, width)

## Draws a text label at a position.
func _draw_label(pos: Vector2, text: String, color: Color = Color.WHITE) -> void:
    var font = ThemeDB.fallback_font
    draw_string(font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, color)
```

### Drawing in the Editor

To show debug draws in the editor (for level design visualization), combine `@tool` with drawing:

```gdscript
@tool
extends Node2D

@export var radius: float = 100.0:
    set(value):
        radius = value
        queue_redraw()

func _draw() -> void:
    draw_arc(Vector2.ZERO, radius, 0, TAU, 64, Color("#80ff0000"), 2.0)
```

This is useful for visualizing detection ranges, spawn areas, trigger zones, and other spatial properties directly in the editor viewport.

## Editor Plugins (`EditorPlugin`)

A `@tool` script lets a node *run* its own code in the editor (e.g. drawing itself via `_draw()`), but it only sees its own instance. An **editor plugin** (`extends EditorPlugin`) is more expressive: it operates on the editor itself, so it can inspect and mutate *other* nodes in the edited scene, capture raw viewport input, drive the undo/redo history, and draw overlays on top of the 2D/3D viewport. Use a plugin when you need the editor to *interact with* scene objects (select, move, connect, generate them) rather than have a single node merely draw a visualization of itself.

A plugin lives under `res://addons/<plugin_name>/` and needs two files: a `plugin.cfg` descriptor and a `@tool extends EditorPlugin` script referenced by it. Enable it in **Project Settings → Plugins**.

```
# addons/my_plugin/plugin.cfg
[plugin]
name="My Plugin"
description="What it does."
author=""
version="1.0"
script="plugin.gd"
```

### Typical Workflow

A plugin that manipulates 2D viewport objects generally implements these `EditorPlugin` overrides:

- **`_handles(object: Object) -> bool`** — called with the currently selected object. Return `true` to make the editor route viewport input to your plugin. This is where you gate *when* the plugin is active. You don't have to inspect `object`: you can check the edited scene as a whole (e.g. "does this scene contain any node I care about?") so the plugin isn't tied to what is currently selected.
- **`_edit(object: Object) -> void`** — called when the editor hands your plugin an object to edit (the current selection). Implement this when your tool operates *on the selected node*. **Omit it** when you want to act on objects regardless of selection — leaving it out is what frees the plugin from the current-selection constraint.
- **`_forward_canvas_gui_input(event: InputEvent) -> bool`** — receives mouse/keyboard events in the 2D viewport while `_handles()` is true. Return `true` to **consume** the event (preventing the editor's own box-select, node-drag, and pan) and `false` to let it pass through. This is the core of click/drag interaction. (`_forward_3d_gui_input` is the 3D equivalent.)
- **`_forward_canvas_draw_over_viewport(overlay: Control) -> void`** — draw overlays (handles, outlines, guides) on top of the viewport. Call `update_overlays()` to request a redraw.

Mutate scene nodes through `get_undo_redo()` rather than assigning properties directly. This makes edits undoable and marks the scene dirty so Godot prompts to save. Merge continuous edits (like a drag) into one history entry with `UndoRedo.MERGE_ENDS`.

```gdscript
var undo_redo := get_undo_redo()
undo_redo.create_action("Move Node", UndoRedo.MERGE_ENDS)
undo_redo.add_do_property(node, "position", new_pos)
undo_redo.add_undo_property(node, "position", node.position)
undo_redo.commit_action()
```

Access the edited scene with `EditorInterface.get_edited_scene_root()` and the selection with `EditorInterface.get_selection()`.

### Example: Drag Multiple Nodes in the Viewport

This plugin lets the user click-drag any `AnchorPoint` (a custom `Node2D`) in the 2D viewport. It deliberately does **not** implement `_edit()`, so dragging works on any anchor regardless of the current selection. The activation condition lives in `_handles()`, which scans the edited scene for `AnchorPoint` children instead of inspecting the selected object.

```gdscript
@tool
extends EditorPlugin

var _dragged: AnchorPoint = null
var _grab_offset: Vector2 = Vector2.ZERO  # origin-to-cursor, local space

## Active whenever the edited scene contains at least one AnchorPoint —
## not tied to the current selection. (No _edit() is implemented.)
func _handles(object: Object) -> bool:
	return _find_anchors().size() > 0

func _forward_canvas_gui_input(event: InputEvent) -> bool:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			return _try_begin_drag()
		_dragged = null
		return false

	if event is InputEventMouseMotion and _dragged != null:
		_update_drag()
		return true  # consume so the editor doesn't box-select/pan
	return false

func _try_begin_drag() -> bool:
	var anchors := _find_anchors()
	# Reverse order so anchors drawn on top win the hit test.
	for i in range(anchors.size() - 1, -1, -1):
		var anchor := anchors[i]
		var local_mouse := anchor.get_local_mouse_position()
		if anchor.is_point_inside(local_mouse):
			_dragged = anchor
			_grab_offset = local_mouse
			return true  # consume so the editor doesn't start its own selection
	return false

func _update_drag() -> void:
	var parent := _dragged.get_parent() as Node2D
	var mouse_in_parent := parent.get_local_mouse_position() if parent != null \
		else _dragged.get_global_mouse_position()
	var offset := _grab_offset.rotated(_dragged.rotation) * _dragged.scale
	var new_pos := mouse_in_parent - offset

	var ur := get_undo_redo()
	ur.create_action("Move AnchorPoint", UndoRedo.MERGE_ENDS)
	ur.add_do_property(_dragged, "position", new_pos)
	ur.add_undo_property(_dragged, "position", _dragged.position)
	ur.commit_action()

## Recursively collect every AnchorPoint in the edited scene.
func _find_anchors() -> Array[AnchorPoint]:
	var result: Array[AnchorPoint] = []
	var root := EditorInterface.get_edited_scene_root()
	if root != null:
		_collect(root, result)
	return result

func _collect(node: Node, into: Array[AnchorPoint]) -> void:
	if node is AnchorPoint:
		into.append(node)
	for child in node.get_children():
		_collect(child, into)
```

Key points: `_handles()` returning `true` is what activates viewport input forwarding, and putting the scene-scan condition there (rather than in `_edit()`) is what lets the plugin act on unselected nodes. `_forward_canvas_gui_input()` returns `true` only while actively dragging, so all other editor interactions remain untouched. The drag is committed through `UndoRedo` with `MERGE_ENDS` so the whole gesture is a single undoable action.
