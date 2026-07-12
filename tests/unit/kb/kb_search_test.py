"""Tests for KB search — index-based cosine similarity, ranking, top_k.

These tests mock the model2vec model to avoid downloading a real model.
The mock model produces deterministic embeddings from text, allowing us to
verify the search pipeline without network access.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from godotllminteraction.kb.search import (
    _cosine_similarity_batch,
    search_kb,
)
from godotllminteraction.kb.storage import (
    append_to_index,
    save_entry,
)
from godotllminteraction.kb.types import KbEntry

pytestmark = [pytest.mark.kb]


def _mock_encode(texts: list[str]) -> np.ndarray:
    """Deterministic mock encoding: hash each word into a fixed-dim vector.

    Similar texts (sharing words) will have higher cosine similarity.
    This lets us verify the search ranking without a real model.
    """
    dim = 16
    results = []
    for text in texts:
        vec = np.zeros(dim, dtype=np.float32)
        for word in text.lower().split():
            h = hash(word) % dim
            vec[h] += 1.0
        # Add some noise from full string hash to make vectors unique
        vec[hash(text) % dim] += 0.5
        results.append(vec)
    return np.array(results, dtype=np.float32)


@pytest.fixture
def mock_model():
    """Patch _get_model to return a mock with deterministic encode."""
    model = MagicMock()
    model.encode = _mock_encode
    model.dim = 16
    with patch("godotllminteraction.kb.search._get_model", return_value=model):
        yield model


@pytest.fixture
def kb_with_entries(tmp_path: Path, mock_model) -> Path:
    """Create a KB folder with entries and pre-embedded index.

    Uses GLI_KB_LOCATION to isolate the KB to tmp_path.
    """
    kb_folder = tmp_path / "kb"
    kb_folder.mkdir()

    entries = [
        KbEntry.create(
            questions=["how to add a node to scene"],
            answer_text="Use add_node tool.",
        ),
        KbEntry.create(
            questions=["how to connect a signal"],
            answer_text="Use connect_signal tool.",
        ),
        KbEntry.create(
            questions=["how to validate scene with godot"],
            answer_text="Use validate tool.",
        ),
    ]

    for entry in entries:
        save_entry(kb_folder, entry)
        emb = _mock_encode(entry.questions)
        append_to_index(kb_folder, entry.id, emb)

    return kb_folder


class TestCosineSimilarityBatch:
    def test_identical_vectors_have_similarity_one(self):
        vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        matrix = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
        sims = _cosine_similarity_batch(vec, matrix)
        assert sims.shape == (1,)
        assert abs(sims[0] - 1.0) < 1e-5

    def test_orthogonal_vectors_have_similarity_zero(self):
        vec = np.array([1.0, 0.0], dtype=np.float32)
        matrix = np.array([[0.0, 1.0]], dtype=np.float32)
        sims = _cosine_similarity_batch(vec, matrix)
        assert abs(sims[0]) < 1e-5

    def test_zero_query_vector_returns_all_zeros(self):
        vec = np.zeros(3, dtype=np.float32)
        matrix = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
        sims = _cosine_similarity_batch(vec, matrix)
        assert sims.shape == (2,)
        assert np.all(sims == 0.0)

    def test_zero_matrix_rows_have_zero_similarity(self):
        vec = np.array([1.0, 1.0], dtype=np.float32)
        matrix = np.array([[0.0, 0.0], [1.0, 1.0]], dtype=np.float32)
        sims = _cosine_similarity_batch(vec, matrix)
        assert sims[0] == 0.0
        assert abs(sims[1] - 1.0) < 1e-5

    def test_multiple_rows_correct_ranking(self):
        query = np.array([1.0, 0.0], dtype=np.float32)
        matrix = np.array(
            [
                [0.0, 1.0],  # orthogonal, sim=0
                [1.0, 0.0],  # identical, sim=1
                [1.0, 1.0],  # 45deg, sim=0.707
            ],
            dtype=np.float32,
        )
        sims = _cosine_similarity_batch(query, matrix)
        assert sims[0] < sims[2] < sims[1]


class TestSearchKb:
    def test_returns_empty_when_no_index(self, tmp_path: Path, mock_model):
        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(tmp_path / "empty_kb")}):
            results = search_kb("query", tmp_path)
            assert results == []

    def test_returns_results_ranked_by_similarity(
        self, kb_with_entries: Path, mock_model
    ):
        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(kb_with_entries)}):
            results = search_kb("how to add a node", Path("/fake"))
            assert len(results) > 0
            # The "add a node" entry should be in top results
            top = results[0]
            assert (
                "add" in top.matched_question.lower()
                or "node" in top.matched_question.lower()
            )

    def test_top_k_limits_results(self, kb_with_entries: Path, mock_model):
        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(kb_with_entries)}):
            results = search_kb("how to add a node", Path("/fake"), top_k=1)
            assert len(results) == 1

    def test_top_k_larger_than_entries_returns_all(
        self, kb_with_entries: Path, mock_model
    ):
        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(kb_with_entries)}):
            results = search_kb("how to", Path("/fake"), top_k=100)
            assert len(results) <= 3  # only 3 entries

    def test_results_sorted_by_score_descending(
        self, kb_with_entries: Path, mock_model
    ):
        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(kb_with_entries)}):
            results = search_kb("how to", Path("/fake"), top_k=10)
            scores = [r.score for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_each_result_has_entry_score_and_matched_question(
        self, kb_with_entries: Path, mock_model
    ):
        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(kb_with_entries)}):
            results = search_kb("how to add a node", Path("/fake"))
            for r in results:
                assert r.entry is not None
                assert isinstance(r.score, float)
                assert 0.0 <= r.score <= 1.0 + 1e-5
                assert isinstance(r.matched_question, str)
                assert len(r.matched_question) > 0

    def test_search_does_not_re_embed_existing_entries(
        self, kb_with_entries: Path, mock_model
    ):
        """Verify search calls model.encode only once (for the query)."""
        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(kb_with_entries)}):
            with patch("godotllminteraction.kb.search._get_model") as mock_get:
                mock_model.encode = MagicMock(side_effect=_mock_encode)
                mock_get.return_value = mock_model
                search_kb("how to add a node", Path("/fake"))
                # Should call encode exactly once (for the query only)
                assert mock_model.encode.call_count == 1

    def test_multi_question_entry_returns_best_match(self, tmp_path: Path, mock_model):
        """Entry with multiple questions should match the best-scoring one."""
        kb_folder = tmp_path / "kb"
        kb_folder.mkdir()
        entry = KbEntry.create(
            questions=[
                "add node to scene",
                "delete node from tree",
                "move node position",
            ],
            answer_text="Use tscn tools.",
        )
        save_entry(kb_folder, entry)
        emb = _mock_encode(entry.questions)
        append_to_index(kb_folder, entry.id, emb)

        with patch.dict(os.environ, {"GLI_KB_LOCATION": str(kb_folder)}):
            results = search_kb("delete node from tree", Path("/fake"))
            assert len(results) == 1
