# tscn editing library + YAML ops CLI (first pass)

## Context

`docs/features/llm_tscn_cli_tool.md` sketches a tool that lets an LLM edit Godot `.tscn` files with typed validation. The repo already has the hard prerequisite: generated pydantic models for every Godot 4.7 class and builtin (`src/godotllminteraction/specifications/v4_7_0/`). What's missing entirely is a tscn parser/writer, a scene data model, and an operation layer — `gli tscn validate` today just shells out to Godot.

Decisions made with the user:
- **Write our own parser/writer.** Core library decoupled from any frontend — plain Python API in its own package; typer CLI on top; MCP server possible later. Never import typer/rich in the core.
- **Pydantic everywhere, no dataclasses.**
- **Version-agile by construction.** Nothing in the core hardcodes v4_7_0 except a default. The validator takes a *spec provider* built from any version's generated pydantic module — a new Godot version means running the existing codegen and pointing the provider at the new module, zero custom validation code.
- **Deterministic operations.** No randomness anywhere (ids, ordering, formatting). Adding X to `a.tscn` always produces the identical file. An add followed by a delete restores the original file byte-for-byte — this is an explicit tested invariant.
- **Two passes.** This plan is pass 1: core library + YAML bulk-ops frontend + `tree`/`check` commands. Pass 2 (later): granular CLI commands (`gli tscn add-node ...`) and a stdin streaming mode — thin frontends over the same core.
- **Full operation set** including signal connections, reparent, and rename.
- **User-defined `class_name` scripts deferred** — class resolution stays behind one seam (`resolve_class(name) -> model | None`) so a project-scan resolver can slot in later.

