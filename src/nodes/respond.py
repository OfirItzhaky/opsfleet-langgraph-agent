# src/nodes/respond.py

from typing import List
from ..state import AgentState

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
    insights = getattr(state, "insights", None) or []
    actions = getattr(state, "actions", None) or []
    followups = getattr(state, "followups", None) or []

    parts: List[str] = []

    if insights:
        parts.append(_format_bullets(insights, "Insights:"))
    else:
        # more informative fallback
        parts.append(
            "No insights were produced. This can happen if the query returned no rows, "
            "the time range was too narrow, or an upstream node chose not to generate insights."
        )

    if actions:
        parts.append(_format_bullets(actions, "Recommended actions:"))

    if followups:
        parts.append(_format_bullets(followups, "Follow-ups:"))

    text = "\n\n".join(p for p in parts if p).strip()

    # length guard (presentation only)
    if len(text) > MAX_RESP_LEN:
        text = text[: MAX_RESP_LEN - 3] + "..."

    # expose as response_text so CLI can just print it
    new_state = state.model_copy(update={"response_text": text})
    return new_state
