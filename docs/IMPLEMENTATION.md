# MCP + Installer + KB Implementation

> **Read this file after every context compression to restore implementation context.**

## Overview

Three modules were added to `gli` (Godot LLM Interaction):

1. **MCP Server** — Exposes all gli CLI capabilities as JSON-RPC tools over stdio via `FastMCP`.
2. **Agent Installer** — Configures the MCP server into coding agents' config files (Windsurf, Claude, Cursor, VS Code, Zed, Codex, Gemini).
3. **Question-Linked Knowledge Base (KB)** — Per-project semantic search linking questions to answers (text, local files, folders, GitHub URLs) using pre-embedded `model2vec` embeddings.

---

## Phase 1: MCP Server

### Files

- `src/godotllminteraction/mcp/__init__.py` — exports `create_server`, `serve`
- `src/godotllminteraction/mcp/server.py` — `create_server()` builds `FastMCP("gli")`, creates `McpContext`, registers all tool groups; `serve()` runs stdio async
- `src/godotllminteraction/mcp/context.py` — `McpContext` dataclass: `godot_version: str | None`, `project_path: str | None`
- `src/godotllminteraction/mcp/tools/__init__.py` — empty
- `src/godotllminteraction/mcp/tools/tscn.py` — 16 tools wrapping `tscn_lib` operations: `add_node`, `delete_node`, `update_properties`, `rename_node`, `move_node`, `attach_script`, `detach_script`, `add_ext_resource`, `create_sub_resource`, `connect_signal`, `disconnect_signal`, `apply_ops_file`, `tree`, `validate`, `set_godot_version`, `set_project`
- `src/godotllminteraction/mcp/tools/image.py` — 3 tools: `image_info`, `tile_grid`, `tile_region` (import from `godotllminteraction.image`, not `cli._common`)
- `src/godotllminteraction/mcp/tools/specs.py` — 1 tool: `get_godot_spec` (version-aware provider loading)
- `src/godotllminteraction/mcp/tools/kb.py` — 4 tools: `kb_search`, `kb_register`, `kb_list`, `kb_remove`

### Key patterns

- MCP tools return **JSON strings**, never print to stdout
- `set_godot_version` / `set_project` mutate `McpContext` session state; other tools default to it
- Error responses: `{"ok": false, "error": "msg"}`
- Success responses: `{"ok": true, ...}` or pydantic `model_dump_json()`

### CLI integration

`src/godotllminteraction/cli/__init__.py` registers `mcp`, `install`, `uninstall`, and `kb` subcommands.

### pyproject.toml

Added `[project.optional-dependencies]`:
- `mcp`: `mcp>=1.0,<2.0`
- `kb`: `model2vec>=0.4.0`, `numpy>=1.24.0`

---

## Phase 2: Agent Installer

### Files

- `src/godotllminteraction/installer/__init__.py` — exports `run`
- `src/godotllminteraction/installer/agents.py` — `AgentTarget` dataclass + `all_targets()` (7 agents) + `detect_installed()`
- `src/godotllminteraction/installer/config.py` — JSON merge/remove for MCP server entries, nested key paths, marked-section instructions blocks
- `src/godotllminteraction/installer/installer.py` — `run(action, agent_ids, yes)` orchestration with rich table + typer prompt

### Agent targets

| Agent | Config path | MCP key | Bare config |
|-------|-----------|---------|-------------|
| Windsurf | `~/.config/windsurf/mcp_config.json` | `mcpServers` | Yes (no `type` field) |
| Claude Code | `~/.claude.json` or `~/.claude/claude_desktop_config.json` | `mcpServers` | No |
| Cursor | `~/.cursor/mcp.json` or `~/.config/Cursor/mcp.json` | `mcpServers` | No |
| VS Code | `~/.config/Code/User/settings.json` | `mcp.servers` (nested) | No |
| Zed | `~/.config/zed/settings.json` | `context_servers` | No |
| Codex | `~/.config/codex/config.json` | `mcp_servers` | No |
| Gemini CLI | `~/.config/gemini/mcp.json` | `mcpServers` | No |

### Server config

```json
{
  "command": "uvx",
  "args": ["--from", "git+https://github.com/OscarPindaro/GodotLLMInteraction.git", "gli", "mcp"],
  "type": "stdio"
}
```

Windsurf uses bare config (no `"type"` field).

### Config editing

- `merge_mcp_server(path, key, name, config)` — adds/updates server in JSON, returns `True` if changed
- `remove_mcp_server(path, key, name)` — removes server, returns `True` if changed
- `add_instructions(path)` / `remove_instructions(path)` — manages `<!-- GLI_START -->...<!-- GLI_END -->` blocks
- Uses stdlib `json` (no comment preservation)
- `_resolve_nested` / `_set_nested` handle dotted key paths like `mcp.servers`

