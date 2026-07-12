# MCP Server, Agent Installer, and Question-Linked Knowledge Base for `gli`

Add an MCP server (`src/godotllminteraction/mcp/`), an agent installer copied from semble (MIT-licensed), and a per-project question-linked knowledge base — all sharing the existing `tscn/` backend as thin wrappers with full feature parity.

---

## Key Decisions (from feedback)

- **License**: semble is MIT — we can copy the installer code directly, let's mention them in the readme!
- **MCP module**: separate `src/godotllminteraction/mcp/` package (not a single file).
- **MCP entry point**: `gli mcp` subcommand starts the server. No argv peeking / auto-dispatch — explicit is cleaner.
- **Stdout concern**: MCP uses stdio for JSON-RPC. The CLI already routes most output to stderr (`err_console`), but `print_text` uses stdout. The MCP server will NOT use any CLI printing — it returns JSON strings from tools. No conflict.
- **Installer**: copy from semble, replace `questionary` with `typer` + `rich` (already deps). No new deps.
- **Installation source**: GitHub, not PyPI. Config uses `uvx --from git+https://github.com/OscarPindaro/GodotLLMInteraction.git gli mcp`.
- **Godot version**: `set_godot_version` tool/command sets it once; all other tools/commands have optional `version` param that defaults to the set version.
- **KB storage**: per-project, under `XDG_DATA_HOME/gli/<project_slug>/kb/` (or platform equivalent). Project slug = directory name + short path hash for uniqueness.
- **KB entry**: pydantic `BaseModel`, not dataclass.
- **Embeddings**: `model2vec` first (same as semble). `sentence-transformers` later. Single model for now.
- **KB search**: use `model2vec` directly for question embedding + cosine similarity. Simple, no need for semble's full indexing pipeline for questions. (Semble can be used separately by the LLM to index the Godot repo code if needed — different concern.)
- **Feature parity**: ALL existing CLI commands exposed as MCP tools. CLI and MCP are both thin wrappers over `tscn/` backend.

---

## Phase 1: MCP Server Module

**Goal**: `gli mcp` starts a stdio MCP server exposing all existing CLI operations as tools.

### New package: `src/godotllminteraction/mcp/`

```
src/godotllminteraction/mcp/
├── __init__.py          # exports serve()
├── server.py            # FastMCP server + tool registration
├── context.py           # session state (godot version, project path)
└── tools/
    ├── __init__.py
    ├── tscn.py          # tscn operation tools (add-node, delete-node, etc.)
    ├── image.py         # image/tilemap tools
    ├── specs.py         # Godot API spec query tool
    └── kb.py            # knowledge base tools (Phase 3)
```

### `server.py` — core pattern

```python
from mcp.server.fastmcp import FastMCP

def create_server() -> FastMCP:
    server = FastMCP("gli", instructions="...")
    ctx = McpContext()  # holds godot_version, project_path

    # Register all tool groups
    from godotllminteraction.mcp.tools import tscn, image, specs, kb
    tscn.register(server, ctx)
    image.register(server, ctx)
    specs.register(server, ctx)
    kb.register(server, ctx)
    return server

async def serve() -> None:
    server = create_server()
    await server.run_stdio_async()
```

### `context.py` — session state

```python
from dataclasses import dataclass, field

@dataclass
class McpContext:
    godot_version: str | None = None    # set by set_godot_version tool
    project_path: str | None = None     # set by set_project tool
```

### Tool registration pattern (per group)

