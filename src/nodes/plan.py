from __future__ import annotations
from typing import Dict, Any, Tuple
import json
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI  # <– use this
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
        params.update({"metric": "revenue", "limit": 20})

    elif intent == "geo":
        template_id = "q_geo_sales"
        params.update({"level": "country", "limit": 200})

    else:
        template_id = "q_sales_trend"
        params.update({"grain": "month", "limit": 1000})

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
    state.params = {**state.params, **refined_params}
    return state


def _maybe_refine_plan_with_llm(
    state: AgentState,
    template_id: str,
    params: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Optionally refines a generated query plan using Gemini for long user queries.

    If the query text is long (>60 chars) and a Gemini API key is available,
    calls the model with a structured prompt to adjust the template_id and params.
    Safely parses and validates the LLM JSON response before applying updates.
    """

    user_query = (state.user_query or "").strip()

    # short/simple → stay deterministic
    if len(user_query) < 60:
        return template_id, params

    # resolve API key (env overrides module-level)
    api_key = GEMINI_API_KEY
    if not api_key:
        raise RuntimeError("plan_node: long query requested LLM refine but GEMINI_API_KEY is missing")

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
    }

    # load prompt template
    prompt_path = Path(__file__).parent.parent / "prompts" / "plan_refine.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")

    prompt = (
        prompt_template
        .replace("{{user_query}}", user_query)
        .replace("{{template_id}}", template_id)
        .replace("{{params}}", str(params))
    )

    # call Gemini via LangChain wrapper
    try:
        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=api_key,
        )
        resp = llm.invoke(prompt)
        if isinstance(resp, AIMessage):
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
        else:
            text = str(resp)
    except Exception as exc:
        raise RuntimeError(f"plan_node: Gemini refine failed: {exc}")

    # parse JSON from LLM
    try:
        refined = json.loads(text)
    except Exception:
        return template_id, params

    # validate template_id
    new_template_id = refined.get("template_id", template_id)
    if new_template_id not in allowed_templates:
        new_template_id = template_id

    # validate params
    new_params_raw = refined.get("params") or {}
    new_params: Dict[str, Any] = dict(params)
    for k, v in new_params_raw.items():
        if k in allowed_param_keys:
            new_params[k] = v

    return new_template_id, new_params
