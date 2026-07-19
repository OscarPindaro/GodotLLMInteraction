# New Tools Proposals for gli MCP

This file records proposed new gli tools that would have been useful during
the hero_rpg implementation.

## 4. `register_autoload` tool

**Problem:** Adding autoloads requires editing `project.godot` manually,
which is outside the scope of gli's scene-editing tools.

**Proposal:** A tool that adds/removes autoload entries in `project.godot`,
validating that the script path exists.

## 5. `add_input_action` tool

**Problem:** Adding input actions (like move_left, move_right) requires
editing the `[input]` section of `project.godot` with verbose
`InputEventKey` serialized objects.

**Proposal:** A tool that adds an input action with a given name and
key bindings (e.g., "move_left" with keys A and Left arrow).

---

## Additional proposals based on implementation experience

## 6. `run_scene` tool

**Problem:** `validate` runs with `--check-only --quit`, which catches parse
errors but NOT runtime errors. During implementation I hit several runtime
errors that only surfaced when the scene's `_ready()` executed:
- `patrol_path` assignment type mismatch (`Array` vs `Array[Vector2i]`)
- `pathfinder` property assignment rejected (`AStar2D` is `RefCounted`, not `Resource`)
- `class_name` resolution failures (needed `--import` to build the class cache)
- Invalid function calls on incorrectly-typed variables

**Proposal:** A `run_scene` tool that launches Godot headless with the scene
as main, runs for a configurable timeout (default 2-3 seconds), captures
stdout/stderr, then quits. This would catch all `_ready()` and early
`_process()` errors that `validate` misses. Essentially:
```
godot --headless --path <project> <scene_path> --quit-after <frames>
```
The output should include any `SCRIPT ERROR` or `ERROR` lines, plus any
`print()` output (useful as a lightweight test harness).

## 7. `check_script_scene_consistency` tool

**Problem:** The user's suggestion. I had multiple issues where a script's
`@export` or `@onready` references didn't match the scene:
- `@export var gamepiece: Path2D` — scene needed a NodePath property pointing to a Path2D node, but I had to manually ensure the node existed
- `@onready var _knight: Path2D = $Knight` — would fail at runtime if the node was missing or renamed
- `@export var pathfinder: RefCounted` — `RefCounted` is not a valid `@export` type, but I only discovered this at runtime

**Proposal:** A tool that takes a `.gd` script path and a `.tscn` scene path
and checks:
1. **Export type validity:** every `@export var X: T` — is `T` a valid export type (built-in, Resource, Node, enum)? Report invalid ones.
2. **Node export wiring:** every `@export var X: NodeType` — does the scene have a NodePath property `X` pointing to a node of type `NodeType`? Report missing/mismatched.
3. **@onready node paths:** every `@onready var X: T = $Path` — does `Path` exist in the scene tree? Is the node at that path of type `T`?
4. **Signal connections:** every `[connection]` in the scene — does the target method exist in the receiver's script?

Output a list of issues with file:line references. This would have caught
3-4 bugs per scene during this implementation.

## 8. `auto_wire_exports` tool

**Problem:** The user's suggestion. When a script has `@export var knight:
Path2D` and the scene has a `Path2D` node named "Knight", the wiring must
be done manually by writing `knight = NodePath("../Knight")` into the scene
file. This is tedious and error-prone.

**Proposal:** A tool that:
1. Reads a `.gd` script, finds all `@export var X: NodeType` where `NodeType` is a Node subclass.
2. Scans the scene for nodes of type `NodeType` with a name matching `X` (case-insensitive).
3. Auto-generates the `X = NodePath("...")` property line in the scene file.
4. If multiple candidates exist, reports them and asks the user to pick (or accepts a hint parameter).

Optionally, the reverse: `auto_generate_node` — given an `@export var X:
NodeType` that has no matching node in the scene, create the node with
name `X` and type `NodeType` at a sensible default position.

## 9. `create_tileset_from_atlas` tool

**Problem:** I avoided using real `TileMapLayer` nodes entirely because
setting up a `TileSet` from an atlas image is extremely verbose in `.tscn`
text — you need to define the atlas, tile size, spacing, and each tile's
coordinates. Instead I generated dozens of individual `Sprite2D` nodes with
`AtlasTexture` sub-resources, which is inefficient and clutters the scene tree.

**Proposal:** A tool that takes:
- An atlas texture path (e.g., `res://asset/tilemap_packed.png`)
- Tile size (e.g., 16x16)
- Optional: spacing, margins, tile names

And creates a `TileSet` resource file (`.tres`) with the atlas properly
configured. Then a companion `paint_tiles` tool that takes a `TileMapLayer`
node path and an `Array[Vector2i]` of cells + atlas coords and paints them.