```python
# tools/tscn.py
from mcp.server.fastmcp import FastMCP
from typing import Annotated
from pydantic import Field
import json
from godotllminteraction import tscn as tscn_lib
from godotllminteraction.mcp.context import McpContext

def register(server: FastMCP, ctx: McpContext) -> None:

    @server.tool()
    async def add_node(
        scene_path: Annotated[str, Field(description="Path to .tscn file")],
        path: Annotated[str, Field(description="Scene path of new node, e.g. 'Player/Sprite'")],
        type: Annotated[str | None, Field(description="Godot class name")] = None,
        instance: Annotated[str | None, Field(description='ExtResource("id") literal')] = None,
        properties: Annotated[dict[str, str] | None, Field(description="Key-value props in Godot literal syntax")] = None,
        groups: Annotated[list[str] | None, Field(description="Node groups")] = None,
        index: Annotated[int | None, Field(description="Position among siblings")] = None,
    ) -> str:
        """Add a node to a Godot scene."""
        op = tscn_lib.AddNode(path=path, type=type, instance=instance,
                              properties=properties or {}, groups=groups, index=index)
        scene = tscn_lib.load_scene(__import__("pathlib").Path(scene_path))
        result = tscn_lib.apply_operations(scene, [op])
        # return JSON with changed/diff info
        ...

    @server.tool()
    async def set_godot_version(
        version: Annotated[str, Field(description="Godot version, e.g. '4.6.0'")],
    ) -> str:
        """Set the default Godot version for subsequent operations."""
        ctx.godot_version = version
        return json.dumps({"ok": True, "version": version})
```

### Full tool list (1:1 with CLI commands)

**tscn tools** (from `cli/tscn.py`):
- `add_node`, `delete_node`, `update_properties`, `rename_node`, `move_node`
- `attach_script`, `detach_script`, `add_ext_resource`, `create_sub_resource`
- `connect_signal`, `disconnect_signal`
- `apply_ops_file` (YAML ops file)
- `tree` (scene tree inspection)
- `validate` (scene/project validation via Godot editor)

**image tools** (from `cli/image.py`):
- `image_info`, `tile_grid`, `tile_region`

**spec tools** (from `tscn/specs.py` `SpecProvider`):
- `get_godot_spec` — query a Godot class's properties, signals, inheritance for a given version
- `set_godot_version` — set default version for subsequent spec queries

**kb tools** (Phase 3):
- `kb_search`, `kb_register`, `kb_list`, `kb_remove`

### CLI integration

Add `mcp` subcommand to Typer app in `cli/__init__.py`:

```python
@app.command()
def mcp() -> None:
    """Start the MCP stdio server."""
    import asyncio
    from godotllminteraction.mcp import serve
    asyncio.run(serve())
```

### `pyproject.toml` changes

```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0,<2.0"]

[project.scripts]
gli = "godotllminteraction.cli:cli"
```

---

## Phase 2: Agent Installer (copied from semble, MIT)

**Goal**: `gli install` / `gli uninstall` auto-configures MCP in detected agents.

### Files to create (adapted from semble's `installer/`):

```
src/godotllminteraction/installer/
├── __init__.py          # exports run()
├── agents.py            # AgentTarget definitions
├── config.py            # JSON/TOML config editing
└── installer.py         # orchestration
```

### Key changes from semble:

1. **MCP server config** — command is `gli mcp`, installed from GitHub:
   ```python
   _STDIO_SERVER_CONFIG = {
       "command": "uvx",
       "args": ["--from", "git+https://github.com/OscarPindaro/GodotLLMInteraction.git", "gli", "mcp"],
       "type": "stdio",
   }
   _BARE_STDIO_SERVER_CONFIG = {  # Windsurf: no "type" field
       "command": "uvx",
       "args": ["--from", "git+https://github.com/OscarPindaro/GodotLLMInteraction.git", "gli", "mcp"],
   }
   ```

2. **Agent targets** — same list as semble (Windsurf, Claude, Cursor, VS Code, Zed, Codex, Gemini, etc.), update config paths and keys from semble's `agents.py`.

3. **Instructions block** — `<!-- GLI_START -->` / `<!-- GLI_END -->` markers, content describes gli's MCP tools and CLI fallback.

4. **Interactive flow** — replace `questionary` with `rich` + `typer`:
   - Agent selection: `rich.table.Table` listing detected agents + `typer.prompt` for choice.
   - Integration selection: same pattern.
   - Confirmation: `typer.confirm`.

5. **Config editing** — copy semble's `config.py` directly (MIT). It handles JSON5 (tree-sitter), TOML, and marked-section replacement. The tree-sitter deps are already pulled in via semble if installed, or we add `tree-sitter` + `tree-sitter-language-pack` as installer deps. **Simpler alternative**: start with plain `json` module (no comment preservation), upgrade to JSON5 later if needed. This avoids adding tree-sitter as a dep.

