"""Installer orchestration — detect agents, configure MCP, add instructions.

Adapted from semble (MIT), using typer + rich for interactive flow.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from godotllminteraction.installer.agents import (
    AgentTarget,
    all_targets,
    detect_installed,
)
from godotllminteraction.installer.config import (
    add_instructions,
    merge_mcp_server,
    remove_instructions,
    remove_mcp_server,
)

SERVER_NAME = "gli"

_STDIO_SERVER_CONFIG = {
    "command": "uvx",
    "args": [
        "--from",
        "git+https://github.com/OscarPindaro/GodotLLMInteraction.git[mcp,kb]",
        "gli",
        "mcp",
    ],
    "type": "stdio",
}

_BARE_STDIO_SERVER_CONFIG = {
    "command": "uvx",
    "args": [
        "--from",
        "git+https://github.com/OscarPindaro/GodotLLMInteraction.git[mcp,kb]",
        "gli",
        "mcp",
    ],
}

console = Console()


def _server_config(target: AgentTarget) -> dict:
    return _BARE_STDIO_SERVER_CONFIG if target.bare_config else _STDIO_SERVER_CONFIG


def _print_agent_table(targets: list[AgentTarget], installed_ids: set[str]) -> None:
    table = Table(title="Detected Agents", show_lines=True)
    table.add_column("#", style="dim")
    table.add_column("Agent")
    table.add_column("ID")
    table.add_column("Status")
    for i, t in enumerate(targets, 1):
        status = (
            "[green]installed[/green]"
            if t.id in installed_ids
            else "[dim]not detected[/dim]"
        )
        table.add_row(str(i), t.name, t.id, status)
    console.print(table)


def run(
    action: str,
    *,
    agent_ids: list[str] | None = None,
    yes: bool = False,
) -> None:
    """Run install or uninstall for the given agents (or interactively)."""
    all_t = all_targets()
    installed = detect_installed(all_t)
    installed_ids = {t.id for t in installed}

    if agent_ids:
        selected = [t for t in all_t if t.id in agent_ids]
        if not selected:
            console.print(f"[red]No matching agents for: {agent_ids}[/red]")
            raise typer.Exit(1)
    else:
        if not installed:
            console.print("[yellow]No coding agents detected.[/yellow]")
            console.print("Available agents:")
            _print_agent_table(all_t, installed_ids)
            console.print("\nPass --agent <id> to configure a specific agent.")
            return
        _print_agent_table(all_t, installed_ids)
        console.print()
        choice = typer.prompt(
            "Enter agent numbers (comma-separated) or 'all'",
            default="all",
        )
        if choice.strip().lower() == "all":
            selected = installed
        else:
            indices: list[int] = []
            for part in choice.split(","):
                part = part.strip()
                if part.isdigit():
                    indices.append(int(part) - 1)
            selected = [all_t[i] for i in indices if 0 <= i < len(all_t)]

    if not selected:
        console.print("[yellow]No agents selected.[/yellow]")
        return

    if not yes:
        names = ", ".join(t.name for t in selected)
        if action == "install":
            confirm = typer.confirm(f"Install gli MCP into: {names}?", default=True)
        else:
            confirm = typer.confirm(f"Remove gli MCP from: {names}?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            return

    for target in selected:
        server_cfg = _server_config(target)
        for cfg_path in target.config_paths:
            if action == "install":
                changed = merge_mcp_server(
                    cfg_path, target.mcp_key, SERVER_NAME, server_cfg
                )
                if changed:
                    console.print(
                        f"[green]✓[/green] {target.name}: added gli to {cfg_path}"
                    )
                else:
                    console.print(
                        f"[dim]•[/dim] {target.name}: already configured in {cfg_path}"
                    )
            else:
                changed = remove_mcp_server(cfg_path, target.mcp_key, SERVER_NAME)
                if changed:
                    console.print(
                        f"[green]✓[/green] {target.name}: removed gli from {cfg_path}"
                    )
                else:
                    console.print(
                        f"[dim]•[/dim] {target.name}: not present in {cfg_path}"
                    )

        if target.instructions_file is not None:
            if action == "install":
                if add_instructions(target.instructions_file):
                    console.print(f"[green]✓[/green] {target.name}: added instructions")
            else:
                if remove_instructions(target.instructions_file):
                    console.print(
                        f"[green]✓[/green] {target.name}: removed instructions"
                    )
