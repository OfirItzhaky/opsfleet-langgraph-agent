
import src.nodes.plan as plan_mod

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
    s = AgentState(
        user_query="show me sales by country for the last 180 days but focus on top products only and limit to 10 rows",
        intent="geo",
    )

    class DummyResp:
        text = (
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

    class DummyClient:
        class models:
            @staticmethod
            def generate_content(model=None, contents=None):
                return DummyResp()

    # make sure refine branch doesn't early-exit
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(plan_mod, "GEMINI_API_KEY", "fake")
    # now plan_mod has a genai attribute we can patch
    monkeypatch.setattr(
        plan_mod,
        "genai",
        types.SimpleNamespace(Client=lambda api_key: DummyClient()),
    )

    # IMPORTANT: call the function from the patched module
    out = plan_mod.plan_node(s)

    assert out.template_id == "q_geo_sales"
    assert out.params["limit"] == 10
    assert out.params["start_date"] == "DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)"
    assert out.params["end_date"] == "CURRENT_DATE()"
