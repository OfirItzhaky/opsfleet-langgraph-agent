from src.nodes.respond import respond_node, MAX_RESP_LEN
from src.agent_state import AgentState


# tests/test_respond.py
from src.nodes.respond import respond_node, MAX_RESP_LEN
from src.agent_state import AgentState


def test_respond_happy_path():
    """Respond node should format insights, actions, and followups."""
    state = AgentState(
        insights=["Sales grew 12% WoW", "US holds 45% of revenue"],
        actions=["Increase budget for US", "Review low-converting SKUs"],
        followups=["Show me geo breakdown", "Run 30d trend"],
    )

    out = respond_node(state)

    # out is AgentState
    assert hasattr(out, "response")
    assert "Insights:" in out.response
    assert "- Sales grew 12% WoW" in out.response
    assert len(out.response) <= MAX_RESP_LEN



def test_respond_informative_when_empty():
    """Respond node should return an informative message if no insights exist."""
    state = AgentState()  # empty, no insights/actions/followups
    out = respond_node(state)
    assert "No insights" in out.response