---

## Phase 3: Knowledge Base

### Architecture

Questions are embedded **once at registration time** and stored in `index.npz`.
Search loads the index, embeds only the query, and does a single batched cosine
similarity — no re-embedding of existing entries.

### Files

- `src/godotllminteraction/kb/__init__.py` — exports `KbEntry`, `KbSearchResult`, `build_answer`
- `src/godotllminteraction/kb/types.py` — Pydantic models
- `src/godotllminteraction/kb/storage.py` — path resolution, entry CRUD, index management
- `src/godotllminteraction/kb/search.py` — semantic search using pre-embedded index
- `src/godotllminteraction/kb/answer.py` — build answer content from files/folders/GitHub URLs
- `src/godotllminteraction/cli/kb.py` — CLI subcommands: `register`, `search`, `list`, `remove`, `clear`

### KbEntry model

```python
class KbEntry(BaseModel):
    id: str  # uuid4 hex
    questions: list[str]
    answer_text: str | None       # inline text answer
    file_paths: list[str]         # local files
    folder_paths: list[str]       # local folders (non-recursive)
    github_urls: list[str]        # GitHub blob/ or tree/ URLs
    description: str
    tags: list[str]
    created_at: datetime
```

Validation: at least one question + at least one answer source (text, files, folders, or github_urls).

### Index structure

- `index.npz` — numpy array, shape `(N, dim)`, one row per question
- `index_meta.json` — `[[entry_id, question_index], ...]` mapping row → (entry_id, question_idx)

Operations:
- `append_to_index(kb_folder, entry_id, embeddings)` — vstack new rows, append mapping
- `remove_from_index(kb_folder, entry_id)` — filter rows, rebuild
- `load_index(kb_folder)` — returns `(embeddings, mapping)` or `None`
- `rebuild_index(kb_folder, embeddings, mapping)` — full overwrite
- `clear_kb(kb_folder)` — removes all entries + index + sidecar

### Search flow

1. `resolve_kb_folder(project_path)` — uses `GLI_KB_LOCATION` env or platform data dir
2. `load_index(kb_folder)` — load `index.npz` + `index_meta.json`
3. `model.encode([query])` — embed only the query (model2vec `minishlab/potion-base-2M`)
4. `_cosine_similarity_batch(query_emb, matrix)` — single normalized matmul
5. Group by `entry_id`, keep best score per entry
6. Load entries lazily to get question text
7. Return sorted `list[KbSearchResult]` top_k

### Answer building (`build_answer`)

Concatenates answer parts with `---` separator:
1. `answer_text` (if present)
2. Each file in `file_paths` → `<path>\n<content>`
3. Each folder in `folder_paths` → all text files (non-recursive, filtered by extension)
4. Each GitHub URL in `github_urls`:
   - `/blob/` URLs → fetch via `raw.githubusercontent.com`
   - `/tree/` URLs → fetch via GitHub Contents API, filter text files, fetch each

Text extensions: `.gd`, `.tscn`, `.tres`, `.json`, `.yaml`, `.yml`, `.txt`, `.md`, `.cfg`, `.toml`, `.py`, `.js`, `.ts`, `.cpp`, `.h`, `.c`, `.hx`, `.glsl`, `.shader`

### KB path resolution

- `GLI_KB_LOCATION` env var → absolute override
- macOS: `~/Library/Application Support/gli/{slug}/kb`
- Linux: `$XDG_DATA_HOME/gli/{slug}/kb` or `~/.local/share/gli/{slug}/kb`
- Windows: `%APPDATA%/gli/{slug}/kb`
- Slug: `{project_name}_{sha256(resolved_path)[:8]}`

---

## Image module (extracted from cli._common)

### File

`src/godotllminteraction/image.py` — shared between CLI and MCP frontends.

### Models

```python
class ImageInfo(BaseModel):
    path: str
    width: int
    height: int
    format: str
    mode: str

class TileGrid(BaseModel):
    image_width: int
    image_height: int
    tile_width: int
    tile_height: int
    columns: int
    rows: int
    total_tiles: int

class TileRegion(BaseModel):
    x: int
    y: int
    width: int
    height: int
    col: int
    row: int

    @property
    def godot_rect2(self) -> str:
        return f"Rect2({self.x}, {self.y}, {self.width}, {self.height})"
```

### Functions

