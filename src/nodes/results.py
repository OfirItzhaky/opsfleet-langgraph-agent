from __future__ import annotations
from typing import List, Dict, Any
import time
import datetime
import pandas as pd

from src.agent_state import AgentState
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _json_sanitize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Make query rows JSON-safe (date/datetime → iso string)."""
    sanitized: List[Dict[str, Any]] = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for k, v in row.items():
            # datetime/date → iso string
            if isinstance(v, (datetime.date, datetime.datetime)):
                new_row[k] = v.isoformat()
            else:
                new_row[k] = v
        sanitized.append(new_row)
    return sanitized


def results_node(state: AgentState) -> AgentState:
    start_time = time.time()
    rows: List[Dict[str, Any]] = state.last_results or []

    logger.info("results_node starting", extra={
        "node": "results",
        "row_count": len(rows)
    })

    if not rows:
        logger.info("results_node no rows to process", extra={"node": "results"})
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

    # 🔐 NEW: sanitize before writing back
    top_preview = _json_sanitize_rows(top_preview)
    all_rows = _json_sanitize_rows(df.to_dict(orient="records"))

    state.params["results_summary"] = summary
    state.params["top_preview"] = top_preview
    state.last_results = all_rows

    duration_ms = (time.time() - start_time) * 1000
    logger.info("results_node completed", extra={
        "node": "results",
        "duration_ms": round(duration_ms, 2),
        "total_rows": summary.get("total_rows"),
        "summary_keys": list(summary.keys())
    })

    return state