Research findings (verified against [official tscn docs](https://github.com/godotengine/godot-docs/blob/master/engine_details/file_formats/tscn.rst)):
- **`unique_id` is standard**: integer node-heading attribute, emitted by Godot 4.6+, used to track nodes across moves/renames. Optional — older files lack it. We preserve it and *generate it deterministically* for new nodes.
- **`load_steps` is deprecated** in the current format ("should be ignored if present"). We preserve it verbatim if present, recompute only when present and resource counts change, and never add it to files that lack it.
- **Signals** live in `extension_api.json` (per-class, with argument types: `{"name": "sources_changed", "arguments": [{"name": "exist", "type": "bool"}]}`; `arguments` absent for zero-arg signals) — the same source the existing codegen consumes. **In scope for pass 1**: extend the specifications codegen to emit a generated `signals.py` per version, and validate signal names in `connect_signal`.

## Module layout

New package `src/godotllminteraction/tscn/` (zero typer/rich imports, all pydantic):

```
tscn/
    __init__.py     # public API: load_scene, dump_scene, apply_operations, validate_scene, render_tree
    exceptions.py   # TscnError base; ParseError, OperationError, ValidationError
    values.py       # GodotValue union: typed literals preserving source form
    lexer.py        # section headers, attributes, property lines, value tokens
    parser.py       # tokens -> Scene
    scene.py        # Scene / NodeEntry / ExtResourceEntry / SubResourceEntry / ConnectionEntry
    writer.py       # Scene -> tscn text, byte-for-byte round-trip
    operations.py   # pydantic op models (discriminated union) + apply dispatch
    validation.py   # spec-backed checks -> ValidationReport
    specs.py        # SpecProvider protocol + provider built from any {Name}v{X}_{Y}_{Z} module
    tree.py         # tree rendering model (nodes / +resources / +properties detail levels)
    godot_check.py  # locate godot executable + run --check-only; structured result
    yaml_ops.py     # YAML ops-file schema + loader (pyyaml lives here only)
src/godotllminteraction/cli/tscn.py   # extend: apply, tree; improve validate (discovery, clear errors, --json)
```

Plus:
- `pyyaml` added to `pyproject.toml`; `out/` added to `.gitignore`.
- **Signals codegen**: new `generate-signals` command in `cli/specifications.py` (wired into `generate-all`, with `--check` like the others) emitting `specifications/v4_7_0/signals.py`. Reuses the existing `ClassSignal` models in `spec.py` for parsing. Generated content: frozen pydantic models `SignalArgument(name, type)` and `GodotSignal(name, arguments)`, plus per-class own-signal dicts `SIGNALS: dict[str, dict[str, GodotSignal]]` keyed by class name. Inheritance is not flattened at generation time — the `SpecProvider` unions own-signal dicts by walking the class model's MRO (inheritance is already mirrored in `classes.py` subclassing), so the generated file stays small and version-mechanical.

## Data model

**Values** (`values.py`): closed union of frozen pydantic models — `GBool`, `GInt`, `GFloat` (with `raw: str | None` preserving `-5.72205e-06` exactly), `GString`, `GStringName` (`&"default"`), `GNodePathLiteral`, `GNull`, `GArray`, `GDict` (ordered key/value pairs), and `GCall(name, args)` covering `Vector2(...)`, `Color(...)`, `ExtResource("id")`, `SubResource("id")`, and flat `Packed*Array(...)`, with helper predicates for resource refs. `values.parse_value("Vector2(1, 2)")` is the shared entry point — the YAML layer and future CLI commands express property values in Godot literal syntax.

**Scene** (`scene.py`): `Scene{header, ext_resources, sub_resources, nodes, connections}` — all pydantic. Every entry keeps a generic insertion-ordered `attributes: dict[str, GodotValue]`, which is how `unique_id`, `index=`, `owner=`, and any future attributes survive untouched. Nodes addressed by path (`Player/Sprite2D`), derived from tscn's own `parent=` + `name` convention. Queries: `node(path)`, `children(path)`, `subtree(path)`.

**Writer contract**: `dump(parse(text)) == text` byte-for-byte. Preserve attribute order, raw numeric tokens, Godot's escaping and multi-line dict/array formatting. Section spacing is canonical and position-independent (exactly one blank line between sections, one trailing newline) so that inserting then removing a section restores the original bytes.

**Determinism rules**:
- New node `unique_id`: deterministic 32-bit hash of (scene uid, node path), bumped on collision with existing ids. Same scene + same op → same id, always.
- New ext/sub resource ids: Godot-shaped (`"3_a4ypi"`, `"RectangleShape2D_uunpc"`) but with the suffix derived from a deterministic hash of (type, path/properties), ordinal from position. No `random`, no `Date.now`-style inputs anywhere in the core.
- Insertion points are fully determined by tree structure (depth-first, after parent's subtree; sub_resources before first node in creation order).
- Invariant test: `apply([add X]); apply([delete X])` → file byte-identical to the original.

## Validation (`specs.py` + `validation.py`)

- **`SpecProvider`**: built from a version module by scanning for pydantic models named `{ClassName}v{major}_{minor}_{patch}`. Exposes `resolve_class(name)`, `resolve_builtin(name)`, `packed_element_width(name)`, and (future) `signals_of(name)`. Default provider wraps `specifications/v4_7_0`; a v4.8 provider is one codegen run + one constructor call. All validation logic works on `model_fields` / annotations generically — no per-version code.
- Property lookup: pydantic merges inherited fields, so `prop in model.model_fields` walks inheritance for free.
- Value type check against `model_fields[prop].annotation`: scalars ↔ G-scalars (GInt accepted where float expected; NodePath/StringName map to str); builtin models ↔ `GCall` name match + arity; `List[X]` (Packed*Array) ↔ flat call args checked for divisibility by element width (derivation mirrors `_packed_array_element_types` in `cli/specifications.py:574`); engine-class annotations ↔ ExtResource/SubResource refs that resolve in-scene, subclass-checked via `issubclass` on spec models; `Any` accepts anything.
- Escape hatches: node with `script` or `instance=` → unknown property is a **warning**; `metadata/...` keys warn at most; instanced nodes without `type=` skip class checks.
- Output: `ValidationReport(errors, warnings)` pydantic model — each `Issue` has node path, property, message. Serializes directly for `--json` output.
- Signal-name validation: `SpecProvider.signals_of(class_name)` unions the generated per-class signal dicts along the class model's MRO. `connect_signal` checks the signal exists on the `from` node's class when the class is known (instanced/scripted nodes fall back to a warning, same escape-hatch policy as properties). The target `method` can't be validated offline (it lives in a script) — no check there.

## Operations (`operations.py`)

Pydantic discriminated union on `op:` literal. Applied in order, all-or-nothing (mutate in memory; write only if every op succeeds). Every op's outcome is recorded in an `OpResult` (op, affected paths, allocated ids, `changed: bool`, report) — the material for `--json` output.

**Idempotency principle**: every op describes a desired state. If the state already holds, the op is a recorded no-op (`changed: false`), never an error; errors are reserved for genuine conflicts. Applying the same ops file twice yields a byte-identical file. Per op:
- `add_node`: node already exists at path with the same type and its properties already at the requested values → no-op. Same path but **different type** → error (conflict). Same path, same type, different property values → error in pass 1 (ambiguous: use `update_properties` to change values; keeps add's meaning unambiguous).
- `update_properties`: setting a property to its current value → no-op (naturally idempotent); `remove` of an already-absent property → no-op.
- `delete_node` / `disconnect_signal`: target already absent → no-op (desired state: gone).
- `add_ext_resource` / `create_sub_resource`: identical (type, path/properties) already present → no-op returning the existing id; same explicit id with different content → error.
- `attach_script`: same script already attached → no-op. `detach_script`: no script attached → no-op.
- `connect_signal`: identical connection already present → no-op.
- `rename_node` / `move_node`: already has the target name / parent+index → no-op.

- `add_node(path, type, properties?, groups?, index?)` — parent must exist; sibling-name conflict rules per idempotency table above; deterministic `unique_id` assigned; inserted depth-first after parent's subtree.
- `delete_node(path, recursive=true)` — deletes subtree; strips connections into the subtree; deleting root errors; with `recursive=false`, error if children exist. Orphaned sub_resources kept in pass 1 (shared-resource GC unsafe; Godot tolerates orphans) — refcount GC is a follow-up. Note: delete-after-add restores original bytes because add's insertions are canonical.
- `update_properties(path, properties: dict[str, value], remove: list[str]?)` — one or more properties per op; values are Godot-literal strings parsed by `values.parse_value`; each validated against spec; `remove` list drops lines (revert to default).
- `rename_node(path, new_name)` / `move_node(path, new_parent, index?)` — cycle rejection on move; sibling-uniqueness at destination; rewrites descendants' `parent=` and connection paths. **NodePath rewriting is exact, not best-effort**: since we hold the full tree, every relative NodePath property in the scene is resolved to its absolute target from its owner's path; if the target or the owner is affected by the rename/move, the path is recomputed relative to the owner's new location. Only paths that escape the scene root (`../..` above root) or point at nonexistent nodes are left untouched with a warning.
- `attach_script(path, script_path, uid?)` — reuse or add `ext_resource type="Script"`, set `script = ExtResource(id)`.
- `detach_script(path)` — remove the node's `script` property; the Script ext_resource is kept if other nodes reference it, removed if this was the only reference. No script attached → no-op.
- `add_ext_resource(type, res_path, uid?, id?)` — dedup by (type, path); deterministic id allocation.
- `create_sub_resource(type, id?, properties?)` — deterministic id; type must be a Resource subclass; properties validated.
- `connect_signal(from, to, signal, method, flags?, binds?)` / `disconnect_signal` — dedup / error-if-missing; signal name validated via `SpecProvider.signals_of` (warning instead of error when the `from` node is scripted/instanced).

## CLI commands (`cli/tscn.py`)

All commands gain `--json` (off by default): print a pydantic-serialized result object (op results, ValidationReport, tree structure) to stdout instead of rich output. Errors are always clear one-line messages with the failing op/node/property named, exit code 1 (2 for usage).

- `gli tscn apply ops.yaml [--scene PATH] [--output PATH] [--dry-run] [--no-strict] [--json]` — the YAML frontend. `--dry-run` prints report + diff without writing (wire the currently-ignored global dry-run flag for real).
- `gli tscn tree SCENE [--detail nodes|resources|properties] [--json]` — visualize the tree. `nodes`: names + types; `resources`: plus each node's ext/sub resource references resolved to type+path; `properties`: plus all set properties. Rich tree rendering; `--json` emits the nested structure.
- `gli tscn validate` (existing) — improved: godot executable discovery in `tscn/godot_check.py` with clear precedence: `--godot` flag → `GODOT_BINARY` env → `godot`/`godot4` on PATH → common per-OS install locations (Linux primary; macOS `/Applications/Godot.app/...`, Windows `%LOCALAPPDATA%`/Program Files best-effort). Failure message states exactly what was tried and how to fix it (`set GODOT_BINARY or pass --godot`). `--json` reports the command run, exit code, and captured output. The check itself stays `godot --headless --check-only --quit --path <project> <target>`.

## YAML ops file (`yaml_ops.py`)

```yaml
version: 1
scene: scenes/door.tscn        # or omit + create: {root_name, root_type} for a new scene
output: out/door_edited.tscn   # default in-place
strict: true
operations:
  - op: add_ext_resource
    type: Texture2D
    path: res://asset/tilemap_packed.png
    ref: tilemap                        # symbolic handle for later ops
  - op: add_node
    path: Door/Hinge
    type: Sprite2D
    properties:
      position: "Vector2(8, 0)"
      texture: { ext_resource: tilemap }
  - op: update_properties
    path: Door/AnimatedSprite2D
    properties:
      autoplay: '"default"'
      speed_scale: "1.5"
  - op: connect_signal
    from: Door/BooleanArea2D
    to: Door
    signal: all_activated
    method: open
```

`OpsFile` pydantic model reuses the same `Operation` union from `operations.py` (single source of truth); YAML is parsed straight into pydantic; the YAML layer only resolves `ref` indirection before apply.

## Tests

Dedicated fixture scenes live in `tests/data/scenes/` so tests don't depend on the rest of the repo — hand-crafted to cover the hard constructs (`unique_id` attrs, nested dict-in-array like SpriteFrames, flat Packed*Arrays, `&"..."` StringNames, exponent floats, `[connection]` sections, instanced scenes, groups, metadata keys, relative NodePaths). **The user will open these in the Godot editor to confirm they're valid** before they become ground truth.

- `tests/unit/tscn_values_test.py` — every literal kind, escapes, round-trip of raw numeric tokens.
- `tests/unit/tscn_roundtrip_test.py` — parametrized over `tests/data/scenes/*.tscn`: `dump(parse(text)) == text` byte-for-byte, plus idempotence. (Repo scenes under `scenes/`/`examples/` run as a secondary, non-load-bearing parametrization.)
- `tests/unit/tscn_operations_test.py` — op semantics: delete-with-children, reparent + exact NodePath rewriting, cycle rejection, sibling collisions, deterministic id/unique_id allocation (same input → same output), **add-then-delete byte-identity invariant**, **idempotency invariant: applying the same ops file twice → byte-identical result, every second-run OpResult has `changed: false`**.
- `tests/unit/tscn_validation_test.py` — checks against the real v4_7_0 provider; script escape hatch; packed-array divisibility; signal-name resolution incl. inherited signals; provider built from a tiny fake version module to prove version-agility.
- `tests/unit/generate_signals_test.py` — signals codegen, following the existing fake-`extension_api.json`-dict pattern of `generate_classes_test.py` (incl. the zero-arg case where `arguments` is absent).
- `tests/unit/tscn_yaml_scenarios_test.py` — YAML scenarios in `tests/data/tscn_scenarios/*.yaml` (`initial`, `operations`, `expect`); with `GLI_SCENARIO_OUT_DIR` set, outputs also land in gitignored `out/tscn_scenarios/` for inspection in the Godot editor. Scenario list seeds from the doc: bodies + every collision-shape type, sprite with atlas texture, AnimatedSprite2D, AnimationPlayer, audio, attached scripts, instanced packed scenes. (Tweening dropped — no scene-file representation.)
- `tests/unit/tscn_tree_test.py` — tree rendering at all three detail levels + json shape.
- `tests/unit/tscn_apply_cli_test.py` — `CliRunner` over `apply`/`tree`/`validate` incl. `--json` and exit codes.
- `tests/integration/tscn_godot_check_test.py` — reuse the existing `godot_binary` skip-if-absent fixture; run the check on fixture scenes and scenario outputs.

## Implementation order

1. **Signals codegen first**: `generate-signals` in `cli/specifications.py` + generated `specifications/v4_7_0/signals.py` + codegen tests.
2. `pyyaml` dep; `out/` in `.gitignore`; author `tests/data/scenes/` fixtures (user validates them in the editor).
3. `exceptions.py` + `values.py` + value tests (the risk core of the parser).
4. `lexer.py` + `parser.py` + `scene.py`; parse all fixture + repo files.
5. `writer.py`; drive round-trip test to byte-for-byte green.
6. `specs.py` (SpecProvider incl. `signals_of`) + `validation.py` + tests.
7. `operations.py` (update_properties → add_node → delete → resources/attach_script/detach_script → connections → rename/move) + determinism and idempotency invariant tests.
8. `tree.py` + `godot_check.py`.
9. `yaml_ops.py` + public API in `__init__.py`.
10. CLI: `apply`, `tree`, improved `validate`, `--json` everywhere + CLI tests.
11. Scenario suite + integration godot-check test.

## Verification

- `uv run pytest tests/unit` — round-trip + determinism invariants are the main correctness gates.
- Run a real scenario: `uv run gli tscn apply <scenario>.yaml --output out/test.tscn`, `uv run gli tscn tree out/test.tscn --detail properties`, then `uv run gli tscn validate out/test.tscn` with a Godot binary and open the result in the editor.

## Follow-ups (explicitly out of pass 1)

- Granular CLI commands and stdin streaming mode (pass 2 frontends).
- User-defined `class_name` resolution via project scan (slots into `resolve_class`).
- Sub-resource refcount GC on delete.
- MCP server over the core API.
