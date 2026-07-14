---
trigger: always
---
# Testing

Use **GUT** for all automated tests. Target Godot 4.6/4.7 — use GUT 9.6.1 for
4.6, GUT 9.7.1 for 4.7.

These tests run **without user interaction** — they are fully automated. User
interaction (manual playtesting, demonstrating a scene to the user) is a
separate workflow covered in `test_godot_scene.md`. Only involve the user when
explicitly asked, when an obvious back-and-forth is needed, or to demonstrate
something.

Organize tests into four categories under `test/`:

## Unit tests (`test/unit/`)

Very fast. Test individual functions/scripts in isolation. No scene tree, no
nodes, no mocking/stubbing unless absolutely necessary — prefer testing code
that is naturally independent (pure functions, stateless logic, static helpers).
If a function requires too much setup or mocking to test, that's a signal it
should be refactored, not mocked around.

## Integration tests (`test/integration/`)

Slower. Test interactions between multiple types/scripts. Instantiate "base"
scenes (e.g. a Player scene) and verify cross-object behavior. If a test
involves the full environment and user interaction, it belongs in e2e instead.

## E2E tests (`test/e2e/`)

Test full, complex scenes end-to-end. Load a complete scene, simulate input,
and assert on the resulting state. These are the slowest tests.

## Consistency tests (`test/consistency/`)

Written by the LLM during development. Verify that the scene/file matches
intent — not how code works, but that things are configured correctly. Examples:
- A Sprite2D's texture is the atlas region the LLM intended to assign.
- Collision layers are set correctly on the expected nodes.
- After `_ready()`, a node has the expected initial state.
- A TileMapLayer has the expected cells/collision.

These are trial/property checks on the scene as it's being built. They catch
LLM mistakes (wrong assignment, missing node, wrong layer) early.
