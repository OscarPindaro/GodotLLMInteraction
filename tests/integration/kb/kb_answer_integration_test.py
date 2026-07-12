"""Integration test: KB entry persistence with file paths, folder paths, and GitHub URLs.

Verifies that entries saved with different answer types are correctly:
1. Serialized to JSON on disk with all fields intact.
2. Reloaded via model_validate_json with full fidelity.
3. Listed correctly from the entries directory.
4. Answer content is built correctly from real file I/O.
5. GitHub URL parsing and fetching (mocked at the HTTP layer) produces
   the same <source>\n<content> format as local files.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from godotllminteraction.kb.answer import build_answer
from godotllminteraction.kb.storage import (
    list_entries,
    load_entry,
    save_entry,
)
from godotllminteraction.kb.types import KbEntry

pytestmark = [pytest.mark.kb]


@contextmanager
def patch_env(key: str, value: str):
    old = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old


@pytest.fixture
def kb_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("kb_answer_integration")
    return d


@pytest.fixture(autouse=True)
def _env_kb_location(kb_dir: Path):
    with patch_env("GLI_KB_LOCATION", str(kb_dir)):
        with patch_env("HF_HUB_DISABLE_PROGRESS_BARS", "1"):
            yield


@pytest.fixture
def project_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A fake project directory with real files for answer building."""
    d = tmp_path_factory.mktemp("project")
    return d


# ---------------------------------------------------------------------------
# Entry persistence with all answer types
# ---------------------------------------------------------------------------


class TestEntryPersistenceAllAnswerTypes:
    """Verify that entries with every answer type survive a save/load cycle."""

    def test_entry_with_answer_text_persists(self, kb_dir: Path):
        entry = KbEntry.create(
            questions=["What is a CharacterBody2D?"],
            answer_text="A 2D physics body for player characters.",
            description="Godot physics body",
            tags=["physics", "2d"],
        )
        save_entry(kb_dir, entry)

        loaded = load_entry(kb_dir, entry.id)
        assert loaded is not None
        assert loaded.questions == entry.questions
        assert loaded.answer_text == entry.answer_text
        assert loaded.file_paths == []
        assert loaded.folder_paths == []
        assert loaded.github_urls == []
        assert loaded.description == entry.description
        assert loaded.tags == entry.tags
        assert loaded.id == entry.id

    def test_entry_with_file_paths_persists(self, kb_dir: Path, project_dir: Path):
        f1 = project_dir / "player.gd"
        f1.write_text("extends CharacterBody2D")
        f2 = project_dir / "enemy.gd"
        f2.write_text("extends RigidBody2D")

        entry = KbEntry.create(
            questions=["How to structure player and enemy scripts?"],
            file_paths=[str(f1), str(f2)],
        )
        save_entry(kb_dir, entry)

        loaded = load_entry(kb_dir, entry.id)
        assert loaded is not None
        assert loaded.file_paths == [str(f1), str(f2)]
        assert loaded.answer_text is None

    def test_entry_with_folder_paths_persists(self, kb_dir: Path, project_dir: Path):
        folder = project_dir / "scripts"
        folder.mkdir()
        (folder / "a.gd").write_text("a")
        (folder / "b.gd").write_text("b")

        entry = KbEntry.create(
            questions=["What scripts are in the project?"],
            folder_paths=[str(folder)],
        )
        save_entry(kb_dir, entry)

        loaded = load_entry(kb_dir, entry.id)
        assert loaded is not None
        assert loaded.folder_paths == [str(folder)]

    def test_entry_with_github_urls_persists(self, kb_dir: Path):
        urls = [
            "https://github.com/godotengine/godot/blob/master/scene/main/scene_tree.cpp",
            "https://github.com/godotengine/godot/tree/master/core/object",
        ]
        entry = KbEntry.create(
            questions=["How does the SceneTree work internally?"],
            github_urls=urls,
        )
        save_entry(kb_dir, entry)

        loaded = load_entry(kb_dir, entry.id)
        assert loaded is not None
        assert loaded.github_urls == urls

    def test_entry_with_all_answer_types_persists(
        self, kb_dir: Path, project_dir: Path
    ):
        f = project_dir / "code.gd"
        f.write_text("code")
        folder = project_dir / "scripts"
        folder.mkdir()
        (folder / "helper.gd").write_text("helper")

        entry = KbEntry.create(
            questions=["Complex question about everything"],
            answer_text="Inline explanation",
            file_paths=[str(f)],
            folder_paths=[str(folder)],
            github_urls=["https://github.com/o/r/blob/main/file.py"],
            description="All types at once",
            tags=["complex", "test"],
        )
        save_entry(kb_dir, entry)

        loaded = load_entry(kb_dir, entry.id)
        assert loaded is not None
        assert loaded.answer_text == "Inline explanation"
        assert loaded.file_paths == [str(f)]
        assert loaded.folder_paths == [str(folder)]
        assert len(loaded.github_urls) == 1
        assert loaded.description == "All types at once"
        assert loaded.tags == ["complex", "test"]

    def test_json_on_disk_contains_all_fields(self, kb_dir: Path):
        entry = KbEntry.create(
            questions=["q1", "q2"],
            answer_text="text",
            file_paths=["a.gd"],
            folder_paths=["src/"],
            github_urls=["https://github.com/o/r/blob/main/x.py"],
            description="desc",
            tags=["t1", "t2"],
        )
        save_entry(kb_dir, entry)
        raw = (kb_dir / "entries" / f"{entry.id}.json").read_text()
        data = json.loads(raw)
        assert data["questions"] == ["q1", "q2"]
        assert data["answer_text"] == "text"
        assert data["file_paths"] == ["a.gd"]
        assert data["folder_paths"] == ["src/"]
        assert data["github_urls"] == ["https://github.com/o/r/blob/main/x.py"]
        assert data["description"] == "desc"
        assert data["tags"] == ["t1", "t2"]
        assert data["id"] == entry.id


