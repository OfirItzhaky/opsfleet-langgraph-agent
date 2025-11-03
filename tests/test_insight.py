# tests/test_insight_node.py
import types
from langchain_core.messages import AIMessage
from src.nodes import insight as insight_mod


def test_insight_node_happy_path(monkeypatch, tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    md_file = prompts_dir / "insights.md"
    md_file.write_text(
        "Insights:\n- X\n\nActions:\n- Y\n\nFollow-ups:\n- Z\n- W\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(insight_mod, "PROMPT_FILE", md_file)

    # mock LangChain LLM
    def fake_llm(*args, **kwargs):
        return types.SimpleNamespace(
            invoke=lambda _: AIMessage(
                content=(
                    "Insights:\n"
                    "- Sales are concentrated in a few products.\n"
                    "- Geo coverage is uneven.\n"
                    "- Customer activity stable.\n"
                    "- Consider device split.\n"
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

    state = {
        "results": {
            "summary": {"total_revenue": 1000, "orders": 20},
            "top_products": [{"name": "Tee", "revenue": 200}],
            "by_geo": [{"country": "US", "revenue": 500}],
        }
    }

    out = insight_mod.insight_node(state)
    ins = out["insights"]
    assert 4 <= len(ins["bullets"]) <= 7
    assert 1 <= len(ins["actions"]) <= 3
    assert len(ins["followups"]) == 2


def test_insight_node_pads_insights(monkeypatch):
    # return only 1 insight, still as AIMessage
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

    state = {"results": {}}
    out = insight_mod.insight_node(state)
    ins = out["insights"]
    assert len(ins["bullets"]) == 4
