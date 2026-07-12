"""E2e test: `gli kb` CLI commands end-to-end with the real model2vec model.

Uses CliRunner to invoke the CLI exactly as a user would, with a real KB
location on disk and the real embedding model. Verifies:
1. `gli kb register --text` creates an entry + index on disk.
2. `gli kb register` with file paths creates an entry with file content.
3. `gli kb register --github` creates an entry with GitHub URLs.
4. `gli kb search --json` returns ranked results with answer content.
5. `gli kb list --json` lists all entries with correct fields.
6. `gli kb remove` removes the entry and cleans the index.
7. `gli kb clear` wipes everything.
8. Validation errors exit with non-zero code.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

import pytest
from typer.testing import CliRunner

from godotllminteraction.cli import app

runner = CliRunner()

pytestmark = [pytest.mark.cli, pytest.mark.kb]


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
def kb_location(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("kb_e2e")
    return d


@pytest.fixture(autouse=True)
def _env_kb(kb_location: Path):
    with patch_env("GLI_KB_LOCATION", str(kb_location)):
        with patch_env("HF_HUB_DISABLE_PROGRESS_BARS", "1"):
            yield


@pytest.fixture
def project_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("project_e2e")
    return d


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


class TestKbRegister:
    def test_register_text_answer_creates_entry_and_index(
        self, kb_location: Path, project_dir: Path
    ):
        result = runner.invoke(
            app,
            [
                "kb",
                "register",
                "--question",
                "How to add a child node?",
                "--question",
                "How to instantiate a node?",
                "--text",
                "Use add_child() on the parent node.",
                "--description",
                "Adding nodes",
                "--tag",
                "nodes",
                "--tag",
                "scene",
                "--project",
                str(project_dir),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        entry_id = data["id"]

        # Entry file exists on disk
        entry_file = kb_location / "entries" / f"{entry_id}.json"
        assert entry_file.exists()
        entry_data = json.loads(entry_file.read_text())
        assert entry_data["questions"] == [
            "How to add a child node?",
            "How to instantiate a node?",
        ]
        assert entry_data["answer_text"] == "Use add_child() on the parent node."
        assert entry_data["description"] == "Adding nodes"
        assert entry_data["tags"] == ["nodes", "scene"]
        assert entry_data["file_paths"] == []
        assert entry_data["folder_paths"] == []
        assert entry_data["github_urls"] == []

        # Index files exist on disk
        assert (kb_location / "index.npz").exists()
        assert (kb_location / "index_meta.json").exists()

    def test_register_file_paths_creates_entry(
        self, kb_location: Path, project_dir: Path
    ):
        f = project_dir / "player.gd"
        f.write_text("extends CharacterBody2D")

        result = runner.invoke(
            app,
            [
                "kb",
                "register",
                "--question",
                "How is the player script structured?",
                str(f),
                "--project",
                str(project_dir),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        entry_id = data["id"]

        entry_data = json.loads(
            (kb_location / "entries" / f"{entry_id}.json").read_text()
        )
        assert entry_data["file_paths"] == [str(f)]
        assert entry_data["answer_text"] is None

    def test_register_folder_paths_creates_entry(
        self, kb_location: Path, project_dir: Path
    ):
        folder = project_dir / "scripts"
        folder.mkdir()
        (folder / "a.gd").write_text("a")

        result = runner.invoke(
            app,
            [
                "kb",
                "register",
                "--question",
                "What scripts exist?",
                "--folder",
                str(folder),
                "--project",
                str(project_dir),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        entry_id = data["id"]

        entry_data = json.loads(
            (kb_location / "entries" / f"{entry_id}.json").read_text()
        )
        assert entry_data["folder_paths"] == [str(folder)]

    def test_register_github_urls_creates_entry(
        self, kb_location: Path, project_dir: Path
    ):
        result = runner.invoke(
            app,
            [
                "kb",
                "register",
                "--question",
                "How does the parser work?",
                "--github",
                "https://github.com/o/r/blob/main/parser.py",
                "--project",
                str(project_dir),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        entry_id = data["id"]

        entry_data = json.loads(
            (kb_location / "entries" / f"{entry_id}.json").read_text()
        )
        assert entry_data["github_urls"] == [
            "https://github.com/o/r/blob/main/parser.py"
        ]

    def test_register_no_answer_source_fails(self, project_dir: Path):
        result = runner.invoke(
            app,
            [
                "kb",
                "register",
                "--question",
                "Some question",
                "--project",
                str(project_dir),
            ],
        )
        assert result.exit_code != 0
        assert "Provide file paths" in result.output or "text" in result.output.lower()

    def test_register_no_questions_fails(self, project_dir: Path):
        result = runner.invoke(
            app,
            [
                "kb",
                "register",
                "--text",
                "Some answer",
                "--project",
                str(project_dir),
            ],
        )
        assert result.exit_code != 0

    def test_multiple_registers_grow_index(self, kb_location: Path, project_dir: Path):
        """Registering multiple entries should append to the index, not overwrite."""
        for i in range(3):
            result = runner.invoke(
                app,
                [
                    "kb",
                    "register",
                    "--question",
                    f"Question number {i}",
                    "--text",
                    f"Answer number {i}",
                    "--project",
                    str(project_dir),
                    "--json",
                ],
            )
            assert result.exit_code == 0, result.output

        # Index should have 3 rows (one question per entry)
        import numpy as np

        data = np.load(kb_location / "index.npz")
        assert data["embeddings"].shape[0] == 3

        # Sidecar should map 3 entries
        mapping = json.loads((kb_location / "index_meta.json").read_text())
        assert len(mapping) == 3
        entry_ids = {m[0] for m in mapping}
        assert len(entry_ids) == 3


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestKbSearch:
    def test_search_returns_ranked_results_with_answer(
        self, kb_location: Path, project_dir: Path
    ):
        # Register entries about different topics
        for q, a in [
            ("How to add a child node to the scene?", "Use add_child() method."),
            ("How to connect a signal in Godot?", "Use signal.connect() method."),
            ("How to validate a tscn scene file?", "Run godot --check-only."),
        ]:
            runner.invoke(
                app,
                [
                    "kb",
                    "register",
                    "--question",
                    q,
                    "--text",
                    a,
                    "--project",
                    str(project_dir),
                    "--json",
                ],
            )

        # Search for node-related question
        result = runner.invoke(
            app,
            [
                "kb",
                "search",
                "How do I add a node?",
                "--project",
                str(project_dir),
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        results = json.loads(result.output)
        assert len(results) > 0
        assert "add_child" in results[0]["answer"]
        assert results[0]["score"] >= results[1]["score"] if len(results) > 1 else True

    def test_search_empty_kb_returns_no_results(self, project_dir: Path):
        result = runner.invoke(
            app,
            ["kb", "search", "anything", "--project", str(project_dir), "--json"],
        )
        assert result.exit_code == 0
        assert json.loads(result.output) == []

    def test_search_top_k_limits_results(self, kb_location: Path, project_dir: Path):
        for i in range(5):
            runner.invoke(
                app,
                [
                    "kb",
                    "register",
                    "--question",
                    f"Question {i}",
                    "--text",
                    f"Answer {i}",
                    "--project",
                    str(project_dir),
                    "--json",
                ],
            )

        result = runner.invoke(
            app,
            [
                "kb",
                "search",
                "Question",
                "--top-k",
                "2",
                "--project",
                str(project_dir),
                "--json",
            ],
        )
        assert result.exit_code == 0
        results = json.loads(result.output)
        assert len(results) <= 2

    def test_search_includes_file_content_in_answer(
        self, kb_location: Path, project_dir: Path
    ):
        f = project_dir / "player.gd"
        f.write_text("extends CharacterBody2D\nvar speed = 300\n")

        runner.invoke(
            app,
            [
                "kb",
                "register",
                "--question",
                "How is the player script?",
                str(f),
                "--project",
                str(project_dir),
                "--json",
            ],
        )

        result = runner.invoke(
            app,
            ["kb", "search", "player script", "--project", str(project_dir), "--json"],
        )
        assert result.exit_code == 0, result.output
        results = json.loads(result.output)
        assert len(results) > 0
        assert "extends CharacterBody2D" in results[0]["answer"]
        assert "var speed = 300" in results[0]["answer"]


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestKbList:
    def test_list_shows_all_entries(self, kb_location: Path, project_dir: Path):
        runner.invoke(
            app,
            [
                "kb",
                "register",
                "--question",
                "Q1",
                "--text",
                "A1",
                "--project",
                str(project_dir),
                "--json",
            ],
        )
        runner.invoke(
            app,
            [
                "kb",
                "register",
                "--question",
                "Q2",
                "--text",
                "A2",
                "--project",
                str(project_dir),
                "--json",
            ],
        )

        result = runner.invoke(
            app,
            ["kb", "list", "--project", str(project_dir), "--json"],
        )
        assert result.exit_code == 0, result.output
        entries = json.loads(result.output)
        assert len(entries) == 2
        questions = {e["questions"][0] for e in entries}
        assert questions == {"Q1", "Q2"}

    def test_list_empty_kb(self, project_dir: Path):
        result = runner.invoke(
            app,
            ["kb", "list", "--project", str(project_dir), "--json"],
        )
        assert result.exit_code == 0
        assert json.loads(result.output) == []


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


class TestKbRemove:
    def test_remove_deletes_entry_and_cleans_index(
        self, kb_location: Path, project_dir: Path
    ):
        # Register an entry
        result = runner.invoke(
            app,
            [
                "kb",
                "register",
                "--question",
                "Q1",
                "--text",
                "A1",
                "--project",
                str(project_dir),
                "--json",
            ],
        )
        entry_id = json.loads(result.output)["id"]

        # Verify it exists
        assert (kb_location / "entries" / f"{entry_id}.json").exists()
        assert (kb_location / "index.npz").exists()

        # Remove it
        result = runner.invoke(
            app,
            ["kb", "remove", entry_id, "--project", str(project_dir)],
        )
        assert result.exit_code == 0, result.output
        assert "Removed" in result.output

        # Entry file gone
        assert not (kb_location / "entries" / f"{entry_id}.json").exists()
        # Index gone (was the only entry)
        assert not (kb_location / "index.npz").exists()

    def test_remove_nonexistent_fails(self, project_dir: Path):
        result = runner.invoke(
            app,
            ["kb", "remove", "nonexistent_id", "--project", str(project_dir)],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_remove_one_of_many_keeps_others(
        self, kb_location: Path, project_dir: Path
    ):
        ids = []
        for i in range(3):
            result = runner.invoke(
                app,
                [
                    "kb",
                    "register",
                    "--question",
                    f"Q{i}",
                    "--text",
                    f"A{i}",
                    "--project",
                    str(project_dir),
                    "--json",
                ],
            )
            ids.append(json.loads(result.output)["id"])

        # Remove the middle one
        result = runner.invoke(
            app,
            ["kb", "remove", ids[1], "--project", str(project_dir)],
        )
        assert result.exit_code == 0

        # Other two still exist
        assert (kb_location / "entries" / f"{ids[0]}.json").exists()
        assert (kb_location / "entries" / f"{ids[2]}.json").exists()
        assert not (kb_location / "entries" / f"{ids[1]}.json").exists()

        # Index still has 2 rows
        import numpy as np

        data = np.load(kb_location / "index.npz")
        assert data["embeddings"].shape[0] == 2


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestKbClear:
    def test_clear_wipes_all_entries_and_index(
        self, kb_location: Path, project_dir: Path
    ):
        for i in range(3):
            runner.invoke(
                app,
                [
                    "kb",
                    "register",
                    "--question",
                    f"Q{i}",
                    "--text",
                    f"A{i}",
                    "--project",
                    str(project_dir),
                    "--json",
                ],
            )

        assert (kb_location / "index.npz").exists()
        assert len(list((kb_location / "entries").glob("*.json"))) == 3

        result = runner.invoke(
            app,
            ["kb", "clear", "--project", str(project_dir), "--yes"],
        )
        assert result.exit_code == 0, result.output
        assert "Cleared" in result.output

        assert not (kb_location / "index.npz").exists()
        assert not (kb_location / "index_meta.json").exists()
        assert len(list((kb_location / "entries").glob("*.json"))) == 0

    def test_clear_without_yes_prompts(self, project_dir: Path):
        result = runner.invoke(
            app,
            ["kb", "clear", "--project", str(project_dir)],
            input="n\n",
        )
        assert "Aborted" in result.output or "Remove all" in result.output
