from __future__ import annotations
from typing import Callable, Dict, Optional
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
import re

def _normalize_dynamic_sql(sql: str) -> str:
    fixed = sql

    # 1) TIMESTAMP vs DATE for "last N days"
    fixed = re.sub(
        r"(\w+)\.created_at\s*>=\s*DATE_SUB\(CURRENT_DATE\(\),\s*INTERVAL\s+(\d+)\s+DAY\)",
        r"DATE(\1.created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL \2 DAY)",
        fixed,
        flags=re.IGNORECASE,
    )

    # 2) TIMESTAMP vs DATE for "last month" window
    fixed = re.sub(
        r"(\w+)\.created_at\s*>=\s*DATE_TRUNC\(DATE_SUB\(CURRENT_DATE\(\),\s*INTERVAL\s+1\s+MONTH\),\s*MONTH\)",
        r"DATE(\1.created_at) >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH)",
        fixed,
        flags=re.IGNORECASE,
    )
    fixed = re.sub(
        r"(\w+)\.created_at\s*<\s*DATE_TRUNC\(CURRENT_DATE\(\),\s*MONTH\)",
        r"DATE(\1.created_at) < DATE_TRUNC(CURRENT_DATE(), MONTH)",
        fixed,
        flags=re.IGNORECASE,
    )

    return fixed



def sqlgen_node(state: AgentState) -> AgentState:
    """
    Build the final SQL string from the chosen template and params.
    Only uses whitelisted templates, except when dynamic plan explicitly
    passes through raw SQL (template_id = "raw_sql").
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

    # ✅ 1) handle dynamic raw SQL first
    if template_id == "raw_sql":
        raw_sql = state.params.get("raw_sql")
        if not raw_sql:
            raise ValueError("sqlgen_node: template_id is 'raw_sql' but params['raw_sql'] is missing")
        logger.info("sqlgen_node pass-through raw SQL", extra={
            "node": "sqlgen",
            "sql_length": len(raw_sql),
        })
        fixed_sql = _normalize_dynamic_sql(raw_sql)
        state.sql = fixed_sql
        state.last_sql = fixed_sql
        state.params["sqlgen_status"] = "ok"
        return state

    # ✅ 2) normal template path
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
            # if your template accepts it, you can pass sort_dir here:
            # sort_dir=p.get("sort_dir"),
        )

    elif template_id == "q_sales_trend":
        sql = func(
            grain=p.get("grain", "month"),
            start_date=start_date,
            end_date=end_date,
            limit=limit or 1000,
            category=p.get("category"),
        )

    elif template_id == "q_geo_sales":
        sql = func(
            level=p.get("level", "country"),
            start_date=start_date,
            end_date=end_date,
            limit=limit or 200,
        )

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
