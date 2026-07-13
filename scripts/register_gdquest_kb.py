"""Register GDQuest KB entries from docs/gdquest_kb_entries.md into the gli KB."""

import re
import sys
from pathlib import Path

import numpy as np


from godotllminteraction.kb.search import _get_model
from godotllminteraction.kb.storage import (
    append_to_index,
    resolve_kb_folder,
    save_entry,
)
from godotllminteraction.kb.types import KbEntry

# Ensure project root on path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))


def parse_entries(md_path: Path) -> list[dict]:
    """Parse the markdown file into a list of entry dicts."""
    content = md_path.read_text()
    entries = []

    # Split by ### Entry headers
    blocks = re.split(r"^### Entry: ", content, flags=re.MULTILINE)
    for block in blocks[1:]:  # skip preamble
        lines = block.strip().split("\n")
        title = lines[0].strip()

        # Join remaining lines for field extraction
        body = "\n".join(lines[1:])

        # Extract Question (single, quoted)
        q_match = re.search(
            r'-\s+\*\*Question\*\*:\s*"(.*?)"\s*$',
            body,
            re.MULTILINE | re.DOTALL,
        )
        question = q_match.group(1).strip() if q_match else ""

        # Extract GitHub URLs
        url_section = re.search(
            r"-\s+\*\*GitHub URLs\*\*:\s*\n((?:\s+-\s+`[^`]+`\n?)+)",
            body,
        )
        urls = []
        if url_section:
            urls = re.findall(r"`([^`]+)`", url_section.group(1))

        # Extract Tags
        tag_section = re.search(r"-\s+\*\*Tags\*\*:\s*(.+)$", body, re.MULTILINE)
        tags = []
        if tag_section:
            tags = [
                t.strip().strip("`")
                for t in tag_section.group(1).split(",")
                if t.strip()
            ]

        if question and urls:
            entries.append(
                {
                    "title": title,
                    "question": question,
                    "github_urls": urls,
                    "tags": tags,
                }
            )

    return entries


def main() -> None:
    md_path = project_root / "docs" / "gdquest_kb_entries.md"
    entries_data = parse_entries(md_path)
    print(f"Parsed {len(entries_data)} entries from {md_path}")

    kb_folder = resolve_kb_folder(project_root)
    model = _get_model()

    for i, ed in enumerate(entries_data, 1):
        entry = KbEntry.create(
            questions=[ed["question"]],
            github_urls=ed["github_urls"],
            description=ed["title"],
            tags=ed["tags"],
        )
        save_entry(kb_folder, entry)
        embeddings = np.array(model.encode(entry.questions), dtype=np.float32)
        append_to_index(kb_folder, entry.id, embeddings)
        print(f"  [{i}/{len(entries_data)}] Registered: {ed['title']}")

    print(f"\nDone! Registered {len(entries_data)} KB entries.")


if __name__ == "__main__":
    main()
