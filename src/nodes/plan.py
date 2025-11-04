from __future__ import annotations
from typing import Dict, Any, Tuple
import json
import re
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

from src import config
from src.agent_state import AgentState

DEFAULT_START = "DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)"
DEFAULT_END = "CURRENT_DATE()"

GEMINI_MODEL = config.GEMINI_MODEL
GEMINI_API_KEY = config.GOOGLE_API_KEY


def plan_node(state: AgentState) -> AgentState:
    intent = state.intent or "trend"

    params: Dict[str, Any] = {
        "start_date": DEFAULT_START,
        "end_date": DEFAULT_END,
    }

    if intent == "segment":
        template_id = "q_customer_segments"
        params.update({"by": "country", "limit": 100})

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

    elif intent == "geo":
        template_id = "q_geo_sales"
        params.update(
            {
                "level": "country",
                "limit": 200,
                # geo “last month?” → 30 days
                "start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)",
                "end_date": "CURRENT_DATE()",
            }
        )

    else:
        # default trend
        template_id = "q_sales_trend"
        params.update({"grain": "month", "limit": 1000})
        state.params["intent_rule"] = state.params.get("intent_rule") or "fallback_trend"

    # ── NEW: lightweight extraction from user text (dates + simple category) ──
    q = (state.user_query or "").lower()

    # past/last N days → override start_date/end_date
    m = re.search(r"(past|last)\s+(\d+)\s+days?", q)
    if m:
        days = int(m.group(2))
        params["start_date"] = f"DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)"
        params["end_date"] = "CURRENT_DATE()"

    # simple category hint for outerwear/coats
    if "outerwear" in q or "coat" in q or "coats" in q:
        # we’ll let sqlgen/node decide how to apply this
        params["category"] = "Outerwear & Coats"

    # make base plan visible in state
    state.template_id = template_id
    state.params = {**state.params, **params}

    # optional LLM refine
    template_id, refined_params = _maybe_refine_plan_with_llm(
        state,
        template_id,
        state.params,
    )

    state.template_id = template_id
    # merge as before
    state.params = {**state.params, **refined_params}

    # NEW: keep LLM-only filters in a safe place so downstream nodes
    # that rewrite params won't lose them
    interesting_keys = ("countries", "department", "category")
    refined_filters = {
        k: v for k, v in refined_params.items() if k in interesting_keys
    }
    if refined_filters:
        # put them under a dedicated key
        existing = state.params.get("refined_filters") or {}
        state.params["refined_filters"] = {**existing, **refined_filters}

    return state


def _maybe_refine_plan_with_llm(
    state: AgentState,
    template_id: str,
    params: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Optionally refines a generated query plan using Gemini.

    We refine when:
    - intent is product or geo (they often need extra params like level/metric/window), OR
    - intent is segment and the query is medium-length (>= 40 chars), OR
    - query is generally long/complex (>= 60 chars).

    Otherwise we keep it deterministic and skip the LLM.
    """
    user_query = (state.user_query or "").strip()
    intent = (state.intent or "").strip()

    def should_refine(intent: str, user_query: str) -> bool:
        if intent in ("product", "geo"):
            return True
        if intent == "segment" and len(user_query) >= 40:
            return True
        if len(user_query) >= 60:
            return True
        return False

    if not should_refine(intent, user_query):
        return template_id, params

    api_key = GEMINI_API_KEY
    if not api_key:
        return template_id, params

    allowed_templates = {
        "q_customer_segments",
        "q_top_products",
        "q_geo_sales",
        "q_sales_trend",
    }
    # added "category" so the LLM can tweak it too if it wants
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
        "department"

    }

    prompt_path = Path(__file__).parent.parent / "prompts" / "plan_refine.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")

    prompt = (
        prompt_template.replace("{{user_query}}", user_query)
        .replace("{{template_id}}", template_id)
        .replace("{{params}}", str(params))
    )

    try:
        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=api_key,
            temperature=0,  # deterministic
        )
        resp = llm.invoke(prompt)
        if isinstance(resp, AIMessage):
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
        else:
            text = str(resp)
    except Exception as exc:
        raise RuntimeError(f"plan_node: Gemini refine failed: {exc}")

    try:
        refined = json.loads(text)
    except Exception:
        return template_id, params

    new_template_id = refined.get("template_id", template_id)
    if new_template_id not in allowed_templates:
        new_template_id = template_id

    new_params_raw = refined.get("params") or {}
    new_params: Dict[str, Any] = dict(params)
    for k, v in new_params_raw.items():
        if k in allowed_param_keys:
            new_params[k] = v

    return new_template_id, new_params

