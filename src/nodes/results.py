from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd

from src.agent_state import AgentState


def results_node(state: AgentState) -> AgentState:
    """
    Post-process the preview rows returned by BigQuery.
    Computes simple aggregates (totals, top-k, shares) and stores them on state.params.
    """
    rows: List[Dict[str, Any]] = state.last_results or []

    if not rows:
        state.params["results_summary"] = {"total_rows": 0}
        state.params["top_preview"] = []
        return state

    df = pd.DataFrame(rows)
    summary: Dict[str, Any] = {
        "total_rows": len(df),
    }

    # totals
    if "revenue" in df.columns:
        total_rev = float(df["revenue"].sum())
        summary["total_revenue"] = round(total_rev, 2)

        # add revenue_share to each row if nonzero
        if total_rev > 0:
            df["revenue_share"] = df["revenue"] / total_rev

    if "orders" in df.columns:
        total_orders = int(df["orders"].sum())
        summary["total_orders"] = total_orders

    # top-k
    if "revenue" in df.columns:
        top_df = df.sort_values("revenue", ascending=False).head(5)
        top_preview = top_df.to_dict(orient="records")
    else:
        top_preview = df.head(5).to_dict(orient="records")

    # write back
    state.params["results_summary"] = summary
    state.params["top_preview"] = top_preview
    state.last_results = df.to_dict(orient="records")

    return state
