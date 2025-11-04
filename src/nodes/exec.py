from __future__ import annotations
from typing import Any, Optional, List, Dict

from src.agent_state import AgentState


try:
    from src.clients.bq_helper import BQHelper
except ImportError:
    BQHelper = None  # for tests without real BQ


def exec_node(state: AgentState, bq: Optional[Any] = None) -> AgentState:
    """
    Execute the SQL in state.last_sql against BigQuery.
    Stores dry-run bytes and a small preview of rows back on the state.
    """
    if not state.last_sql:
        raise ValueError("exec_node: state.last_sql is empty")

    # build helper if not provided (real run)
    if bq is None:
        if BQHelper is None:
            raise RuntimeError("exec_node: BQHelper is not available")
        bq = BQHelper()

    sql = state.last_sql

    # dry-run first
    try:
        dry_bytes = bq.dry_run(sql)
        state.dry_run_bytes = dry_bytes
    except Exception as e:  # keep it running
        state.dry_run_bytes = None
        state.params["exec_error"] = f"dry_run_failed: {e}"
        return state

    try:
        df = bq.execute_safe(sql, preview_limit=50)
    except Exception as e:
        state.params["exec_error"] = f"execute_failed: {e}"
        state.last_results = []
        return state

    rows = df.to_dict(orient="records") if not df.empty else []
    state.last_results = rows
    state.params["rowcount"] = len(rows)
    return state

    # normalize to list[dict]
    rows = df.to_dict(orient="records") if not df.empty else []
    state.last_results = rows
    state.params["rowcount"] = len(rows)
    return state

    # normalize rows to list[dict]
    if rows is None:
        rows = []

    if not isinstance(rows, list):
        rows = list(rows)

    state.last_results = rows  # preview
    state.params["rowcount"] = total_rows
    return state
