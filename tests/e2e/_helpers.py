"""Shared helpers for e2e tests (importable, unlike conftest.py)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_VERSION_RE = re.compile(r"godot-(\d+\.\d+(?:\.\d+)?)-stable")


def discover_godot_binaries() -> list[tuple[str, str]]:
    """Discover installed Godot binaries via ``godotctl list``."""
    binaries: list[tuple[str, str]] = []

    godotctl = shutil.which("godotctl")
    if godotctl is not None:
        result = subprocess.run(
            [godotctl, "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                match = _VERSION_RE.search(line)
                if match:
                    version = match.group(1)
                    binary_name = match.group(0)
                    binary = shutil.which(binary_name) or binary_name
                    if Path(binary).is_file():
                        binaries.append((version, binary))
            binaries.sort(key=lambda v: [int(x) for x in v[0].split(".")])
            return binaries

    godot = shutil.which("godot")
    if godot is not None:
        result = subprocess.run(
            [godot, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version = result.stdout.strip().split(".")[0:3]
            version_str = ".".join(v.split("-")[0] for v in version[:3])
            binaries.append((version_str, godot))

    return binaries


def _normalize_version(v: str) -> str:
    """Strip trailing .0 patch version so '4.7.0' matches '4.7'."""
    parts = v.split(".")
    if len(parts) == 3 and parts[2] == "0":
        return ".".join(parts[:2])
    return v


def godot_binary_path(version: str) -> str | None:
    """Find the Godot binary for a specific version.

    Matches both ``4.7`` and ``4.7.0`` — Godot binaries for x.y.0 releases
    are often named ``godot-x.y-stable`` (without the patch).
    """
    target = _normalize_version(version)
    for v, path in discover_godot_binaries():
        if _normalize_version(v) == target:
            return path
    return None


def discover_all_versions() -> list[str]:
    """Read all versions from godot-versions.txt via the stable paths module."""
    from godotllminteraction.paths import GODOT_VERSIONS_FILE

    if not GODOT_VERSIONS_FILE.exists():
        return []
    return [
        line.strip()
        for line in GODOT_VERSIONS_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def installed_godot_versions() -> list[str]:
    """List of installed Godot version strings (normalized to x.y.z), sorted."""
    result = []
    for v, _ in discover_godot_binaries():
        parts = v.split(".")
        if len(parts) == 2:
            result.append(f"{v}.0")
        else:
            result.append(v)
    return result


def dump_extension_api(binary: str, out_dir: Path) -> Path:
    """Dump extension_api.json from a Godot binary into out_dir."""
    result = subprocess.run(
        [binary, "--headless", "--dump-extension-api", "--quit"],
        cwd=out_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    dump_path = out_dir / "extension_api.json"
    if result.returncode != 0 or not dump_path.exists():
        raise RuntimeError(
            f"Godot failed to dump extension_api.json (exit code {result.returncode}):\n"
            f"{result.stderr}"
        )
    return dump_path


def import_project(binary: str, project_dir: Path) -> None:
    """Run Godot --headless --import to generate .godot/ and .import files."""
    subprocess.run(
        [binary, "--headless", "--import", "--quit", "--path", str(project_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )


def check_scene(
    binary: str, project_dir: Path, scene_name: str
) -> subprocess.CompletedProcess:
    """Run Godot --check-only on a scene, importing the project first if needed."""
    if not (project_dir / ".godot").exists():
        import_project(binary, project_dir)
    return subprocess.run(
        [
            binary,
            "--headless",
            "--check-only",
            "--path",
            str(project_dir),
            "--quit",
            scene_name,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


def output_scene_path(scenes_dir: Path, scene_name: str, suffix: str = "_e2e") -> Path:
    """Return a temp output path inside the fixture project dir.

    The file does *not* need to exist — CLI ``--output`` writes it there.
    Living inside the fixture dir means Godot can find ``project.godot``
    and resources.
    """
    stem = scenes_dir / scene_name
    return stem.with_name(f"{stem.stem}{suffix}.tscn")


def cleanup_test_scenes(scenes_dir: Path) -> None:
    """Remove any ``*_e2e.tscn`` files left behind in *scenes_dir*."""
    for f in scenes_dir.glob("*_e2e.tscn"):
        f.unlink(missing_ok=True)


def run_cli_edit(args: list[str]):
    """Invoke a ``gli tscn <args>`` command via CliRunner.

    ``args`` is the full list after ``tscn``, e.g. ``["add-node", str(path),
    "TempNode", "--type", "Node"]``.
    """
    from typer.testing import CliRunner

    from godotllminteraction.cli import app

    runner = CliRunner()
    return runner.invoke(app, ["tscn", *args])


def validate_both(
    scene_path: Path,
    scenes_dir: Path,
    binary: str,
) -> tuple[int, int]:
    """Run both CLI ``validate`` and Godot ``--check-only`` on *scene_path*.

    Returns ``(cli_exit, godot_exit)`` so callers can assert agreement.
    """
    cli_result = run_cli_edit(
        [
            "validate",
            str(scene_path),
            "--project",
            str(scenes_dir),
            "--godot",
            binary,
        ],
    )
    godot_result = check_scene(binary, scenes_dir, scene_path.name)
    return cli_result.exit_code, godot_result.returncode