# ---------------------------------------------------------------------------
# Listing entries
# ---------------------------------------------------------------------------


class TestListEntries:
    def test_list_returns_all_entries_with_correct_fields(self, kb_dir: Path):
        e1 = KbEntry.create(questions=["q1"], answer_text="a1", tags=["t1"])
        e2 = KbEntry.create(
            questions=["q2"],
            file_paths=["some_file.gd"],
        )
        e3 = KbEntry.create(
            questions=["q3"],
            github_urls=["https://github.com/o/r/blob/main/x.py"],
        )
        for e in [e1, e2, e3]:
            save_entry(kb_dir, e)

        entries = list_entries(kb_dir)
        assert len(entries) == 3
        by_id = {e.id: e for e in entries}
        assert by_id[e1.id].answer_text == "a1"
        assert by_id[e2.id].file_paths == ["some_file.gd"]
        assert by_id[e3.id].github_urls == ["https://github.com/o/r/blob/main/x.py"]


# ---------------------------------------------------------------------------
# Answer building from real files
# ---------------------------------------------------------------------------


class TestBuildAnswerFromRealFiles:
    def test_file_content_appears_in_answer(self, kb_dir: Path, project_dir: Path):
        f = project_dir / "player.gd"
        f.write_text("extends CharacterBody2D\n\nvar speed = 300\n")

        entry = KbEntry.create(
            questions=["How to make a player?"],
            file_paths=[str(f)],
        )
        save_entry(kb_dir, entry)
        loaded = load_entry(kb_dir, entry.id)
        assert loaded is not None

        answer = build_answer(loaded)
        assert "extends CharacterBody2D" in answer
        assert "var speed = 300" in answer
        assert str(f) in answer

    def test_folder_content_all_files_in_answer(self, kb_dir: Path, project_dir: Path):
        folder = project_dir / "scripts"
        folder.mkdir()
        (folder / "player.gd").write_text("# player code")
        (folder / "enemy.gd").write_text("# enemy code")
        (folder / "config.json").write_text('{"hp": 100}')
        (folder / "image.png").write_bytes(b"\x89PNG")  # should be excluded

        entry = KbEntry.create(
            questions=["What is in the scripts folder?"],
            folder_paths=[str(folder)],
        )
        save_entry(kb_dir, entry)
        loaded = load_entry(kb_dir, entry.id)
        assert loaded is not None

        answer = build_answer(loaded)
        assert "# player code" in answer
        assert "# enemy code" in answer
        assert '"hp": 100' in answer
        assert "\x89PNG" not in answer  # binary file excluded

    def test_relative_paths_resolved_against_project(
        self, kb_dir: Path, project_dir: Path
    ):
        (project_dir / "src").mkdir()
        (project_dir / "src" / "main.gd").write_text("func _ready(): pass")

        entry = KbEntry.create(
            questions=["How does main start?"],
            file_paths=["src/main.gd"],  # relative path
        )
        save_entry(kb_dir, entry)
        loaded = load_entry(kb_dir, entry.id)
        assert loaded is not None

        answer = build_answer(loaded, project_path=project_dir)
        assert "func _ready(): pass" in answer

    def test_combined_text_and_files_in_answer(self, kb_dir: Path, project_dir: Path):
        f = project_dir / "code.gd"
        f.write_text("extends Node")

        entry = KbEntry.create(
            questions=["How does this work?"],
            answer_text="Here is the explanation:",
            file_paths=[str(f)],
        )
        save_entry(kb_dir, entry)
        loaded = load_entry(kb_dir, entry.id)
        assert loaded is not None

        answer = build_answer(loaded)
        assert "Here is the explanation:" in answer
        assert "extends Node" in answer
        assert "---" in answer  # separator between text and file


