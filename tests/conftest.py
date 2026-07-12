"""Root conftest — auto-applies tier markers (unit/integration/e2e) by directory."""

from __future__ import annotations

from pathlib import Path

import pytest

_TESTS_ROOT = Path(__file__).resolve().parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-mark tests with tier markers based on their directory."""
    for item in items:
        parts = Path(item.fspath).resolve().relative_to(_TESTS_ROOT).parts
        if "unit" in parts:
            item.add_marker(pytest.mark.unit)
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
        if "e2e" in parts:
            item.add_marker(pytest.mark.e2e)
