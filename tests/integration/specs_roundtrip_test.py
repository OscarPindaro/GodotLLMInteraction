from __future__ import annotations

import importlib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.specs]

SPECIFICATIONS_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "godotllminteraction"
    / "specifications"
)


def _discover_version_packages() -> list[str]:
    """Find all version packages (vX_Y_Z) in the specifications directory."""
    if not SPECIFICATIONS_ROOT.is_dir():
        return []
    packages = []
    for d in SPECIFICATIONS_ROOT.iterdir():
        if d.is_dir() and d.name.startswith("v") and (d / "spec.py").exists():
            packages.append(d.name)
    return sorted(packages)


_VERSION_PACKAGES = _discover_version_packages()


def _get_specification_class(version_pkg: str):
    """Import the Specification class from a version package."""
    module = importlib.import_module(
        f"godotllminteraction.specifications.{version_pkg}.spec"
    )
    suffix = version_pkg[1:] if version_pkg.startswith("v") else version_pkg
    class_name = f"Specification{suffix}"
    return getattr(module, class_name)


@pytest.mark.parametrize("version_pkg", _VERSION_PACKAGES)
def test_specification_round_trips_extension_api_json(
    extension_api_json: dict, version_pkg: str
) -> None:
    """Each version's Specification model should round-trip extension_api.json."""
    SpecClass = _get_specification_class(version_pkg)
    spec = SpecClass(**extension_api_json)
    dumped = spec.model_dump(mode="json", exclude_unset=True)
    assert dumped == extension_api_json