This would replace the `floor_generator.gd` hack with proper tilemap usage.

## 10. `run_gdscript_function` tool

**Problem:** Several times I needed to verify a computation — e.g., "what
pixel region does `TileAtlas.region_for(Vector2i(1, 8))` return?" or "does
`Gameboard.cell_to_index(Vector2i(5, 3))` return the right value?" I had
to reason about these manually or wait until a scene ran to see `print()` output.

**Proposal:** A tool that takes a `.gd` script path, a function name, and
arguments (as Godot literals), executes the function headless, and returns
the result. Like a REPL for GDScript. Example:
```
run_gdscript_function(
    script="res://examples/hero_rpg/scripts/grid/tile_atlas.gd",
    function="region_for",
    args=["Vector2i(1, 8)"]
)
→ "Rect2(16, 128, 16, 16)"
```
This would also be useful as a lightweight test harness for unit-testing
individual functions without creating full scenes.

## 11. `rebuild_class_cache` tool

**Problem:** When I created new `class_name` scripts, the headless Godot
validator couldn't resolve them until I ran `--import` to rebuild the class
cache. This caused cascading "Could not find type X in the current scope"
errors that were misleading — the scripts were correct, just not cached.

**Proposal:** A tool that runs `godot --headless --import --quit` to rebuild
the global class cache, then reports which `class_name` registrations
succeeded or failed. Ideally this would be called automatically before
`validate` if any `.gd` files have changed since the last cache build.

## 12. `get_scene_signals` tool

**Problem:** To connect signals in scenes, I needed to know the exact signal
names and parameter types of nodes. I had to read the script files manually
to find `signal spotted_player` vs `signal spotted_player(target: Node)`.
The `mcp0_get_godot_spec` tool covers built-in Godot signals but not custom
script signals.

**Proposal:** A tool that takes a `.gd` script path and returns all declared
signals with their parameter names and types. This would make
`mcp0_connect_signal` calls much easier to construct correctly.

## 13. `set_main_scene` tool

**Problem:** Setting the main scene requires editing `project.godot` to add
`run/main_scene="res://path/to/scene.tscn"` under the `[application]` section.
When no main scene is set, `godot --headless --quit` fails with "Can't run
project: no main scene defined" — and pressing F5 in the editor shows a dialog
asking the user to pick one. During development I had to manually edit
`project.godot` or tell the user to set it via the editor UI.

**Proposal:** A tool that takes a scene path and sets it as the main scene in
`project.godot`. It should:
1. Validate that the `.tscn` file exists at the given `res://` path.
2. Add or update the `run/main_scene` key under `[application]`.
3. Optionally also set `run/main_scene` for a specific editor configuration
   (e.g. when testing different demo scenes as the entry point).

Bonus: a `get_main_scene` companion that reads the current main scene path,
useful for checking whether one is set before running.

## 14. `set_particles2d` tool

**Problem:** Configuring `GPUParticles2D` or `CPUParticles2D` nodes in a
`.tscn` file by hand is extremely verbose. The GPU variant needs a
`ParticleProcessMaterial` sub_resource with dozens of properties (`direction`,
`spread`, `initial_velocity_min/max`, `gravity`, `scale_min/max`, `color`,
`color_ramp` which is a `GradientTexture1D` wrapping a `Gradient`, etc.). The
CPU variant has many of the same properties directly on the node but still
verbose. Setting this up via raw text or multiple MCP calls is tedious and
error-prone — I hit a type error immediately (`color_ramp` expects
`GradientTexture1D`, not `Gradient`).

**Proposal:** A tool that takes a node path and a high-level particle
description, and creates/configures the particles node + its material + any
sub-resources in one call. Works for both `GPUParticles2D` and `CPUParticles2D`.

```
set_particles2d(
    scene="res://examples/hero_rpg/scenes/floor_item.tscn",
    node="FloorItem/Particles",
    type="gpu",  # or "cpu"
    texture="res://asset/particle_glow.png",
    amount=6,
    lifetime=1.5,
    direction=Vector2(0, -1),
    spread=15.0,
    initial_velocity_min=15.0,
    initial_velocity_max=30.0,
    gravity=Vector2.ZERO,
    scale_min=0.3,
    scale_max=0.5,
    color=Color(1, 0.8, 0.3, 0.8),
    color_ramp=[(0.0, Color(1,1,1,1)), (1.0, Color(1,1,1,0))],
    emitting=true
)
```

**Tool behavior:**
1. If the particles node doesn't exist, create it (`GPUParticles2D` or
   `CPUParticles2D` based on `type`).
