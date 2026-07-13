"""Resolve user-defined ``class_name`` types to base type + script path.

Scans ``.gd`` files under a Godot project for ``class_name`` and ``extends``
declarations, producing a lightweight mapping that :mod:`scene_builder` uses to
turn a declarative node spec into the correct ``AddNode`` + ``AttachScript``
operation pair.

The scan is regex-based and intentionally lightweight — no Godot binary
required.  Companion ``.uid`` files (Godot 4.4+) are read when present so the
caller can emit ``uid="..."`` in ext_resource entries if it ever needs to.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from godotllminteraction.tscn.paths import ResPath

_DEFAULT_BASE = "RefCounted"
"""Default base class when a GDScript omits ``extends`` (confirmed in Godot docs)."""

_CLASS_NAME_RE = re.compile(r"^\s*class_name\s+(\w+)", re.MULTILINE)
_EXTENDS_RE = re.compile(r'\bextends\s+("[^"]+"|[\w.]+)')


class ClassInfo(BaseModel):
    """Minimal description of a user-defined GDScript class."""

    class_name: str
    base_type: str
    script_path: str
    uid: str | None = None


class ClassResolver:
    """Lazy, rescan-on-miss registry of ``class_name`` scripts in a project."""

    def __init__(self, project_path: Path) -> None:
        self._project_path = Path(project_path)
        self._cache: dict[str, ClassInfo] | None = None

    # ------------------------------------------------------------------ scan

    def _scan(self) -> dict[str, ClassInfo]:
        result: dict[str, ClassInfo] = {}
        for gd_file in self._project_path.rglob("*.gd"):
            try:
                text = gd_file.read_text(encoding="utf-8")
            except OSError:
                continue
            cn_match = _CLASS_NAME_RE.search(text)
            if cn_match is None:
                continue
            class_name = cn_match.group(1)
            ext_match = _EXTENDS_RE.search(text)
            if ext_match is not None:
                raw = ext_match.group(1)
                base_type = raw.strip('"')
            else:
                base_type = _DEFAULT_BASE
            try:
                res_path = str(ResPath.from_filesystem(gd_file, self._project_path))
            except ValueError:
                res_path = f"res://{gd_file.relative_to(self._project_path)}"
            uid = self._read_uid(gd_file)
            result[class_name] = ClassInfo(
                class_name=class_name,
                base_type=base_type,
                script_path=res_path,
                uid=uid,
            )
        return result

    @staticmethod
    def _read_uid(gd_file: Path) -> str | None:
        uid_file = gd_file.with_suffix(gd_file.suffix + ".uid")
        if not uid_file.is_file():
            return None
        text = uid_file.read_text(encoding="utf-8").strip()
        if text.startswith("uid://"):
            return text
        return None

    # ----------------------------------------------------------------- public

    def _ensure_cache(self) -> dict[str, ClassInfo]:
        if self._cache is None:
            self._cache = self._scan()
        return self._cache

    def resolve(self, name: str) -> ClassInfo | None:
        """Return ``ClassInfo`` for *name*, rescanning once on miss."""
        cache = self._ensure_cache()
        info = cache.get(name)
        if info is not None:
            return info
        # Rescan: the project may have gained a new .gd file.
        self._cache = self._scan()
        return self._cache.get(name)

    def all_classes(self) -> dict[str, ClassInfo]:
        return dict(self._ensure_cache())
