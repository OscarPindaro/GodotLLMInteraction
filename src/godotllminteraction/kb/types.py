"""Pydantic models for KB entries and search results.

A KB entry links one or more questions to an "answer" that can be:
- inline text (answer_text)
- one or more local files (file_paths)
- one or more local folders (folder_paths)
- one or more GitHub URLs (github_urls) — file (/blob/) or folder (/tree/)

At registration time, all questions are embedded and the embeddings are
saved into index.npz so search never needs to re-embed existing entries.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class KbEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    questions: list[str] = Field(
        description="One or more questions this entry answers."
    )
    answer_text: str | None = Field(
        None, description="Inline text answer (NLP or code)."
    )
    file_paths: list[str] = Field(
        default_factory=list, description="Local files whose content is the answer."
    )
    folder_paths: list[str] = Field(
        default_factory=list,
        description="Local folders whose file contents are the answer.",
    )
    github_urls: list[str] = Field(
        default_factory=list,
        description="GitHub URLs (blob/ or tree/) to fetch as the answer.",
    )
    description: str = Field("", description="Human-readable description.")
    tags: list[str] = Field(default_factory=list, description="Optional tags.")
    created_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        *,
        questions: list[str],
        answer_text: str | None = None,
        file_paths: list[str] | None = None,
        folder_paths: list[str] | None = None,
        github_urls: list[str] | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ) -> KbEntry:
        if not questions:
            raise ValueError("At least one question is required.")
        if not answer_text and not file_paths and not folder_paths and not github_urls:
            raise ValueError(
                "Provide answer_text, file_paths, folder_paths, or github_urls."
            )
        return cls(
            questions=questions,
            answer_text=answer_text,
            file_paths=file_paths or [],
            folder_paths=folder_paths or [],
            github_urls=github_urls or [],
            description=description,
            tags=tags or [],
        )

    def save(self, kb_folder: Path) -> None:
        entries_dir = kb_folder / "entries"
        entries_dir.mkdir(parents=True, exist_ok=True)
        (entries_dir / f"{self.id}.json").write_text(self.model_dump_json(indent=2))


class KbSearchResult(BaseModel):
    entry: KbEntry
    score: float = Field(description="Cosine similarity (0..1).")
    matched_question: str = Field(description="Which question matched best.")
