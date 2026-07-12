# Multi-Version Godot Specification System

Build a system that can generate and maintain Python pydantic specifications for multiple Godot versions (4.4.0 → 4.4.1 → 4.5.0 → 4.6.0 → 4.6.2 → 4.7), with automated schema-diff detection, code generation, per-version tests, and a human-friendly workflow script. Use the semble MCP to search the Godot engine repo (pass URL + tag/commit hash) when source-level research is needed.

## Architecture

### Shared base + version overrides

```
specifications/
  shared/
    __init__.py
    spec.py          # Hand-written base models (Header, BuiltinClass, GodotClass, ...)
                     # All version-variant fields are Optional with defaults
  v4_4_0/
    __init__.py      # Exports Specification4_4_0
    spec.py          # Imports shared models + version-specific enums + Specification4_4_0
    builtin_classes.py  # Auto-generated (existing generator, already version-agnostic)
    classes.py          # Auto-generated
    constants.py        # Auto-generated
    signals.py          # Auto-generated
  v4_4_1/ ...        # If enums identical to v4_4_0, imports enums from v4_4_0
  v4_5_0/ ...
  v4_6_0/ ...
  v4_6_2/ ...
  v4_7_0/            # Left as-is for now; migrated to shared later (manual, incremental)
```

The `shared/spec.py` contains the common pydantic models extracted from the current `v4_7_0/spec.py`. Fields that may differ between versions are `Optional` with defaults. Each version's `spec.py` imports these shared models, defines version-specific generated enums (or imports them from a base version if identical), and declares a `SpecificationX_Y_Z` class.

### What stays constant (shared schema) — to be verified by tests

Based on analysis of the current spec and the godot-cpp reference JSONs (4.3 through 4.7):

- **Top-level sections**: `header`, `builtin_class_sizes`, `builtin_class_member_offsets`, `global_constants`, `global_enums`, `utility_functions`, `builtin_classes`, `classes`, `singletons`, `native_structures` — present in all 4.x versions
- **Model structure**: `Header`, `GlobalConstant`, `GodotEnum`, `UtilityFunction`, `BuiltinClass`, `GodotClass`, `Singleton`, `NativeStructure` and their sub-models — field names are stable across 4.x
- **Enum value sets**: `GodotTypeNameEnum`, `UtilityFunctionCategoryEnum`, `BuiltinClassOperatorNameEnum`, `GodotArgumentMetaEnum`, `ClassApiTypeEnum` — the *set* of values may grow between versions but the enum *names* are stable. These are auto-generated per version.

**These claims are verified by e2e tests** (see Step 7) that dump `extension_api.json` from each installed Godot binary and check the sections/enum names.

### What may change between versions

- **Field presence**: Some fields are optional in certain versions (e.g., `hash_compatibility` was added in 4.4 for virtual methods, `is_required` may not exist in older versions). These are already `Optional` in the current models.
- **Enum values**: New types, operators, metas, api_types may appear in newer versions. Handled by the enum sync CLI.
- **Header values**: `version_major`, `version_minor`, etc. change per version. The `Header` model is shared; defaults are auto-filled from the JSON.
- **Data content**: New classes, methods, properties, signals appear. Handled by the existing generate-* commands.

## Version Tracking: `godot-versions.txt`

A plain text file at the repo root listing all supported Godot versions, one per line, in ascending order (last line = latest version):
```
4.4.0
4.4.1
4.5.0
4.6.0
4.6.2
4.7.0
```
- Assumption: **linear updates** — each version builds on the previous; the last entry is the latest.
- Used by: `add-version` CLI (to determine the previous version for `--base-version`), test parametrization (to discover version packages), `godotctl download-apis` (to know which files to fetch).
- The `add-version` CLI reads this file to auto-suggest `--base-version` (the line before the new version).

## extension_api.json Storage