### CLI integration

```python
@app.command()
def install(
    agent: Annotated[list[str] | None, typer.Option("--agent", help="Agent(s) to configure non-interactively.")] = None,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation.")] = False,
) -> None:
    """Configure gli across coding agents."""
    from godotllminteraction.installer import run
    run("install", agent_ids=agent, yes=yes)

@app.command()
def uninstall(
    agent: Annotated[list[str] | None, typer.Option("--agent", help="Agent(s) to remove.")] = None,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation.")] = False,
) -> None:
    """Remove gli configuration from coding agents."""
    from godotllminteraction.installer import run
    run("uninstall", agent_ids=agent, yes=yes)
```

### No new dependencies

Uses existing `typer` + `rich`. Installer config editing uses stdlib `json` (plain, no JSON5 comment preservation initially).

---

## Phase 3: Per-Project Question-Linked Knowledge Base

**Goal**: Register files/folders/snippets linked to questions. Search by question similarity → return linked files. Per-project storage.

### Concept

Q→Code mapping with semantic search on the question side:
- Register: "How do I create an animated sprite?" → `examples/areas/boolean_area.tscn`
- Query: "How to make animated sprites?" → semantic match on question → return linked files
- Multiple questions per entry; multiple entries per file; tags for filtering

### Storage location

```
Linux:   ~/.local/share/gli/<project_slug>/kb/
macOS:   ~/Library/Application Support/gli/<project_slug>/kb/
Windows: %APPDATA%\gli\<project_slug>\kb\
```

`project_slug` = `{dir_name}_{sha256(abs_path)[:8]}` for uniqueness.

Override via `GLI_KB_LOCATION` env var (absolute path).

```python
# src/godotllminteraction/kb/storage.py
def resolve_kb_folder(project_path: Path | None = None) -> Path:
    project_path = project_path or Path.cwd()
    slug = f"{project_path.name}_{hashlib.sha256(str(project_path.resolve()).encode()).hexdigest()[:8]}"
    # ... platform resolution ...
    return base / "gli" / slug / "kb"
```

### Data model (pydantic)

```python
# src/godotllminteraction/kb/types.py
from pydantic import BaseModel, Field
from datetime import datetime

class KbEntry(BaseModel):
    id: str                              # UUID4 hex
    questions: list[str]                 # one or more questions
    file_paths: list[str] = []           # linked files (project-relative or absolute)
    snippet: str | None = None           # optional inline code
    description: str = ""                # human-readable
    tags: list[str] = []                 # optional tags
    created_at: datetime = Field(default_factory=datetime.now)

class KbSearchResult(BaseModel):
    entry: KbEntry
    score: float                         # cosine similarity (0..1)
    matched_question: str                # which question matched best
```

### Storage format

```
<kb_folder>/
├── entries/
│   ├── {uuid1}.json     # KbEntry serialized
│   └── {uuid2}.json
└── index.npz            # numpy array of question embeddings + entry ID mapping
```

On `register`: save entry JSON, append embedding to `index.npz`.
On `search`: load `index.npz`, embed query, cosine similarity, return top-k.
On `remove`: delete entry JSON, rebuild `index.npz`.

### Search implementation (model2vec)

```python
# src/godotllminteraction/kb/search.py
from model2vec import StaticModel
import numpy as np

_model: StaticModel | None = None

def _get_model() -> StaticModel:
    global _model
    if _model is None:
        _model = StaticModel.from_pretrained("minishlab/potion-base-2M-v1")
    return _model

def search_kb(query: str, project_path: Path, top_k: int = 5) -> list[KbSearchResult]:
    model = _get_model()
    query_emb = model.encode([query])[0]
    # load index.npz → embeddings array + entry_ids list
    # cosine similarity → top-k → load entries → return
    ...
```

