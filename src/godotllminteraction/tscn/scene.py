"""Data model for a parsed .tscn scene.

Every entry keeps a generic insertion-ordered `attributes` dict rather than
named fields, so attributes we don't interpret (`unique_id`, `index`,
`owner`, future additions) survive parse -> edit -> write untouched. Typed
accessors are provided for the attributes the library does interpret.

Nodes are addressed by *scene path*, mirroring tscn's own `parent=`
convention: the root node's path is ".", its children have path "<name>"
(their `parent` attribute is "."), and deeper nodes have path
"<parent-path>/<name>".
"""

from __future__ import annotations

from pydantic import BaseModel

from godotllminteraction.tscn.paths import ScenePath
from godotllminteraction.tscn.values import GodotValue, GString


def _string_attr(attributes: dict[str, GodotValue], key: str) -> str | None:
    value = attributes.get(key)
    return value.value if isinstance(value, GString) else None


class SceneHeader(BaseModel):
    """The [gd_scene ...] file descriptor."""

    attributes: dict[str, GodotValue] = {}

    @property
    def uid(self) -> str | None:
        return _string_attr(self.attributes, "uid")


class ExtResourceEntry(BaseModel):
    """[ext_resource type=... path=... id=...] — a reference to an external file."""

    attributes: dict[str, GodotValue] = {}

    @property
    def type(self) -> str | None:
        return _string_attr(self.attributes, "type")

    @property
    def path(self) -> str | None:
        return _string_attr(self.attributes, "path")

    @property
    def id(self) -> str | None:
        return _string_attr(self.attributes, "id")


class SubResourceEntry(BaseModel):
    """[sub_resource type=... id=...] — a resource embedded in the scene file."""

    attributes: dict[str, GodotValue] = {}
    properties: dict[str, GodotValue] = {}

    @property
    def type(self) -> str | None:
        return _string_attr(self.attributes, "type")

    @property
    def id(self) -> str | None:
        return _string_attr(self.attributes, "id")


class NodeEntry(BaseModel):
    """[node name=... type=... parent=...] plus its property lines.

    `type` is None for nodes instanced from another scene (`instance=`) and
    for override entries of an instanced child. Property keys are stored
    exactly as spelled in the file (including quoting, if any).
    """

    attributes: dict[str, GodotValue] = {}
    properties: dict[str, GodotValue] = {}

    @property
    def name(self) -> str:
        name = _string_attr(self.attributes, "name")
        return name if name is not None else ""

    @property
    def type(self) -> str | None:
        return _string_attr(self.attributes, "type")

    @property
    def parent(self) -> str | None:
        """The parent path attribute; None only for the scene root."""
        return _string_attr(self.attributes, "parent")

    @property
    def is_instance(self) -> bool:
        return "instance" in self.attributes

    def path(self) -> str:
        parent = self.parent
        if parent is None:
            return "."
        if parent == ".":
            return self.name
        return f"{parent}/{self.name}"


class ConnectionEntry(BaseModel):
    """[connection signal=... from=... to=... method=...]."""

    attributes: dict[str, GodotValue] = {}

    @property
    def signal(self) -> str | None:
        return _string_attr(self.attributes, "signal")

    @property
    def from_path(self) -> str | None:
        return _string_attr(self.attributes, "from")

    @property
    def to_path(self) -> str | None:
        return _string_attr(self.attributes, "to")

    @property
    def method(self) -> str | None:
        return _string_attr(self.attributes, "method")


class GenericSection(BaseModel):
    """Any section type the library doesn't interpret (e.g. [editable path=...]).

    Preserved verbatim and written after all known sections.
    """

    name: str
    attributes: dict[str, GodotValue] = {}
    properties: dict[str, GodotValue] = {}


def normalize_path(path: str) -> str:
    """Normalize a user-supplied scene path ('' and '.' both mean the root)."""
    return str(ScenePath(path))


def parent_path_of(path: str) -> str | None:
    """The scene path of a path's parent; None for the root itself."""
    scene_path = ScenePath(path)
    return None if scene_path.is_root() else str(scene_path.parent)


class Scene(BaseModel):
    """A parsed .tscn file, in file order (nodes: parent before child)."""

    header: SceneHeader = SceneHeader()
    ext_resources: list[ExtResourceEntry] = []
    sub_resources: list[SubResourceEntry] = []
    nodes: list[NodeEntry] = []
    connections: list[ConnectionEntry] = []
    others: list[GenericSection] = []

    def root(self) -> NodeEntry | None:
        for node in self.nodes:
            if node.parent is None:
                return node
        return None

    def node(self, path: str) -> NodeEntry | None:
        path = normalize_path(path)
        for node in self.nodes:
            if node.path() == path:
                return node
        return None

    def node_index(self, path: str) -> int | None:
        path = normalize_path(path)
        for i, node in enumerate(self.nodes):
            if node.path() == path:
                return i
        return None

    def children(self, path: str) -> list[NodeEntry]:
        path = normalize_path(path)
        return [node for node in self.nodes if node.parent == path]

    def subtree(self, path: str) -> list[NodeEntry]:
        """The node at `path` and all its descendants, in file order."""
        path = normalize_path(path)
        if path == ".":
            return list(self.nodes)
        prefix = path + "/"
        return [
            node
            for node in self.nodes
            if node.path() == path or node.path().startswith(prefix)
        ]

    def ext_resource(self, resource_id: str) -> ExtResourceEntry | None:
        for entry in self.ext_resources:
            if entry.id == resource_id:
                return entry
        return None

    def sub_resource(self, resource_id: str) -> SubResourceEntry | None:
        for entry in self.sub_resources:
            if entry.id == resource_id:
                return entry
        return None
