from src.nodes.plan import plan_node, DEFAULT_START, DEFAULT_END
from src.state import AgentState


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
