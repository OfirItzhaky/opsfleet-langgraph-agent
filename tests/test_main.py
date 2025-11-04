# tests/test_main.py

import importlib
import types
from langchain_core.messages import AIMessage

from src.graph import build_graph
from src.agent_state import AgentState


def test_cli_graph_invokes_with_minimal_state(monkeypatch):
    # 1) make sure env vars exist
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    # 2) reload config so it picks up the patched env
    importlib.reload(importlib.import_module("src.config"))

    # 3) reload insight module and mock the LLM it uses
    insight_mod = importlib.reload(importlib.import_module("src.nodes.insight"))

    def fake_llm(*args, **kwargs):
        # behave like the real LLM object: have .invoke(...) that returns an AIMessage
        return types.SimpleNamespace(
            invoke=lambda _: AIMessage(
                content=(
                    "Insights:\n"
                    "- Dummy insight for test.\n"
                    "Actions:\n"
                    "- Dummy action.\n"
                    "Follow-ups:\n"
                    "- Dummy follow-up 1.\n"
                    "- Dummy follow-up 2.\n"
                )
            )
        )

    # patch the symbol the node actually calls
    monkeypatch.setattr(insight_mod, "ChatGoogleGenerativeAI", fake_llm)

    # 4) now build and run the graph
    graph = build_graph()
    state = AgentState(user_query="show me sales by country")

    out = graph.invoke(state.model_dump())

    assert isinstance(out, dict)
    assert "user_query" in out
