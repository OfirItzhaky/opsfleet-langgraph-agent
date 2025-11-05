from __future__ import annotations

import os
from typing import Dict, Any, Tuple
import json
import re
import time
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage
from src.config import GEMINI_API_KEY, GEMINI_MODEL

from src import config
from src.agent_state import AgentState
from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_START = "DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)"
DEFAULT_END = "CURRENT_DATE()"

GEMINI_MODEL = config.GEMINI_MODEL
GEMINI_API_KEY = config.GEMINI_API_KEY

# simple keyword families so we can expand later
CATEGORY_KEYWORDS = {
    "Outerwear & Coats": ["outerwear", "coat", "coats", "jackets", "parka"],
}

SEASONALITY_KEYWORDS = [
    "last year",
    "previous year",
    "seasonality",
    "seasonal pattern",
    "compare to last year",
    "year over year",
    "yoy",
]


def plan_node(state: AgentState) -> AgentState:
    start_time = time.time()
    intent = state.intent or "trend"

    logger.info("plan_node starting", extra={
        "node": "plan",
        "intent": intent,
        "query": state.user_query
    })

    # 1) base params
    params: Dict[str, Any] = {
        "start_date": DEFAULT_START,
        "end_date": DEFAULT_END,
    }

    # 2) rule-based → pick template + LOCK it
    # this is the key to stop regressions
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
                # product asks are usually short-window
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
                # geo “last month?” → 30 days (we can override below if user said something else)
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
        # keep trace of fallback
        state.params["intent_rule"] = state.params.get("intent_rule") or "fallback_trend"

    # 3) lightweight extraction from user text (dates + category + seasonality)
    q = (state.user_query or "").lower()

    # past/last N days → override start_date/end_date
    m = re.search(r"(past|last)\s+(\d+)\s+days?", q)
    if m:
        days = int(m.group(2))
        params["start_date"] = f"DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)"
        params["end_date"] = "CURRENT_DATE()"

    # seasonality / YOY → force longer window + monthly grain (mainly for trends)
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

    # make base plan visible in state
    state.template_id = template_id
    state.params = {**state.params, **params}

    logger.info("plan_node base plan created", extra={
        "node": "plan",
        "template_id": template_id,
        "params_keys": list(params.keys())
    })

    # 4) optional LLM refine
    # IMPORTANT: we only refine when we DON'T have a locked template.
    # i.e. intent was unknown or something very long/complex
    llm_start = time.time()
    if not params.get("locked_template"):
        template_id, refined_params = _maybe_refine_plan_with_llm(
            state,
            template_id,
            state.params,
        )
    else:
        template_id, refined_params = template_id, {}

    llm_duration_ms = (time.time() - llm_start) * 1000

    # 5) merge refined params (but keep locked template)
    state.template_id = template_id
    state.params = {**state.params, **refined_params}

    # keep LLM-only filters in a safe place so downstream nodes won't lose them
    interesting_keys = ("countries", "department", "category")
    refined_filters = {
        k: v for k, v in refined_params.items() if k in interesting_keys
    }
    if refined_filters:
        existing = state.params.get("refined_filters") or {}
        state.params["refined_filters"] = {**existing, **refined_filters}

    duration_ms = (time.time() - start_time) * 1000
    logger.info("plan_node completed", extra={
        "node": "plan",
        "duration_ms": round(duration_ms, 2),
        "final_template_id": state.template_id,
        "param_count": len(state.params),
        "llm_duration_ms": round(llm_duration_ms, 2),
    })

    return state


def _maybe_refine_plan_with_llm(
    state: AgentState,
    template_id: str,
    params: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Optionally refine the plan with an LLM.
    IMPORTANT: we always start from the original params and overlay
    refined ones, so callers never lose defaults.
    """
    user_query = (state.user_query or "").strip()

    # always start from base params
    base_params: Dict[str, Any] = dict(params or {})

    api_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY

    if not api_key:
        logger.warning("plan_node skipping LLM refinement: no API key", extra={"node": "plan"})
        return template_id, base_params

    allowed_templates = {
        "q_customer_segments",
        "q_top_products",
        "q_geo_sales",
        "q_sales_trend",
    }
    allowed_param_keys = {
        "start_date",
        "end_date",
        "by",
        "limit",
        "metric",
        "level",
        "grain",
        "category",
        "countries",
        "department",
    }

    prompt_path = Path(__file__).parent.parent / "prompts" / "plan_refine.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")

    prompt = (
        prompt_template.replace("{{user_query}}", user_query)
        .replace("{{template_id}}", template_id)
        .replace("{{params}}", str(base_params))
    )

    try:
        logger.debug("plan_node calling LLM for refinement", extra={
            "node": "plan",
            "model": GEMINI_MODEL,
            "prompt_length": len(prompt)
        })
        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=api_key,
        )
        resp = llm.invoke(prompt)

        if isinstance(resp, AIMessage):
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
        else:
            text = str(resp)

        logger.debug("plan_node LLM response received", extra={
            "node": "plan",
            "response_length": len(text)
        })
    except Exception as exc:
        logger.error("plan_node LLM refinement failed", extra={
            "node": "plan",
            "error": str(exc)
        }, exc_info=True)
        # 🔴 keep base params, don't return {}
        return template_id, base_params

    # Strip ```json fences if present
    text_clean = text.strip()
    if text_clean.startswith("```"):
        lines = text_clean.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text_clean = "\n".join(lines)

    try:
        refined = json.loads(text_clean)
    except Exception as e:
        logger.warning("plan_node LLM response not valid JSON", extra={
            "node": "plan",
            "error": str(e),
            "response_preview": text_clean[:200]
        })
        # 🔴 keep base params, don't return {}
        return template_id, base_params

    # template may change, but only to known ones
    new_template_id = refined.get("template_id", template_id)
    if new_template_id not in allowed_templates:
        new_template_id = template_id

    # ✅ overlay refined params on top of base params
    merged_params: Dict[str, Any] = dict(base_params)
    new_params_raw = refined.get("params") or {}
    for k, v in new_params_raw.items():
        if k in allowed_param_keys:
            merged_params[k] = v

    return new_template_id, merged_params