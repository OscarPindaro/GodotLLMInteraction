from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

GODOT_BINARY_ENV_VAR = "GODOT_BINARY"
DEFAULT_GODOT_BINARY = "godot"


@pytest.fixture(scope="session")
def godot_binary() -> str:
    """Resolve the Godot executable to use for integration tests.

    Defaults to "godot" on PATH; override with the GODOT_BINARY env var
    (either a binary name to resolve on PATH, or an absolute path).
    """
    binary = os.environ.get(GODOT_BINARY_ENV_VAR, DEFAULT_GODOT_BINARY)
    resolved = shutil.which(binary) or (binary if os.path.isfile(binary) else None)
    if resolved is None:
        pytest.skip(
            f"Godot executable not found: {binary!r} "
            f"(set {GODOT_BINARY_ENV_VAR} to override)"
        )
    return resolved


@pytest.fixture(scope="session")
def extension_api_json(
    godot_binary: str, tmp_path_factory: pytest.TempPathFactory
) -> dict:
    """Dump extension_api.json fresh from the Godot binary and load it as a dict."""
    out_dir = tmp_path_factory.mktemp("extension_api")
    result = subprocess.run(
        [godot_binary, "--headless", "--dump-extension-api", "--quit"],
        cwd=out_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    dump_path = out_dir / "extension_api.json"
    if result.returncode != 0 or not dump_path.exists():
        pytest.fail(
            f"Godot failed to dump extension_api.json (exit code {result.returncode}):\n"
            f"{result.stderr}"
        )
    return json.loads(dump_path.read_text())
