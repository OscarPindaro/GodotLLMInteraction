"""Cross-platform KB storage: path resolution, entry CRUD, and pre-embedded index.

The index (index.npz) stores a flat numpy matrix of question embeddings.
Each row corresponds to one question of one entry.  The mapping from row
index → (entry_id, question_index) is stored alongside as a JSON sidecar.

On register: embed the new entry's questions, append rows to the index.
On remove: rebuild the index from remaining entries (rare operation).
On search: load the index, embed only the query, do a single matmul.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

from godotllminteraction.kb.types import KbEntry


def _project_slug(project_path: Path) -> str:
    resolved = str(project_path.resolve())
    digest = hashlib.sha256(resolved.encode()).hexdigest()[:8]
    return f"{project_path.name}_{digest}"


def resolve_kb_folder(project_path: Path | None = None) -> Path:
    """Resolve the KB folder for a project.

    Honors GLI_KB_LOCATION env var (absolute path override).
    Otherwise uses platform-appropriate data directory.
    """
    override = os.environ.get("GLI_KB_LOCATION")
    if override:
        return Path(override)

    project_path = project_path or Path.cwd()
    slug = _project_slug(project_path)

    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"

    return base / "gli" / slug / "kb"


def _entries_dir(kb_folder: Path) -> Path:
    return kb_folder / "entries"


def save_entry(kb_folder: Path, entry: KbEntry) -> None:
    entries_dir = _entries_dir(kb_folder)
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / f"{entry.id}.json").write_text(entry.model_dump_json(indent=2))


def load_entry(kb_folder: Path, entry_id: str) -> KbEntry | None:
    p = _entries_dir(kb_folder) / f"{entry_id}.json"
    if not p.exists():
        return None
    return KbEntry.model_validate_json(p.read_text())


def list_entries(kb_folder: Path) -> list[KbEntry]:
    entries_dir = _entries_dir(kb_folder)
    if not entries_dir.exists():
        return []
    result: list[KbEntry] = []
    for p in sorted(entries_dir.glob("*.json")):
        try:
            result.append(KbEntry.model_validate_json(p.read_text()))
        except Exception:
            continue
    return result


def remove_entry(kb_folder: Path, entry_id: str) -> bool:
    p = _entries_dir(kb_folder) / f"{entry_id}.json"
    if not p.exists():
        return False
    p.unlink()
    return True


def clear_kb(kb_folder: Path) -> int:
    """Remove all entries and the index. Returns count removed."""
    entries_dir = _entries_dir(kb_folder)
    count = 0
    if entries_dir.exists():
        for p in entries_dir.glob("*.json"):
            p.unlink()
            count += 1
    idx = index_path(kb_folder)
    if idx.exists():
        idx.unlink()
    sidecar = _index_sidecar_path(kb_folder)
    if sidecar.exists():
        sidecar.unlink()
    return count


def index_path(kb_folder: Path) -> Path:
    return kb_folder / "index.npz"


def _index_sidecar_path(kb_folder: Path) -> Path:
    return kb_folder / "index_meta.json"


def load_index(kb_folder: Path) -> tuple[np.ndarray, list[tuple[str, int]]] | None:
    """Load the pre-embedded index.

    Returns (embeddings_matrix, mapping) where mapping[i] = (entry_id, question_index).
        Returns None if no index exists.
    """
    idx = index_path(kb_folder)
    sidecar = _index_sidecar_path(kb_folder)
    if not idx.exists() or not sidecar.exists():
        return None
    data = np.load(idx)
    embeddings = data["embeddings"]
    mapping = json.loads(sidecar.read_text())
    mapping_tuples = [(m[0], m[1]) for m in mapping]
    return embeddings, mapping_tuples


def rebuild_index(
    kb_folder: Path, embeddings: np.ndarray, mapping: list[tuple[str, int]]
) -> None:
    """Save the full index to disk (overwrites)."""
    kb_folder.mkdir(parents=True, exist_ok=True)
    np.savez(index_path(kb_folder), embeddings=embeddings)
    _index_sidecar_path(kb_folder).write_text(json.dumps([[e, q] for e, q in mapping]))


def append_to_index(kb_folder: Path, entry_id: str, new_embeddings: np.ndarray) -> None:
    """Append new question embeddings for a single entry to the index."""
    existing = load_index(kb_folder)
    n_new = new_embeddings.shape[0]
    new_mapping = [(entry_id, i) for i in range(n_new)]
    if existing is None:
        rebuild_index(kb_folder, new_embeddings, new_mapping)
        return
    old_emb, old_map = existing
    combined = np.vstack([old_emb, new_embeddings])
    combined_map = old_map + new_mapping
    rebuild_index(kb_folder, combined, combined_map)


def remove_from_index(kb_folder: Path, entry_id: str) -> None:
    """Remove an entry's rows from the index. Rebuilds from remaining entries."""
    existing = load_index(kb_folder)
    if existing is None:
        return
    embeddings, mapping = existing
    keep_rows = [i for i, (eid, _) in enumerate(mapping) if eid != entry_id]
    if len(keep_rows) == len(mapping):
        return
    if not keep_rows:
        idx = index_path(kb_folder)
        sidecar = _index_sidecar_path(kb_folder)
        if idx.exists():
            idx.unlink()
        if sidecar.exists():
            sidecar.unlink()
        return
    new_emb = embeddings[keep_rows]
    new_map = [mapping[i] for i in keep_rows]
    rebuild_index(kb_folder, new_emb, new_map)