- **Location**: `tests/data/extension_api/` (gitignored)
- **Naming**: `extension_api-4.4.0.json`, `extension_api-4.4.1.json`, etc.
- **Source**: Downloaded from the godot-cpp GitHub repo for offline use. The godot-cpp files are minor-version only (`extension_api-4-4.json`), so patch versions within the same minor share the same reference file (e.g. 4.4.0 and 4.4.1 both use `extension_api-4-4.json`). This assumption is verified by e2e tests that dump fresh from the actual binary.
- **Download**: `godotctl download-apis` command (added to `install-godot.sh`). Reads `godot-versions.txt`, fetches the appropriate `extension_api-4-X.json` from `https://raw.githubusercontent.com/godotengine/godot-cpp/master/gdextension/`, saves to `tests/data/extension_api/`.
- **Never load into LLM context**: These files are 5-7 MB each. All interaction is via code (Python `json.loads`, `jq`, etc.).
- **Add to .gitignore**: `tests/data/extension_api/`

### Currently installed Godot binaries

```
/opt/godot/godot-4.4.1-stable
/opt/godot/godot-4.6.2-stable
/opt/godot/godot-4.7-stable
```

Missing: 4.4.0, 4.5.0, 4.6.0. The `setup.sh` script (see Step 5) reports which binaries are missing and prints instructions on how to get them:
```
Missing Godot binaries for versions: 4.4.0, 4.5.0, 4.6.0
  Download from: https://godotengine.org/download/archive/
  Then register with: godotctl register <path-to-binary> godot-<version>-stable
  e2e tests for these versions will be skipped until the binaries are installed.
```

e2e tests skip automatically when a binary is not found (existing pattern in `tests/integration/conftest.py`).

## Implementation Steps

### Step 1: Create `specifications/shared/spec.py`

Extract the common pydantic models from `v4_7_0/spec.py` into `specifications/shared/spec.py`:
- Move all model classes (`Header`, `ClassSize`, `BuiltinClassSizeType`, ... `GodotClass`, etc.)
- Remove the generated enum blocks (those stay per-version)
- Keep the type aliases (`GodotTypeName`, `UtilityFunctionCategory`, etc.) as `Union[str, str]` placeholders — the version-specific spec.py overrides them with the generated enums
- Add `specifications/shared/__init__.py`
- **No leading-underscore class names** — use plain names like `FrozenModel` if needed

**Key**: The shared models use `Union[str, str]` (effectively `str`) for type-alias fields like `GodotTypeName`. Each version's `spec.py` redefines these aliases with the actual generated enum `Union[GodotTypeNameEnum, str]`, and the version-specific `Specification` class uses those aliases. Pydantic resolves the annotations at class definition time.

### Step 2: Generalize enum sync to any version

Refactor `sync-enums-v4-7-0` into `sync-enums`:
- New command: `gli specifications sync-enums --version vX_Y_Z --api <json>`
- The marker comments in each version's `spec.py` use the version name: `# === GENERATED: GodotTypeNameEnum (run: gli specifications sync-enums --version vX_Y_Z) ===`
- The `_block_pattern` function uses the version name instead of hardcoded "v4-7-0"
- The render functions (`_render_type_name_block`, etc.) already work on any JSON — no changes needed
- **Mark `sync-enums-v4-7-0` as deprecated**: Add a deprecation warning when invoked, pointing users to `sync-enums --version v4_7_0`. Keep it functional for backward compatibility.

### Step 3: Build the schema diff CLI

New command: `gli specifications diff-schema --version vX_Y_Z --api <json> --base-version vA_B_C [--report <path>] [--format yaml|json]`

