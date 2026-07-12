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
                    binary = shutil.which(line) or line
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


def godot_binary_path(version: str) -> str | None:
    """Find the Godot binary for a specific version."""
    for v, path in discover_godot_binaries():
        if v == version:
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
    """List of installed Godot version strings, sorted."""
    return [v for v, _ in discover_godot_binaries()]


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