# ---------------------------------------------------------------------------
# GitHub URL answer building (HTTP mocked)
# ---------------------------------------------------------------------------


class TestBuildAnswerFromGithubUrls:
    @patch("godotllminteraction.kb.answer._fetch_url")
    def test_github_blob_url_in_answer_same_format_as_local(
        self, mock_fetch: MagicMock
    ):
        """GitHub blob content should use the same <source>\n<content> format."""
        mock_fetch.return_value = "extends Node2D\n"
        entry = KbEntry.create(
            questions=["How is Node2D implemented?"],
            github_urls=["https://github.com/o/r/blob/main/node2d.gd"],
        )
        answer = build_answer(entry)
        assert "<https://github.com/o/r/blob/main/node2d.gd>" in answer
        assert "extends Node2D" in answer

    @patch("godotllminteraction.kb.answer.urlopen")
    @patch("godotllminteraction.kb.answer._fetch_url")
    def test_github_tree_url_multiple_files_in_answer(
        self, mock_fetch: MagicMock, mock_urlopen: MagicMock
    ):
        """GitHub tree content should fetch all text files and format them consistently."""
        api_response = [
            {
                "name": "a.gd",
                "type": "file",
                "download_url": "https://raw.githubusercontent.com/o/r/main/folder/a.gd",
            },
            {
                "name": "b.gd",
                "type": "file",
                "download_url": "https://raw.githubusercontent.com/o/r/main/folder/b.gd",
            },
            {"name": "subdir", "type": "dir", "download_url": None},
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(api_response).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        mock_fetch.side_effect = lambda url: f"content_of_{url.split('/')[-1]}"

        entry = KbEntry.create(
            questions=["What files are in that folder?"],
            github_urls=["https://github.com/o/r/tree/main/folder"],
        )
        answer = build_answer(entry)

        # Both files should appear with the same <source>\n<content> format
        assert "<https://github.com/o/r/blob/main/folder/a.gd>" in answer
        assert "content_of_a.gd" in answer
        assert "<https://github.com/o/r/blob/main/folder/b.gd>" in answer
        assert "content_of_b.gd" in answer
        # Directories should be skipped
        assert "subdir" not in answer or "content_of_subdir" not in answer

    @patch("godotllminteraction.kb.answer._fetch_url")
    def test_github_and_local_files_same_format(
        self, mock_fetch: MagicMock, tmp_path: Path
    ):
        """Local files and GitHub files should produce the same <source>\n<content> format."""
        mock_fetch.return_value = "github content"
        local_file = tmp_path / "local.gd"
        local_file.write_text("local content")

        entry = KbEntry.create(
            questions=["Compare local and remote"],
            file_paths=[str(local_file)],
            github_urls=["https://github.com/o/r/blob/main/remote.gd"],
        )
        answer = build_answer(entry)

        # Both should use <source>\n<content> format
        assert f"<{local_file}>\nlocal content" in answer
        assert "<https://github.com/o/r/blob/main/remote.gd>\ngithub content" in answer
        # Separated by ---
        assert "---" in answer

    @patch("godotllminteraction.kb.answer._fetch_url")
    def test_invalid_github_url_produces_error_in_answer(self, mock_fetch: MagicMock):
        entry = KbEntry.create(
            questions=["q"],
            github_urls=["https://gitlab.com/o/r/blob/main/file.py"],
        )
        answer = build_answer(entry)
        assert "error" in answer
        assert "not a valid GitHub" in answer
