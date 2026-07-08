# Agentic RAG over a folder of Markdown (Gemini 3.1 Flash Lite)



```
ingest.py     files (pdf/docx/...) --> Markdown in ./knowledge_base/  (+ manifest.json)
kb_tools.py   the tools the agent calls: list_documents / find_documents /
              search_documents (grep) / read_document
agent.py      LangChain agent + Gemini 3.1 Flash Lite -> interactive Q&A loop
```

---

## 1. Prerequisites

- Python 3.10 or newer (`python3 --version` to check).
- A Gemini API key (free tier works) — get one at Google AI Studio:
  https://aistudio.google.com/apikey

---

## 2. Install

From the project folder:

```bash
cd /Users/vqlinh020607/Desktop/vscode/agent_RAG_test
```

(Optional but recommended) create an isolated virtual environment so these
packages don't mix with anything else on your machine:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt` pulls in `langchain`, `langgraph`, `langchain-google-genai`,
and `markitdown[all]` (used by `ingest.py` to convert PDFs/DOCX/etc. to Markdown).

---

## 3. Set your Gemini API key

Set it for the current terminal session:

```bash
export GOOGLE_API_KEY="your_gemini_api_key"   # or GEMINI_API_KEY
```

To avoid retyping this every time you open a new terminal, add it to your
shell profile instead:

```bash
echo 'export GOOGLE_API_KEY="your_gemini_api_key"' >> ~/.zshrc
source ~/.zshrc
```

Verify it's picked up:

```bash
python3 -c "import os; print('set' if os.environ.get('GOOGLE_API_KEY') else 'missing')"
```

---

## 4. Build the knowledge base

Generate and ingest a few sample documents (financial report, security policy,
onboarding guide, a Vietnamese note) to try things out immediately:

```bash
python3 ingest.py --demo
```

Or ingest your own files/folders:

```bash
python3 ingest.py report.pdf notes.docx ./some_folder
```

This writes one `.md` file per source document into `./knowledge_base/`, plus a
`manifest.json` recording where each came from. By default the output goes to
`./knowledge_base` — override with the `KB_DIR` environment variable if you
want a different location:

```bash
export KB_DIR="/path/to/another/kb"
```

(Set `KB_DIR` the same way before running `agent.py` too, so the agent reads
from the same place you ingested into.)

---

## 5. Run the agent

Run it directly:

```bash
python3 agent.py
```

Or, since it has a shebang and is executable, just:

```bash
./agent.py
```

This drops you into an interactive prompt:

```
Q: What was the total revenue in Q3?
  [tool] search_documents({'query': 'revenue'})
  [result] 1 match(es) for 'revenue' (showing up to 20):
  [tool] read_document({'filenames': 'q3_report.md'})
  [result] # q3_report.md (lines 1-6 of 6)

A: Total revenue in Q3 2026 was 12.4 million USD, up 8% from Q2.

Q: How does that compare to operating costs?
...

Q: reset
Memory cleared.

Q: exit
Stopped
```

**Commands available at the `Q:` prompt:**
| Type              | Effect                                                        |
|-------------------|----------------------------------------------------------------|
| any question      | asks the agent, using tools to search/read the knowledge base |
| `reset` / `clear` / `new` | wipes the conversation history and starts fresh          |
| `exit` / `quit` / `q`     | ends the session                                          |
| Ctrl+C / Ctrl+D           | also ends the session                                     |

The `[tool]` / `[result]` lines show you exactly what the agent searched for
and what it got back, so you can see its reasoning, not just the final answer.

---

## How memory works

Within a single run of `agent.py`, the whole conversation (your questions, the
agent's answers, and its tool calls) is kept in a list in memory and resent on
every turn, so follow-up questions like "how does *that* compare..." work
without repeating context. This memory:

- **lives only in RAM** for as long as the script is running — it is *not*
  saved to disk, so restarting `agent.py` always starts with a blank slate.
- can be **manually cleared mid-session** with `reset` (or `clear`/`new`)
  without restarting the program.
- **grows every turn**, so a very long conversation sends more tokens to
  Gemini on each question — `reset` periodically if that matters to you.

---

## How it maps to the design

- **search_documents** is the `grep` core of agentic search. Swap its body for
  a real `ripgrep` subprocess call for speed at scale.
- **Unicode NFC** normalization is applied on ingest and on every query, so
  Vietnamese (and CJK) text matches correctly.
- **Path safety**: every tool is confined to `./knowledge_base/` (or `KB_DIR`).
- **Token efficiency**: results are capped, carry line numbers, and reads are
  bounded — the agent lists/searches first, then reads only what it needs.
  `read_document` defaults to returning a whole document (up to 400 lines) and
  accepts multiple comma-separated filenames in one call.

## Next steps (not in this prototype)

- **Sandbox**: run the tools inside a Docker container (network off, read-only mount).
- **Per-user access control**: store `viewers` per file in `manifest.json`, filter the
  file list per request, and mount only allowed files — the agent never sees the rest.
- **Hybrid**: keep this grep path for instant availability, and add a background
  embedding/graph index that queries upgrade to once it finishes.
- **Persistent memory**: currently conversation memory is in-RAM only; saving
  the message history to disk (e.g. JSON) would let it survive across runs.

## Troubleshooting

- **Arrow keys print `^[[D`/`^[[C` instead of moving the cursor**: this means
  the `readline` module wasn't hooked into `input()`. `agent.py` already
  imports `readline` at the top to fix this — make sure you're running the
  updated file.
- **`ValueError: Function must have a docstring...`**: a tool in `kb_tools.py`
  is missing a docstring (LangChain's `@tool` needs one, or an explicit
  `description=`).
- **`UserWarning: Core Pydantic V1 functionality isn't compatible with Python
  3.14...`**: harmless warning from a dependency, not from this project's
  code. Safe to ignore; if it bothers you, run this project under Python
  3.11–3.12 instead of 3.14.
- **Model 404 / not found**: switch the model via
  `export GEMINI_MODEL="gemini-3.1-flash-lite-preview"` (or another available
  Gemini model id).
- **Requires LangChain 1.0+** (`create_agent`); `agent.py` falls back to
  LangGraph's `create_react_agent` automatically if that's not available.
