"""Per-project question-linked knowledge base."""

from __future__ import annotations

from godotllminteraction.kb.answer import build_answer
from godotllminteraction.kb.types import KbEntry, KbSearchResult

__all__ = ["KbEntry", "KbSearchResult", "build_answer"]
