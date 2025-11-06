from __future__ import annotations

from src.agent_state import AgentState
from src.plan_deterministic import deterministic_plan
from src.config import INTENT_MODE
from src.plan_dynamic import dynamic_plan


def plan_node(state: AgentState) -> AgentState:

    if INTENT_MODE.lower() == "dynamic":
        return  dynamic_plan(state)
    else:
        return deterministic_plan(state)