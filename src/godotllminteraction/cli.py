from __future__ import annotations

import enum
import signal
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from PIL import Image
from rich.console import Console
from rich.table import Table

# ── Exit codes ──────────────────────────────────────────────────────────────

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130

# ── Consoles ────────────────────────────────────────────────────────────────

console = Console()
err_console = Console(stderr=True)

# ── Verbosity ───────────────────────────────────────────────────────────────


class Verbosity(enum.IntEnum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2


_verbosity: Verbosity = Verbosity.NORMAL


def _should_print(min_level: Verbosity) -> bool:
    return _verbosity >= min_level


# ── Output helpers ──────────────────────────────────────────────────────────


def print_success(msg: str, *, bold: bool = False) -> None:
    if _should_print(Verbosity.NORMAL):
        style = "bold green" if bold else "green"
        err_console.print(f"[{style}]{msg}[/{style}]")


def print_error(msg: str, *, bold: bool = True) -> None:
    style = "bold red" if bold else "red"
    err_console.print(f"[{style}]{msg}[/{style}]")


def print_warning(msg: str, *, bold: bool = False) -> None:
    if _should_print(Verbosity.NORMAL):
        style = "bold yellow" if bold else "yellow"
        err_console.print(f"[{style}]{msg}[/{style}]")


def print_info(msg: str, *, bold: bool = False) -> None:
    if _should_print(Verbosity.NORMAL):
        style = "bold cyan" if bold else "cyan"
        err_console.print(f"[{style}]{msg}[/{style}]")


def print_detail(msg: str, *, bold: bool = False) -> None:
    if _should_print(Verbosity.VERBOSE):
        style = "bold white" if bold else "white"
        err_console.print(f"[{style}]{msg}[/{style}]")


def print_text(msg: str) -> None:
    if _should_print(Verbosity.NORMAL):
        console.print(msg)


# ── Core logic ──────────────────────────────────────────────────────────────


class ImageError(Exception):
    """Failed to open or read an image."""


class TileError(Exception):
    """Tile index or grid parameters are invalid."""


def load_image(path: Path) -> Image.Image:
    try:
        return Image.open(path)
    except FileNotFoundError as exc:
        raise ImageError(f"File not found: {path}") from exc
    except Exception as exc:
        raise ImageError(f"Cannot open image: {exc}") from exc


def get_image_info(path: Path) -> dict[str, str]:
    img = load_image(path)
    return {
        "path": str(path),
        "width": str(img.width),
        "height": str(img.height),
        "format": str(img.format or "unknown"),
        "mode": str(img.mode),
    }


def compute_tile_grid(path: Path, tile_width: int, tile_height: int) -> dict[str, int]:
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
    return {
        "image_width": img.width,
        "image_height": img.height,
        "tile_width": tile_width,
        "tile_height": tile_height,
        "columns": cols,
        "rows": rows,
        "total_tiles": cols * rows,
    }


def compute_tile_region(
    path: Path,
    tile_width: int,
    tile_height: int,
    col: int,
    row: int,
) -> dict[str, int]:
    grid = compute_tile_grid(path, tile_width, tile_height)
    if col < 0 or col >= grid["columns"]:
        raise TileError(f"Column {col} out of range (0..{grid['columns'] - 1}).")
    if row < 0 or row >= grid["rows"]:
        raise TileError(f"Row {row} out of range (0..{grid['rows'] - 1}).")
    x = col * tile_width
    y = row * tile_height
    return {
        "x": x,
        "y": y,
        "width": tile_width,
        "height": tile_height,
        "col": col,
        "row": row,
    }


def make_table(
    title: str, columns: list[str], rows: list[list[str]], *, show_lines: bool = False
) -> Table:
    table = Table(title=title, show_lines=show_lines)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*row)
    return table


# ── Signal handling ─────────────────────────────────────────────────────────


def _handle_sigterm(signum: int, frame: object) -> None:
    print_warning("\nReceived SIGTERM — shutting down.")
    raise SystemExit(EXIT_INTERRUPTED)


signal.signal(signal.SIGTERM, _handle_sigterm)

# ── App ─────────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="godotllminteraction",
    help="Image utilities for Godot tilemap and scene generation.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        print_text("godotllminteraction 0.1.0")
        raise typer.Exit(code=EXIT_OK)


@app.callback()
def main(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Increase output verbosity.")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress all non-error output.")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would happen without executing."),
    ] = False,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    global _verbosity
    if verbose and quiet:
        print_error("Cannot use both --verbose and --quiet.")
        raise typer.Exit(code=EXIT_USAGE)
    if quiet:
        _verbosity = Verbosity.QUIET
    elif verbose:
        _verbosity = Verbosity.VERBOSE
    else:
        _verbosity = Verbosity.NORMAL


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


# ── Entrypoint ──────────────────────────────────────────────────────────────


def cli() -> None:
    try:
        app()
    except KeyboardInterrupt:
        print_warning("\nInterrupted.")
        sys.exit(EXIT_INTERRUPTED)
    except BrokenPipeError:
        sys.stderr.close()
        sys.exit(EXIT_OK)
    except SystemExit as exc:
        sys.exit(exc.code)
    except Exception as exc:
        print_error(f"Unexpected error: {exc}")
        sys.exit(EXIT_ERROR)
