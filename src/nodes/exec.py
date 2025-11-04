from __future__ import annotations
from typing import Any, Optional, List, Dict
import time

from src.agent_state import AgentState
from src.utils.logging import get_logger

logger = get_logger(__name__)


try:
    from src.clients.bq_helper import BQHelper
except ImportError:
    BQHelper = None  # for tests without real BQ


def exec_node(state: AgentState, bq: Optional[Any] = None) -> AgentState:
    """
    Execute the SQL in state.last_sql against BigQuery.
    Stores dry-run bytes and a small preview of rows back on the state.
    """
    start_time = time.time()
    
    logger.info("exec_node starting", extra={
        "node": "exec",
        "sql_length": len(state.last_sql) if state.last_sql else 0
    })
    
    if not state.last_sql:
        logger.error("exec_node no SQL provided", extra={"node": "exec"})
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
        logger.info("exec_node dry_run completed", extra={
            "node": "exec",
            "estimated_bytes": dry_bytes
        })
    except Exception as e:  # keep it running
        logger.warning("exec_node dry_run failed", extra={
            "node": "exec",
            "error": str(e)
        })
        state.dry_run_bytes = None
        state.params["exec_error"] = f"dry_run_failed: {e}"
        return state

    try:
        query_start = time.time()
        df = bq.execute_safe(sql, preview_limit=50)
        query_duration_ms = (time.time() - query_start) * 1000
        logger.info("exec_node query executed", extra={
            "node": "exec",
            "query_duration_ms": round(query_duration_ms, 2),
            "row_count": len(df)
        })
    except Exception as e:
        logger.error("exec_node query execution failed", extra={
            "node": "exec",
            "error": str(e)
        }, exc_info=True)
        state.params["exec_error"] = f"execute_failed: {e}"
        state.last_results = []
        return state

    rows = df.to_dict(orient="records") if not df.empty else []
    state.last_results = rows
    state.params["rowcount"] = len(rows)
    
    duration_ms = (time.time() - start_time) * 1000
    logger.info("exec_node completed", extra={
        "node": "exec",
        "duration_ms": round(duration_ms, 2),
        "rows_returned": len(rows),
        "bytes_scanned": dry_bytes
    })
    
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
