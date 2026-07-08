
import os
import re
import unicodedata
from pathlib import Path

try:
    from langchain.tools import tool
except ImportError:  
    from langchain_core.tools import tool

KB_DIR = Path(os.environ.get("KB_DIR") or "knowledge_base").resolve()

MAX_RESULTS = 25
MAX_SNIPPET_CHARS = 300
MAX_READ_LINES = 2000


def _nfc(text: str) -> str:
    """Normalize to Unicode NFC so queries match the NFC-normalized corpus."""
    return unicodedata.normalize("NFC", text)


def _safe_path(filename: str) -> Path:
    """Resolve a filename inside KB_DIR and refuse anything that escapes it."""
    candidate = (KB_DIR / filename).resolve()
    if KB_DIR not in candidate.parents and candidate != KB_DIR:
        raise ValueError("Path escapes the knowledge base directory.")
    return candidate


def _docs() -> list[Path]:
    return sorted(KB_DIR.glob("*.md"))


@tool
def list_documents() -> str:
    """List all documents currently in the knowledge base."""
    files = _docs()
    if not files:
        return f"The knowledge base at {KB_DIR} is empty. Run ingest.py first."
    lines = [f"- {p.name} ({p.stat().st_size} bytes)" for p in files]
    return f"{len(files)} document(s):\n" + "\n".join(lines)


@tool
def find_documents(name_contains: str) -> str:
    """Find documents by FILENAME substring only. Does not search file content —
    use search_documents instead if you're looking for a topic or term."""
    sub = name_contains.lower()
    files = [p for p in _docs() if sub in p.name.lower()]
    if not files:
        return f"No documents with '{name_contains}' in the name."
    return "Matching documents:\n" + "\n".join(f"- {p.name}" for p in files)


@tool
def search_documents(query: str, max_results: int = 20, context_lines: int = 2) -> str:
    """Search the CONTENT of every document for a term or regex. This is usually the
    right first step for any topic-based question. Returns short snippets with filename
    and line number; call read_document afterward if a snippet needs more surrounding
    context, or if search returns hits in multiple files, pass all their filenames to
    read_document at once (comma-separated) instead of calling it once per file."""
    q = _nfc(query)
    try:
        pattern = re.compile(q, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(q), re.IGNORECASE)

    cap = min(max_results, MAX_RESULTS)
    results: list[str] = []
    for path in _docs():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if pattern.search(line):
                lo = max(0, i - context_lines)
                hi = min(len(lines), i + context_lines + 1)
                snippet = "\n".join(lines[lo:hi]).strip()[:MAX_SNIPPET_CHARS]
                results.append(f"{path.name}:{i + 1}\n{snippet}")
                if len(results) >= cap:
                    break
        if len(results) >= cap:
            break

    if not results:
        return f"No matches for {query!r}. Try a shorter or different term."
    return (
        f"{len(results)} match(es) for {query!r} (showing up to {cap}):\n"
        + "\n---\n".join(results)
    )


def _read_one(filename: str, start_line: int, end_line: int | None) -> str:
    try:
        path = _safe_path(filename)
    except ValueError as exc:
        return str(exc)
    if not path.exists():
        return f"File not found: {filename}. Use list_documents to see what exists."

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, start_line)
    if start > len(lines):
        return f"{filename} has only {len(lines)} lines."
    cap = start + MAX_READ_LINES - 1
    end = min(len(lines), cap if end_line is None else min(end_line, cap))
    body = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
    more = f" ({len(lines) - end} more lines — call again with start_line={end + 1} to continue)" if end < len(lines) else ""
    return f"# {filename} (lines {start}-{end} of {len(lines)}){more}\n{body}"


@tool
def read_document(filenames: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read one or more documents in the knowledge base. Called with just a filename,
    this returns the document from the start (up to 400 lines per call) — prefer this
    by default so your answer is grounded in the full article, not just the snippet
    search_documents matched on. If the result header says "N more lines — call again
    with start_line=X", the document is longer than one call can return: call
    read_document again with that start_line (leave end_line unset) to fetch the next
    chunk, and repeat until there's no "more lines" note left. Pass several filenames
    separated by commas to read them all in one call instead of one call per file."""
    names = [n.strip() for n in filenames.split(",") if n.strip()]
    if not names:
        return "No filename provided."
    if len(names) == 1:
        return _read_one(names[0], start_line, end_line)
    return "\n\n".join(_read_one(name, start_line, end_line) for name in names)


KB_TOOLS = [list_documents, find_documents, search_documents, read_document]