2. For GPU: create a `ParticleProcessMaterial` sub_resource and set all
   properties. For CPU: set properties directly on the node.
3. If `color_ramp` is provided, create a `Gradient` + `GradientTexture1D`
   sub_resource chain and assign it to `color_ramp` (GPU) or set the
   `color_ramp` Gradient directly (CPU, which accepts a raw `Gradient`).
4. If `scale_curve`, `alpha_curve`, etc. are provided, create the appropriate
   `CurveTexture` / `CurveXYZTexture` subresources.
5. Set the `texture` property (load the texture as ext_resource if not already
   present).
6. Validate the resulting scene.

This eliminates the multi-step dance of creating sub-resources, wrapping
gradients in textures, and managing all the property names.

### Particle presets and pre-generated textures

**Problem:** Every time particles are needed, the full configuration must be
specified from scratch. Many particle effects share common patterns (sparkles,
smoke, fire, pickup glow, dust) that differ only in color and a few
parameters. Additionally, the particle textures (glow circles, soft blobs,
star shapes) are reusable assets that should be generated once and referenced
by path.

**Proposal:** Support a **preset** system:

1. **Pre-generated textures:** A set of reusable particle sprite textures
   generated via PIL and stored in `asset/particles/`. The user provides these
   once, then the tool can reference them by name:
   ```
   texture="preset:glow"       # → res://asset/particles/glow.png
   texture="preset:soft_blob"  # → res://asset/particles/soft_blob.png
   texture="preset:star"       # → res://asset/particles/star.png
   texture="preset:smoke"      # → res://asset/particles/smoke.png
   ```
   The tool resolves the preset name to the actual `res://` path. The user can
   add new presets by generating textures and registering them (e.g. in a
   `particle_presets.cfg` file or a known directory convention).

2. **Behavior presets:** Named parameter bundles that fill in sensible defaults
   for common effect types:
   ```
   set_particles2d(
       scene=...,
       node="FloorItem/Particles",
       preset="pickup_sparkle",  # fills in amount, lifetime, direction, etc.
       color=Color(1, 0.8, 0.3, 0.8),  # override specific values
   )
   ```
   Built-in presets could include:
   - `pickup_sparkle`: few particles, upward, slow rise, fade out, glow texture
   - `dust_puff`: burst outward, gravity, short lifetime, soft_blob texture
   - `fire_flicker`: continuous emit, upward, orange-red, small scale variation
   - `smoke_trail`: slow upward, expanding scale, dark color, long lifetime
   - `magic_aura`: orbit-like, pulsing scale, bright color, long lifetime

   The preset provides defaults; explicit parameters override individual
   fields. This way most calls become one-liners:
   ```
   set_particles2d(scene=..., node=..., preset="pickup_sparkle", color=Color.CYAN)
   ```

3. **Preset registration:** The user can register custom presets (texture +
   parameter bundle) so project-specific effects are reusable across scenes.
   A `register_particle_preset` tool or a config file could store:
   ```
   [preset:my_effect]
   texture = "res://asset/particles/custom.png"
   amount = 12
   lifetime = 2.0
   direction = Vector2(0, -1)
   spread = 30.0
   ...
   ```

---

## KB Improvement Proposals

The following proposals improve the gli knowledge base, ordered by priority.
They build on each other: the folder-based storage layout (§15) is the
foundation that enables semble code search (§16), chunk-based retrieval (§17),
and eventually multi-KB support (§18).

### 15. `kb_persist_github` — cache GitHub content locally

**Problem:** GitHub URLs in KB entries are fetched fresh from the network on
**every search** that matches the entry (`build_answer` → `_fetch_github_url`).
There is no caching. If the entry matches 10 searches, that's 10 HTTP requests
to `raw.githubusercontent.com` or the GitHub Contents API. If the link goes
dead, the answer is lost permanently.

**Proposal:** At registration time, download GitHub content to the local KB
folder and store the local path alongside the original URL. The `KbEntry` JSON
interface stays unchanged — the caller still passes `github_urls` as before.
The storage layer resolves them to local files internally.

**New on-disk KB structure** (per entry, inside the KB folder):

```
<kb_folder>/
  entries/
    <entry_id>.json          # metadata + resolved paths
  files/
    <entry_id>/
      questions.yaml         # questions for this entry
      answer.txt             # inline answer_text (if any)
      github/
        <owner>__<repo>__<branch>/
          blob/
            <path...>        # mirrors the original repo path
          tree/
            <path...>/       # mirrors the original folder structure
              file1.gd
              file2.gd
      local_files/           # copies of registered file_paths
      local_folders/         # copies of registered folder_paths
  index.npz                  # question embeddings (existing)
  semble_index/              # semble code index (see §16)
```

