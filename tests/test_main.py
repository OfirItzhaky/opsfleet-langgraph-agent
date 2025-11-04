from src.graph import build_graph
from src.agent_state import AgentState


def test_cli_graph_invokes_with_minimal_state():
    """Graph should accept a state-like dict and run end-to-end."""
    graph = build_graph()
    state = AgentState(user_query="show me sales by country")

    out = graph.invoke(state.model_dump())

    assert isinstance(out, dict)
    assert "user_query" in out