**`--base-version` is mandatory** unless `--first-version` is passed (for the very first version added to the system, where there's no base to compare against).

**What it does:**
1. Loads the `extension_api.json` (via code, never into LLM context)
2. Recursively walks the JSON, collecting all keys at each path (e.g., `classes.methods.hash_compatibility`)
3. For list fields, unions keys across all items (since optional fields may not appear in every item)
4. Compares the collected key set against the shared model's field definitions (walked recursively via `model.model_fields`)
5. Compares the new JSON's enum values against the base version's enums to determine which can be imported vs need fresh generation
6. **Writes a machine-parseable report** to `--report <path>` (default: `schema_diff_vX_Y_Z.yaml`). **Format is YAML by default**; `--format json` produces JSON instead.

**Report format** (YAML by default, designed for both LLM and human consumption):
```yaml
version: v4_4_1
base_version: v4_4_0
requires_human_intervention: false
added_fields:
  - path: classes.methods.hash_compatibility
    type: Optional[List[int]]
    auto_generatable: true
removed_fields:
  - path: classes.methods.is_required
    was_optional: true
    action: no_action_needed
type_changes: []
new_top_level_sections: []
enum_comparison:
  GodotTypeNameEnum:
    identical_to_base: true
    import_from_base: true
  ClassApiTypeEnum:
    identical_to_base: true
    import_from_base: true
test_guidance:
  detectable:
    - "Added field classes.methods.hash_compatibility: write a unit test asserting the field is Optional and defaults to None"
    - "Enum GodotTypeNameEnum differs from base: write an integration test asserting new enum members are present"
  generic: "Some schema changes were detected that may require version-specific test assertions. Review the diff report and add tests as needed."
```

The `test_guidance` section provides actionable hints: if we can detect what to test (e.g., a new field, a changed enum), we output a specific suggestion. Otherwise, a generic message tells the dev that tests need to be written.

**Auto-generation rules (pure code, no LLM):**
- ADDED field on an existing model → generate a version-specific subclass with the new `Optional` field
- REMOVED field that's already `Optional` in shared → no action needed (pydantic accepts missing optional fields)
- REMOVED field that's required in shared → flag for human (the shared model needs updating)
- TYPE_CHANGE → flag for human
- New top-level section → flag for human

**Exit code**: 0 if no human intervention needed, non-zero if structural changes detected.

**Report parsability**: The report (YAML or JSON) is structured so that future helper functions can parse it programmatically (e.g., an LLM could read the report file and make targeted edits without loading the full extension_api.json).

### Step 4: Build the `add-version` CLI

New command: `gli specifications add-version --version vX_Y_Z --api <json> --base-version vA_B_C [--first-version]`

**`--base-version` is mandatory** unless `--first-version` is passed. The CLI reads `godot-versions.txt` to auto-suggest the base version (the line before the new version) if `--base-version` is omitted — but still requires the flag explicitly.

**Orchestrates the full version-addition workflow:**
1. Run `diff-schema` — if human intervention needed, stop and report (write report to file)
2. Create `specifications/vX_Y_Z/` package
3. Generate `spec.py` from a template:
   - Compare enums extracted from new JSON against base version's enums. **Import only if identical** — for each enum, if the extracted values match the base version's values, import from base; otherwise generate fresh enum blocks in the new version's spec.py
   - If `--first-version`: always generate fresh enum blocks (no base to compare against)
   - Import shared models from `specifications/shared/spec.py`
   - Define `SpecificationX_Y_Z` class with the same fields as `Specification4_7`
4. Run `sync-enums --version vX_Y_Z --api <json>` (only for enums that weren't imported from base)
5. Run `generate-builtin-classes --version vX_Y_Z --api <json>`
6. Run `generate-classes --version vX_Y_Z --api <json>`
7. Run `generate-signals --version vX_Y_Z --api <json>`
8. Generate `__init__.py` exporting `SpecificationX_Y_Z`
9. Append the new version to `godot-versions.txt`
10. Report success or issues, including **test guidance** from the diff report (specific suggestions where detectable, generic message otherwise)

**Enum import logic** (import only if identical):
```python
# For each of the 5 enums:
new_values = extract_enum_values(new_json, enum_name)
base_values = get_enum_values_from_module(base_version_module, enum_name)
if new_values == base_values:
    # Import from base version
    generate_import_statement(base_version, enum_name)
else:
    # Generate fresh enum block with marker comments
    generate_enum_block(enum_name, new_values)
```

**Open point for later**: A `dereference` command that inlines imported enums into a version's spec.py, in case we want to decouple versions. Leave as TODO.

### Step 5: Add `download-apis` to godotctl + update `setup.sh`

**Add `download-apis` command to `install-godot.sh`** (the `godotctl` script):
- New command: `godotctl download-apis [--out-dir <path>] [--versions-file <path>] [--force]`
- Reads `godot-versions.txt` from the repo root (or `--versions-file`)
- For each version, determines the minor version (e.g. 4.4.0 → 4.4) and fetches `extension_api-4-4.json` from `https://raw.githubusercontent.com/godotengine/godot-cpp/master/gdextension/`
- Saves to `tests/data/extension_api/extension_api-<version>.json`
- Patch versions within the same minor share the same source file (copied)
- Skips files that already exist (unless `--force`)
- Reports which files were downloaded, skipped, or failed

**Update `setup.sh`** to call `godotctl download-apis` after `uv sync`:
```bash
# After uv sync and pre-commit install:
# Download extension_api.json reference files for integration tests
echo "Downloading extension_api.json reference files..."
godotctl download-apis || echo "Warning: could not download extension_api.json files. Integration tests will be skipped."

# Check for missing Godot binaries and report to the user
# (reads godot-versions.txt, checks /opt/godot/ for each)
```

**Missing binary reporting** (in `setup.sh` or a helper called by it):
- Reads `godot-versions.txt`, checks which binaries are installed in `/opt/godot/`
- Prints a clear message for each missing binary with download instructions:
  ```
  Missing Godot binaries for versions: 4.4.0, 4.5.0, 4.6.0
    Download from: https://godotengine.org/download/archive/
    Then register with: godotctl register <path-to-binary> godot-<version>-stable
    e2e tests for these versions will be skipped until the binaries are installed.
  ```
- This is informational only — setup.sh does not fail, just warns. Other developers can still run unit/integration tests.

Add `tests/data/extension_api/` to `.gitignore`.

### Step 6: Add 4.4.0 as the first new version

**Workflow:**
```bash
# If binary not installed, download from Godot releases and register:
# godotctl register <path-to-binary> godot-4.4.0-stable
godotctl switch 4.4.0
godot --headless --dump-extension-api --quit
gli specifications add-version --version v4_4_0 --api extension_api.json --first-version
```

- Run the schema diff against 4.4.0's JSON (no base version comparison since `--first-version`)
- Expected differences (based on research):
  - `hash_compatibility` may not exist on some methods (added in 4.4)
  - `is_required` may not exist on virtual methods
  - Fewer classes/builtins (data differences, not structural)
  - Header values differ
- If the diff is clean (only Optional field differences), auto-generate the full spec package
- If structural changes are detected, report them for human review

### Step 7: Add remaining versions incrementally

Add 4.4.1 → 4.5.0 → 4.6.0 → 4.6.2 → 4.7, each with `--base-version` pointing to the previous:

```bash
# 4.4.1 (base: 4.4.0 — likely identical enums, will import from base)
godotctl switch 4.4.1
godot --headless --dump-extension-api --quit
gli specifications add-version --version v4_4_1 --api extension_api.json --base-version v4_4_0

# 4.5.0 (base: 4.4.1)
godotctl switch 4.5.0
godot --headless --dump-extension-api --quit
gli specifications add-version --version v4_5_0 --api extension_api.json --base-version v4_4_1

# 4.6.0 (base: 4.5.0)
godotctl switch 4.6.0
godot --headless --dump-extension-api --quit
gli specifications add-version --version v4_6_0 --api extension_api.json --base-version v4_5_0

# 4.6.2 (base: 4.6.0 — likely identical enums, will import from base)
godotctl switch 4.6.2
godot --headless --dump-extension-api --quit
gli specifications add-version --version v4_6_2 --api extension_api.json --base-version v4_6_0

# 4.7 (base: 4.6.2 — v4_7_0 already exists, this is for verification)
# Skip: v4_7_0 already exists. Migrate it to shared later (manual, incremental).
```

Each addition tests the schema diff detection and the enum import logic. The `add-version` CLI outputs **test guidance** from the diff report: specific suggestions where detectable (e.g., "new field X: write a test asserting it's Optional"), or a generic message ("review the diff report and add tests as needed"). Expected: 4.6+ may introduce new fields not in 4.4/4.5.

### Step 8: Tests

#### Test classification

- **e2e**: Uses a real Godot binary (via `godotctl`/PATH) to dump `extension_api.json`. Slow, requires binaries. Skips if binary not found.
- **integration**: Uses pre-downloaded `extension_api.json` files + our pydantic models. Tests interaction between our code and the external Godot API data. No binary needed.
- **unit**: Uses fake/synthetic data. Very fast. Tests individual functions in isolation.

#### e2e tests (`tests/e2e/`)

**`tests/e2e/spec_sections_stability_test.py`**:
- For each installed Godot version (discovered via `/opt/godot/` or `godotctl list`):
  - Dump `extension_api.json` from the binary
  - Assert all 10 top-level sections are present: `header`, `builtin_class_sizes`, `builtin_class_member_offsets`, `global_constants`, `global_enums`, `utility_functions`, `builtin_classes`, `classes`, `singletons`, `native_structures`
- Skips if binary not found

**`tests/e2e/spec_enum_names_stability_test.py`**:
- For each installed Godot version:
  - Dump `extension_api.json` from the binary
  - Extract enum values using the existing `_extract_*` functions
  - Assert the 5 enum class names are stable: `GodotTypeNameEnum`, `UtilityFunctionCategoryEnum`, `BuiltinClassOperatorNameEnum`, `GodotArgumentMetaEnum`, `ClassApiTypeEnum`
  - Assert enum *member names* are a superset of the previous version's (values may grow but not shrink)
- Skips if binary not found

**`tests/e2e/add_version_cli_test.py`** (generalize existing `generate_all_cli_test.py`):
- For each installed Godot version:
  - Dump `extension_api.json`
  - Run `gli specifications add-version --version v_test --api <json> --base-version v4_4_0` (into a temp directory; use `--first-version` for the first)
  - Verify the generated package imports correctly
  - Verify `Specification` class can parse the JSON
- Skips if binary not found

#### integration tests (`tests/integration/`)

**`tests/integration/specs_roundtrip_test.py`** (generalize existing):
- Parametrize over all version packages found in `specifications/`
- For each version: load the pre-downloaded `extension_api.json` from `tests/data/extension_api/`, parse with the version's `Specification` model, dump it back, assert equality
- No Godot binary needed — uses the downloaded reference files

**`tests/integration/schema_diff_test.py`**:
- Load two pre-downloaded `extension_api.json` files (e.g. 4.4.0 and 4.5.0)
- Run the schema diff between them
- Assert the diff report is correct (known differences between versions)
- Verify the report is valid YAML (and valid JSON with `--format json`)
- **Note**: These tests cannot be auto-generated. When `add-version` runs, it outputs test guidance: if we can detect what to test (e.g., a specific new field), it outputs a specific suggestion; otherwise a generic message tells the dev to review the diff and write tests. The dev writes these tests manually as part of the version-addition workflow.

**`tests/integration/enum_import_test.py`**:
- Load a pre-downloaded `extension_api.json`
- Extract enum values
- Compare against another version's enum values
- Assert the import logic correctly identifies identical vs different enums

#### unit tests (`tests/unit/`)

**`tests/unit/sync_enums_test.py`** (extend existing):
- Test `sync-enums --version v_test` with fake data (already partially done)
- Test the generalized `_block_pattern` with version-specific markers
- Test deprecation warning for `sync-enums-v4-7-0`

**`tests/unit/schema_diff_test.py`**:
- Test the JSON key walker with synthetic data
- Test the pydantic model field walker
- Test the diff report generation with known inputs/outputs
- Test `requires_human_intervention` flag logic

**`tests/unit/add_version_test.py`**:
- Test the spec.py template generation
- Test the enum import logic (identical → import, different → generate fresh)
- Test `--base-version` mandatory enforcement (errors if missing without `--first-version`)
- Test `--first-version` flag (generates fresh enums, no base comparison)
- Test `godot-versions.txt` reading and auto-suggestion of base version

### Step 9: tscn format schema (initial)

Create `tscn/format_schema.py` to model .tscn format differences per version:

**Key differences identified (from Godot docs + research):**
- `load_steps` attribute in `[gd_scene]`: present in all 4.x, deprecated in 4.6+ (still written but ignored)
- `uid` attribute in `[ext_resource]`: optional, present in 4.4+ (with `.gd.uid` sidecars). May be absent in older scenes.
- `uid` attribute in `[gd_scene]`: present since Godot 4.0
- `format=3`: all Godot 4.x versions

**Approach:**
- A `TscnFormatSchema` pydantic model that describes which attributes are expected/optional per version
- A CLI: `gli tscn detect-format --version vX_Y_Z` that reports the format features for a version
- The existing `SceneHeader`, `ExtResourceEntry`, etc. already use generic `attributes` dict — they handle unknown attributes gracefully
- The `id`/`uid` difference is flagged for human intervention: the CLI reports it but doesn't auto-migrate

**Cross-version scene testing:**
- `gli tscn check --scene <file> --godot <version>` — runs a specific Godot version's `--check-only` on a scene
- This enables: take a scene from 4.4.1, check it against 4.7's Godot binary (and vice versa)
- If the check fails (e.g., missing `uid`), report the issue for human intervention

### Step 10 (deferred): tscn grammar extraction

Automatic extraction of a formal grammar/spec for .tscn files per version. This is a follow-up after the multi-version spec system is working. Potential approaches:
- Parse sample scenes from each version to infer the format schema
- Use the Godot source code (`resource_format_text.cpp`) as reference — **this file differs between versions**, so we can clone the godot engine repo and navigate between branches/tags to compare
- Generate a validation schema that can check .tscn files against a version's format

## TODO (open points for later)

- **Human workflow script**: A full script (e.g. `scripts/add_version.sh` or `gli specifications add-version-interactive`) that guides a human step-by-step: check binary → dump API → run diff → review report → generate → test. Embeds the process in code so the human doesn't need to read documentation.
- **Enum dereference command**: `gli specifications dereference-enums --version vX_Y_Z` that inlines imported enums into a version's spec.py, decoupling it from the base version.
- **Migrate v4_7_0 to shared**: Refactor `v4_7_0/spec.py` to import from `shared/spec.py`. Done manually, incrementally, after the new system is proven with other versions.
- **tscn grammar extraction**: Step 10 above.
- **tscn CLI --version flag**: Allow tscn commands to accept a `--version` flag to use a specific spec provider.

## Key Design Decisions

1. **Shared models use `str` fallback for type aliases**: `GodotTypeName = Union[str, str]` in shared, overridden to `Union[GodotTypeNameEnum, str]` per version. This avoids circular dependencies.
2. **Schema diff is pure code**: No LLMs. Recursive JSON key walking + pydantic model field comparison. Auto-generation only for `Optional` field additions.
3. **Schema diff report is a YAML file by default** (JSON with `--format json`): Machine-parseable, designed for future helper functions. Written to disk so an LLM can read just the report (small) instead of the full extension_api.json (huge). Includes a `test_guidance` section with specific suggestions where detectable.
4. **Human intervention for structural changes**: New top-level sections, type changes, or required field removals stop the `add-version` CLI with a clear report.
5. **Enum import only if identical**: `--base-version` is mandatory (unless `--first-version`). Each of the 5 enums is compared. If identical, import from base; if different, generate fresh. Minimizes duplication while staying correct.
6. **Existing generators are reused as-is**: `generate-builtin-classes`, `generate-classes`, `generate-signals` already work for any version. Only `sync-enums` needs generalizing.
7. **No leading-underscore class names**: Use plain names (e.g. `FrozenModel` not `FrozenModel`).
8. **extension_api.json never loaded into LLM context**: All interaction via code. Files stored in gitignored `tests/data/extension_api/`. Downloaded via `godotctl download-apis` (part of `setup.sh`).
9. **Tests classify by system interaction**: e2e (Godot binary), integration (pre-downloaded JSON + our models), unit (fake data, fast).
10. **v4_7_0 migration deferred**: Do it manually later, after the new system is proven with 4.4.0-4.6.2.
11. **`godot-versions.txt` tracks supported versions**: Linear ordering, last = latest. Read by `add-version` (for base-version auto-suggestion), tests (for parametrization), and `godotctl download-apis`.
12. **semble MCP for Godot source research**: When investigating `resource_format_text.cpp` or other engine source files across versions, use the semble MCP with the Godot repo URL + tag/commit hash to search without cloning.

## Out of Scope (for this plan)

- Migrating v4_7_0 to the shared system (deferred — manual, incremental)
- tscn grammar extraction (Step 10, deferred)
- Auto-migration of scenes between versions (id/uid conversion)
- Supporting Godot 3.x (format=2, fundamentally different API)
- The human workflow script (TODO — build after the core system works)