- `load_image(path) -> Image.Image` — raises `ImageError`
- `get_image_info(path) -> ImageInfo`
- `compute_tile_grid(path, tile_width, tile_height) -> TileGrid` — raises `TileError` on bad dimensions
- `compute_tile_region(path, tile_width, tile_height, col, row) -> TileRegion` — raises `TileError` on out-of-range

`cli/_common.py` no longer contains image code or PIL import. Both `cli/image.py` and `mcp/tools/image.py` import from `godotllminteraction.image`.

---

## Testing

### Unit tests (`tests/unit/`)

- `tests/unit/image/image_test.py` — Pydantic model returns, tile math, error handling
- `tests/unit/installer/installer_config_test.py` — JSON merge/remove, nested keys, instructions blocks
- `tests/unit/installer/installer_agents_test.py` — Agent target definitions, detection logic, XDG override
- `tests/unit/kb/kb_types_test.py` — KbEntry validation, defaults, save/roundtrip
- `tests/unit/kb/kb_storage_test.py` — Path resolution, entry CRUD, index append/remove/load, sidecar JSON
- `tests/unit/kb/kb_answer_test.py` — GitHub URL regex, file/folder collection, answer building, format consistency
- `tests/unit/kb/kb_search_test.py` — Cosine similarity math, search ranking, top_k, no-re-embedding guarantee (mocked model)

### Integration tests (`tests/integration/`)

- `tests/integration/kb/kb_index_integration_test.py` — **Uses the real model2vec model**. Verifies:
  1. Index files (`index.npz`, `index_meta.json`) are created on disk
  2. Loaded embeddings are byte-identical (`np.array_equal`) to what was saved
  3. Similarity scores are identical whether computed in-memory or from persisted index
  4. Incremental appends produce an index identical to a full rebuild
  5. `search_kb` returns correct ranked results from the persisted index
  6. Scores from `search_kb` match raw cosine similarity computation
  7. Search still works after removing an entry from the index
  8. `build_answer` works end-to-end with real file I/O

- `tests/integration/kb/kb_answer_integration_test.py` — Entry persistence with all answer types:
  1. Entries with `answer_text`, `file_paths`, `folder_paths`, `github_urls` survive save/load with full fidelity
  2. JSON on disk contains all fields
  3. `list_entries` returns all entries with correct fields
  4. `build_answer` reads real file content from disk
  5. `build_answer` from folder includes all text files, excludes binary
  6. Relative paths resolved against project dir
  7. GitHub blob/tree URLs produce same `<source>\n<content>` format as local files (HTTP mocked)
  8. Invalid GitHub URLs produce error strings

### E2e tests (`tests/e2e/`)

- `tests/e2e/kb/kb_cli_e2e_test.py` — **Uses the real model2vec model + CliRunner**. Verifies:
  1. `gli kb register --text/--github/--folder` creates entries + index on disk
  2. `gli kb search --json` returns ranked results with answer content
  3. `gli kb list --json` lists all entries
  4. `gli kb remove` deletes entry + cleans index
  5. `gli kb clear --yes` wipes everything
  6. Validation errors exit non-zero
  7. Multiple registers grow the index incrementally
  8. File content appears in search results

Run all KB tests:
```
uv run pytest tests/unit/kb/ tests/integration/kb/ tests/e2e/kb/ -v
```

### Test markers

**Tier markers** (`unit`, `integration`, `e2e`) are auto-applied by `tests/conftest.py` based on directory.

**Module and interface markers** are set explicitly via `pytestmark = [...]` in each test file:

| Marker | How applied | Description |
|--------|-------------|-------------|
| `unit` | auto (dir `tests/unit/`) | Mocked or pure logic, no external deps |
| `integration` | auto (dir `tests/integration/`) | Real models, real file I/O, no CLI |
| `e2e` | auto (dir `tests/e2e/`) | Real CLI invocations or Godot binary |
| `cli` | `pytestmark` | Exercises the typer CLI |
| `mcp` | `pytestmark` | Exercises the MCP server tools |
| `kb` | `pytestmark` | Knowledge base module |
| `installer` | `pytestmark` | Agent installer module |
| `image` | `pytestmark` | Image/tilemap utilities |
| `tscn` | `pytestmark` | Tscn scene editing |
| `specs` | `pytestmark` | Godot API specifications |

Filter examples:
```bash
# Only unit tests
uv run pytest -m unit

# Only KB tests (all tiers)
uv run pytest -m kb

# CLI tests only
uv run pytest -m cli

# Integration + e2e, excluding unit
uv run pytest -m "not unit"

# KB e2e tests only
uv run pytest -m "kb and e2e"

# Everything except slow e2e
uv run pytest -m "not e2e"
```
