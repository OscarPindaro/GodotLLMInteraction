from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from godotllminteraction.cli._common import (
    EXIT_USAGE,
    ImageError,
    TileError,
    compute_tile_grid,
    compute_tile_region,
    get_image_info,
    make_table,
    print_error,
    print_info,
    print_text,
)

app = typer.Typer(help="Tilemap and image utilities.")


@app.command()
def info(
    image: Annotated[
        Path,
        typer.Argument(help="Path to the image file.", exists=True, readable=True),
    ],
) -> None:
    """Show image dimensions, format, and mode."""
    try:
        result = get_image_info(image)
    except ImageError as exc:
        print_error(f"{exc}")
        raise typer.Exit(code=EXIT_USAGE) from exc

    table = make_table(
        "Image Info",
        ["Property", "Value"],
        [[k, v] for k, v in result.items()],
    )
    print_text(table)


@app.command()
def tiles(
    image: Annotated[
        Path,
        typer.Argument(help="Path to the tilemap image.", exists=True, readable=True),
    ],
    tile_width: Annotated[
        int, typer.Option("--tile-width", "-w", help="Tile width in pixels.")
    ] = 16,
    tile_height: Annotated[
        int, typer.Option("--tile-height", "-h", help="Tile height in pixels.")
    ] = 16,
) -> None:
    """Compute the tile grid (columns, rows, total tiles) for a tilemap."""
    try:
        result = compute_tile_grid(image, tile_width, tile_height)
    except ImageError as exc:
        print_error(f"{exc}")
        raise typer.Exit(code=EXIT_USAGE) from exc
    except TileError as exc:
        print_error(f"{exc}")
        raise typer.Exit(code=EXIT_USAGE) from exc

    table = make_table(
        "Tile Grid",
        ["Property", "Value"],
        [[k, str(v)] for k, v in result.items()],
    )
    print_text(table)


@app.command()
def region(
    image: Annotated[
        Path,
        typer.Argument(help="Path to the tilemap image.", exists=True, readable=True),
    ],
    col: Annotated[int, typer.Argument(help="Tile column index (0-based).")],
    row: Annotated[int, typer.Argument(help="Tile row index (0-based).")],
    tile_width: Annotated[
        int, typer.Option("--tile-width", "-w", help="Tile width in pixels.")
    ] = 16,
    tile_height: Annotated[
        int, typer.Option("--tile-height", "-h", help="Tile height in pixels.")
    ] = 16,
) -> None:
    """Compute the pixel region (Rect2) for a specific tile in a tilemap.

    Useful for generating AtlasTexture region values in Godot .tscn files.
    """
    try:
        result = compute_tile_region(image, tile_width, tile_height, col, row)
    except ImageError as exc:
        print_error(f"{exc}")
        raise typer.Exit(code=EXIT_USAGE) from exc
    except TileError as exc:
        print_error(f"{exc}")
        raise typer.Exit(code=EXIT_USAGE) from exc

    table = make_table(
        f"Tile Region (col={col}, row={row})",
        ["Property", "Value"],
        [[k, str(v)] for k, v in result.items()],
    )
    print_text(table)

    print_info(
        f"Godot Rect2: Rect2({result['x']}, {result['y']}, {result['width']}, {result['height']})"
    )
