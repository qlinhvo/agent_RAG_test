# Agentic RAG over a folder of Markdown (Gemini 3.1 Flash Lite)


```
ingest.py     files (pdf/docx/...) --> Markdown in ./knowledge_base/  (+ manifest.json)
kb_tools.py   the tools the agent calls: list / find / search(grep) / read
agent.py      LangChain agent + Gemini 3.1 Flash Lite -> answers a question
```

## 1. Install

```bash
pip install -r requirements.txt
```

## 2. Set your Gemini API key

```bash
export GOOGLE_API_KEY="gemini_api_key"   # or GEMINI_API_KEY
```


## 3. Build the knowledge base


```bash
python ingest.py --demo
```


```bash
python ingest.py report.pdf notes.docx ./some_folder
```

This writes `*.md` files into `./knowledge_base/`.

## 4. Ask questions

```bash
python agent.py "What was the Q3 revenue?"
python agent.py "What is the password policy?"
python agent.py "Doanh thu quý 3 thế nào?"
```

You'll see the agent's tool calls (its searches) followed by the final answer.

## How it maps to the design

- **search_documents** is the `grep` core of agentic search. Swap its body for a real
  `ripgrep` subprocess call for speed at scale (see the note in `kb_tools.py`).
- **Unicode NFC** normalization is applied on ingest and on every query, so Vietnamese
  (and CJK) text matches correctly.
- **Path safety**: every tool is confined to `./knowledge_base/`.
- **Token efficiency**: results are capped, carry line numbers, and reads are bounded —
  the agent lists/searches first, then reads only the needed slice.

## Next steps (not in this prototype)

- **Sandbox**: run the tools inside a Docker container (network off, read-only mount).
- **Per-user access control**: store `viewers` per file in `manifest.json`, filter the
  file list per request, and mount only allowed files — the agent never sees the rest.
- **Hybrid**: keep this grep path for instant availability, and add a background
  embedding/graph index that queries upgrade to once it finishes.

## Notes

- Requires LangChain 1.0+ (`create_agent`); `agent.py` falls back to LangGraph's
  `create_react_agent` automatically if needed.
- If the model id returns a 404, switch `GEMINI_MODEL` to `gemini-3.1-flash-lite-preview`.