**Entry JSON changes** (additive, backward-compatible):

```json
{
  "id": "...",
  "questions": ["..."],
  "answer_text": "inline text",
  "file_paths": ["src/foo.gd"],
  "folder_paths": ["examples/combat/"],
  "github_urls": ["https://github.com/owner/repo/blob/main/gun.gd"],
  "resolved_github_urls": [
    {
      "original_url": "https://github.com/owner/repo/blob/main/gun.gd",
      "type": "blob",
      "local_path": "files/<entry_id>/github/owner__repo__main/blob/gun.gd",
      "commit_sha": "a1b2c3d4e5f6...",
      "fetched_at": "2026-07-13T23:30:00"
    }
  ],
  "description": "...",
  "tags": ["..."],
  "created_at": "..."
}
```

**Questions storage — `questions.yaml`:**

Questions are stored as a YAML file for easy human inspection and editing:

```yaml
questions:
  - "How do I make an auto-aim turret with Area2D?"
  - "How to use look_at for 2D targeting?"
  - |
    A multi-line question can be written as a YAML block scalar
    so newlines are preserved without escaping.
```

YAML handles multi-line strings cleanly (block scalars), is easy to open and
inspect, and avoids the escaping mess of one-line-per-question TXT files.

**Tool behavior:**

1. At `kb_register` time, for each `github_url`:
   - Detect blob (`/blob/`) vs tree (`/tree/`) URL.
   - Resolve the branch ref to a commit SHA via the GitHub API
     (`GET /repos/{owner}/{repo}/commits/{branch}`). This pins the exact
     version we downloaded.
   - Fetch the content (blob: raw file; tree: all text files in the folder
     via Contents API, preserving the original folder structure).
   - Write to `files/<entry_id>/github/<owner>__<repo>__<branch>/blob|tree/<path>`.
   - Store the local path, `commit_sha`, and `fetched_at` in
     `resolved_github_urls` in the entry JSON.
2. At `kb_search` time, `build_answer`:
   - For entries with `resolved_github_urls`, read from the **local cached
     path** instead of hitting the network.
   - If the local file is missing (deleted manually), fall back to fetching
     from the network and log a warning.
   - The returned answer format is unchanged — the LLM sees `<url>\n<content>`
     just like now.
3. For `file_paths` and `folder_paths`: if the original path no longer exists
   on disk, return the KB-cached copy path. This makes entries resilient to
   file moves/deletions.
4. A `kb_refresh_github` tool (or `--refresh` flag on `kb_register`) re-downloads
   content for entries whose GitHub source may have updated:
   - Resolve the branch ref to the current commit SHA.
   - Compare against the stored `commit_sha`. If unchanged, skip (content is
     identical, no re-download needed).
   - If changed, re-download the content, update `commit_sha` and `fetched_at`,
     and flag the semble index for re-indexing (see §16).
   - Optionally keep the old version in a `versions/` subfolder with the old
     commit SHA as a suffix, so diffs are inspectable. This is off by default.

**Why this matters for semble (§16):** Semble indexes local files. Without
local copies of GitHub content, semble cannot index those entries at all.
This step is the prerequisite.

### 16. `kb_code_search` — semble-powered code-aware search

**Problem:** The current KB search embeds only the **questions** and returns
whole entries. It has no awareness of the actual code content in the answer
files. A query like `"Area2D get_overlapping_bodies"` would match poorly
because it's code vocabulary, not natural-language question phrasing. Semble
solves exactly this with hybrid semantic + BM25 retrieval over code chunks.

**Proposal:** A `kb_code_search` tool that uses semble to index the KB's local
file storage (from §15) and returns code-aware chunk results.

**How it works:**

1. **Indexing:** Point `SembleIndex.from_path` at the KB's `files/` directory.
   Semble handles tree-sitter chunking, dual indexing (semantic + BM25), and
   disk caching. The semble index lives at `<kb_folder>/semble_index/`.
2. **Mapping:** A sidecar `chunk_to_entry.json` maps each indexed file path to
   its parent `entry_id`, so chunk results can be traced back to KB entries.
3. **Search:** Call `semble.search(query, top_k)` → get ranked chunks. Group
   chunks by `entry_id` (same dedup pattern as current `search_kb`). Return
   entry metadata + the matched chunks (not whole files).
4. **Cache invalidation:** Reuse semble's built-in mtime-based invalidation.
   When new entries are registered, their files are added to the `files/`
   directory; semble detects the changes on next search and re-indexes.

**Return format:**

