
import os
import sys

from langchain_google_genai import ChatGoogleGenerativeAI

from kb_tools import KB_TOOLS

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


def run_query(question: str, verbose: bool = True) -> str:
    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    messages = result["messages"]

    if verbose:
        for m in messages:
            for call in getattr(m, "tool_calls", None) or []:
                print(f"  [tool] {call['name']}({call['args']})")

    content = messages[-1].content
    if isinstance(content, list):
        content = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ).strip()
    return content


if __name__ == "__main__":
    agent = build_agent()
    while True:
        try:
            question = input("Q: ").strip()
        except (EOFError, KeyboardInterrupt):  
            print("\nStopped")
            break

        if question.lower() in {"exit", "quit", "q"}:
            print("Stopped")
            break
        if not question:          
            continue

        answer = run_query(question)
        print(f"\nA: {answer}\n")
