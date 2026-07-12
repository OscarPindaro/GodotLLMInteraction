"""Tests for KB answer building — local files, folders, GitHub URL parsing, format."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from godotllminteraction.kb.answer import (
    _GITHUB_BLOB_RE,
    _GITHUB_TREE_RE,
    _collect_folder_files,
    _fetch_github_url,
    build_answer,
)
from godotllminteraction.kb.types import KbEntry

pytestmark = [pytest.mark.kb]


class TestGithubBlobRegex:
    def test_matches_standard_blob_url(self):
        url = "https://github.com/owner/repo/blob/main/src/player.gd"
        m = _GITHUB_BLOB_RE.match(url)
        assert m is not None
        assert m["owner"] == "owner"
        assert m["repo"] == "repo"
        assert m["branch"] == "main"
        assert m["path"] == "src/player.gd"

    def test_matches_nested_path(self):
        url = "https://github.com/o/r/blob/v1.0.0/deep/nested/path/file.py"
        m = _GITHUB_BLOB_RE.match(url)
        assert m is not None
        assert m["path"] == "deep/nested/path/file.py"
        assert m["branch"] == "v1.0.0"

    def test_matches_http(self):
        url = "http://github.com/owner/repo/blob/main/file.py"
        m = _GITHUB_BLOB_RE.match(url)
        assert m is not None

    def test_does_not_match_tree_url(self):
        url = "https://github.com/owner/repo/tree/main/src"
        assert _GITHUB_BLOB_RE.match(url) is None

    def test_does_not_match_non_github(self):
        url = "https://gitlab.com/owner/repo/blob/main/file.py"
        assert _GITHUB_BLOB_RE.match(url) is None


class TestGithubTreeRegex:
    def test_matches_standard_tree_url(self):
        url = "https://github.com/owner/repo/tree/main/src/player"
        m = _GITHUB_TREE_RE.match(url)
        assert m is not None
        assert m["owner"] == "owner"
        assert m["path"] == "src/player"

    def test_does_not_match_blob_url(self):
        url = "https://github.com/owner/repo/blob/main/file.py"
        assert _GITHUB_TREE_RE.match(url) is None


class TestFetchGithubUrl:
    def test_invalid_url_returns_error_string(self):
        result = _fetch_github_url("https://example.com/foo")
        assert "error" in result
        assert "not a valid GitHub" in result

    @patch("godotllminteraction.kb.answer._fetch_url")
    def test_blob_url_fetches_raw_content(self, mock_fetch: MagicMock):
        mock_fetch.return_value = "print('hello')"
        result = _fetch_github_url("https://github.com/o/r/blob/main/player.gd")
        assert "print('hello')" in result
        assert "<https://github.com/o/r/blob/main/player.gd>" in result
        # Verify it called raw.githubusercontent.com
        called_url = mock_fetch.call_args[0][0]
        assert "raw.githubusercontent.com" in called_url
        assert "o/r/main/player.gd" in called_url

    @patch("godotllminteraction.kb.answer._fetch_url")
    @patch("godotllminteraction.kb.answer.urlopen")
    def test_tree_url_fetches_multiple_files(
        self, mock_urlopen: MagicMock, mock_fetch: MagicMock
    ):
        # Mock the GitHub Contents API response
        api_response = [
            {
                "name": "player.gd",
                "type": "file",
                "download_url": "https://raw.githubusercontent.com/o/r/main/src/player.gd",
            },
            {
                "name": "enemy.gd",
                "type": "file",
                "download_url": "https://raw.githubusercontent.com/o/r/main/src/enemy.gd",
            },
            {
                "name": "README.md",
                "type": "file",
                "download_url": "https://raw.githubusercontent.com/o/r/main/src/README.md",
            },
            {"name": "subfolder", "type": "dir", "download_url": None},
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        import json as _json

        mock_resp.read.return_value = _json.dumps(api_response).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        mock_fetch.side_effect = lambda url: f"content of {url.split('/')[-1]}"

        result = _fetch_github_url("https://github.com/o/r/tree/main/src")
        assert "player.gd" in result
        assert "enemy.gd" in result
        assert "README.md" in result
        # Should not include directories
        assert "subfolder" not in result or "content of subfolder" not in result


class TestCollectFolderFiles:
    def test_collects_text_files_only(self, tmp_path: Path):
        (tmp_path / "player.gd").write_text("code")
        (tmp_path / "scene.tscn").write_text("scene")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        (tmp_path / "data.bin").write_bytes(b"\x00\x01")
        files = _collect_folder_files(tmp_path)
        names = [f.name for f in files]
        assert "player.gd" in names
        assert "scene.tscn" in names
        assert "image.png" not in names
        assert "data.bin" not in names

    def test_returns_sorted(self, tmp_path: Path):
        (tmp_path / "b.gd").write_text("b")
        (tmp_path / "a.gd").write_text("a")
        (tmp_path / "c.gd").write_text("c")
        files = _collect_folder_files(tmp_path)
        assert [f.name for f in files] == ["a.gd", "b.gd", "c.gd"]

    def test_nonexistent_folder_returns_empty(self):
        assert _collect_folder_files(Path("/nonexistent/path")) == []

    def test_ignores_subdirectories(self, tmp_path: Path):
        (tmp_path / "file.gd").write_text("x")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.gd").write_text("y")
        files = _collect_folder_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "file.gd"


class TestBuildAnswer:
    def test_answer_text_only(self):
        entry = KbEntry.create(questions=["q"], answer_text="The answer is 42.")
        result = build_answer(entry)
        assert result == "The answer is 42."

    def test_file_paths_included_with_content(self, tmp_path: Path):
        f = tmp_path / "player.gd"
        f.write_text("extends CharacterBody2D\n")
        entry = KbEntry.create(
            questions=["q"],
            file_paths=[str(f)],
        )
        result = build_answer(entry)
        assert str(f) in result
        assert "extends CharacterBody2D" in result

    def test_relative_file_paths_resolved_against_project(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        f = tmp_path / "src" / "player.gd"
        f.write_text("code here")
        entry = KbEntry.create(
            questions=["q"],
            file_paths=["src/player.gd"],
        )
        result = build_answer(entry, project_path=tmp_path)
        assert "code here" in result

    def test_folder_paths_include_all_text_files(self, tmp_path: Path):
        folder = tmp_path / "scripts"
        folder.mkdir()
        (folder / "a.gd").write_text("content_a")
        (folder / "b.gd").write_text("content_b")
        entry = KbEntry.create(
            questions=["q"],
            folder_paths=[str(folder)],
        )
        result = build_answer(entry)
        assert "content_a" in result
        assert "content_b" in result
        assert "---" in result

    def test_multiple_parts_separated_by_divider(self, tmp_path: Path):
        f1 = tmp_path / "a.gd"
        f1.write_text("content_a")
        f2 = tmp_path / "b.gd"
        f2.write_text("content_b")
        entry = KbEntry.create(
            questions=["q"],
            file_paths=[str(f1), str(f2)],
        )
        result = build_answer(entry)
        assert "content_a" in result
        assert "content_b" in result
        assert "---" in result

    def test_nonexistent_file_silently_skipped(self, tmp_path: Path):
        entry = KbEntry.create(
            questions=["q"],
            file_paths=[str(tmp_path / "missing.gd")],
            answer_text="fallback",
        )
        result = build_answer(entry)
        assert "fallback" in result
        assert "error" not in result

    def test_combined_answer_text_and_files(self, tmp_path: Path):
        f = tmp_path / "code.gd"
        f.write_text("actual code")
        entry = KbEntry.create(
            questions=["q"],
            answer_text="Explanation here",
            file_paths=[str(f)],
        )
        result = build_answer(entry)
        assert "Explanation here" in result
        assert "actual code" in result
        assert "---" in result

    @patch("godotllminteraction.kb.answer._fetch_github_url")
    def test_github_urls_included(self, mock_fetch: MagicMock):
        mock_fetch.return_value = "<github:...>\nfetched content"
        entry = KbEntry.create(
            questions=["q"],
            github_urls=["https://github.com/o/r/blob/main/file.py"],
        )
        result = build_answer(entry)
        assert "fetched content" in result
