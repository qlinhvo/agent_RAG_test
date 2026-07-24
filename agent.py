import json
import os
import readline
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver

from kb_tools import KB_TOOLS

load_dotenv()

MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.1-flash-lite"
AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH") or "audit.log"

SYSTEM_PROMPT = """You are a knowledge-base research assistant that answers using agentic RAG:
gather evidence with your tools (list_documents, find_documents, search_documents,
read_document, semantic_search) before answering, rather than relying on outside/prior
knowledge.

- Use ONLY information found in the knowledge base. If something isn't in the documents
  you retrieved, say so plainly instead of guessing or filling the gap with outside knowledge.
- Prefer search_documents (exact/regex match) first. If it finds nothing and the question
  is conceptual or likely phrased differently than the source text, try semantic_search
  (meaning-based match) before giving up.
- You MAY reason over retrieved facts: compute numbers, compare figures across documents,
  summarize, or synthesize an answer from multiple sources. This is expected and encouraged.
- Clearly separate what a document explicitly states from what you are inferring. Never
  assert a causal or logical connection between two documents (e.g. "X requires Y" or
  "X is necessary for Y") unless the documents actually say so — if two documents are
  simply unrelated, say that plainly rather than inventing a link between them.
- When a fact isn't obvious from context, mention which document it came from.
"""


def _make_agent(model, tools, checkpointer):
    try:
        from langchain.agents import create_agent

        return create_agent(
            model, tools=tools, system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer
        )
    except ImportError:
        from langgraph.prebuilt import create_react_agent

        return create_react_agent(
            model, tools, prompt=SYSTEM_PROMPT, checkpointer=checkpointer
        )


def build_agent():
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit(
            "Set GOOGLE_API_KEY (or GEMINI_API_KEY) to your Gemini API key first."
        )
    os.environ["GOOGLE_API_KEY"] = key
    model = ChatGoogleGenerativeAI(model=MODEL, temperature=0)
    return _make_agent(model, KB_TOOLS, MemorySaver())


def _audit(event: dict) -> None:
    record = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_query(agent, thread_id: str, question: str, verbose: bool = True) -> str:
    config = {"configurable": {"thread_id": thread_id}}
    prior_state = agent.get_state(config)
    prev_len = len(prior_state.values.get("messages", [])) if prior_state.values else 0

    _audit({"type": "question", "thread_id": thread_id, "question": question})
    result = agent.invoke({"messages": [{"role": "user", "content": question}]}, config=config)
    messages = result["messages"]
    new_messages = messages[prev_len + 1:]  # only this turn's messages, not prior history

    for m in new_messages:
        for call in getattr(m, "tool_calls", None) or []:
            if verbose:
                print(f"  [tool] {call['name']}({call['args']})")
            _audit({"type": "tool_call", "tool": call["name"], "args": call["args"]})
        if isinstance(m, ToolMessage):
            preview = m.content if isinstance(m.content, str) else str(m.content)
            first_line = preview.splitlines()[0] if preview else "(empty)"
            if verbose:
                print(f"  [result] {first_line}")
            _audit({
                "type": "tool_result",
                "tool": getattr(m, "name", None),
                "result": preview[:500],
            })

    content = messages[-1].content
    if isinstance(content, list):
        content = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ).strip()
    _audit({"type": "answer", "answer": content})
    return content


if __name__ == "__main__":
    agent = build_agent()
    thread_id = str(uuid.uuid4())
    while True:
        try:
            question = input("Q: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nStopped")
            break

        if question.lower() in {"exit", "quit", "q"}:
            print("Stopped")
            break
        if question.lower() in {"reset", "clear", "new"}:
            thread_id = str(uuid.uuid4())
            print("Memory cleared.\n")
            continue
        if not question:
            continue

        answer = run_query(agent, thread_id, question)
        print(f"\nA: {answer}\n")
