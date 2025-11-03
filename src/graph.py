from __future__ import annotations

from langgraph.graph import StateGraph, END

from src.nodes.intent import intent_node
from src.nodes.plan import plan_node
from src.nodes.sqlgen import sqlgen_node
from src.nodes.exec import exec_node
from src.nodes.results import results_node
from src.nodes.insight import insight_node
from src.nodes.respond import respond_node


def build_graph():
    sg = StateGraph(dict)

    sg.add_node("intent", intent_node)
    sg.add_node("plan", plan_node)
    sg.add_node("sqlgen", sqlgen_node)
    sg.add_node("exec", exec_node)
    sg.add_node("results", results_node)
    sg.add_node("insight", insight_node)
    sg.add_node("respond", respond_node)

    sg.set_entry_point("intent")
    sg.add_edge("intent", "plan")
    sg.add_edge("plan", "sqlgen")
    sg.add_edge("sqlgen", "exec")
    sg.add_edge("exec", "results")
    sg.add_edge("results", "insight")
    sg.add_edge("insight", "respond")
    sg.add_edge("respond", END)

    return sg.compile()