**Why model2vec directly, not semble**: semble indexes files (code chunks via tree-sitter). Our KB indexes questions (short text strings). Using model2vec directly for question embedding + cosine similarity is simpler and fits the use case. Semble can be used separately by the LLM (it's already an MCP server) to search the project's code — different concern, different tool.

### CLI commands

```bash
# Register a file with questions
gli kb register --question "How do I create an animated sprite?" --question "How to animate sprites in 2D?" examples/areas/boolean_area.tscn

# Register a folder
gli kb register --question "How do boolean areas work?" examples/areas/

# Register an inline snippet
gli kb register --question "How to follow a player?" --snippet "extends Node2D ..."

# Register with tags
gli kb register --question "How do doors work?" --tag scenes --tag interactable scenes/door.tscn

# Search
gli kb search "animated sprites"

# List all entries
gli kb list

# Remove by ID
gli kb remove <entry-id>

# Clear all
gli kb clear
```

### MCP tools

```python
@server.tool()
async def kb_search(
    query: Annotated[str, Field(description="Natural language question.")],
    top_k: Annotated[int, Field(description="Number of results.", ge=1)] = 5,
) -> str:
    """Search the project's knowledge base by question similarity."""

@server.tool()
async def kb_register(
    questions: Annotated[list[str], Field(description="Questions this content answers.")],
    file_paths: Annotated[list[str] | None, Field(description="Files/folders to link.")] = None,
    snippet: Annotated[str | None, Field(description="Inline snippet.")] = None,
    description: Annotated[str, Field(description="Human-readable description.")] = "",
    tags: Annotated[list[str] | None, Field(description="Optional tags.")] = None,
) -> str:
    """Register files or snippets as answers to questions in the KB."""
```

### File structure

```
src/godotllminteraction/
├── mcp/                        # MCP server package (Phase 1)
│   ├── __init__.py
│   ├── server.py
│   ├── context.py
│   └── tools/
│       ├── __init__.py
│       ├── tscn.py
│       ├── image.py
│       ├── specs.py
│       └── kb.py
├── installer/                  # agent auto-registration (Phase 2)
│   ├── __init__.py
│   ├── agents.py
│   ├── config.py
│   └── installer.py
├── kb/                         # knowledge base (Phase 3)
│   ├── __init__.py
│   ├── types.py                # KbEntry, KbSearchResult (pydantic)
│   ├── storage.py              # cross-platform path resolution, load/save
│   ├── search.py               # model2vec embedding + cosine similarity
│   └── cli.py                  # Typer subcommand group for `gli kb`
├── tscn/                       # existing backend (unchanged)
├── cli/                        # existing CLI (modified: +mcp, +install, +uninstall, +kb)
└── ...
```

---

## Phase 4: Polish & Testing

1. **Tests**:
   - Config editing (merge/remove JSON member, marked section replacement)
   - KB storage (register, search, list, remove, clear)
   - KB search accuracy (basic: register known Q→A, search with paraphrased Q, verify top-1)
   - MCP tool responses (mock FastMCP or test via direct function calls)

2. **Documentation** — update README:
   - `gli install` quickstart
   - MCP server tool table
   - KB CLI usage examples
   - Manual setup per agent

3. **Linting** — ensure new modules pass existing ruff/mypy config.

---

## Implementation Order

1. **Phase 1** — MCP server + `gli mcp` command + `mcp` optional dep
2. **Phase 2** — Installer (copy from semble, adapt to typer/rich, GitHub source)
3. **Phase 3** — Knowledge base (storage → register CLI → search → MCP tools)
4. **Phase 4** — Tests + docs

Each phase is independently shippable.

---

## Dependencies Summary

```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0,<2.0"]
kb = ["model2vec>=0.4.0", "numpy>=1.24.0"]

# No changes to base dependencies — typer + rich already present.
# installer uses stdlib json only (no tree-sitter, no questionary).
```

---

## Relationship with semble

- **semble** (already an MCP server in the IDE) handles **code search** — finding code by intent in any repo.
- **gli MCP** handles **Godot-specific operations** — scene editing, validation, API specs, and the question-linked KB.
- They complement each other: the LLM can use semble to search the Godot source code, and gli to edit scenes and query the KB.
- The KB uses `model2vec` directly (semble's underlying embedding lib) for question similarity — no need to go through semble's file-indexing pipeline for short text.
- No conflict: they're separate MCP servers, separate tools, separate concerns.
