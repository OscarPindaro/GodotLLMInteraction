from __future__ import annotations

import enum
import signal
from pathlib import Path

import typer
from PIL import Image
from rich.console import Console
from rich.table import Table

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130

console = Console()
err_console = Console(stderr=True)


class Verbosity(enum.IntEnum):
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2


_verbosity: Verbosity = Verbosity.NORMAL


def _should_print(min_level: Verbosity) -> bool:
    return _verbosity >= min_level


def set_verbosity(value: Verbosity) -> None:
    global _verbosity
    _verbosity = value


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


def make_table(
    title: str, columns: list[str], rows: list[list[str]], *, show_lines: bool = False
) -> Table:
    table = Table(title=title, show_lines=show_lines)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*row)
    return table


def _version_callback(value: bool) -> None:
    if value:
        print_text("gli 0.1.0")
        raise typer.Exit(code=EXIT_OK)


def _handle_sigterm(signum: int, frame: object) -> None:
    print_warning("\nReceived SIGTERM — shutting down.")
    raise SystemExit(EXIT_INTERRUPTED)


signal.signal(signal.SIGTERM, _handle_sigterm)


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
