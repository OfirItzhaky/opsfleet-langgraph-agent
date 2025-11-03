
from __future__ import annotations
from langgraph.graph import StateGraph, END
from src.state import AgentState


def build_graph():
    sg = StateGraph(AgentState)

    # placeholder nodes
    sg.add_node("intent", lambda state: state)
    sg.add_node("plan", lambda state: state)
    sg.add_node("sqlgen", lambda state: state)
    sg.add_node("exec", lambda state: state)
    sg.add_node("results", lambda state: state)
    sg.add_node("insight", lambda state: state)
    sg.add_node("respond", lambda state: state)

    # edges (deterministic path)
    sg.add_edge("intent", "plan")
    sg.add_edge("plan", "sqlgen")
    sg.add_edge("sqlgen", "exec")
    sg.add_edge("exec", "results")
    sg.add_edge("results", "insight")
    sg.add_edge("insight", "respond")
    sg.add_edge("respond", END)

    sg.set_entry_point("intent")

    app = sg.compile()
    return app
