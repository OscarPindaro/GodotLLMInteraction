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
from godotllminteraction.tscn.exceptions import OperationError, TscnError
from godotllminteraction.tscn.godot_check import GodotNotFoundError

app = typer.Typer(help="Godot scene (.tscn) utilities.")

_JSON_OPTION = typer.Option(
    "--json",
    help="Print a machine-readable JSON result on stdout instead of rich output.",
)
_OUTPUT_OPTION = typer.Option(
    "--output", "-o", help="Where to write the result; defaults to in-place."
)
_DRY_RUN_OPTION = typer.Option(
    "--dry-run", help="Show the report and diff without writing."
)
_STRICT_OPTION = typer.Option(
    "--strict/--no-strict",
    help="Whether spec-validation errors abort the operation.",
)
_PROPERTY_OPTION = typer.Option(
    "--property",
    help="A 'key=value' pair (value in Godot literal syntax, e.g. "
    "'position=Vector2(1, 2)'); repeatable.",
)


def _emit_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def _report_payload(report: tscn_lib.ValidationReport) -> list[dict]:
    return [issue.model_dump() for issue in report.issues]


def _parse_properties(pairs: list[str]) -> dict[str, str]:
    properties: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            print_error(f"Invalid --property {pair!r}; expected 'key=value'.")
            raise typer.Exit(code=EXIT_USAGE)
        properties[key] = value
    return properties


def _load_scene_for_edit(scene_path: Path) -> tuple[tscn_lib.Scene, str]:
    if not scene_path.exists():
        print_error(f"Scene file not found: {scene_path}")
        raise typer.Exit(code=EXIT_USAGE)
    try:
        scene = tscn_lib.load_scene(scene_path)
        return scene, tscn_lib.dump_scene(scene)
    except TscnError as exc:
        print_error(str(exc))
        raise typer.Exit(code=EXIT_ERROR) from exc


def _finish_apply(
    result: tscn_lib.ApplyResult,
    *,
    original_text: str,
    input_path: Path | None,
    output: Path | None,
    dry_run: bool,
    json_output: bool,
) -> None:
    """Shared tail for every command that edits a scene: report, diff/write,
    exit code. `input_path` is None only for a brand-new (`create:`) scene."""
    output_path = output or input_path
    if output_path is None:
        print_error("No output destination: pass --output.")
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


def _run_operation(
    scene_path: Path,
    operation: tscn_lib.Operation,
    *,
    output: Path | None,
    dry_run: bool,
    strict: bool,
    json_output: bool,
) -> None:
    """Load `scene_path`, apply one operation, and run it through _finish_apply."""
    scene, original_text = _load_scene_for_edit(scene_path)
    try:
        result = tscn_lib.apply_operations(scene, [operation], strict=strict)
    except OperationError as exc:
        if json_output:
            _emit_json({"ok": False, "error": str(exc)})
        print_error(str(exc))
        raise typer.Exit(code=EXIT_ERROR) from exc
    _finish_apply(
        result,
        original_text=original_text,
        input_path=scene_path,
        output=output,
        dry_run=dry_run,
        json_output=json_output,
    )


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

    output_path = output or (Path(ops.output) if ops.output else None)
    _finish_apply(
        result,
        original_text=original_text,
        input_path=input_path,
        output=output_path,
        dry_run=dry_run,
        json_output=json_output,
    )


