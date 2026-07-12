"""KB search — load pre-embedded index, embed only the query, single matmul.

Inspired by semble's approach: embeddings are pre-computed at registration
and stored in index.npz.  At search time we only embed the query and do a
single normalized dot-product against the full matrix.
"""

from __future__ import annotations
from pathlib import Path

import numpy as np

from godotllminteraction.kb.types import KbSearchResult

_model = None


def _get_model():
    global _model
    if _model is None:
        from model2vec import StaticModel

        _model = StaticModel.from_pretrained("minishlab/potion-base-2M-v1")
    return _model


def _cosine_similarity_batch(query_emb: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of one query vector against all rows of matrix."""
    q_norm = np.linalg.norm(query_emb)
    if q_norm == 0:
        return np.zeros(matrix.shape[0])
    m_norms = np.linalg.norm(matrix, axis=1)
    safe = m_norms > 0
    sims = np.zeros(matrix.shape[0])
    sims[safe] = (matrix[safe] @ query_emb) / (m_norms[safe] * q_norm)
    return sims


def search_kb(
    query: str,
    project_path: Path,
    top_k: int = 5,
) -> list[KbSearchResult]:
    """Search the KB for entries matching the query by question similarity.

    Loads the pre-embedded index (index.npz), embeds only the query, and
    does a single batched cosine similarity.  No re-embedding of entries.
    """
    from godotllminteraction.kb.storage import load_index, resolve_kb_folder

    kb_folder = resolve_kb_folder(project_path)
    index_data = load_index(kb_folder)
    if index_data is None:
        return []
    embeddings, mapping = index_data
    if embeddings.shape[0] == 0:
        return []

    model = _get_model()
    query_emb = model.encode([query])[0]

    sims = _cosine_similarity_batch(query_emb, embeddings)

    # Group by entry_id, keeping the best score per entry
    entry_best: dict[str, tuple[float, str]] = {}
    for row_idx, (entry_id, q_idx) in enumerate(mapping):
        score = float(sims[row_idx])
        if entry_id not in entry_best or score > entry_best[entry_id][0]:
            # We need the question text; load the entry lazily
            entry_best[entry_id] = (score, "")  # placeholder, fill below

    # Load entries to get question text
    from godotllminteraction.kb.storage import load_entry

    scored: list[KbSearchResult] = []
    for entry_id, (score, _) in entry_best.items():
        entry = load_entry(kb_folder, entry_id)
        if entry is None:
            continue
        # Find the best matching question text
        best_q = entry.questions[0] if entry.questions else ""
        best_s = score
        for row_idx, (eid, q_idx) in enumerate(mapping):
            if eid == entry_id and float(sims[row_idx]) > best_s:
                best_s = float(sims[row_idx])
                if q_idx < len(entry.questions):
                    best_q = entry.questions[q_idx]
        scored.append(
            KbSearchResult(entry=entry, score=best_s, matched_question=best_q)
        )

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]
