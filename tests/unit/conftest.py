from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def load_module(tmp_path: Path):
    """Factory fixture: write generated source to a real file and import it as a module.

    Needed because `from __future__ import annotations` makes pydantic field
    annotations lazy string forward-refs; resolving them requires a real
    module in sys.modules, which a bare exec()-with-dict namespace can't provide.
    """

    def _load(source: str):
        name = f"_generated_{uuid.uuid4().hex}"
        path = tmp_path / f"{name}.py"
        path.write_text(source)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        # Left registered in sys.modules (not cleaned up): pydantic resolves
        # `from __future__ import annotations` forward refs lazily by looking up
        # `sys.modules[cls.__module__]`, which can happen after this function returns.
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    return _load