@app.command("add-node")
def add_node(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    path: Annotated[str, typer.Argument(help="Scene path of the new node.")],
    type: Annotated[
        Optional[str],
        typer.Option("--type", "-t", help="Godot class of the node."),
    ] = None,
    instance: Annotated[
        Optional[str],
        typer.Option(
            "--instance",
            help='ExtResource("id") literal pointing at a PackedScene, instead of --type.',
        ),
    ] = None,
    property_pairs: Annotated[list[str], _PROPERTY_OPTION] = [],  # noqa: B006
    group: Annotated[
        list[str], typer.Option("--group", help="Node group name; repeatable.")
    ] = [],  # noqa: B006
    index: Annotated[
        Optional[int], typer.Option("--index", help="Position among siblings.")
    ] = None,
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Add a node to the scene tree."""
    operation = tscn_lib.AddNode(
        path=path,
        type=type,
        instance=instance,
        properties=_parse_properties(property_pairs),
        groups=group or None,
        index=index,
    )
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("delete-node")
def delete_node(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    path: Annotated[str, typer.Argument(help="Scene path of the node to delete.")],
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive/--no-recursive",
            help="Also delete descendants; with --no-recursive, a node with "
            "children is an error.",
        ),
    ] = True,
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Delete a node (and, by default, its whole subtree)."""
    operation = tscn_lib.DeleteNode(path=path, recursive=recursive)
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("update-properties")
def update_properties(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    path: Annotated[str, typer.Argument(help="Scene path of the node.")],
    property_pairs: Annotated[list[str], _PROPERTY_OPTION] = [],  # noqa: B006
    remove: Annotated[
        list[str],
        typer.Option(
            "--remove", help="Property name to drop (revert to default); repeatable."
        ),
    ] = [],  # noqa: B006
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Set and/or remove properties on an existing node."""
    operation = tscn_lib.UpdateProperties(
        path=path, properties=_parse_properties(property_pairs), remove=remove
    )
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("rename-node")
def rename_node(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    path: Annotated[str, typer.Argument(help="Scene path of the node to rename.")],
    new_name: Annotated[str, typer.Argument(help="The node's new name.")],
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Rename a node; descendants, connections, and NodePath values are rewritten."""
    operation = tscn_lib.RenameNode(path=path, new_name=new_name)
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("move-node")
def move_node(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    path: Annotated[str, typer.Argument(help="Scene path of the node to move.")],
    new_parent: Annotated[
        str, typer.Argument(help="Scene path of the new parent ('.' for the root).")
    ],
    index: Annotated[
        Optional[int],
        typer.Option("--index", help="Position among the new siblings."),
    ] = None,
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Reparent a node; descendants, connections, and NodePath values are rewritten."""
    operation = tscn_lib.MoveNode(path=path, new_parent=new_parent, index=index)
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("attach-script")
def attach_script(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    path: Annotated[str, typer.Argument(help="Scene path of the node.")],
    script_path: Annotated[str, typer.Argument(help="res:// path of the .gd script.")],
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Attach a script to a node, reusing or adding the Script ext_resource."""
    operation = tscn_lib.AttachScript(path=path, script_path=script_path)
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("detach-script")
def detach_script(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    path: Annotated[str, typer.Argument(help="Scene path of the node.")],
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Remove a node's script (and the Script ext_resource, if unreferenced elsewhere)."""
    operation = tscn_lib.DetachScript(path=path)
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("add-ext-resource")
def add_ext_resource(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    type: Annotated[
        str, typer.Argument(help="Godot resource class, e.g. 'Texture2D'.")
    ],
    res_path: Annotated[str, typer.Argument(help="res:// path of the external file.")],
    id: Annotated[
        Optional[str],
        typer.Option(
            "--id", help="Scene-local resource id; leave unset for a generated one."
        ),
    ] = None,
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Declare an external resource the scene can reference."""
    operation = tscn_lib.AddExtResource(type=type, path=res_path, id=id)
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("create-sub-resource")
def create_sub_resource(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    type: Annotated[
        str, typer.Argument(help="Godot Resource subclass, e.g. 'RectangleShape2D'.")
    ],
    property_pairs: Annotated[list[str], _PROPERTY_OPTION] = [],  # noqa: B006
    id: Annotated[
        Optional[str],
        typer.Option(
            "--id", help="Scene-local resource id; leave unset for a generated one."
        ),
    ] = None,
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Embed a resource inside the scene file."""
    operation = tscn_lib.CreateSubResource(
        type=type, id=id, properties=_parse_properties(property_pairs)
    )
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("connect-signal")
def connect_signal(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    from_: Annotated[
        str,
        typer.Option("--from", help="Scene path of the node emitting the signal."),
    ],
    to: Annotated[
        str, typer.Option("--to", help="Scene path of the node whose method is called.")
    ],
    signal: Annotated[str, typer.Option("--signal", help="Signal name.")],
    method: Annotated[
        str,
        typer.Option("--method", help="Receiving method name on the target's script."),
    ],
    flags: Annotated[
        Optional[int], typer.Option("--flags", help="Godot ConnectFlags bitmask.")
    ] = None,
    binds: Annotated[
        Optional[str],
        typer.Option("--binds", help="Extra bound arguments, e.g. '[1, \"two\"]'."),
    ] = None,
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Add a connection wiring a signal to a method on another node."""
    operation = tscn_lib.ConnectSignal(
        **{"from": from_, "to": to, "signal": signal, "method": method},
        flags=flags,
        binds=binds,
    )
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


@app.command("disconnect-signal")
def disconnect_signal(
    scene_path: Annotated[
        Path, typer.Argument(help="Scene file to edit.", exists=True, dir_okay=False)
    ],
    from_: Annotated[
        str, typer.Option("--from", help="Scene path of the emitting node.")
    ],
    to: Annotated[str, typer.Option("--to", help="Scene path of the target node.")],
    signal: Annotated[str, typer.Option("--signal", help="Signal name.")],
    method: Annotated[str, typer.Option("--method", help="Receiving method name.")],
    output: Annotated[Optional[Path], _OUTPUT_OPTION] = None,
    dry_run: Annotated[bool, _DRY_RUN_OPTION] = False,
    strict: Annotated[bool, _STRICT_OPTION] = True,
    json_output: Annotated[bool, _JSON_OPTION] = False,
) -> None:
    """Remove a matching signal connection."""
    operation = tscn_lib.DisconnectSignal(
        **{"from": from_, "to": to, "signal": signal, "method": method}
    )
    _run_operation(
        scene_path,
        operation,
        output=output,
        dry_run=dry_run,
        strict=strict,
        json_output=json_output,
    )


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
            help="A .tscn file (res:// or a normal filesystem path), or "
            "'project.godot' to validate the whole project."
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
