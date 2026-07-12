"""Tests for KB storage — path resolution, entry CRUD, index management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from godotllminteraction.kb.storage import (
    _project_slug,
    append_to_index,
    clear_kb,
    index_path,
    _index_sidecar_path,
    list_entries,
    load_entry,
    load_index,
    rebuild_index,
    remove_entry,
    remove_from_index,
    resolve_kb_folder,
    save_entry,
)
from godotllminteraction.kb.types import KbEntry

pytestmark = [pytest.mark.kb]


@pytest.fixture
def kb_folder(tmp_path: Path) -> Path:
    """Isolated KB folder for each test."""
    d = tmp_path / "kb"
    d.mkdir()
    return d


@pytest.fixture
def sample_entry() -> KbEntry:
    return KbEntry.create(
        questions=["How to add a node?", "How to create a scene?"],
        answer_text="Use add_node tool.",
    )


class TestProjectSlug:
    def test_slug_contains_project_name(self, tmp_path: Path):
        slug = _project_slug(tmp_path)
        assert tmp_path.name in slug

    def test_slug_contains_hash_suffix(self, tmp_path: Path):
        slug = _project_slug(tmp_path)
        parts = slug.rsplit("_", 1)
        assert len(parts) == 2
        assert len(parts[1]) == 8

    def test_different_paths_produce_different_slugs(self, tmp_path: Path):
        a = tmp_path / "project_a"
        b = tmp_path / "project_b"
        a.mkdir()
        b.mkdir()
        assert _project_slug(a) != _project_slug(b)


class TestResolveKbFolder:
    def test_gli_kb_location_override(self, tmp_path: Path):
        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(tmp_path / "custom_kb")}):
            result = resolve_kb_folder(Path("/fake/project"))
            assert result == tmp_path / "custom_kb"

    def test_gli_kb_location_takes_precedence_over_platform(self, tmp_path: Path):
        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(tmp_path / "override")}):
            result = resolve_kb_folder()
            assert result == tmp_path / "override"

    def test_linux_path_uses_xdg(self, tmp_path: Path):
        with (
            patch.dict(
                os.environ, {"GLI_KB_LOCATION": "", "XDG_DATA_HOME": str(tmp_path)}
            ),
            patch("sys.platform", "linux"),
        ):
            result = resolve_kb_folder(Path("/home/user/myproject"))
            assert str(result).startswith(str(tmp_path))
            assert "gli" in result.parts


class TestEntryCRUD:
    def test_save_and_load_entry(self, kb_folder: Path, sample_entry: KbEntry):
        save_entry(kb_folder, sample_entry)
        loaded = load_entry(kb_folder, sample_entry.id)
        assert loaded is not None
        assert loaded.questions == sample_entry.questions
        assert loaded.answer_text == sample_entry.answer_text

    def test_load_nonexistent_returns_none(self, kb_folder: Path):
        assert load_entry(kb_folder, "nonexistent_id") is None

    def test_list_entries_returns_all(self, kb_folder: Path):
        e1 = KbEntry.create(questions=["q1"], answer_text="a1")
        e2 = KbEntry.create(questions=["q2"], answer_text="a2")
        save_entry(kb_folder, e1)
        save_entry(kb_folder, e2)
        entries = list_entries(kb_folder)
        assert len(entries) == 2
        ids = {e.id for e in entries}
        assert ids == {e1.id, e2.id}

    def test_list_entries_empty_when_no_entries(self, kb_folder: Path):
        assert list_entries(kb_folder) == []

    def test_list_entries_skips_corrupt_files(self, kb_folder: Path):
        e1 = KbEntry.create(questions=["q1"], answer_text="a1")
        save_entry(kb_folder, e1)
        # Write a corrupt JSON file alongside
        (kb_folder / "entries" / "corrupt.json").write_text("not valid json{{{")
        entries = list_entries(kb_folder)
        assert len(entries) == 1
        assert entries[0].id == e1.id

    def test_remove_entry_returns_true_and_deletes(
        self, kb_folder: Path, sample_entry: KbEntry
    ):
        save_entry(kb_folder, sample_entry)
        assert remove_entry(kb_folder, sample_entry.id) is True
        assert load_entry(kb_folder, sample_entry.id) is None

    def test_remove_nonexistent_returns_false(self, kb_folder: Path):
        assert remove_entry(kb_folder, "nope") is False

    def test_clear_kb_removes_entries_and_index(
        self, kb_folder: Path, sample_entry: KbEntry
    ):
        save_entry(kb_folder, sample_entry)
        # Also create an index
        emb = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        append_to_index(kb_folder, sample_entry.id, emb)
        assert index_path(kb_folder).exists()
        count = clear_kb(kb_folder)
        assert count == 1
        assert not index_path(kb_folder).exists()
        assert not _index_sidecar_path(kb_folder).exists()
        assert list_entries(kb_folder) == []

    def test_clear_kb_on_empty_returns_zero(self, kb_folder: Path):
        assert clear_kb(kb_folder) == 0


class TestIndexManagement:
    def test_load_index_returns_none_when_no_index(self, kb_folder: Path):
        assert load_index(kb_folder) is None

    def test_rebuild_and_load_index(self, kb_folder: Path):
        emb = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        mapping = [("entry_a", 0), ("entry_a", 1)]
        rebuild_index(kb_folder, emb, mapping)
        loaded = load_index(kb_folder)
        assert loaded is not None
        loaded_emb, loaded_map = loaded
        assert loaded_emb.shape == (2, 2)
        assert loaded_map == mapping

    def test_append_to_empty_index(self, kb_folder: Path):
        emb = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
        append_to_index(kb_folder, "entry_a", emb)
        loaded = load_index(kb_folder)
        assert loaded is not None
        loaded_emb, loaded_map = loaded
        assert loaded_emb.shape == (1, 3)
        assert loaded_map == [("entry_a", 0)]

    def test_append_to_existing_index_grows_matrix(self, kb_folder: Path):
        emb1 = np.array([[0.1, 0.2]], dtype=np.float32)
        append_to_index(kb_folder, "entry_a", emb1)
        emb2 = np.array([[0.3, 0.4], [0.5, 0.6]], dtype=np.float32)
        append_to_index(kb_folder, "entry_b", emb2)
        loaded = load_index(kb_folder)
        assert loaded is not None
        loaded_emb, loaded_map = loaded
        assert loaded_emb.shape == (3, 2)
        assert loaded_map == [("entry_a", 0), ("entry_b", 0), ("entry_b", 1)]

    def test_append_multiple_entries_preserves_order(self, kb_folder: Path):
        for i in range(5):
            emb = np.array([[float(i), float(i + 1)]], dtype=np.float32)
            append_to_index(kb_folder, f"entry_{i}", emb)
        loaded = load_index(kb_folder)
        assert loaded is not None
        loaded_emb, loaded_map = loaded
        assert loaded_emb.shape == (5, 2)
        assert loaded_map[0] == ("entry_0", 0)
        assert loaded_map[4] == ("entry_4", 0)

    def test_remove_from_index_filters_rows(self, kb_folder: Path):
        emb_a = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
        append_to_index(kb_folder, "entry_a", emb_a)
        emb_b = np.array([[0.5, 0.6]], dtype=np.float32)
        append_to_index(kb_folder, "entry_b", emb_b)
        remove_from_index(kb_folder, "entry_a")
        loaded = load_index(kb_folder)
        assert loaded is not None
        loaded_emb, loaded_map = loaded
        assert loaded_emb.shape == (1, 2)
        assert loaded_map == [("entry_b", 0)]

    def test_remove_last_entry_deletes_index_files(self, kb_folder: Path):
        emb = np.array([[0.1, 0.2]], dtype=np.float32)
        append_to_index(kb_folder, "entry_a", emb)
        remove_from_index(kb_folder, "entry_a")
        assert not index_path(kb_folder).exists()
        assert not _index_sidecar_path(kb_folder).exists()

    def test_remove_nonexistent_entry_is_noop(self, kb_folder: Path):
        emb = np.array([[0.1, 0.2]], dtype=np.float32)
        append_to_index(kb_folder, "entry_a", emb)
        remove_from_index(kb_folder, "nonexistent")
        loaded = load_index(kb_folder)
        assert loaded is not None
        assert loaded[0].shape == (1, 2)

    def test_remove_from_nonexistent_index_is_noop(self, kb_folder: Path):
        remove_from_index(kb_folder, "entry_a")
        assert not index_path(kb_folder).exists()

    def test_index_sidecar_contains_valid_json_mapping(self, kb_folder: Path):
        emb = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
        append_to_index(kb_folder, "entry_a", emb)
        sidecar = _index_sidecar_path(kb_folder)
        mapping = json.loads(sidecar.read_text())
        assert mapping == [["entry_a", 0], ["entry_a", 1]]
