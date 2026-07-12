"""Integration test: KB index persistence and search consistency.

Uses the REAL model2vec model (minishlab/potion-base-2M-v1) to verify:
1. Index is saved to disk and persists across calls.
2. Embeddings loaded from disk are byte-identical to what was saved.
3. A query produces the same similarity scores whether computed in-memory
   (before saving) or from the persisted index (after saving).
4. Incremental appends produce an index identical to a full rebuild.
5. Search returns correct ranked results from the persisted index.

Requires network access to download the model on first run.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest

from godotllminteraction.kb.answer import build_answer
from godotllminteraction.kb.search import (
    _cosine_similarity_batch,
    _get_model,
    search_kb,
)
from godotllminteraction.kb.storage import (
    append_to_index,
    index_path,
    _index_sidecar_path,
    load_index,
    rebuild_index,
    remove_from_index,
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


@pytest.fixture(scope="module")
def model():
    """Load the real model2vec model once for all tests in this module."""
    return _get_model()


@pytest.fixture
def kb_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Isolated KB directory on disk."""
    d = tmp_path_factory.mktemp("kb_integration")
    return d


@pytest.fixture(autouse=True)
def _env_kb_location(kb_dir: Path):
    """Force all KB operations to use our temp dir via GLI_KB_LOCATION."""
    with patch_env("GLI_KB_LOCATION", str(kb_dir)):
        with patch_env("HF_HUB_DISABLE_PROGRESS_BARS", "1"):
            yield


# ---------------------------------------------------------------------------
# Test data — realistic Godot-related questions
# ---------------------------------------------------------------------------

QUESTIONS_A = [
    "How do I add a child node to a scene tree in Godot?",
    "How to instantiate a node and add it to the scene?",
]

QUESTIONS_B = [
    "How do I connect a signal to a function in Godot?",
    "How to wire up button pressed signal to a handler?",
]

