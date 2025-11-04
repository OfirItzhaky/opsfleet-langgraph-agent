from src.agent_state import AgentState

def test_agent_state_defaults_and_validation():
    s = AgentState()
    assert s.params == {}
    assert isinstance(s.last_results, list)
    assert s.intent is None
    # ensure it serializes without error
    assert "user_query" in s.model_dump_json()

def test_agent_state_has_followups_default():
    s = AgentState()
    assert hasattr(s, "followups")
    assert isinstance(s.followups, list)
    assert s.followups == []

from src.agent_state import AgentState

def test_agent_state_defaults():
    s = AgentState()
    assert s.params == {}
    assert s.last_results == []
    assert s.insights == []