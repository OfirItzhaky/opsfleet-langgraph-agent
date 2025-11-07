from __future__ import annotations

import os
from typing import Dict, Any, Tuple
import json
import re
import time
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI

from constants.plan_constants import ALLOWED_TEMPLATES, ALLOWED_PARAM_KEYS
from src.config import GEMINI_API_KEY, GEMINI_MODEL, SEASONALITY_KEYWORDS, CATEGORY_KEYWORDS, DEPARTMENT_KEYWORDS, \
    COUNTRY_KEYWORDS
from src.agent_state import AgentState
from src.utils.llm import extract_text, strip_code_fences
from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_START = "DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)"
DEFAULT_END = "CURRENT_DATE()"


def deterministic_plan(state: AgentState) -> AgentState:
    start_time = time.time()
    intent = state.intent or "trend"

    logger.info(
        "plan_node starting",
        extra={"node": "plan", "intent": intent, "query": state.user_query},
    )

    # 1) base params
    params: Dict[str, Any] = {
        "start_date": DEFAULT_START,
        "end_date": DEFAULT_END,
    }

    # 2) rule-based → pick template + LOCK it
    if intent == "segment":
        template_id = "q_customer_segments"
        params.update({"by": "country", "limit": 100})
        params["locked_template"] = True

    elif intent == "product":
        template_id = "q_top_products"
        params.update(
            {
                "metric": "revenue",
                "limit": 20,
                "start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)",
                "end_date": "CURRENT_DATE()",
            }
        )
        params["locked_template"] = True

    elif intent == "geo":
        template_id = "q_geo_sales"
        params.update(
            {
                "level": "country",
                "limit": 200,
                "start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)",
                "end_date": "CURRENT_DATE()",
            }
        )
        params["locked_template"] = True

    else:
        # default trend
        template_id = "q_sales_trend"
        params.update({"grain": "month", "limit": 1000})
        params["locked_template"] = True
        state.params["intent_rule"] = state.params.get("intent_rule") or "fallback_trend"

    # 3) lightweight extraction from user text (dates + category + seasonality)
    q = (state.user_query or "").lower()

    # past/last N days → override start_date/end_date
    m = re.search(r"(past|last)\s+(\d+)\s+days?", q)
    if m:
        days = int(m.group(2))
        params["start_date"] = f"DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)"
        params["end_date"] = "CURRENT_DATE()"

    # seasonality / YOY
    if any(kw in q for kw in SEASONALITY_KEYWORDS):
        if template_id == "q_sales_trend":
            params["start_date"] = "DATE_SUB(CURRENT_DATE(), INTERVAL 730 DAY)"
            params["end_date"] = "CURRENT_DATE()"
            params["grain"] = "month"
            params["comparison_mode"] = "yoy"

    # simple category family lookup (outerwear/coats)
    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            params["category"] = cat_name
            break

    ### NEW: department extraction ###
    for dep_name, keywords in DEPARTMENT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            params["department"] = dep_name
            break

    ### NEW: country extraction ###
    found_countries = [
        cname for cname, kws in COUNTRY_KEYWORDS.items() if any(kw in q for kw in kws)
    ]
    if found_countries:
        params["countries"] = list(set(found_countries))  # unique list

    ### NEW: relative date phrases ###
    if "last quarter" in q:
        params["start_date"] = "DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)"
        params["end_date"] = "CURRENT_DATE()"
    elif "last year" in q or "previous year" in q:
        params["start_date"] = "DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)"
        params["end_date"] = "CURRENT_DATE()"
    elif "this month" in q:
        params["start_date"] = "DATE_TRUNC(CURRENT_DATE(), MONTH)"
        params["end_date"] = "CURRENT_DATE()"

    ### NEW: auto daily grain for short windows ###
    m_short = re.search(r"(past|last)\s+(\d+)\s+days?", q)
    if m_short and intent == "trend":
        days = int(m_short.group(2))
        if days <= 30:
            params["grain"] = "day"

    # make base plan visible in state
    state.template_id = template_id
    state.params = {**state.params, **params}

    logger.info(
        "plan_node base plan created",
        extra={
            "node": "plan",
            "template_id": template_id,
            "params_keys": list(params.keys()),
        },
    )

    # 4) optional LLM refine
    llm_start = time.time()
    if not params.get("locked_template"):
        template_id, refined_params = _maybe_refine_plan_with_llm(
            state, template_id, state.params
        )
    else:
        template_id, refined_params = template_id, {}

    llm_duration_ms = (time.time() - llm_start) * 1000

    # 5) merge refined params
    state.template_id = template_id
    state.params = {**state.params, **refined_params}

    # keep LLM-only filters in a safe place
    interesting_keys = ("countries", "department", "category")
    refined_filters = {k: v for k, v in refined_params.items() if k in interesting_keys}
    if refined_filters:
        existing = state.params.get("refined_filters") or {}
        state.params["refined_filters"] = {**existing, **refined_filters}

    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "plan_node completed",
        extra={
            "node": "plan",
            "duration_ms": round(duration_ms, 2),
            "final_template_id": state.template_id,
            "param_count": len(state.params),
            "llm_duration_ms": round(llm_duration_ms, 2),
        },
    )

    ### NEW: confidence metadata (Phase 5 polish) ###
    if not params.get("locked_template"):
        state.params["plan_confidence"] = "deterministic_refined"
    else:
        state.params["plan_confidence"] = "deterministic_rule"
    state.params["plan_variant"] = f"{state.template_id}_base"

    return state


def _maybe_refine_plan_with_llm(
    state: AgentState, template_id: str, params: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    """Optionally refine the plan with an LLM."""
    user_query = (state.user_query or "").strip()
    base_params: Dict[str, Any] = dict(params or {})

    api_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not api_key:
        logger.warning("plan_node skipping LLM refinement: no API key", extra={"node": "plan"})
        return template_id, base_params

    prompt_path = Path(__file__).parent.parent / "prompts" / "plan_refine.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")
    prompt = (
        prompt_template.replace("{{user_query}}", user_query)
        .replace("{{template_id}}", template_id)
        .replace("{{params}}", str(base_params))
    )

    try:
        llm_start = time.time()
        llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=api_key)
        resp = llm.invoke(prompt)
        llm_duration_ms = (time.time() - llm_start) * 1000
        text = extract_text(resp)

        from src.utils.llm import log_llm_usage
        cost = log_llm_usage(
            logger=logger,
            node_name="plan",
            resp=resp,
            model=GEMINI_MODEL,
            duration_ms=llm_duration_ms,
            extra_context={"response_length": len(text)},
        )
        state.total_llm_cost += cost
        state.llm_calls_count += 1
    except Exception as exc:
        logger.error("plan_node LLM refinement failed", extra={"node": "plan", "error": str(exc)}, exc_info=True)
        return template_id, base_params

    text_clean = strip_code_fences(text)
    try:
        refined = json.loads(text_clean)
    except Exception as e:
        logger.warning("plan_node LLM response not valid JSON", extra={"node": "plan", "error": str(e), "response_preview": text_clean[:200]})
        return template_id, base_params

    new_template_id = refined.get("template_id", template_id)
    if new_template_id not in ALLOWED_TEMPLATES:
        new_template_id = template_id

    merged_params: Dict[str, Any] = dict(base_params)
    new_params_raw = refined.get("params") or {}
    for k, v in new_params_raw.items():
        if k in ALLOWED_PARAM_KEYS:
            merged_params[k] = v

    return new_template_id, merged_params
