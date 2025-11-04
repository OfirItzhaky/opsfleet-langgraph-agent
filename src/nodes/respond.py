# src/nodes/respond.py
from typing import List

from src.agent_state import AgentState

MAX_RESP_LEN = 2000


def _format_bullets(items: List[str], title: str) -> str:
    """Build a titled bullet list section."""
    if not items:
        return ""
    lines = [title]
    for it in items:
        lines.append(f"- {it}")
    return "\n".join(lines)


def respond_node(state: AgentState) -> AgentState:
    """
    Final, deterministic node that turns structured insight fields on the state
    into a CLI-friendly string. No LLM calls here.
    """
    insights = state.insights or []
    actions = state.actions or []
    followups = state.followups or []

    # backward/defensive: if some earlier node put a dict in insights
    if isinstance(insights, dict):
        bullets = insights.get("bullets") or []
        if not actions:
            actions = insights.get("actions") or []
        if not followups:
            followups = insights.get("followups") or []
        insights = bullets

    parts: List[str] = []

    if insights:
        parts.append(_format_bullets(insights, "Insights:"))
    else:
        parts.append(
            "No insights were produced. This can happen if the query returned no rows, "
            "the time range was too narrow, or an upstream node chose not to generate insights."
        )

    if actions:
        parts.append(_format_bullets(actions, "Recommended actions:"))

    if followups:
        parts.append(_format_bullets(followups, "Follow-ups:"))

    text = "\n\n".join(p for p in parts if p).strip()

    if len(text) > MAX_RESP_LEN:
        text = text[: MAX_RESP_LEN - 3] + "..."

    state.response = text

    return state
