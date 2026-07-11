"""Locate the Godot executable and run the editor's scene check.

Discovery precedence: explicit argument -> GODOT_BINARY env var -> `godot` /
`godot4` on PATH -> common per-OS install locations. Failures carry the full
list of attempted locations so the fix (set GODOT_BINARY or pass --godot) is
obvious from the message alone.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel

from godotllminteraction.tscn.exceptions import TscnError


class GodotNotFoundError(TscnError):
    def __init__(self, attempts: list[str]) -> None:
        self.attempts = attempts
        detail = "\n".join(f"  - {a}" for a in attempts)
        super().__init__(
            "Could not find a Godot executable. Tried:\n"
            f"{detail}\n"
            "Set the GODOT_BINARY environment variable or pass --godot "
            "with the path to your Godot 4 executable."
        )


def _common_locations() -> list[Path]:
    if sys.platform == "darwin":
        return [
            Path("/Applications/Godot.app/Contents/MacOS/Godot"),
            Path.home() / "Applications/Godot.app/Contents/MacOS/Godot",
        ]
    if sys.platform.startswith("win"):
        local_app_data = os.environ.get("LOCALAPPDATA")
        candidates = []
        if local_app_data:
            candidates.append(Path(local_app_data) / "Godot" / "godot.exe")
        candidates.extend(
            Path(root) / "Godot" / "godot.exe"
            for root in ("C:/Program Files", "C:/Program Files (x86)")
        )
        return candidates
    return [
        Path("/usr/local/bin/godot"),
        Path("/usr/bin/godot"),
        Path.home() / ".local/bin/godot",
        Path("/var/lib/flatpak/exports/bin/org.godotengine.Godot"),
    ]


def find_godot(explicit: str | None = None) -> str:
    """Absolute path to a Godot executable, or raise GodotNotFoundError."""
    attempts: list[str] = []

    if explicit:
        resolved = shutil.which(explicit) or explicit
        if Path(resolved).is_file():
            return str(resolved)
        raise GodotNotFoundError([f"--godot argument: {explicit!r} (not found)"])

    env_binary = os.environ.get("GODOT_BINARY")
    if env_binary:
        resolved = shutil.which(env_binary) or env_binary
        if Path(resolved).is_file():
            return str(resolved)
        attempts.append(f"GODOT_BINARY={env_binary!r} (not found)")
    else:
        attempts.append("GODOT_BINARY environment variable (not set)")

    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return found
        attempts.append(f"{name!r} on PATH (not found)")

    for candidate in _common_locations():
        if candidate.is_file():
            return str(candidate)
        attempts.append(f"{candidate} (not found)")

    raise GodotNotFoundError(attempts)


class GodotCheckResult(BaseModel):
    ok: bool
    command: list[str]
    exit_code: int
    output: str


def check_scene(
    target: str,
    *,
    project_dir: Path = Path("."),
    godot: str | None = None,
    timeout: float = 120,
) -> GodotCheckResult:
    """Run Godot's own validation on a scene (or `project.godot` for a full
    import check). `target` is a res:// path or a path relative to the
    project directory."""
    executable = find_godot(godot)
    if str(target).endswith("project.godot"):
        command = [
            executable,
            "--headless",
            "--import",
            "--quit",
            "--path",
            str(project_dir),
        ]
    else:
        command = [
            executable,
            "--headless",
            "--check-only",
            "--quit",
            "--path",
            str(project_dir),
            str(target),
        ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    return GodotCheckResult(
        ok=completed.returncode == 0,
        command=command,
        exit_code=completed.returncode,
        output=(completed.stdout + completed.stderr).strip(),
    )
