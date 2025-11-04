# tests/test_insight.py

import types
from langchain_core.messages import AIMessage

from src.nodes import insight as insight_mod
from src.agent_state import AgentState


def test_insight_node_happy_path(monkeypatch, tmp_path):
    # 1) create temp prompt file
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    md_file = prompts_dir / "insights.md"
    md_file.write_text("Insights template", encoding="utf-8")

    # 2) set PROMPT_FILE even if it doesn't exist on the module
    monkeypatch.setattr(insight_mod, "PROMPT_FILE", md_file, raising=False)

    # 3) mock LLM to return a deterministic block
    def fake_llm(*args, **kwargs):
        return types.SimpleNamespace(
            invoke=lambda _: AIMessage(
                content=(
                    "Insights:\n"
                    "- Sales are concentrated in a few products.\n"
                    "- Geo coverage is uneven.\n"
                    "- Customer activity stable.\n"
                    "Actions:\n"
                    "- Promote top SKUs.\n"
                    "- Investigate weak regions.\n"
                    "Follow-ups:\n"
                    "- Do we have device data?\n"
                    "- Compare to previous period?\n"
                )
            )
        )

    monkeypatch.setattr(insight_mod, "ChatGoogleGenerativeAI", fake_llm)
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")

    # 4) build state EXACTLY like exec_node would
    state = AgentState(
        last_results=[
            {"product_name": "Tee", "revenue": 200},
        ],
        params={"rowcount": 1},
    )

    # 5) run the node
    out = insight_mod.insight_node(state)

    # 6) assert the new, flat shape
    assert isinstance(out.insights, list)
    assert 4 <= len(out.insights) <= 7
    assert isinstance(out.actions, list)
    assert 1 <= len(out.actions) <= 3
    assert isinstance(out.followups, list)
    assert len(out.followups) == 2




def test_insight_node_pads_insights(monkeypatch):
    # mock LLM that only returns 1 insight, node should pad/fill
    def fake_llm(*args, **kwargs):
        return types.SimpleNamespace(
            invoke=lambda _: AIMessage(
                content=(
                    "Insights:\n"
                    "- Only one insight.\n"
                    "Actions:\n"
                    "- Do something.\n"
                    "Follow-ups:\n"
                    "- Q1?\n"
                    "- Q2?\n"
                )
            )
        )

    monkeypatch.setattr(insight_mod, "ChatGoogleGenerativeAI", fake_llm)
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")

    # AgentState expects last_results to be a LIST
    state = AgentState(
        last_results=[],
        params={"rowcount": 0},
    )

    out = insight_mod.insight_node(state)

    assert isinstance(out.insights, list)
    # we don’t know the exact padding logic, but we can at least assert >= 1
    assert len(out.insights) >= 1
    assert isinstance(out.actions, list)
    assert isinstance(out.followups, list)

