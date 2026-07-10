# GDScript Linting & Formatting Guide

This project uses [godot-gdscript-toolkit](https://github.com/Scony/godot-gdscript-toolkit) (`gdlint` + `gdformat`) via pre-commit hooks to enforce consistent GDScript style.

## Setup

Pre-commit is installed automatically by `setup.sh`. To run manually:

```bash
uv run pre-commit run --all-files
```

The config lives at `.pre-commit-config.yaml` and pins `godot-gdscript-toolkit` at `4.5.0`.

## Definition Order (`class-definitions-order`)

This is the most common gdlint failure. Every `.gd` file must declare its members in this exact order:

1. `@tool`
2. `class_name`
3. `extends`
4. `signal`
5. `enum`
6. `const`
7. `@export var`
8. `var` (public)
9. `_var` (private, prefixed with underscore)
10. `@onready var` (public)
11. `@onready _var` (private)
12. `func`

### Example

```gdscript
@tool
class_name MyClass
extends Node

signal value_changed(new_value: int)

enum State { IDLE, MOVING, JUMPING }

const MAX_SPEED: float = 300.0

@export var speed: float = 200.0
@export var health: int = 100

var current_state: State = State.IDLE
var _internal_counter: int = 0

@onready var sprite: Sprite2D = $Sprite2D
@onready var _animator: AnimationPlayer = $AnimationPlayer

func _ready() -> void:
    pass
```

### Common Mistakes

- **`extends` before `class_name`**: gdlint requires `class_name` first. Swap them.
- **`signal` after `var`**: Signals must come before any variable declarations.
- **`const` after `static var`**: Constants must come before all variable declarations, including `static var`.
- **`@onready var` before `var`**: `@onready` variables come after regular variables, not before.
- **`@export var` after `@onready var`**: Exports come before regular and onready variables.
- **Interleaved `@export var` and `var`**: Group all `@export var` declarations together, then all plain `var` declarations.

## Line Length (`max-line-length`)

Maximum 100 characters per line. To fix:

- Break long comments onto multiple lines with `#` on each.
- Break long function calls across multiple lines using parentheses or line continuation.
- Extract complex expressions into intermediate variables.

## Unused Arguments (`unused-argument`)

Prefix unused function arguments with `_`:

```gdscript
# Bad — gdlint error if delta is not used:
func _process(delta: float) -> void:
    do_something()

# Good:
func _process(_delta: float) -> void:
    do_something()
```

This convention applies to any function argument that is not referenced in the body.

## Unnecessary `pass` (`unnecessary-pass`)

Remove `pass` statements from functions that have other statements. `pass` is only needed in completely empty function bodies:

```gdscript
# Bad — pass after real statements:
func _ready() -> void:
    setup()
    pass

# Good:
func _ready() -> void:
    setup()

# Good — pass is the only statement:
func empty_function() -> void:
    pass
```

## Formatting (`gdformat`)

`gdformat` auto-formatters indentation, spacing, and line breaks. It runs automatically via pre-commit and modifies files in place. If it fails, re-run `pre-commit run gdformat --all-files` and commit the reformatted files.

### Tabs vs Spaces

GDScript uses **tabs** for indentation. `gdformat` enforces this automatically.

## Disabling Rules Inline

To suppress a specific gdlint rule on a line, use a `# gdlint: disable=<rule-name>` comment:

```gdscript
var my_unconventionally_named_var = 42  # gdlint: disable=class-variable-name
```

## Project-Specific Configuration

A `.gdlintrc` file can be placed at the project root to customize or disable rules globally:

```ini
[class-definitions-order]
# Disable the order check entirely (not recommended)
disable = true

[max-line-length]
# Increase to 120
max_line_length = 120
```

See the [gdlint wiki](https://github.com/Scony/godot-gdscript-toolkit/wiki/3.-Linter) for all available rules and configuration options.
