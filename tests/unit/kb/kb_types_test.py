"""Tests for KB types — model validation, field defaults, serialization roundtrip."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import pytest

from godotllminteraction.kb.types import KbEntry, KbSearchResult

pytestmark = [pytest.mark.kb]


class TestKbEntryCreate:
    def test_creates_with_answer_text(self):
        entry = KbEntry.create(
            questions=["How to add a node?"],
            answer_text="Use add_node tool.",
        )
        assert entry.questions == ["How to add a node?"]
        assert entry.answer_text == "Use add_node tool."
        assert entry.file_paths == []
        assert entry.folder_paths == []
        assert entry.github_urls == []

    def test_creates_with_file_paths(self):
        entry = KbEntry.create(
            questions=["How to structure a scene?"],
            file_paths=["scenes/player.tscn"],
        )
        assert entry.file_paths == ["scenes/player.tscn"]
        assert entry.answer_text is None

    def test_creates_with_folder_paths(self):
        entry = KbEntry.create(
            questions=["What files are in the project?"],
            folder_paths=["src/player"],
        )
        assert entry.folder_paths == ["src/player"]

    def test_creates_with_github_urls(self):
        entry = KbEntry.create(
            questions=["How does the parser work?"],
            github_urls=["https://github.com/user/repo/blob/main/parser.py"],
        )
        assert len(entry.github_urls) == 1
        assert "parser.py" in entry.github_urls[0]

    def test_creates_with_all_answer_types(self):
        entry = KbEntry.create(
            questions=["Complex question"],
            answer_text="Quick answer",
            file_paths=["file.gd"],
            folder_paths=["folder/"],
            github_urls=["https://github.com/u/r/blob/main/x.py"],
            description="Test entry",
            tags=["test", "complex"],
        )
        assert entry.description == "Test entry"
        assert entry.tags == ["test", "complex"]

    def test_no_questions_raises(self):
        with pytest.raises(ValueError, match="At least one question"):
            KbEntry.create(questions=[], answer_text="x")

    def test_no_answer_source_raises(self):
        with pytest.raises(ValueError, match="Provide answer_text"):
            KbEntry.create(questions=["q"])

    def test_auto_generates_unique_ids(self):
        e1 = KbEntry.create(questions=["q1"], answer_text="a")
        e2 = KbEntry.create(questions=["q2"], answer_text="b")
        assert e1.id != e2.id
        # Verify it's a valid hex uuid
        uuid.UUID(e1.id)

    def test_created_at_is_datetime(self):
        entry = KbEntry.create(questions=["q"], answer_text="a")
        assert isinstance(entry.created_at, datetime)


class TestKbEntrySave:
    def test_save_writes_json_file(self, tmp_path: Path):
        entry = KbEntry.create(questions=["q"], answer_text="a")
        entry.save(tmp_path)
        entry_file = tmp_path / "entries" / f"{entry.id}.json"
        assert entry_file.exists()
        content = entry_file.read_text()
        assert entry.id in content
        assert "How to" not in content or "q" in content

    def test_save_creates_entries_dir(self, tmp_path: Path):
        entry = KbEntry.create(questions=["q"], answer_text="a")
        assert not (tmp_path / "entries").exists()
        entry.save(tmp_path)
        assert (tmp_path / "entries").exists()

    def test_roundtrip_preserves_all_fields(self, tmp_path: Path):
        entry = KbEntry.create(
            questions=["q1", "q2"],
            answer_text="answer",
            file_paths=["a.gd", "b.tscn"],
            folder_paths=["src/"],
            github_urls=["https://github.com/u/r/blob/main/x.py"],
            description="desc",
            tags=["t1"],
        )
        entry.save(tmp_path)
        loaded = KbEntry.model_validate_json(
            (tmp_path / "entries" / f"{entry.id}.json").read_text()
        )
        assert loaded.questions == entry.questions
        assert loaded.answer_text == entry.answer_text
        assert loaded.file_paths == entry.file_paths
        assert loaded.folder_paths == entry.folder_paths
        assert loaded.github_urls == entry.github_urls
        assert loaded.description == entry.description
        assert loaded.tags == entry.tags
        assert loaded.id == entry.id


class TestKbSearchResult:
    def test_model_construction(self):
        entry = KbEntry.create(questions=["q"], answer_text="a")
        result = KbSearchResult(entry=entry, score=0.85, matched_question="q")
        assert result.score == 0.85
        assert result.matched_question == "q"
        assert result.entry.id == entry.id
