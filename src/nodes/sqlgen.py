from __future__ import annotations
from typing import Any, Callable, Dict, Optional
from src.agent_state import AgentState
from src import sql_templates as qt


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
    If we detect those, we return None so the template uses its own default.
    """
    if val is None:
        return None
    v = val.strip().upper()
    if v.startswith("DATE_SUB(") or v == "CURRENT_DATE()":
        return None
    return val


def sqlgen_node(state: AgentState) -> AgentState:
    """
    Build the final SQL string from the chosen template and params.
    Only uses whitelisted templates.
    """
    template_id = state.template_id
    if not template_id:
        raise ValueError("sqlgen_node: template_id is missing on state")

    if template_id not in TEMPLATE_REGISTRY:
        raise ValueError(f"sqlgen_node: unknown template_id '{template_id}'")

    func = TEMPLATE_REGISTRY[template_id]
    p = state.params or {}

    # unify param names across templates
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
        sql = func(
            grain=p.get("grain", "month"),
            start_date=start_date,
            end_date=end_date,
            limit=limit or 1000,
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
    # optional marker for logging
    state.params["sqlgen_status"] = "ok"
    return state
