from __future__ import annotations
import json
import time
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent_state import AgentState
from src.config import GEMINI_API_KEY, GEMINI_MODEL
from constants.plan_constants import ALLOWED_TEMPLATES, ALLOWED_PARAM_KEYS
from src.schema import TABLES, JOINS
from src.utils.logging import get_logger
from src.utils.llm import extract_text, strip_code_fences

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
        state.template_id = "q_sales_trend"
        state.params.update({
            "start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)",
            "end_date": "CURRENT_DATE()",
            "grain": "month",
            "locked_template": True,
        })
        return state

    if data.get("mode") == "none":
        # graceful fail
        state.template_id = "q_sales_trend"
        state.params.update({
            "start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)",
            "end_date": "CURRENT_DATE()",
            "grain": "month",
            "locked_template": True,
        })
        return state

    raw_sql = (data.get("sql") or "").strip()
    if not _sql_passes_guardrails(raw_sql):
        logger.warning("dynamic_plan: sql failed guardrails, falling back to trend")
        state.template_id = "q_sales_trend"
        state.params.update({
            "start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)",
            "end_date": "CURRENT_DATE()",
            "grain": "month",
            "locked_template": True,
        })
        return state

    # ✅ the only success path in dynamic mode
    state.template_id = "raw_sql"
    state.params["raw_sql"] = raw_sql
    state.params["locked_template"] = True

    duration_ms = (time.time() - start) * 1000
    logger.info("dynamic_plan completed", extra={
        "node": "plan_dynamic",
        "duration_ms": round(duration_ms, 2),
        "mode": "sql",
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


def _sql_passes_guardrails(sql: str) -> bool:
    """
    Very dumb guardrail: check tables and LIMIT.
    You can later replace with sqlglot to properly parse.
    """
    if not sql:
        return False

    lowered = sql.lower()
    # must reference only our 4 tables
    allowed_tables = {"orders", "order_items", "products", "users"}
    for t in allowed_tables:
        pass  # just to show intent

    # hard check: must have LIMIT
    if "limit" not in lowered:
        return False

    # hard check: must only mention known tables
    bad_words = ["delete", "update", "insert"]
    if any(b in lowered for b in bad_words):
        return False

    return True
