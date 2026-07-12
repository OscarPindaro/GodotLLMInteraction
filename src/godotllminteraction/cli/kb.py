"""CLI subcommand group for `gli kb` — per-project question-linked knowledge base."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

import numpy as np
import typer

from godotllminteraction.cli._common import (
    EXIT_USAGE,
    print_error,
    print_success,
    print_text,
)
from godotllminteraction.kb.answer import build_answer
from godotllminteraction.kb.search import _get_model, search_kb
from godotllminteraction.kb.storage import (
    append_to_index,
    clear_kb,
    list_entries,
    remove_entry,
    remove_from_index,
    resolve_kb_folder,
    save_entry,
)
from godotllminteraction.kb.types import KbEntry

app = typer.Typer(help="Per-project question-linked knowledge base.")


@app.command()
def register(
    questions: Annotated[
        list[str],
        typer.Option(
            "--question", "-q", help="Question this content answers; repeatable."
        ),
    ],
    paths: Annotated[
        list[str],
        typer.Argument(help="Files to link (project-relative or absolute)."),
    ] = [],
    folders: Annotated[
        list[str],
        typer.Option("--folder", help="Folder whose files are the answer; repeatable."),
    ] = [],
    answer_text: Annotated[
        Optional[str],
        typer.Option("--text", help="Inline text answer (NLP or code)."),
    ] = None,
    github_urls: Annotated[
        list[str],
        typer.Option("--github", help="GitHub URL (blob/ or tree/); repeatable."),
    ] = [],
    description: Annotated[
        str, typer.Option("--description", "-d", help="Human-readable description.")
    ] = "",
    tags: Annotated[
        list[str], typer.Option("--tag", "-t", help="Optional tag; repeatable.")
    ] = [],
    project: Annotated[
        Path,
        typer.Option("--project", "-p", help="Project directory; defaults to cwd."),
    ] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Print JSON result.")
    ] = False,
) -> None:
    """Register an answer (text, files, or folders) linked to questions in the KB."""
    if not questions:
        print_error("At least one --question is required.")
        raise typer.Exit(code=EXIT_USAGE)
    if not paths and not folders and not answer_text and not github_urls:
        print_error("Provide file paths, --folder, --text, or --github.")
        raise typer.Exit(code=EXIT_USAGE)

    entry = KbEntry.create(
        questions=questions,
        answer_text=answer_text,
        file_paths=paths,
        folder_paths=folders,
        github_urls=github_urls,
        description=description,
        tags=tags,
    )
    kb_folder = resolve_kb_folder(project)
    save_entry(kb_folder, entry)
    # Embed questions and append to index
    model = _get_model()
    embeddings = np.array(model.encode(entry.questions), dtype=np.float32)
    append_to_index(kb_folder, entry.id, embeddings)
    if json_output:
        print(json.dumps({"ok": True, "id": entry.id}, indent=2))
    else:
        print_success(f"Registered entry {entry.id} with {len(questions)} question(s).")


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Natural language question to search.")],
    top_k: Annotated[int, typer.Option("--top-k", "-k", help="Number of results.")] = 5,
    project: Annotated[
        Path,
        typer.Option("--project", "-p", help="Project directory; defaults to cwd."),
    ] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Print JSON result.")
    ] = False,
) -> None:
    """Search the KB by question similarity."""
    results = search_kb(query, project, top_k=top_k)
    if json_output:
        print(
            json.dumps(
                [
                    {
                        "entry": r.entry.model_dump(mode="json"),
                        "score": r.score,
                        "matched_question": r.matched_question,
                        "answer": build_answer(r.entry, project),
                    }
                    for r in results
                ],
                indent=2,
            )
        )
    else:
        if not results:
            print_text("No results.")
            return
        for r in results:
            answer = build_answer(r.entry, project)
            preview = answer[:200] + "..." if len(answer) > 200 else answer
            print_text(f"[{r.score:.3f}] {r.matched_question}\n  answer: {preview}")


@app.command()
def list(
    project: Annotated[
        Path,
        typer.Option("--project", "-p", help="Project directory; defaults to cwd."),
    ] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Print JSON result.")
    ] = False,
) -> None:
    """List all KB entries for the project."""
    kb_folder = resolve_kb_folder(project)
    entries = list_entries(kb_folder)
    if json_output:
        print(json.dumps([e.model_dump(mode="json") for e in entries], indent=2))
    else:
        if not entries:
            print_text("No entries.")
            return
        for e in entries:
            print_text(
                f"{e.id}: {e.questions[0]} ({len(e.questions)} q, {len(e.file_paths)} files)"
            )


@app.command()
def remove(
    entry_id: Annotated[str, typer.Argument(help="ID of the KB entry to remove.")],
    project: Annotated[
        Path,
        typer.Option("--project", "-p", help="Project directory; defaults to cwd."),
    ] = Path("."),
) -> None:
    """Remove a KB entry by ID."""
    kb_folder = resolve_kb_folder(project)
    if remove_entry(kb_folder, entry_id):
        remove_from_index(kb_folder, entry_id)
        print_success(f"Removed entry {entry_id}.")
    else:
        print_error(f"Entry {entry_id} not found.")
        raise typer.Exit(code=EXIT_USAGE)


@app.command()
def clear(
    project: Annotated[
        Path,
        typer.Option("--project", "-p", help="Project directory; defaults to cwd."),
    ] = Path("."),
    yes: Annotated[
        bool, typer.Option("-y", "--yes", help="Skip confirmation.")
    ] = False,
) -> None:
    """Clear all KB entries for the project."""
    if not yes:
        if not typer.confirm("Remove all KB entries?"):
            print_text("Aborted.")
            return
    kb_folder = resolve_kb_folder(project)
    count = clear_kb(kb_folder)
    print_success(f"Cleared {count} entr(y/ies).")
