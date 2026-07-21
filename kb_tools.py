
import json
import os
import re
import shutil
import subprocess
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


_RG_BIN = shutil.which("rg")


def _rg_matches(pattern: str, cap: int) -> list[tuple[Path, int]] | None:
    """Use ripgrep (if installed) to quickly find matching (file, line_number)
    pairs. Returns None if rg isn't available or errors, so the caller falls
    back to the pure-Python scan."""
    if not _RG_BIN:
        return None
    try:
        proc = subprocess.run(
            [_RG_BIN, "--json", "-i", "-g", "*.md", "-e", pattern, str(KB_DIR)],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    matches: list[tuple[Path, int]] = []
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "match":
            continue
        data = event["data"]
        matches.append((Path(data["path"]["text"]), data["line_number"]))
        if len(matches) >= cap:
            break
    return matches


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
    cap = min(max_results, MAX_RESULTS)
    results: list[str] = []

    rg_matches = _rg_matches(q, cap)
    if rg_matches is not None:
        file_cache: dict[Path, list[str]] = {}
        for path, line_no in rg_matches:
            if path not in file_cache:
                file_cache[path] = path.read_text(encoding="utf-8", errors="replace").splitlines()
            lines = file_cache[path]
            i = line_no - 1
            lo = max(0, i - context_lines)
            hi = min(len(lines), i + context_lines + 1)
            snippet = "\n".join(lines[lo:hi]).strip()[:MAX_SNIPPET_CHARS]
            results.append(f"{path.name}:{line_no}\n{snippet}")
    else:
        try:
            pattern = re.compile(q, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(q), re.IGNORECASE)

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
    this returns the document from the start (up to 2000 lines per call) — prefer this
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


EMBED_MODEL = os.environ.get("EMBED_MODEL") or "models/gemini-embedding-001"
_INDEX_DIR = KB_DIR / ".chroma"


def _semantic_collection():
    if not _INDEX_DIR.exists():
        return None
    import chromadb

    client = chromadb.PersistentClient(path=str(_INDEX_DIR))
    try:
        return client.get_collection("kb_chunks")
    except Exception:
        return None


@tool
def semantic_search(query: str, max_results: int = 5) -> str:
    """Search the knowledge base by MEANING rather than exact words, using an
    embedding index (built ahead of time by build_index.py). Use this when
    search_documents (exact/regex match) comes up empty, or when the question is
    conceptual/paraphrased and unlikely to share exact wording with the source
    text (e.g. "dangers of climate change" should still find text about "risks
    of global warming"). If no index has been built yet, this tells you so —
    fall back to search_documents/read_document in that case."""
    collection = _semantic_collection()
    if collection is None:
        return (
            "No semantic index found yet. Run build_index.py to enable "
            "meaning-based search, or use search_documents/read_document instead."
        )

    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    embeddings = GoogleGenerativeAIEmbeddings(model=EMBED_MODEL)
    try:
        vector = embeddings.embed_query(_nfc(query))
    except Exception as exc:
        return (
            f"semantic_search is temporarily unavailable ({exc}). "
            "Fall back to search_documents/read_document instead."
        )

    cap = min(max_results, MAX_RESULTS)
    found = collection.query(query_embeddings=[vector], n_results=cap)
    docs = found.get("documents", [[]])[0]
    metas = found.get("metadatas", [[]])[0]
    if not docs:
        return f"No semantically similar passages found for {query!r}."

    results = []
    for doc, meta in zip(docs, metas):
        snippet = doc.strip()[:MAX_SNIPPET_CHARS]
        results.append(f"{meta['source']}:{meta['start_line']}-{meta['end_line']}\n{snippet}")
    return (
        f"{len(results)} semantically similar passage(s) for {query!r}:\n"
        + "\n---\n".join(results)
    )


KB_TOOLS = [list_documents, find_documents, search_documents, read_document, semantic_search]