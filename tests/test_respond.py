from src.nodes.respond import respond_node, MAX_RESP_LEN
from src.state import AgentState


def test_respond_happy_path():
    """Respond node should format insights, actions, and followups."""
    state = AgentState(
        insights=["Sales grew 12% WoW", "US holds 45% of revenue"],
        actions=["Increase budget for US", "Review low-converting SKUs"],
        followups=["Show me geo breakdown", "Run 30d trend"],
    ).model_dump()

    out = respond_node(state)

    assert "response_text" in out
    txt = out["response_text"]

    assert "Insights:" in txt
    assert "- Sales grew 12% WoW" in txt
    assert "Recommended actions:" in txt
    assert "Follow-ups:" in txt
    assert len(txt) <= MAX_RESP_LEN


def test_respond_informative_when_empty():
    """Respond node should return an informative message if no insights exist."""
    state = AgentState().model_dump()

    out = respond_node(state)

    assert "response_text" in out
    assert "No insights were produced." in out["response_text"]
    assert len(out["response_text"]) <= MAX_RESP_LEN
