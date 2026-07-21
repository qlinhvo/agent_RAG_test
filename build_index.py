#!/usr/bin/env python3
"""Build/update the semantic (embedding) index over the knowledge base, so
semantic_search can find passages by meaning instead of exact wording.

Run this after ingest.py, any time documents are added, changed, or removed.
Unchanged files are skipped (tracked by content hash), so re-running this is
cheap once the index is caught up.
"""
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

KB_DIR = Path(os.environ.get("KB_DIR") or "knowledge_base").resolve()
INDEX_DIR = KB_DIR / ".chroma"
STATE_FILE = INDEX_DIR / "index_state.json"
EMBED_MODEL = os.environ.get("EMBED_MODEL") or "models/gemini-embedding-001"
COLLECTION_NAME = "kb_chunks"

CHUNK_LINES = 40
CHUNK_OVERLAP = 8


def _chunk(lines: list[str]) -> list[tuple[int, int, str]]:
    """Split lines into overlapping (start_line, end_line, text) chunks, 1-indexed."""
    chunks = []
    step = CHUNK_LINES - CHUNK_OVERLAP
    i = 0
    while i < len(lines):
        start, end = i, min(len(lines), i + CHUNK_LINES)
        text = "\n".join(lines[start:end]).strip()
        if text:
            chunks.append((start + 1, end, text))
        if end == len(lines):
            break
        i += step
    return chunks


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_index() -> None:
    import chromadb

    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("Set GOOGLE_API_KEY (or GEMINI_API_KEY) to your Gemini API key first.")
    os.environ["GOOGLE_API_KEY"] = key

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    state: dict = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    collection = client.get_or_create_collection(COLLECTION_NAME)
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBED_MODEL)

    docs = sorted(KB_DIR.glob("*.md"))
    current_names = {p.name for p in docs}

    for name in list(state):
        if name not in current_names:
            collection.delete(where={"source": name})
            del state[name]
            print(f"  removed (deleted): {name}")

    for path in docs:
        digest = _file_hash(path)
        if state.get(path.name) == digest:
            continue

        collection.delete(where={"source": path.name})
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        chunks = _chunk(lines)
        if not chunks:
            state[path.name] = digest
            STATE_FILE.write_text(json.dumps(state, indent=2))
            continue

        texts = [c[2] for c in chunks]
        vectors = embeddings.embed_documents(texts)
        ids = [f"{path.name}::{start}-{end}" for start, end, _ in chunks]
        metadatas = [
            {"source": path.name, "start_line": start, "end_line": end}
            for start, end, _ in chunks
        ]
        collection.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
        state[path.name] = digest
        STATE_FILE.write_text(json.dumps(state, indent=2))
        print(f"  indexed: {path.name} ({len(chunks)} chunk(s))")

    print(f"Done. Index at {INDEX_DIR}")


if __name__ == "__main__":
    build_index()
