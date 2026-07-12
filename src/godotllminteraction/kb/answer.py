"""Build answer content from KB entries — read files/folders/github and format output."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.request import Request, urlopen

from godotllminteraction.kb.types import KbEntry

_GITHUB_BLOB_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/blob/(?P<branch>[^/]+)/(?P<path>.+)$"
)
_GITHUB_TREE_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/tree/(?P<branch>[^/]+)/(?P<path>.+)$"
)
_TEXT_EXTENSIONS = {
    ".gd",
    ".tscn",
    ".tres",
    ".json",
    ".yaml",
    ".yml",
    ".txt",
    ".md",
    ".cfg",
    ".toml",
    ".py",
    ".js",
    ".ts",
    ".cpp",
    ".h",
    ".c",
    ".hx",
    ".glsl",
    ".shader",
}


def _read_file(path: Path) -> str:
    try:
        return path.read_text()
    except Exception as exc:
        return f"[error reading {path}: {exc}]"


def _collect_folder_files(folder: Path) -> list[Path]:
    """Collect all readable text files from a folder (non-recursive for now)."""
    if not folder.is_dir():
        return []
    result: list[Path] = []
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix in _TEXT_EXTENSIONS:
            result.append(p)
    return result


def _fetch_url(url: str) -> str:
    try:
        req = Request(url, headers={"User-Agent": "gli-kb"})
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return f"[error fetching {url}: {exc}]"


def _fetch_github_blob(owner: str, repo: str, branch: str, path: str) -> str:
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    content = _fetch_url(raw_url)
    source_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
    return f"<{source_url}>\n{content}"


def _fetch_github_tree(owner: str, repo: str, branch: str, path: str) -> str:
    """Fetch all text files from a GitHub folder via the contents API."""
    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    )
    try:
        req = Request(
            api_url,
            headers={"User-Agent": "gli-kb", "Accept": "application/vnd.github+json"},
        )
        with urlopen(req, timeout=30) as resp:
            import json

            items = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return f"[error fetching github tree {owner}/{repo}/{branch}/{path}: {exc}]"

    if not isinstance(items, list):
        return f"[error: expected list from GitHub API, got {type(items).__name__}]"

    parts: list[str] = []
    for item in sorted(items, key=lambda i: i.get("name", "")):
        if item.get("type") != "file":
            continue
        name = item.get("name", "")
        if not any(name.endswith(ext) for ext in _TEXT_EXTENSIONS):
            continue
        download_url = item.get("download_url")
        if not download_url:
            continue
        content = _fetch_url(download_url)
        source_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}/{name}"
        parts.append(f"<{source_url}>\n{content}")

    return "\n---\n".join(parts)


def _fetch_github_url(url: str) -> str:
    """Fetch content from a GitHub blob or tree URL."""
    m = _GITHUB_BLOB_RE.match(url)
    if m:
        return _fetch_github_blob(m["owner"], m["repo"], m["branch"], m["path"])
    m = _GITHUB_TREE_RE.match(url)
    if m:
        return _fetch_github_tree(m["owner"], m["repo"], m["branch"], m["path"])
    return f"[error: not a valid GitHub blob/tree URL: {url}]"


def build_answer(entry: KbEntry, project_path: Path | None = None) -> str:
    """Build the full answer text for a KB entry.

    Format:
        <file_path>
        content of file
        ---
        <file_path>
        content of file

    Or inline answer_text if no files/folders.
    """
    parts: list[str] = []

    if entry.answer_text:
        parts.append(entry.answer_text)

    for fp in entry.file_paths:
        p = Path(fp)
        if not p.is_absolute() and project_path is not None:
            p = project_path / p
        if p.exists() and p.is_file():
            content = _read_file(p)
            parts.append(f"<{p}>\n{content}")

    for folder in entry.folder_paths:
        f = Path(folder)
        if not f.is_absolute() and project_path is not None:
            f = project_path / f
        if f.is_dir():
            for file_p in _collect_folder_files(f):
                content = _read_file(file_p)
                parts.append(f"<{file_p}>\n{content}")

    for url in entry.github_urls:
        parts.append(_fetch_github_url(url))

    return "\n---\n".join(parts)
