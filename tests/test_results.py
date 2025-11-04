from src.nodes.results import results_node
from src.agent_state import AgentState


def test_results_empty_rows():
    s = AgentState(last_results=[])
    out = results_node(s)
    assert out.params["results_summary"]["total_rows"] == 0
    assert out.params["top_preview"] == []


def test_results_with_revenue():
    s = AgentState(
        last_results=[
            {"country": "USA", "revenue": 100.0},
            {"country": "Israel", "revenue": 50.0},
        ]
    )
    out = results_node(s)
    summary = out.params["results_summary"]
    assert summary["total_rows"] == 2
    assert summary["total_revenue"] == 150.0
    top = out.params["top_preview"]
    assert len(top) == 2
    # revenue_share added
    assert "revenue_share" in out.last_results[0]


def test_results_with_orders_only():
    s = AgentState(
        last_results=[
            {"city": "Tel Aviv", "orders": 10},
            {"city": "Haifa", "orders": 5},
        ]
    )
    out = results_node(s)
    summary = out.params["results_summary"]
    assert summary["total_rows"] == 2
    assert summary["total_orders"] == 15
    # top_preview should still exist
    assert len(out.params["top_preview"]) == 2