```json
{
  "ok": true,
  "results": [
    {
      "entry": { "id": "...", "questions": [...], "description": "..." },
      "score": 0.85,
      "matched_chunks": [
        {
          "file_path": "files/<id>/github/.../gun.gd",
          "start_line": 15,
          "end_line": 32,
          "content": "func _process(delta):\n    var bodies = get_overlapping_bodies()\n    ..."
        }
      ]
    }
  ]
}
```

**Coexistence with existing `kb_search`:** Both tools are available. The LLM
chooses:
- `kb_search` — question-semantic matching, returns full answers (current
  behavior, good for "how do I..." queries).
- `kb_code_search` — code-aware hybrid search, returns chunks (good for
  "where is `get_overlapping_bodies` used" or symbol-based queries).

**Scaling to large KBs — ANN backends (open-ended):**

Semble currently uses `vicinity`'s `BASIC` backend (brute-force cosine
similarity, O(N×D) per query). This is fine for typical repos (~500-5000
chunks, ~1.5ms per query). As the KB grows — many entries, many GitHub
folders cached locally — the chunk count could reach 50k-100k+.

`vicinity` ([MinishLab/vicinity](https://github.com/MinishLab/vicinity)) is
MinishLab's dedicated ANN library with a unified interface across multiple
backends:

| Backend | Algorithm | Insertion | Deletion |
|---------|-----------|-----------|----------|
| BASIC   | Flat exact | Yes | Yes |
| HNSW    | Hierarchical Navigable Small World (`hnswlib`) | Yes | No (rebuild) |
| USEARCH | Optimized HNSW (`usearch`) | Yes | No (rebuild) |
| FAISS   | HNSW / IVF / etc. (`faiss`) | Yes | No (rebuild) |
| ANNOY   | Random projection trees (`annoy`) | No (read-only) | No |
| PYNNDESCENT | Approximate kNN graph (`pynndescent`) | No | No |
| VOYAGER | Spotify's fast ANN (`voyager`) | Yes | No (rebuild) |

Swapping is a backend change, not an architecture change — the `query()`
interface is identical across all backends. Semble's `SelectableBasicBackend`
subclasses `CosineBasicBackend`, so a KB-specific subclass could use HNSW or
USEARCH instead.

**Tradeoff note:** ANN backends don't support dynamic deletion (must rebuild
the whole index). Since `kb_remove` is a rare operation and the KB index is
already rebuilt on removal in the current implementation, this is acceptable.
Insertion (the common case, `kb_register`) is supported by HNSW, USEARCH, and
FAISS.

**When to revisit:** No immediate need. Profile at 10k+ chunks. If query
latency exceeds ~50ms, swap to HNSW or USEARCH. The `vicinity` evaluation
tooling (`evaluate()` method) can benchmark recall vs. QPS for each backend
on the actual KB data before committing to a choice.

### 17. `kb_chunk_search` — token-efficient chunked retrieval

**Problem:** Even with semble (§16), the current `build_answer` returns the
**entire** file content for every matching entry. For large files this wastes
tokens — the LLM may only need the specific function or class that matched.

**Proposal:** A `kb_chunk_search` tool that returns only the matched chunks
(like §16) plus a companion `kb_fetch_file` tool to retrieve the full parent
file on demand.

**Tool behavior:**

1. `kb_chunk_search(query, top_k)`:
   - Same semble search as §16.
   - Returns **only the matched chunks** with line ranges, not full files.
   - Each chunk includes a `parent_file` path and `entry_id` for follow-up.
2. `kb_fetch_file(entry_id, file_path)`:
   - Returns the full content of a specific file from an entry's local storage.
   - Used when the LLM needs more context around a chunk.

This two-step pattern (search chunks → fetch full file if needed) mirrors
semble's own `search` + `read_file` workflow and dramatically reduces token
usage for large codebases.

### 18. Multi-KB support (tentative, future)

**Problem:** Currently one project → one KB. Some projects may benefit from
multiple named KBs (e.g., one for Godot patterns, one for project-specific
scripts, one for external reference code).

**Proposal:** Allow naming KBs at registration and search time:

```
kb_register --kb godot_patterns --question "..." --file ...
kb_search --kb godot_patterns "how to add a node"
```

This is tentative — no immediate need. The folder-based storage from §15
makes this straightforward (just add a `kb_name` subfolder), but it's not
required for the semble integration or chunk-based retrieval.

### 19. Folder-based KB loading (future)

**Problem:** The current KB is stored in a platform-specific data directory
(`~/.local/share/gli/<slug>/kb/`), making it hard to inspect, version-control,
or share between machines.

**Proposal:** Support loading a KB from any folder that has the expected
structure (from §15):

```
my_kb/
  entries/
    *.json
  files/
    <entry_id>/
      ...
  index.npz
  semble_index/
```

Point `kb_search` / `kb_register` at any folder with `--kb-location <path>`
(or `GLI_KB_LOCATION`), and if the structure matches, it loads directly. This
enables:
- Version-controllable KBs committed alongside the project.
- Portable KBs shared between team members.
- Project-local KBs in `project_root/.gli/kb/`.

This is a natural extension of the §15 storage layout — the on-disk format is
already self-contained, it just needs a loader that accepts arbitrary paths.

### 20. `kb_feedback` — record useful results for dataset building

**Problem:** The KB has no way to know which search results were actually
useful to the LLM. Over time, this creates a dataset of (query, useful answer)
pairs that can be used to improve search quality, prune bad entries, reword
questions, and (eventually) fine-tune embeddings or train a reranker.

**Key design decision — snapshot, don't reference:**

Feedback entries store a **snapshot** of the entry's content at feedback time,
not just the `entry_id`. If the entry is later removed or modified, the
feedback data is still complete and usable as a training dataset. The feedback
log is a self-contained dataset, not a reference table that breaks when
entries are deleted.

**Tool signature:**

```
kb_feedback(
    query: str,                          # the original search query
    useful: list[str] = [],              # entry_ids that were helpful
    not_useful: list[str] = [],          # entry_ids that were noise
    chunk_ids: list[str] = [],           # (with §16/§17) specific chunk IDs
    task_context: str = "",              # optional: what the LLM was trying to do
    search_tool: str = "kb_search",      # which tool was used
) -> str
```

The LLM reports only what it actually used. Absence from both lists = "didn't
look at it" (neutral, not negative).

**Storage — feedback log in the KB folder:**

```
<kb_folder>/
  feedback/
    feedback.jsonl          # append-only, one JSON object per feedback event
    snapshots/
      <entry_id>.json       # snapshot of entry at feedback time (deduplicated)
```

Each line in `feedback.jsonl`:

```json
{
  "query": "how to make area2d turret",
  "search_tool": "kb_search",
  "model": "minishlab/potion-code-16M",
  "model_version": "1.0",
  "useful": ["a1b2c3...", "e4f5g6..."],
  "not_useful": ["d7e8f9..."],
  "chunk_ids": ["a1b2c3...:gun.gd:15-32"],
  "task_context": "building a tower defense enemy targeting system",
  "timestamp": "2026-07-13T23:34:00"
}
```

**Snapshots** are stored separately in `snapshots/<entry_id>.json` and are
deduplicated — if the entry hasn't changed since the last snapshot, we reuse
the existing file. The snapshot contains the full `KbEntry` JSON plus a
content hash, so we can detect if the entry was modified between feedback
events:

```json
{
  "entry_id": "a1b2c3...",
  "snapshot_at": "2026-07-13T23:34:00",
  "content_hash": "sha256:...",
  "entry": {
    "questions": ["..."],
    "answer_text": "...",
    "file_paths": ["..."],
    "github_urls": ["..."],
    "resolved_github_urls": [...],
    "description": "...",
    "tags": ["..."]
  }
}
```

If the entry is later removed or modified, the snapshot preserves the exact
version the LLM found useful. This makes the feedback log a permanent,
self-contained training dataset.

**Chunk IDs** (with §16/§17 semble integration): chunks are identified by
`(entry_id, file_path, start_line, end_line)`, encoded as a string:
`"entry_id:file_path:start-end"`. The snapshot of the parent entry is still
stored, so the full file context is recoverable even if the entry is deleted.

**Implicit feedback (zero extra calls):**

- **`kb_fetch_file` after `kb_chunk_search`** — if the LLM fetches the full
  parent file of a chunk, that chunk was useful. Log it automatically.
- **`kb_search` followed by no feedback** — ambiguous, don't infer anything.

**What the dataset enables:**

1. **Search quality metrics** — precision@k, MRR, recall. Of the top_k
   results, how many were marked useful? How high was the first useful result?
2. **Question improvement** — if query Q consistently matches entry X but X is
   marked `not_useful`, X's questions are misleading. Flag for revision. If
   query Q never matches entry X but the LLM reports X would have been useful,
   X needs additional question phrasings.
3. **Entry pruning** — entries never marked useful across many searches →
   candidates for removal or question rewording.
4. **Embedding fine-tuning (future)** — (query, useful_entry) pairs are
   training data for contrastive learning. (query, not_useful_entry) pairs are
   hard negatives. Could fine-tune `potion-code-16M` or train a lightweight
   reranker on top of the KB's specific domain.
5. **Query clustering** — group similar queries to identify common information
   needs that the KB serves well or poorly.

**Companion tool — `kb_feedback_stats`:**

```
kb_feedback_stats(
    project_path: str = None,
    metric: str = "precision_at_k",   # precision_at_k | mrr | entry_usage | query_clusters
    days: int = 30,                   # lookback window
    model: str = None,                # filter by model (e.g. "minishlab/potion-code-16M")
) -> str
```

Returns aggregate stats from the feedback log. Useful for the LLM to
self-assess or for the user to audit KB quality.

**Model tracking:** each feedback event records the `model` and
`model_version` used for the search that produced the results. This is
critical for metrics — if the embedding model is changed (e.g., swapping
`potion-code-16M` for a larger model), the ranking changes and old metrics
aren't comparable. `kb_feedback_stats` accepts a `model` filter so you can:
- Compare precision@k between model A and model B on the same queries.
- Track metric regression when upgrading models.
- Exclude feedback from a deprecated model.

When no `model` filter is passed, stats are computed across all models (with
a per-model breakdown in the output).

**Design considerations:**

- **Append-only**: `feedback.jsonl` is never rewritten. Safe for concurrent
  writes. No corruption risk.
- **Privacy**: `task_context` is optional. Default to empty, let the LLM
  decide.
- **Backward compatible**: feedback is purely additive. No existing tool
  changes. The KB works fine without it.
- **No network**: feedback is local-only. No telemetry sent anywhere.
- **Snapshot dedup**: if the entry's `content_hash` matches an existing
  snapshot, skip writing a new one. Snapshots are cheap (one JSON file per
  unique entry version).

**CLI export — `kb export-feedback` (not an MCP tool):**

The feedback log accumulates over time with full snapshots, which is great for
durability but verbose for downstream use. A slim CLI command exports a compact
dataset for those who want it:

```
uv run python -m godotllminteraction.cli.kb export-feedback \
    --project /path/to/project \
    --output feedback_dataset.jsonl \
    [--format jsonl|csv] \
    [--since 2026-01-01] \
    [--include-negative] \
    [--resolve-content] \
    [--compact]
```

**`--compact` (default):** one line per feedback event with only the fields
needed for training/analysis — no full entry snapshots, just `entry_id` +
`content_hash` for traceability back to the KB:

```json
{"query": "how to make area2d turret", "useful": ["a1b2c3..."], "not_useful": ["d7e8f9..."], "content_hashes": {"a1b2c3...": "sha256:..."}, "timestamp": "2026-07-13T23:34:00"}
```

**`--resolve-content`:** inline the actual answer content from snapshots into
each line, producing a fully self-contained training file (no KB needed to
use it):

```json
{"query": "how to make area2d turret", "useful": [{"entry_id": "a1b2c3...", "questions": [...], "answer_text": "...", "content_hash": "sha256:..."}], "timestamp": "2026-07-13T23:34:00"}
```

**`--include-negative`:** include `not_useful` entries in the export (off by
default, since most use cases want positive pairs only).

This command is CLI-only — it's a batch operation for dataset building, not
something the LLM calls during a coding session. The MCP tools (`kb_feedback`,
`kb_feedback_stats`) handle the real-time loop; the CLI handles the export.

---

## Cross-platform validation proposals

### 21. `lint` tool — lightweight no-Godot scene validation

> **Note:** This is a more complex proposal than the others above. It does not
> add a single narrow helper — it promotes an existing internal subsystem (the
> spec-backed `validate_scene` in `tscn/validation.py`) into a first-class CLI
> command and MCP tool, with target resolution, multi-file aggregation, and
> reporting. The validation engine itself already exists and is battle-tested
> (it powers strict-mode checks on every `add_node` / `update_properties` /
> `connect_signal` call); the work is wiring it into a standalone, flexible
> entry point that works without a Godot binary on any platform.

**Problem:** The current `validate` command (and the `mcp0_validate` MCP tool)
shells out to the Godot binary via `godot --headless --check-only --quit`. This
means:

- **Godot must be installed** on the machine running gli. On CI, in containers,
  or on an OS where Godot isn't easily available, `validate` is unusable.
- **Cross-platform friction:** `find_godot()` searches PATH, `GODOT_BINARY`,
  and per-OS install locations, but any mismatch (Flatpak, Snap, non-standard
  install path) requires manual configuration. A lightweight path that needs
  zero configuration is valuable.
- **No partial feedback:** Godot's `--check-only` returns a single pass/fail
  exit code plus opaque stderr. It does not enumerate *which* property on
  *which* node is wrong, or distinguish errors from warnings — the LLM has to
  parse free-text output to act on the result.

Meanwhile, gli already ships a pure-Python, spec-backed validator —
`validate_scene()` in `tscn/validation.py` — that checks:

- **Structure:** exactly one root node, no duplicate sibling names, parent
  references resolve and appear before children.
- **Classes:** every node/sub_resource `type` is a known engine class (or
  degrades to a warning if a script is attached).
- **Properties:** each property key exists on the class's spec model, and the
  value's type matches the annotation (bool/int/float/string, builtins like
  `Vector2(x, y)`, resource refs via `ExtResource`/`SubResource`, typed arrays
  including `Packed*Array` flat literals). Unknown properties on script-less
  nodes are errors; on script-attached nodes they're warnings.
