from __future__ import annotations
from typing import Dict, Any
from src.state import AgentState


# date defaults expressed as SQL snippets so the next node can drop them in
DEFAULT_START = "DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)"
DEFAULT_END = "CURRENT_DATE()"


def plan_node(state: AgentState) -> AgentState:
    """
    Choose which SQL template to run and with which parameters,
    based on the intent decided earlier.
    """
    intent = state.intent or "trend"

    # base params all templates can use
    params: Dict[str, Any] = {
        "start_date": DEFAULT_START,
        "end_date": DEFAULT_END,
    }

    if intent == "segment":
        state.template_id = "q_customer_segments"
        params.update({
            "by": "country",
            "limit": 100,
        })

    elif intent == "product":
        state.template_id = "q_top_products"
        params.update({
            "metric": "revenue",
            "limit": 20,
        })

    elif intent == "geo":
        state.template_id = "q_geo_sales"
        params.update({
            "level": "country",
            "limit": 200,
        })

    else:  # trend or fallback
        state.template_id = "q_sales_trend"
        params.update({
            "grain": "month",
            "limit": 1000,
        })

    # store the final params
    state.params.update(params)
    return state
