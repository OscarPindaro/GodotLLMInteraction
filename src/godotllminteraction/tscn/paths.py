"""pathlib-style path types for scenes and Godot resources.

`ScenePath` addresses a node inside a scene tree, mirroring tscn's
`parent="..."` convention: the root is ".", its children are "Name", deeper
nodes "Parent/Child". `ResPath` is a `res://` resource path that converts to
and from real filesystem paths given a project root. Both are immutable,
hashable, and support `/` joining like `pathlib.PurePath`.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath


class ScenePath:
    """The address of a node inside a scene tree."""

    __slots__ = ("_segments",)

    def __init__(self, path: str | ScenePath = ".") -> None:
        if isinstance(path, ScenePath):
            self._segments: tuple[str, ...] = path._segments
            return
        segments: list[str] = []
        for part in str(path).strip().split("/"):
            part = part.strip()
            if part in ("", "."):
                continue
            if part == "..":
                raise ValueError(
                    f"scene path {path!r} may not contain '..': tree addresses "
                    "are absolute (relative NodePaths belong in property values)"
                )
            segments.append(part)
        self._segments = tuple(segments)

    @classmethod
    def root(cls) -> ScenePath:
        return cls(".")

    @property
    def segments(self) -> tuple[str, ...]:
        return self._segments

    @property
    def name(self) -> str:
        """The node's own name; '' for the root."""
        return self._segments[-1] if self._segments else ""

    @property
    def parent(self) -> ScenePath:
        """The parent path; the root's parent is the root (as in pathlib)."""
        if not self._segments:
            return self
        result = ScenePath()
        result._segments = self._segments[:-1]
        return result

    def is_root(self) -> bool:
        return not self._segments

    def __truediv__(self, other: str | ScenePath) -> ScenePath:
        other = ScenePath(other)
        result = ScenePath()
        result._segments = self._segments + other._segments
        return result

    def is_within(self, other: str | ScenePath) -> bool:
        """Whether this path is `other` itself or a descendant of it."""
        other = ScenePath(other)
        return self._segments[: len(other._segments)] == other._segments

    def rebase(self, old: str | ScenePath, new: str | ScenePath) -> ScenePath | None:
        """This path with the `old` subtree prefix replaced by `new`;
        None if this path is not inside `old`."""
        old = ScenePath(old)
        if not self.is_within(old):
            return None
        new = ScenePath(new)
        result = ScenePath()
        result._segments = new._segments + self._segments[len(old._segments) :]
        return result

    def node_path_to(self, target: str | ScenePath) -> str:
        """The relative NodePath string ('../Sibling/Child') that points from
        a node at this path to a node at `target`."""
        target = ScenePath(target)
        common = 0
        while (
            common < len(self._segments)
            and common < len(target._segments)
            and self._segments[common] == target._segments[common]
        ):
            common += 1
        parts = [".."] * (len(self._segments) - common) + list(
            target._segments[common:]
        )
        return "/".join(parts) if parts else "."

    def resolve_node_path(self, node_path: str) -> ScenePath | None:
        """The absolute ScenePath a relative NodePath value points at, from a
        node at this path. None when the path is absolute ('/root/...') or
        climbs above the scene root — those reference the runtime tree and
        cannot be resolved offline."""
        if node_path.startswith("/"):
            return None
        segments = list(self._segments)
        for part in node_path.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if not segments:
                    return None
                segments.pop()
            else:
                segments.append(part)
        result = ScenePath()
        result._segments = tuple(segments)
        return result

    def __str__(self) -> str:
        return "/".join(self._segments) if self._segments else "."

    def __repr__(self) -> str:
        return f"ScenePath({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ScenePath):
            return self._segments == other._segments
        if isinstance(other, str):
            return self == ScenePath(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._segments)


class ResPath:
    """A Godot `res://` resource path."""

    __slots__ = ("_path",)

    PREFIX = "res://"

    def __init__(self, path: str | ResPath | PurePosixPath) -> None:
        if isinstance(path, ResPath):
            self._path: PurePosixPath = path._path
            return
        text = str(path)
        if text.startswith(self.PREFIX):
            text = text[len(self.PREFIX) :]
        self._path = PurePosixPath(text.lstrip("/"))

    @property
    def name(self) -> str:
        return self._path.name

    @property
    def stem(self) -> str:
        return self._path.stem

    @property
    def suffix(self) -> str:
        return self._path.suffix

    @property
    def parts(self) -> tuple[str, ...]:
        return self._path.parts

    @property
    def parent(self) -> ResPath:
        return ResPath(self._path.parent)

    def __truediv__(self, other: str) -> ResPath:
        return ResPath(self._path / other)

    def to_filesystem(self, project_root: str | Path) -> Path:
        """The real file this res:// path names, given the directory that
        contains project.godot."""
        return Path(project_root) / self._path

    @classmethod
    def from_filesystem(cls, path: str | Path, project_root: str | Path) -> ResPath:
        """The res:// path for a real file inside the project. `path` may be
        absolute or relative to the current directory; raises ValueError if
        it lies outside `project_root`."""
        resolved = Path(path).resolve()
        root = Path(project_root).resolve()
        return cls(PurePosixPath(resolved.relative_to(root).as_posix()))

    def __str__(self) -> str:
        text = str(self._path)
        return self.PREFIX + ("" if text == "." else text)

    def __repr__(self) -> str:
        return f"ResPath({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ResPath):
            return self._path == other._path
        if isinstance(other, str):
            return self == ResPath(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._path)
