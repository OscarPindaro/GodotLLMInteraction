from __future__ import annotations

import enum
import signal

import typer
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


_dry_run: bool = False


def set_dry_run(value: bool) -> None:
    global _dry_run
    _dry_run = value


def is_dry_run() -> bool:
    return _dry_run


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
