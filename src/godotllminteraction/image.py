"""Image and tilemap utilities — shared between CLI and MCP frontends."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pydantic import BaseModel


class ImageError(Exception):
    """Failed to open or read an image."""


class TileError(Exception):
    """Tile index or grid parameters are invalid."""


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


def load_image(path: Path) -> Image.Image:
    try:
        return Image.open(path)
    except FileNotFoundError as exc:
        raise ImageError(f"File not found: {path}") from exc
    except Exception as exc:
        raise ImageError(f"Cannot open image: {exc}") from exc


def get_image_info(path: Path) -> ImageInfo:
    img = load_image(path)
    return ImageInfo(
        path=str(path),
        width=img.width,
        height=img.height,
        format=str(img.format or "unknown"),
        mode=str(img.mode),
    )


def compute_tile_grid(path: Path, tile_width: int, tile_height: int) -> TileGrid:
    img = load_image(path)
    if tile_width <= 0 or tile_height <= 0:
        raise TileError("Tile dimensions must be positive integers.")
    cols = img.width // tile_width
    rows = img.height // tile_height
    if cols == 0 or rows == 0:
        raise TileError(
            f"Tile size {tile_width}x{tile_height} is larger than "
            f"image {img.width}x{img.height}."
        )
    return TileGrid(
        image_width=img.width,
        image_height=img.height,
        tile_width=tile_width,
        tile_height=tile_height,
        columns=cols,
        rows=rows,
        total_tiles=cols * rows,
    )


def compute_tile_region(
    path: Path,
    tile_width: int,
    tile_height: int,
    col: int,
    row: int,
) -> TileRegion:
    grid = compute_tile_grid(path, tile_width, tile_height)
    if col < 0 or col >= grid.columns:
        raise TileError(f"Column {col} out of range (0..{grid.columns - 1}).")
    if row < 0 or row >= grid.rows:
        raise TileError(f"Row {row} out of range (0..{grid.rows - 1}).")
    x = col * tile_width
    y = row * tile_height
    return TileRegion(
        x=x,
        y=y,
        width=tile_width,
        height=tile_height,
        col=col,
        row=row,
    )
