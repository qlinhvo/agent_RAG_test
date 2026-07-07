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


**Commands available at the `Q:` prompt:**
| Type              | Effect                                                        |
|-------------------|----------------------------------------------------------------|
| any question      | asks the agent, using tools to search/read the knowledge base |
| `reset` / `clear` / `new` | wipes the conversation history and starts fresh          |
| `exit` / `quit` / `q`     | ends the session                                          |
| Ctrl+C / Ctrl+D           | also ends the session                                     |

The `[tool]` / `[result]` lines show you exactly what the agent searched for
and what it got back, so you can see its reasoning, not just the final answer.

