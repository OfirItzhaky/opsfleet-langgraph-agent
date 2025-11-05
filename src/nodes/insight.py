import json
import time
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

from src import config
from src.agent_state import AgentState
from src.utils.logging import get_logger
from src.utils.llm import log_llm_usage, strip_code_fences

INSIGHTS_MODEL = config.GEMINI_MODEL
logger = get_logger(__name__)


def insight_node(state: AgentState) -> AgentState:
    """
    Turn numeric aggregates into narrative insights.
    """
    start_time = time.time()

    rows = state.last_results or []
    summary = (state.params or {}).get("results_summary") or {}
    top_preview = (state.params or {}).get("top_preview") or []

    logger.info("insight_node starting", extra={
        "node": "insight",
        "row_count": len(rows),
        "has_summary": bool(summary),
    })

    # 1) no data → static fallback
    if not rows:
        _apply_empty_fallback(state)
        return state

    # 2) build prompt
    prompt = _build_insight_prompt(summary, top_preview or rows)

    # 3) call LLM
    text = _call_insight_llm(prompt, state)

    # 4) parse to 3 lists
    insights, actions, followups = _parse_insight_text(text, state)

    state.insights = insights
    state.actions = actions
    state.followups = followups

    duration_ms = (time.time() - start_time) * 1000
    logger.info("insight_node completed", extra={
        "node": "insight",
        "duration_ms": round(duration_ms, 2),
        "insights_count": len(insights),
        "actions_count": len(actions),
        "followups_count": len(followups),
    })
    return state


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _apply_empty_fallback(state: AgentState) -> None:
    state.insights = [
        "No rows were returned for this query.",
        "Try broadening the date range or removing a filter.",
        "The agent could not produce product-level insights.",
        "(no further insight provided)",
    ]
    state.actions = [
        "Verify that the underlying BigQuery tables contain data for the requested period.",
    ]
    state.followups = [
        "Do you want to re-run this for the last 365 days?",
    ]
    logger.info("insight_node using fallback (no rows)", extra={"node": "insight"})


def _build_insight_prompt(summary: dict, rows: list) -> str:
    # load template once per call (fine for now)
    prompt_path = Path(__file__).parent.parent / "prompts" / "insights.md"
    template = prompt_path.read_text(encoding="utf-8")
    return (
        template
        .replace("{{summary}}", json.dumps(summary, ensure_ascii=False))
        .replace("{{top_rows}}", json.dumps(rows[:5], ensure_ascii=False))
    )


def _call_insight_llm(prompt: str, state: AgentState) -> str:
    api_key = config.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError("insight_node: missing GEMINI_API_KEY (Gemini required)")

    llm_start = time.time()
    llm = ChatGoogleGenerativeAI(
        model=INSIGHTS_MODEL,
        google_api_key=api_key,
    )

    logger.debug("insight_node calling LLM", extra={
        "node": "insight",
        "model": INSIGHTS_MODEL,
        "prompt_length": len(prompt),
    })

    try:
        resp = llm.invoke(prompt)
    except Exception as exc:
        logger.error("insight_node LLM call failed", extra={
            "node": "insight",
            "error": str(exc),
        }, exc_info=True)
        raise RuntimeError(f"insight_node: Gemini call failed: {exc}")

    llm_duration_ms = (time.time() - llm_start) * 1000

    # log cost/tokens (will be 0 if google didn’t return usage)
    if isinstance(resp, AIMessage):
        cost = log_llm_usage(
            logger=logger,
            node_name="insight",
            resp=resp,
            model=INSIGHTS_MODEL,
            duration_ms=llm_duration_ms,
            extra_context={"response_length": len(str(resp.content))},
        )
        # keep totals on state
        state.total_llm_cost += cost
        state.llm_calls_count += 1
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
    else:
        # unexpected type
        text = str(resp)

    # if model wrapped it in ```json we strip it
    return strip_code_fences(text)


def _parse_insight_text(text: str, state: AgentState):
    insights: list[str] = []
    actions: list[str] = []
    followups: list[str] = []

    current = "insights"
    for line in text.splitlines():
        line = line.strip()
        lower = line.lower()

        if "insight" in lower:
            current = "insights"
            continue
        if "action" in lower:
            current = "actions"
            continue
        if "follow" in lower:
            current = "followups"
            continue

        if line.startswith("-") or line.startswith("*"):
            item = line.lstrip("-* ").strip()
            if not item:
                continue
            if current == "insights":
                insights.append(item)
            elif current == "actions":
                actions.append(item)
            elif current == "followups":
                followups.append(item)

    # normalize sizes
    insights = insights[:7]
    while len(insights) < 4:
        insights.append("(no further insight provided)")
    actions = actions[:3]
    followups = followups[:2]

    # tiny context-aware enrichment (the one you had)
    _maybe_add_segment_followup(state, followups)

    return insights, actions, followups


def _maybe_add_segment_followup(state: AgentState, followups: list[str]) -> None:
    q_text = (state.user_query or "").lower()
    if (
        state.template_id == "q_customer_segments"
        and any(word in q_text for word in ["buy", "bought", "purchas", "product", "brand", "item"])
    ):
        hint = (
            "To understand what these high-value customers are buying, "
            "run a top-products query for their top regions (e.g., China, US)."
        )
        if hint not in followups:
            followups.append(hint)
