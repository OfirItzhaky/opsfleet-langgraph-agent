
import src.nodes.plan as plan_mod
import types
from langchain_core.messages import AIMessage
import src.nodes.plan as plan_mod
from src.state import AgentState
from src.nodes.plan import plan_node, DEFAULT_START, DEFAULT_END
def test_plan_for_segment():
    s = AgentState(user_query="segment customers", intent="segment")
    out = plan_node(s)
    assert out.template_id == "q_customer_segments"
    assert out.params["by"] == "country"
    assert out.params["start_date"] == DEFAULT_START
    assert out.params["end_date"] == DEFAULT_END
    assert out.params["limit"] == 100


def test_plan_for_product():
    s = AgentState(user_query="top products", intent="product")
    out = plan_node(s)
    assert out.template_id == "q_top_products"
    assert out.params["metric"] == "revenue"
    assert out.params["limit"] == 20


def test_plan_for_trend_default():
    s = AgentState(user_query="sales trend", intent="trend")
    out = plan_node(s)
    assert out.template_id == "q_sales_trend"
    assert out.params["grain"] == "month"
    assert out.params["limit"] == 1000


def test_plan_for_geo():
    s = AgentState(user_query="sales by country", intent="geo")
    out = plan_node(s)
    assert out.template_id == "q_geo_sales"
    assert out.params["level"] == "country"
    assert out.params["limit"] == 200


def test_plan_fallback_when_intent_missing():
    s = AgentState(user_query="just show me something")
    out = plan_node(s)
    # falls back to trend
    assert out.template_id == "q_sales_trend"
    assert out.params["start_date"] == DEFAULT_START
    assert out.params["end_date"] == DEFAULT_END

def test_plan_preserves_existing_params():
    s = AgentState(user_query="top products", intent="product", params={"limit": 5})
    out = plan_node(s)
    # our plan sets limit=20, so it should overwrite
    assert out.params["limit"] == 20

# tests/test_plan.py
from src.nodes.plan import plan_node, DEFAULT_START, DEFAULT_END, _maybe_refine_plan_with_llm
from src.state import AgentState
import types


def test_plan_for_segment():
    s = AgentState(user_query="segment customers", intent="segment")
    out = plan_node(s)
    assert out.template_id == "q_customer_segments"
    assert out.params["by"] == "country"
    assert out.params["start_date"] == DEFAULT_START
    assert out.params["end_date"] == DEFAULT_END
    assert out.params["limit"] == 100


def test_plan_for_product():
    s = AgentState(user_query="top products", intent="product")
    out = plan_node(s)
    assert out.template_id == "q_top_products"
    assert out.params["metric"] == "revenue"
    assert out.params["limit"] == 20


def test_plan_for_trend_default():
    s = AgentState(user_query="sales trend", intent="trend")
    out = plan_node(s)
    assert out.template_id == "q_sales_trend"
    assert out.params["grain"] == "month"
    assert out.params["limit"] == 1000


def test_plan_for_geo():
    s = AgentState(user_query="sales by country", intent="geo")
    out = plan_node(s)
    assert out.template_id == "q_geo_sales"
    assert out.params["level"] == "country"
    assert out.params["limit"] == 200


def test_plan_fallback_when_intent_missing():
    s = AgentState(user_query="just show me something")
    out = plan_node(s)
    # falls back to trend
    assert out.template_id == "q_sales_trend"
    assert out.params["start_date"] == DEFAULT_START
    assert out.params["end_date"] == DEFAULT_END


def test_plan_preserves_existing_params():
    s = AgentState(user_query="top products", intent="product", params={"limit": 5})
    out = plan_node(s)
    # our plan sets limit=20, so it should overwrite
    assert out.params["limit"] == 20


def test_plan_llm_refine_for_long_query(monkeypatch):
    # long query → should trigger refine
    state = AgentState(
        user_query=(
            "show me sales by country for the last 180 days but focus on top "
            "products only and limit to 10 rows please this is long"
        ),
        intent="geo",
    )

    # make the prompt loader return a fixed template (avoid filesystem)
    monkeypatch.setattr(
        plan_mod.Path,
        "read_text",
        lambda self, encoding="utf-8": (
            "You may ONLY use these template ids: q_customer_segments, q_top_products, "
            "q_geo_sales, q_sales_trend.\n"
            "User question: {{user_query}}\n"
            "Current template_id: {{template_id}}\n"
            "Current params: {{params}}\n"
        ),
    )

    # fake LLM that returns the refined plan
    class FakeLLM:
        def __init__(self, model, google_api_key):
            pass

        def invoke(self, _):
            return AIMessage(
                content=(
                    '{'
                    '"template_id": "q_geo_sales",'
                    '"params": {'
                    '"level": "country",'
                    '"limit": 10,'
                    '"start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)",'
                    '"end_date": "CURRENT_DATE()"'
                    '}'
                    '}'
                )
            )

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(plan_mod, "ChatGoogleGenerativeAI", FakeLLM)

    # base plan before refine (what the node would have produced)
    base_template = "q_geo_sales"
    base_params = {"limit": 200}

    new_template, new_params = _maybe_refine_plan_with_llm(
        state,
        base_template,
        base_params,
    )

    assert new_template == "q_geo_sales"
    assert new_params["limit"] == 10
    assert new_params["start_date"] == "DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)"
    assert new_params["end_date"] == "CURRENT_DATE()"
    assert new_params["level"] == "country"