- **Connections:** signal/from/to/method attributes are present, target nodes
  exist, and the signal is declared on the source node's class (or a warning
  if the source has a script).

This validator is currently only invoked *internally* by the operation
appliers (strict mode). It is not exposed as a standalone command or tool.

**Proposal:** A new `lint` command (CLI) and `lint` tool (MCP) that run
`validate_scene` without requiring Godot. The existing Godot-based `validate`
command stays untouched — `lint` is the lightweight, always-available
companion.

**Target resolution — flexible input:**

The `target` argument accepts any of:

| Input | Behavior |
|-------|----------|
| A `.tscn` file path | Validate that single file. |
| A directory path | Validate every `*.tscn` found recursively (`rglob`). |
| `project.godot` | Validate the containing directory's scenes (same as passing the dir). |
| A directory containing `project.godot` | Treated as the project root; validate all scenes. |

This mirrors how a user thinks ("lint this scene", "lint this folder", "lint
the project") without forcing them to know whether they're pointing at a file
or a directory.

**Aggregated report:**

```
LintReport:
  files:
    - path: "res://scenes/enemy.tscn"
      ok: false
      issues:
        - severity: error
          message: "unknown property 'helth' for class 'Sprite2D'"
          node_path: "Enemy/EnemySprite"
          property: "helth"
        - severity: warning
          message: "property 'radius' is not in the Node2D spec; assuming ..."
          node_path: "Enemy/VisionCone"
          property: "radius"
    - path: "res://scenes/player.tscn"
      ok: true
      issues: []
  ok: false            # false if any file has errors
  error_count: 1
  warning_count: 1
```

Parse errors (`ParseError`) on a file become a single error `Issue` on that
file, so a broken file doesn't abort the whole run — every other file is still
linted.

**CLI — `gli tscn lint`:**

```
gli tscn lint <target> [--json]
```

- `target`: a `.tscn` file, a directory, or `project.godot`.
- `--json`: print the `LintReport` as JSON on stdout.
- Text output: per-file issue list (path + `error [node.path]: message`),
  then a summary line: `1 error, 1 warning across 2 files`.
- Exit codes: `0` if no errors, `1` if any errors, `2` (usage) for a bad
  target path.

**MCP — `lint` tool:**

```
lint(target: str, project: str = ".") -> str   # JSON LintReport
```

Mirrors the CLI. No `godot` parameter — it is lightweight by design. The
existing `validate` MCP tool (Godot-based) remains for users who want the
engine's own check.

**Why this is more complex than the other proposals:**

1. **It promotes an internal subsystem to a public interface** — not a green
   field helper, but careful wiring of `validate_scene` + `parse_scene` +
   target resolution + aggregation into both a Typer command and an MCP tool,
   with consistent exit-code / JSON semantics.
2. **Multi-file aggregation** — every other tool operates on one scene; `lint`
   on a directory/project fans out across N files, collects per-file reports,
   and must handle per-file parse failures gracefully without aborting the run.
3. **Target resolution logic** — file vs. directory vs. `project.godot` vs.
   project-root detection is a new piece of path-handling code that doesn't
   exist yet and needs its own unit tests.
4. **Dual surface (CLI + MCP)** — must be added in two places with matching
   behavior, plus tests for both.
5. **Reporting model** — a new `LintReport` / `FileIssues` pydantic model
   layer on top of the existing `ValidationReport` / `Issue`, with summary
   properties (`ok`, `error_count`, `warning_count`).

**Scope boundaries (explicitly out of scope):**

- The Godot-based `validate` command is unchanged.
- No `class_name` script resolution — unknown script-defined classes already
  degrade to warnings in `validate_scene`, which is the correct behavior for a
  no-Godot linter.
- Single bundled spec version (`v4_7_0` via `default_provider()`); per-project
  Godot version selection is a separate future concern.
- `lint` does not catch runtime errors (that's `run_scene`, §6) — it catches
  structural/spec errors that the offline validator can see.
