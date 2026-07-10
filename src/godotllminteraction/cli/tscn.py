from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from godotllminteraction.cli._common import (
    EXIT_ERROR,
    EXIT_USAGE,
    print_error,
    print_success,
    print_text,
    print_warning,
)

app = typer.Typer(help="Godot scene (.tscn) utilities.")


@app.command()
def validate(
    target: Annotated[
        str,
        typer.Argument(
            help="res:// path to a .tscn file, or 'project.godot' to validate the whole project."
        ),
    ],
    project: Annotated[
        Path,
        typer.Option(
            "--project",
            "-p",
            help="Project directory containing project.godot.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("."),
    godot: Annotated[
        str,
        typer.Option("--godot", "-g", help="Path to the Godot executable."),
    ] = "godot",
) -> None:
    """Validate a Godot scene or the whole project using the Godot editor."""
    godot_path = shutil.which(godot) or godot
    if not Path(godot_path).exists():
        print_error(f"Godot executable not found: {godot}")
        raise typer.Exit(code=EXIT_USAGE)

    if target.endswith("project.godot"):
        cmd = [
            str(godot_path),
            "--headless",
            "--import",
            "--quit",
            "--path",
            str(project),
        ]
    else:
        if not target.endswith(".tscn"):
            print_warning(
                "Target does not look like a .tscn file; validation may still proceed."
            )
        cmd = [
            str(godot_path),
            "--headless",
            "--check-only",
            "--quit",
            "--path",
            str(project),
            target,
        ]

    print_text(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode == 0:
        print_success("Validation passed.")
    else:
        print_error(f"Validation failed with exit code {result.returncode}.")
        raise typer.Exit(code=EXIT_ERROR)
