# src/nodes/plan.py
from __future__ import annotations
from typing import Dict, Any, Tuple
import os
import json

from src.state import AgentState

# date defaults expressed as SQL snippets so the next node can drop them in
DEFAULT_START = "DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)"
DEFAULT_END = "CURRENT_DATE()"

# hard-coded per your decision
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

try:
    from google import genai  # real import
except Exception:             # if not installed or in tests
    genai = None

def plan_node(state: AgentState) -> AgentState:
    """
    Choose which SQL template to run and with which parameters,
    based on the intent decided earlier.
    Then (optionally) let an LLM refine only the allowed params
    when the user query is long/ambiguous.
    """
    intent = state.intent or "trend"

    # base params all templates can use
    params: Dict[str, Any] = {
        "start_date": DEFAULT_START,
        "end_date": DEFAULT_END,
    }

    # ----- deterministic base plan -----
    if intent == "segment":
        template_id = "q_customer_segments"
        params.update({
            "by": "country",
            "limit": 100,
        })

    elif intent == "product":
        template_id = "q_top_products"
        params.update({
            "metric": "revenue",
            "limit": 20,
        })

    elif intent == "geo":
        template_id = "q_geo_sales"
        params.update({
            "level": "country",
            "limit": 200,
        })

    else:  # trend or fallback
        template_id = "q_sales_trend"
        params.update({
            "grain": "month",
            "limit": 1000,
        })

    # merge into state first so LLM sees current values
    state.template_id = template_id
    state.params.update(params)

    template_id, refined_params = _maybe_refine_plan_with_llm(state, template_id, state.params)

    # store back
    state.template_id = template_id
    state.params.update(refined_params)

    return state


def _maybe_refine_plan_with_llm(
    state: AgentState,
    template_id: str,
    params: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """
    Optionally call Gemini to refine the plan.

    Rules:
    - only run for "longer" or "messier" user queries
    - only allow updates to a small whitelist of param keys
    - never let the model change the template_id to something we don't know
    - if anything fails, just return original
    """
    user_query = (state.user_query or "").strip()

    # 1) keep short/simple queries fully deterministic
    if len(user_query) < 60:
        return template_id, params

    # 2) need an API key, otherwise stay with deterministic plan
    if not GEMINI_API_KEY:
        return template_id, params

    # 3) need the genai client available at module level (so tests can patch it)
    #    if it's None (e.g. package not installed), skip
    if genai is None:  # type: ignore[name-defined]
        return template_id, params

    # allowed values so the model can't go wild
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

    prompt = (
        "You are helping refine an analytics plan for a fixed e-commerce dataset.\n"
        "You will receive:\n"
        "1) the user's original question,\n"
        "2) an intent-derived template id,\n"
        "3) current template parameters.\n\n"
        "Your job: ONLY adjust the parameters so they match the user's question better.\n"
        "Return STRICT JSON with keys: template_id, params.\n"
        "You may ONLY use these template ids: "
        f"{list(allowed_templates)}.\n"
        "You may ONLY edit these param keys: "
        f"{list(allowed_param_keys)}.\n"
        "If the user mentions a time frame, update start_date/end_date as SQL expressions.\n"
        "If the user mentions country/region, update 'level' or 'by' accordingly.\n"
        "If unsure, keep values as-is.\n"
        "Example output:\n"
        '{\n'
        '  "template_id": "q_geo_sales",\n'
        '  "params": { "level": "country", "limit": 200, '
        '"start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY)", '
        '"end_date": "CURRENT_DATE()" }\n'
        '}\n'
        "\n"
        f"User question: {user_query}\n"
        f"Current template_id: {template_id}\n"
        f"Current params: {params}\n"
    )

    # 4) call the already-imported / already-patchable client
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)  # type: ignore[name-defined]
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        text = resp.text or ""
    except Exception:
        # fail soft
        return template_id, params

    # 5) parse JSON from model
    try:
        refined = json.loads(text)
    except Exception:
        return template_id, params

    # 6) validate template_id
    new_template_id = refined.get("template_id", template_id)
    if new_template_id not in allowed_templates:
        new_template_id = template_id  # ignore invalid change

    # 7) validate params
    new_params_raw = refined.get("params") or {}
    new_params: Dict[str, Any] = dict(params)  # start from existing
    for k, v in new_params_raw.items():
        if k in allowed_param_keys:
            new_params[k] = v  # allow override

    return new_template_id, new_params

