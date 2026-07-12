"""MCP tools for the per-project question-linked knowledge base."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import numpy as np
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from godotllminteraction.kb.answer import build_answer
from godotllminteraction.kb.search import _get_model, search_kb
from godotllminteraction.kb.storage import (
    append_to_index,
    list_entries,
    remove_entry,
    remove_from_index,
    resolve_kb_folder,
)
from godotllminteraction.kb.types import KbEntry
from godotllminteraction.mcp.context import McpContext


def _error_json(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


def register(server: FastMCP, ctx: McpContext) -> None:

    @server.tool()
    async def kb_search(
        query: Annotated[str, Field(description="Natural language question.")],
        top_k: Annotated[int, Field(description="Number of results.", ge=1)] = 5,
        project_path: Annotated[
            str | None, Field(description="Project path; defaults to set project.")
        ] = None,
    ) -> str:
        """Search the project's knowledge base by question similarity.

        Returns matching entries with their scores and the full answer content
        (inline text + file contents concatenated).
        """
        p = project_path or ctx.project_path
        if p is None:
            return _error_json(
                "No project path set. Call set_project first or pass project_path."
            )
        try:
            results = search_kb(query, Path(p), top_k=top_k)
        except Exception as exc:
            return _error_json(str(exc))
        return json.dumps(
            {
                "ok": True,
                "results": [
                    {
                        "entry": r.entry.model_dump(mode="json"),
                        "score": r.score,
                        "matched_question": r.matched_question,
                        "answer": build_answer(r.entry, Path(p)),
                    }
                    for r in results
                ],
            },
            indent=2,
        )

    @server.tool()
    async def kb_register(
        questions: Annotated[
            list[str], Field(description="Questions this content answers.")
        ],
        answer_text: Annotated[
            str | None, Field(description="Inline text answer (NLP or code).")
        ] = None,
        file_paths: Annotated[
            list[str] | None, Field(description="Files whose content is the answer.")
        ] = None,
        folder_paths: Annotated[
            list[str] | None,
            Field(description="Folders whose file contents are the answer."),
        ] = None,
        github_urls: Annotated[
            list[str] | None,
            Field(description="GitHub URLs (blob/ or tree/) to fetch as the answer."),
        ] = None,
        description: Annotated[
            str, Field(description="Human-readable description.")
        ] = "",
        tags: Annotated[list[str] | None, Field(description="Optional tags.")] = None,
        project_path: Annotated[
            str | None, Field(description="Project path; defaults to set project.")
        ] = None,
    ) -> str:
        """Register an answer (text, files, folders, or GitHub URLs) linked to questions in the KB.

        Questions are pre-embedded at registration time and stored in the index
        so subsequent searches never need to re-embed them.
        """
        p = project_path or ctx.project_path
        if p is None:
            return _error_json(
                "No project path set. Call set_project first or pass project_path."
            )
        try:
            entry = KbEntry.create(
                questions=questions,
                answer_text=answer_text,
                file_paths=file_paths or [],
                folder_paths=folder_paths or [],
                github_urls=github_urls or [],
                description=description,
                tags=tags or [],
            )
            kb_folder = resolve_kb_folder(Path(p))
            entry.save(kb_folder)
            # Embed questions and append to index
            model = _get_model()
            embeddings = np.array(model.encode(entry.questions), dtype=np.float32)
            append_to_index(kb_folder, entry.id, embeddings)
        except Exception as exc:
            return _error_json(str(exc))
        return json.dumps({"ok": True, "id": entry.id}, indent=2)

    @server.tool()
    async def kb_list(
        project_path: Annotated[
            str | None, Field(description="Project path; defaults to set project.")
        ] = None,
    ) -> str:
        """List all KB entries for the project."""
        p = project_path or ctx.project_path
        if p is None:
            return _error_json(
                "No project path set. Call set_project first or pass project_path."
            )
        try:
            kb_folder = resolve_kb_folder(Path(p))
            entries = list_entries(kb_folder)
        except Exception as exc:
            return _error_json(str(exc))
        return json.dumps(
            {"ok": True, "entries": [e.model_dump(mode="json") for e in entries]},
            indent=2,
        )

    @server.tool()
    async def kb_remove(
        entry_id: Annotated[str, Field(description="ID of the KB entry to remove.")],
        project_path: Annotated[
            str | None, Field(description="Project path; defaults to set project.")
        ] = None,
    ) -> str:
        """Remove a KB entry by ID."""
        p = project_path or ctx.project_path
        if p is None:
            return _error_json(
                "No project path set. Call set_project first or pass project_path."
            )
        try:
            kb_folder = resolve_kb_folder(Path(p))
            remove_entry(kb_folder, entry_id)
            remove_from_index(kb_folder, entry_id)
        except Exception as exc:
            return _error_json(str(exc))
        return json.dumps({"ok": True, "removed": entry_id}, indent=2)
