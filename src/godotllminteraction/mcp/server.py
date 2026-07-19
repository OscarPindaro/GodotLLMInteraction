"""FastMCP server creation and stdio entry point."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from godotllminteraction.mcp.context import McpContext

_INSTRUCTIONS = (
    "gli (Godot LLM Interaction) MCP server.\n\n"
    "Tools wrap the gli CLI for editing Godot .tscn scene files, querying "
    "Godot API specifications, inspecting images/tilemaps, and managing a "
    "per-project question-linked knowledge base.\n\n"
    "Call set_godot_version once to set the default version for subsequent "
    "spec queries. Call set_project to set the working project path for KB "
    "operations."
)


def create_server() -> FastMCP:
    server = FastMCP("gli", instructions=_INSTRUCTIONS)
    ctx = McpContext()

    from godotllminteraction.mcp.tools import image, kb, project, specs, tscn

    tscn.register(server, ctx)
    image.register(server, ctx)
    specs.register(server, ctx)
    kb.register(server, ctx)
    project.register(server, ctx)
    return server


async def serve() -> None:
    server = create_server()
    await server.run_stdio_async()
