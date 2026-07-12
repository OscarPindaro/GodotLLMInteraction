"""MCP server for gli — exposes all CLI operations as stdio JSON-RPC tools."""

from __future__ import annotations

from godotllminteraction.mcp.server import create_server, serve

__all__ = ["create_server", "serve"]
