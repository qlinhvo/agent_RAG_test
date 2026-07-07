#!/usr/bin/env python3
import os
import readline

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from kb_tools import KB_TOOLS

load_dotenv()

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

SYSTEM_PROMPT = """You are a knowledge-base research assistant that answers with agentic RAG.
You may ONLY use information found in the knowledge base, which you reach through your tools.

"""


def _make_agent(model, tools):
    try:
        from langchain.agents import create_agent

        return create_agent(model, tools=tools, system_prompt=SYSTEM_PROMPT)
    except ImportError:
        from langgraph.prebuilt import create_react_agent

        return create_react_agent(model, tools, prompt=SYSTEM_PROMPT)


def build_agent():
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit(
            "Set GOOGLE_API_KEY (or GEMINI_API_KEY) to your Gemini API key first."
        )
    os.environ["GOOGLE_API_KEY"] = key
    model = ChatGoogleGenerativeAI(model=MODEL, temperature=0)
    return _make_agent(model, KB_TOOLS)


def run_query(agent, messages: list, question: str, verbose: bool = True) -> tuple[str, list]:
    messages = messages + [{"role": "user", "content": question}]
    result = agent.invoke({"messages": messages})
    messages = result["messages"]

    if verbose:
        for m in messages:
            for call in getattr(m, "tool_calls", None) or []:
                print(f"  [tool] {call['name']}({call['args']})")
            if isinstance(m, ToolMessage):
                preview = m.content if isinstance(m.content, str) else str(m.content)
                first_line = preview.splitlines()[0] if preview else "(empty)"
                print(f"  [result] {first_line}")

    content = messages[-1].content
    if isinstance(content, list):
        content = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ).strip()
    return content, messages


if __name__ == "__main__":
    agent = build_agent()
    messages: list = []
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
            messages = []
            print("Memory cleared.\n")
            continue
        if not question:
            continue

        answer, messages = run_query(agent, messages, question)
        print(f"\nA: {answer}\n")
