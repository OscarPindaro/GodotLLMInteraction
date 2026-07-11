from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from godotllminteraction import tscn as tscn_lib
from godotllminteraction.cli._common import (
    EXIT_ERROR,
    EXIT_OK,
    EXIT_USAGE,
    is_dry_run,
    print_error,
    print_success,
    print_text,
    print_warning,
)
from godotllminteraction.tscn.exceptions import TscnError
from godotllminteraction.tscn.godot_check import GodotNotFoundError

app = typer.Typer(help="Godot scene (.tscn) utilities.")

_JSON_OPTION = typer.Option(
    "--json",
    help="Print a machine-readable JSON result on stdout instead of rich output.",
)


def _emit_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def _report_payload(report: tscn_lib.ValidationReport) -> list[dict]:
    return [issue.model_dump() for issue in report.issues]


@app.command()
def apply(
    ops_file: Annotated[
        Path,
        typer.Argument(
            help="YAML operations file (see docs/tscn-editing.md).",
            exists=True,
            dir_okay=False,
        ),
    ],
    scene_path: Annotated[
        Optional[Path],
        typer.Option(
            "--scene",
            "-s",
            help="Scene file to edit; overrides the ops file's 'scene' key.",
        ),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Where to write the result; overrides the ops file's 'output' key. "
            "Defaults to in-place.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show the report and diff without writing."),
    ] = False,
    strict: Annotated[
        Optional[bool],
        typer.Option(
            "--strict/--no-strict",
            help="Whether spec-validation errors abort the batch; when omitted, "
            "the ops file's 'strict' key (default true) applies.",
        ),
    ] = None,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Apply a YAML operations file to a scene.

    All-or-nothing: if any operation fails, nothing is written. Operations
    are deterministic and idempotent — re-applying the same file is a no-op.
    """
    try:
        ops = tscn_lib.load_ops_file(ops_file)
    except TscnError as exc:
        print_error(str(exc))
        raise typer.Exit(code=EXIT_USAGE) from exc

    if strict is not None:
        ops.strict = strict

    input_path = scene_path or (Path(ops.scene) if ops.scene else None)
    try:
        if input_path is not None:
            if not input_path.exists():
                print_error(f"Scene file not found: {input_path}")
                raise typer.Exit(code=EXIT_USAGE)
            scene = tscn_lib.load_scene(input_path)
            original_text = tscn_lib.dump_scene(scene)
        else:
            scene = tscn_lib.initial_scene(ops)
            original_text = ""
    except TscnError as exc:
        print_error(str(exc))
        raise typer.Exit(code=EXIT_ERROR) from exc

    try:
        result = tscn_lib.apply_ops_file(ops, scene)
    except TscnError as exc:
        if json_output:
            _emit_json({"ok": False, "error": str(exc)})
        print_error(str(exc))
        raise typer.Exit(code=EXIT_ERROR) from exc

    output_path = output or (Path(ops.output) if ops.output else input_path)
    if output_path is None:
        print_error(
            "No output destination: pass --output or set 'output' in the ops file."
        )
        raise typer.Exit(code=EXIT_USAGE)

    new_text = tscn_lib.dump_scene(result.scene)
    effective_dry_run = dry_run or is_dry_run()

    warnings = [str(w) for r in result.results for w in r.report.warnings]

    if json_output:
        _emit_json(
            {
                "ok": True,
                "changed": result.changed,
                "dry_run": effective_dry_run,
                "output": str(output_path),
                "operations": [
                    {
                        "op": r.op,
                        "changed": r.changed,
                        "affected_paths": r.affected_paths,
                        "allocated_ids": r.allocated_ids,
                        "issues": _report_payload(r.report),
                    }
                    for r in result.results
                ],
            }
        )
    else:
        for warning in warnings:
            print_warning(warning)
        noops = sum(1 for r in result.results if not r.changed)
        summary = f"{len(result.results)} operation(s) applied"
        if noops:
            summary += f" ({noops} already satisfied)"
        print_success(summary)

    if effective_dry_run:
        if not json_output:
            diff = difflib.unified_diff(
                original_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=str(input_path or "<new scene>"),
                tofile=str(output_path),
            )
            # plain print: tscn section headers look like rich markup
            print("".join(diff) or "(no changes)")
            print_warning("Dry run: nothing written.")
        return

    if result.changed or not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(new_text)
        if not json_output:
            print_success(f"Wrote {output_path}.")
    elif not json_output:
        print_text("Scene already in the desired state; nothing written.")


@app.command()
def tree(
    scene_path: Annotated[
        Path,
        typer.Argument(help="Scene file to inspect.", exists=True, dir_okay=False),
    ],
    detail: Annotated[
        str,
        typer.Option(
            "--detail",
            "-d",
            help="Detail level: 'nodes', 'resources' (adds resource references), "
            "or 'properties' (adds every set property).",
        ),
    ] = "nodes",
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Print the scene tree."""
    if detail not in ("nodes", "resources", "properties"):
        print_error(
            f"Invalid --detail {detail!r}; expected nodes, resources, or properties."
        )
        raise typer.Exit(code=EXIT_USAGE)
    try:
        scene = tscn_lib.load_scene(scene_path)
    except TscnError as exc:
        print_error(str(exc))
        raise typer.Exit(code=EXIT_ERROR) from exc

    built = tscn_lib.build_tree(scene, detail)  # type: ignore[arg-type]
    if built is None:
        print_error("Scene has no root node.")
        raise typer.Exit(code=EXIT_ERROR)
    if json_output:
        _emit_json(built.model_dump())
    else:
        print(tscn_lib.render_tree(built))


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
        Optional[str],
        typer.Option("--godot", "-g", help="Path to the Godot executable."),
    ] = None,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Validate a Godot scene or the whole project using the Godot editor."""
    if not target.endswith((".tscn", "project.godot")):
        print_warning(
            "Target does not look like a .tscn file; validation may still proceed."
        )
    try:
        result = tscn_lib.check_scene(target, project_dir=project, godot=godot)
    except GodotNotFoundError as exc:
        if json_output:
            _emit_json({"ok": False, "error": str(exc)})
        print_error(str(exc))
        raise typer.Exit(code=EXIT_USAGE) from exc

    if json_output:
        _emit_json(result.model_dump())
    else:
        print_text(f"Running: {' '.join(result.command)}")
        if result.output:
            print_text(result.output)
        if result.ok:
            print_success("Validation passed.")
        else:
            print_error(f"Validation failed with exit code {result.exit_code}.")
    raise typer.Exit(code=EXIT_OK if result.ok else EXIT_ERROR)
