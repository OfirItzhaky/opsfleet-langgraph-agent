from __future__ import annotations
import json
import time
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent_state import AgentState
from src.config import GEMINI_API_KEY, GEMINI_MODEL
from constants.plan_constants import ALLOWED_TEMPLATES, ALLOWED_PARAM_KEYS  # now used
from src.schema import TABLES, JOINS
from src.utils.logging import get_logger
from src.utils.llm import extract_text, strip_code_fences
from src.utils.sql_guardrails import validate_dynamic_sql  # NEW

logger = get_logger(__name__)

DYNAMIC_PROMPT_PATH = Path(__file__).parent / "prompts" / "plan_dynamic.md"


def dynamic_plan(state: AgentState) -> AgentState:
    start = time.time()
    user_query = (state.user_query or "").strip()

    schema_summary = _build_schema_summary()
    prompt_template = DYNAMIC_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = (
        prompt_template
        .replace("{{user_query}}", user_query)
        .replace("{{schema}}", schema_summary)
    )

    logger.info("dynamic_plan calling LLM", extra={
        "node": "plan_dynamic",
        "query": user_query,
    })

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0.0,
    )
    resp = llm.invoke(prompt)
    text = extract_text(resp)
    text_clean = strip_code_fences(text)

    try:
        data = json.loads(text_clean)
    except Exception as e:
        logger.error("dynamic_plan: bad JSON from LLM, fallback to trend", extra={
            "error": str(e),
            "response_preview": text_clean[:200],
        })
        return _fallback_to_trend(state, days=90)

    mode = (data.get("mode") or "").lower()

    # ------------------------------------------------------------------
    # 1) template mode → only accept known templates
    # ------------------------------------------------------------------
    if mode == "template":
        template_id = data.get("template_id")
        params = data.get("params") or {}

        if template_id not in ALLOWED_TEMPLATES:
            logger.warning("dynamic_plan: LLM returned template %s not in allowed list, fallback", template_id)
            return _fallback_to_trend(state, days=30)

        # keep only allowed param keys
        clean_params = {}
        for k, v in params.items():
            if k in ALLOWED_PARAM_KEYS:
                clean_params[k] = v

        state.template_id = template_id
        state.params.update(clean_params)
        state.params["locked_template"] = True

        duration_ms = (time.time() - start) * 1000
        logger.info("dynamic_plan completed (template mode)", extra={
            "node": "plan_dynamic",
            "duration_ms": round(duration_ms, 2),
            "mode": "template",
            "template_id": template_id,
        })
        return state

    # ------------------------------------------------------------------
    # 2) sql mode → validate with utils
    # ------------------------------------------------------------------
    if mode == "sql":
        raw_sql = (data.get("sql") or "").strip()
        raw_sql = raw_sql.rstrip().rstrip(';')

        raw_sql = (data.get("sql") or "").strip()

        ok, info = validate_dynamic_sql(raw_sql)
        if not ok:
            # do NOT pretend we answered their actual query
            state.template_id = "q_sales_trend"
            state.params.update({
                "start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)",
                "end_date": "CURRENT_DATE()",
                "grain": "month",
                "locked_template": True,
                # 👇 this is the important part
                "dynamic_guardrail_blocked": True,
                "dynamic_guardrail_reason": info.get("reason"),
                "dynamic_guardrail_pattern": info.get("pattern"),
            })
            return state

        # success path
        state.template_id = "raw_sql"
        state.params["raw_sql"] = raw_sql
        state.params["locked_template"] = True

        duration_ms = (time.time() - start) * 1000
        logger.info("dynamic_plan completed", extra={
            "node": "plan_dynamic",
            "duration_ms": round(duration_ms, 2),
            "mode": "sql",
            "tables": info.get("tables"),
            "limit": info.get("limit"),
        })
        return state

    # ------------------------------------------------------------------
    # 3) mode == none or unknown → fallback
    # ------------------------------------------------------------------
    return _fallback_to_trend(state, days=30)


def _fallback_to_trend(
    state: AgentState,
    days: int = 30,
    guardrail_reason: str | None = None,
    guardrail_pattern: str | None = None,
) -> AgentState:
    """
    Generic fallback to the safe trend template.
    Optionally include guardrail reason if called after SQL validation failure.
    """
    state.template_id = "q_sales_trend"
    state.params.update({
        "start_date": f"DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)",
        "end_date": "CURRENT_DATE()",
        "grain": "month",
        "locked_template": True,
    })

    if guardrail_reason:
        state.params.update({
            "dynamic_guardrail_blocked": True,
            "dynamic_guardrail_reason": guardrail_reason,
            "dynamic_guardrail_pattern": guardrail_pattern,
        })

    return state



def _build_schema_summary() -> str:
    lines = []
    lines.append("You may ONLY use these tables and columns:\n")
    for name, tbl in TABLES.items():
        cols = ", ".join(sorted(tbl.columns))
        lines.append(f"- {name}: {cols}")
    lines.append("\nYou may ONLY join tables using these keys:")
    for lt, rt, lk, rk in JOINS:
        lines.append(f"- {lt}.{lk} = {rt}.{rk}")
    lines.append(
        "\nRevenue / sales should be computed from order_items.sale_price joined via the allowed joins."
    )
    lines.append(
        "\nAlways include a LIMIT (e.g. 200)."
    )
    return "\n".join(lines)
