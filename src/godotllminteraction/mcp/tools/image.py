"""MCP tools for image and tilemap utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from godotllminteraction.image import (
    ImageError,
    TileError,
    compute_tile_grid,
    compute_tile_region,
    get_image_info,
)
from godotllminteraction.mcp.context import McpContext


def _error_json(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


def register(server: FastMCP, ctx: McpContext) -> None:

    @server.tool()
    async def image_info(
        image_path: Annotated[str, Field(description="Path to the image file.")],
    ) -> str:
        """Show image dimensions, format, and mode."""
        try:
            result = get_image_info(Path(image_path))
        except ImageError as exc:
            return _error_json(str(exc))
        return result.model_dump_json(indent=2)

    @server.tool()
    async def tile_grid(
        image_path: Annotated[str, Field(description="Path to the tilemap image.")],
        tile_width: Annotated[int, Field(description="Tile width in pixels.")] = 16,
        tile_height: Annotated[int, Field(description="Tile height in pixels.")] = 16,
    ) -> str:
        """Compute the tile grid (columns, rows, total tiles) for a tilemap."""
        try:
            result = compute_tile_grid(Path(image_path), tile_width, tile_height)
        except (ImageError, TileError) as exc:
            return _error_json(str(exc))
        return result.model_dump_json(indent=2)

    @server.tool()
    async def tile_region(
        image_path: Annotated[str, Field(description="Path to the tilemap image.")],
        col: Annotated[int, Field(description="Tile column index (0-based, x-axis).")],
        row: Annotated[int, Field(description="Tile row index (0-based, y-axis).")],
        tile_width: Annotated[int, Field(description="Tile width in pixels.")] = 16,
        tile_height: Annotated[int, Field(description="Tile height in pixels.")] = 16,
    ) -> str:
        """Compute the pixel region (Rect2) for a specific tile in a tilemap.

        Tile coordinates use (col, row) order, matching the (x, y) cartesian
        convention: the first index is the column (horizontal, x-axis) and the
        second index is the row (vertical, y-axis). When a user gives a tile as
        (a, b), pass col=a and row=b.
        """
        try:
            result = compute_tile_region(
                Path(image_path), tile_width, tile_height, col, row
            )
        except (ImageError, TileError) as exc:
            return _error_json(str(exc))
        return result.model_dump_json(indent=2)
