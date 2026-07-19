"""Resolve user-defined ``class_name`` types to base type + script path.

Scans ``.gd`` files under a Godot project for ``class_name`` and ``extends``
declarations, producing a lightweight mapping that :mod:`scene_builder` uses to
turn a declarative node spec into the correct ``AddNode`` + ``AttachScript``
operation pair.

The scan is regex-based and intentionally lightweight — no Godot binary
required.  Companion ``.uid`` files (Godot 4.4+) are read when present so the
caller can emit ``uid="..."`` in ext_resource entries if it ever needs to.

``@export`` variable declarations are also collected so that validation can
confirm a property is script-exported (suppressing the "not in spec" warning).
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
# Matches @export var <name>, @export_range(...) var <name>, etc.
_EXPORT_RE = re.compile(r"@export(?:\([^)]*\))?\s+var\s+(\w+)", re.MULTILINE)


class ClassInfo(BaseModel):
    """Minimal description of a user-defined GDScript class."""

    class_name: str | None = None
    base_type: str
    script_path: str
    uid: str | None = None
    exported_vars: list[str] = []


class ClassResolver:
    """Lazy, rescan-on-miss registry of ``class_name`` scripts in a project."""

    def __init__(self, project_path: Path) -> None:
        self._project_path = Path(project_path)
        self._cache: dict[str, ClassInfo] | None = None
        self._by_path: dict[str, ClassInfo] | None = None

    # ------------------------------------------------------------------ scan

    def _scan(self) -> tuple[dict[str, ClassInfo], dict[str, ClassInfo]]:
        by_name: dict[str, ClassInfo] = {}
        by_path: dict[str, ClassInfo] = {}
        for gd_file in self._project_path.rglob("*.gd"):
            try:
                text = gd_file.read_text(encoding="utf-8")
            except OSError:
                continue
            cn_match = _CLASS_NAME_RE.search(text)
            class_name = cn_match.group(1) if cn_match is not None else None
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
            exported_vars = _EXPORT_RE.findall(text)
            info = ClassInfo(
                class_name=class_name,
                base_type=base_type,
                script_path=res_path,
                uid=uid,
                exported_vars=exported_vars,
            )
            by_path[res_path] = info
            if class_name is not None:
                by_name[class_name] = info
        return by_name, by_path

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
            self._cache, self._by_path = self._scan()
        return self._cache

    def resolve(self, name: str) -> ClassInfo | None:
        """Return ``ClassInfo`` for *name*, rescanning once on miss."""
        cache = self._ensure_cache()
        info = cache.get(name)
        if info is not None:
            return info
        # Rescan: the project may have gained a new .gd file.
        self._cache, self._by_path = self._scan()
        return self._cache.get(name)

    def resolve_by_path(self, script_path: str) -> ClassInfo | None:
        """Return ``ClassInfo`` for a ``res://`` script path."""
        self._ensure_cache()
        info = self._by_path.get(script_path) if self._by_path else None
        if info is not None:
            return info
        # Rescan on miss.
        self._cache, self._by_path = self._scan()
        return self._by_path.get(script_path) if self._by_path else None

    def all_classes(self) -> dict[str, ClassInfo]:
        return dict(self._ensure_cache())
