from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from godotllminteraction.cli import image, specifications, tscn
from godotllminteraction.cli import kb as kb_cli
from godotllminteraction.cli._common import (
    EXIT_ERROR,
    EXIT_INTERRUPTED,
    EXIT_OK,
    EXIT_USAGE,
    Verbosity,
    _version_callback,
    print_error,
    print_warning,
    set_dry_run,
    set_verbosity,
)

app = typer.Typer(
    name="gli",
    help="Godot LLM Interaction CLI tools.",
    no_args_is_help=True,
)

app.add_typer(image.app, name="image", help="Tilemap and image utilities.")
app.add_typer(tscn.app, name="tscn", help="Godot scene (.tscn) utilities.")
app.add_typer(
    specifications.app,
    name="specifications",
    help="Codegen utilities for versioned Godot API specifications.",
)
app.add_typer(kb_cli.app, name="kb", help="Per-project question-linked knowledge base.")


@app.command()
def mcp() -> None:
    """Start the MCP stdio server."""
    import asyncio

    from godotllminteraction.mcp import serve

    asyncio.run(serve())


@app.command()
def install(
    agent: Annotated[
        list[str] | None,
        typer.Option("--agent", help="Agent(s) to configure non-interactively."),
    ] = None,
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Skip confirmation.")
    ] = False,
) -> None:
    """Configure gli across coding agents."""
    from godotllminteraction.installer import run

    run("install", agent_ids=agent, yes=yes)


@app.command()
def uninstall(
    agent: Annotated[
        list[str] | None,
        typer.Option("--agent", help="Agent(s) to remove."),
    ] = None,
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Skip confirmation.")
    ] = False,
) -> None:
    """Remove gli configuration from coding agents."""
    from godotllminteraction.installer import run

    run("uninstall", agent_ids=agent, yes=yes)


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
    if verbose and quiet:
        print_error("Cannot use both --verbose and --quiet.")
        raise typer.Exit(code=EXIT_USAGE)
    if quiet:
        set_verbosity(Verbosity.QUIET)
    elif verbose:
        set_verbosity(Verbosity.VERBOSE)
    else:
        set_verbosity(Verbosity.NORMAL)

    set_dry_run(dry_run)


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
