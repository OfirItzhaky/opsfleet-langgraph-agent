from __future__ import annotations
from typing import Any, Callable, Dict, Optional
import time
from src.agent_state import AgentState
from src import sql_templates as qt
from src.utils.logging import get_logger

logger = get_logger(__name__)

# map template_id -> callable
TEMPLATE_REGISTRY: Dict[str, Callable[..., str]] = {
    "q_customer_segments": qt.q_customer_segments,
    "q_top_products": qt.q_top_products,
    "q_sales_trend": qt.q_sales_trend,
    "q_geo_sales": qt.q_geo_sales,
}


def _normalize_date(val: Optional[str]) -> Optional[str]:
    """
    Plan sometimes stores SQL-like date snippets.
    We pass them through; templates know how to handle DATE_SUB(...) etc.
    """
    if val is None:
        return None
    return val.strip()


def sqlgen_node(state: AgentState) -> AgentState:
    """
    Build the final SQL string from the chosen template and params.
    Only uses whitelisted templates.
    """
    start_time = time.time()
    template_id = state.template_id
    
    logger.info("sqlgen_node starting", extra={
        "node": "sqlgen",
        "template_id": template_id
    })
    
    if not template_id:
        logger.error("sqlgen_node missing template_id", extra={"node": "sqlgen"})
        raise ValueError("sqlgen_node: template_id is missing on state")

    if template_id not in TEMPLATE_REGISTRY:
        logger.error("sqlgen_node unknown template", extra={
            "node": "sqlgen",
            "template_id": template_id,
            "available_templates": list(TEMPLATE_REGISTRY.keys())
        })
        raise ValueError(f"sqlgen_node: unknown template_id '{template_id}'")

    func = TEMPLATE_REGISTRY[template_id]
    p = state.params or {}

    start_date = _normalize_date(p.get("start_date"))
    end_date = _normalize_date(p.get("end_date"))
    limit = p.get("limit")

    if template_id == "q_customer_segments":
        sql = func(
            by=p.get("by", "country"),
            start_date=start_date,
            end_date=end_date,
            limit=limit or 100,
        )

    elif template_id == "q_top_products":
        sql = func(
            metric=p.get("metric", "revenue"),
            start_date=start_date,
            end_date=end_date,
            limit=limit or 20,
        )

    elif template_id == "q_sales_trend":
        # only trend gets category
        sql = func(
            grain=p.get("grain", "month"),
            start_date=start_date,
            end_date=end_date,
            limit=limit or 1000,
            category=p.get("category"),
        )

    elif template_id == "q_geo_sales":
        # geo DOES NOT get category
        sql = func(
            level=p.get("level", "country"),
            start_date=start_date,
            end_date=end_date,
            limit=limit or 200,
        )

    elif state.template_id == "raw_sql":
        state.sql = state.params["raw_sql"]
        return state

    else:
        # should not happen due to registry check
        raise ValueError(f"sqlgen_node: no handler for template_id '{template_id}'")

    state.last_sql = sql
    state.params["sqlgen_status"] = "ok"
    
    duration_ms = (time.time() - start_time) * 1000
    logger.info("sqlgen_node completed", extra={
        "node": "sqlgen",
        "template_id": template_id,
        "sql_length": len(sql),
        "duration_ms": round(duration_ms, 2)
    })
    
    return state