QUESTIONS_C = [
    "How do I validate a tscn scene file with the Godot editor?",
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIndexPersistence:
    """Verify that the index is saved, persists, and is byte-identical."""

    def test_index_files_created_after_append(self, kb_dir: Path, model):
        emb = model.encode(QUESTIONS_A)
        append_to_index(kb_dir, "entry_a", np.array(emb, dtype=np.float32))

        assert index_path(kb_dir).exists(), "index.npz was not created"
        assert _index_sidecar_path(kb_dir).exists(), "index_meta.json was not created"

    def test_loaded_embeddings_identical_to_saved(self, kb_dir: Path, model):
        """The matrix loaded from disk must be byte-identical to what was saved."""
        original = np.array(model.encode(QUESTIONS_A + QUESTIONS_B), dtype=np.float32)
        mapping = [
            ("entry_a", 0),
            ("entry_a", 1),
            ("entry_b", 0),
            ("entry_b", 1),
        ]
        rebuild_index(kb_dir, original, mapping)

        loaded_data = load_index(kb_dir)
        assert loaded_data is not None
        loaded_emb, loaded_map = loaded_data

        assert loaded_emb.shape == original.shape
        assert np.array_equal(loaded_emb, original), (
            "Loaded embeddings differ from saved embeddings"
        )
        assert loaded_map == mapping

    def test_sidecar_mapping_correct(self, kb_dir: Path, model):
        emb = np.array(model.encode(QUESTIONS_A), dtype=np.float32)
        append_to_index(kb_dir, "entry_a", emb)

        loaded_data = load_index(kb_dir)
        assert loaded_data is not None
        _, mapping = loaded_data
        assert mapping == [("entry_a", 0), ("entry_a", 1)]

    def test_incremental_append_matches_full_rebuild(self, kb_dir: Path, model):
        """Appending entries one-by-one should produce the same index as
        rebuilding from the full concatenated matrix."""
        emb_a = np.array(model.encode(QUESTIONS_A), dtype=np.float32)
        emb_b = np.array(model.encode(QUESTIONS_B), dtype=np.float32)
        emb_c = np.array(model.encode(QUESTIONS_C), dtype=np.float32)

        # Incremental path
        append_to_index(kb_dir, "entry_a", emb_a)
        append_to_index(kb_dir, "entry_b", emb_b)
        append_to_index(kb_dir, "entry_c", emb_c)
        incremental_data = load_index(kb_dir)
        assert incremental_data is not None
        inc_emb, inc_map = incremental_data

        # Full rebuild path
        other_dir = kb_dir.parent / "kb_rebuild"
        other_dir.mkdir()
        full_emb = np.vstack([emb_a, emb_b, emb_c])
        full_map = [
            ("entry_a", 0),
            ("entry_a", 1),
            ("entry_b", 0),
            ("entry_b", 1),
            ("entry_c", 0),
        ]
        rebuild_index(other_dir, full_emb, full_map)
        rebuilt_data = load_index(other_dir)
        assert rebuilt_data is not None
        reb_emb, reb_map = rebuilt_data

        assert np.array_equal(inc_emb, reb_emb), (
            "Incremental append produced different embeddings than full rebuild"
        )
        assert inc_map == reb_map


class TestSearchConsistency:
    """Verify that search from persisted index matches in-memory computation."""

    def test_similarity_identical_before_and_after_saving(self, kb_dir: Path, model):
        """The core guarantee: computing similarity in-memory (before saving)
        must produce the same scores as loading from disk and computing there."""
        # Embed questions in-memory
        all_questions = QUESTIONS_A + QUESTIONS_B + QUESTIONS_C
        question_embeddings = np.array(model.encode(all_questions), dtype=np.float32)
        mapping = [
            ("entry_a", 0),
            ("entry_a", 1),
            ("entry_b", 0),
            ("entry_b", 1),
            ("entry_c", 0),
        ]

        # Save entries to disk so search_kb can load them
        for eid, questions in [
            ("entry_a", QUESTIONS_A),
            ("entry_b", QUESTIONS_B),
            ("entry_c", QUESTIONS_C),
        ]:
            entry = KbEntry.create(
                questions=questions,
                answer_text=f"Answer for {eid}",
            )
            entry.id = eid
            save_entry(kb_dir, entry)

        # Save index to disk
        rebuild_index(kb_dir, question_embeddings, mapping)

        # Pick a query and embed it
        query = "How to add a node to the scene tree?"
        query_emb = model.encode([query])[0]

        # Compute similarity in-memory (ground truth)
        in_memory_sims = _cosine_similarity_batch(query_emb, question_embeddings)

        # Compute similarity from persisted index (what search_kb does)
        loaded_data = load_index(kb_dir)
        assert loaded_data is not None
        loaded_emb, _ = loaded_data
        from_disk_sims = _cosine_similarity_batch(query_emb, loaded_emb)

        # They must be identical
        assert np.allclose(in_memory_sims, from_disk_sims, atol=1e-6), (
            f"In-memory sims {in_memory_sims} differ from disk sims {from_disk_sims}"
        )

    def test_search_kb_returns_correct_ranking(self, kb_dir: Path, model):
        """search_kb should rank the most relevant entry first."""
        # Create and save entries
        entries = []
        for eid, questions, answer in [
            ("entry_a", QUESTIONS_A, "Use add_child() to add a node."),
            ("entry_b", QUESTIONS_B, "Use connect() to wire signals."),
            ("entry_c", QUESTIONS_C, "Run godot --check-only to validate."),
        ]:
            entry = KbEntry.create(questions=questions, answer_text=answer)
            entry.id = eid
            save_entry(kb_dir, entry)
            emb = np.array(model.encode(questions), dtype=np.float32)
            append_to_index(kb_dir, eid, emb)
            entries.append(entry)

        # Query that should match entry_a best
        results = search_kb("How do I add a child node?", Path("/fake"), top_k=3)
        assert len(results) == 3
        assert results[0].entry.id == "entry_a"
        assert results[0].score >= results[1].score
        assert results[0].score >= results[2].score

        # Query that should match entry_b best
        results = search_kb(
            "How to connect a signal to a function?", Path("/fake"), top_k=3
        )
        assert results[0].entry.id == "entry_b"

        # Query that should match entry_c best
        results = search_kb("How to validate a scene file?", Path("/fake"), top_k=3)
        assert results[0].entry.id == "entry_c"

    def test_search_kb_scores_match_raw_computation(self, kb_dir: Path, model):
        """The scores returned by search_kb must match what we get by
        manually computing cosine similarity against the saved index."""
        entry = KbEntry.create(
            questions=QUESTIONS_A,
            answer_text="Use add_child().",
        )
        entry.id = "entry_a"
        save_entry(kb_dir, entry)
        emb = np.array(model.encode(QUESTIONS_A), dtype=np.float32)
        append_to_index(kb_dir, "entry_a", emb)

        query = "How to add a node to the scene?"
        query_emb = model.encode([query])[0]

        # Manual computation
        loaded_data = load_index(kb_dir)
        assert loaded_data is not None
        manual_sims = _cosine_similarity_batch(query_emb, loaded_data[0])
        manual_best = float(np.max(manual_sims))

        # search_kb computation
        results = search_kb(query, Path("/fake"), top_k=1)
        assert len(results) == 1
        assert abs(results[0].score - manual_best) < 1e-5, (
            f"search_kb score {results[0].score} != manual score {manual_best}"
        )

    def test_search_after_remove_still_works(self, kb_dir: Path, model):
        """After removing an entry from the index, search should still
        return correct results from the remaining entries."""
        for eid, questions, answer in [
            ("entry_a", QUESTIONS_A, "Use add_child()."),
            ("entry_b", QUESTIONS_B, "Use connect()."),
        ]:
            entry = KbEntry.create(questions=questions, answer_text=answer)
            entry.id = eid
            save_entry(kb_dir, entry)
            emb = np.array(model.encode(questions), dtype=np.float32)
            append_to_index(kb_dir, eid, emb)

        # Remove entry_a from index
        remove_from_index(kb_dir, "entry_a")

        # Search should only return entry_b
        results = search_kb("How to connect a signal?", Path("/fake"), top_k=5)
        assert all(r.entry.id == "entry_b" for r in results), (
            "Removed entry still appearing in search results"
        )
        assert len(results) == 1


class TestAnswerBuildingIntegration:
    """Verify build_answer works with real file I/O alongside the index."""

    def test_answer_built_from_saved_entry(self, kb_dir: Path, model, tmp_path: Path):
        """Register an entry with a real file, search for it, and verify
        the answer content includes the file contents."""
        answer_file = tmp_path / "player.gd"
        answer_file.write_text("extends CharacterBody2D\n\nfunc _ready():\n    pass\n")

        entry = KbEntry.create(
            questions=["How to structure a player script?"],
            file_paths=[str(answer_file)],
        )
        save_entry(kb_dir, entry)
        emb = np.array(model.encode(entry.questions), dtype=np.float32)
        append_to_index(kb_dir, entry.id, emb)

        results = search_kb("player script structure", Path("/fake"), top_k=1)
        assert len(results) == 1
        answer = build_answer(results[0].entry)
        assert "extends CharacterBody2D" in answer
        assert str(answer_file) in answer
