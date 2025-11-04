import json
import time
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

from src import config
from src.agent_state import AgentState
from src.utils.logging import get_logger

INSIGHTS_MODEL = config.GEMINI_MODEL  # or whatever you used
logger = get_logger(__name__)


def insight_node(state: AgentState) -> AgentState:
    """
    Turn numeric aggregates from results_node into narrative insights.
    Uses last_results and the summaries that results_node stored in params.
    """
    start_time = time.time()
    # pull actual data from state
    rows = state.last_results or []
    summary = (state.params or {}).get("results_summary") or {}
    top_preview = (state.params or {}).get("top_preview") or []
    
    logger.info("insight_node starting", extra={
        "node": "insight",
        "row_count": len(rows),
        "has_summary": bool(summary)
    })

    # if no rows at all -> fallback text
    if not rows:
        logger.info("insight_node using fallback (no rows)", extra={"node": "insight"})
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
        return state

    # build a simple prompt from what we *do* have
    prompt_path = Path(__file__).parent.parent / "prompts" / "insights.md"
    template = prompt_path.read_text(encoding="utf-8")
    prompt = (
        template
        .replace("{{summary}}", json.dumps(summary, ensure_ascii=False))
        .replace("{{top_rows}}", json.dumps((top_preview or rows)[:5], ensure_ascii=False))
    )

    api_key = config.GOOGLE_API_KEY
    if not api_key:
        # soft fallback
        if not api_key:
            raise RuntimeError("insight_node: missing GOOGLE_API_KEY (Gemini required)")

    # call Gemini
    try:
        logger.debug("insight_node calling LLM", extra={
            "node": "insight",
            "model": INSIGHTS_MODEL,
            "prompt_length": len(prompt)
        })
        llm_start = time.time()
        llm = ChatGoogleGenerativeAI(
            model=INSIGHTS_MODEL,
            google_api_key=api_key,
        )
        resp = llm.invoke(prompt)
        llm_duration_ms = (time.time() - llm_start) * 1000
        
        if isinstance(resp, AIMessage):
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
        else:
            text = str(resp)
        
        logger.info("insight_node LLM response received", extra={
            "node": "insight",
            "llm_duration_ms": round(llm_duration_ms, 2),
            "response_length": len(text)
        })
    except Exception as exc:
        logger.error("insight_node LLM call failed", extra={
            "node": "insight",
            "error": str(exc)
        }, exc_info=True)
        raise RuntimeError(f"insight_node: Gemini call failed: {exc}")

    # parse LLM text into 3 sections
    bullets = []
    actions = []
    followups = []
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
                bullets.append(item)
            elif current == "actions":
                actions.append(item)
            elif current == "followups":
                followups.append(item)

    # normalize counts
    bullets = bullets[:7]
    while len(bullets) < 4:
        bullets.append("(no further insight provided)")
    actions = actions[:3]
    followups = followups[:2]
    # --- Context-aware enrichment: segment + "what they buy" ---
    q_text = (state.user_query or "").lower()
    if (
        state.template_id == "q_customer_segments"
        and any(word in q_text for word in ["buy", "bought", "purchas", "product", "brand", "item"])
    ):
        # append a follow-up only if not already present
        hint = (
            "To understand what these high-value customers are buying, "
            "run a top-products query for their top regions (e.g., China, US)."
        )
        if hint not in followups:
            followups.append(hint)

    state.insights = bullets
    state.actions = actions
    state.followups = followups
    
    duration_ms = (time.time() - start_time) * 1000
    logger.info("insight_node completed", extra={
        "node": "insight",
        "duration_ms": round(duration_ms, 2),
        "insights_count": len(bullets),
        "actions_count": len(actions),
        "followups_count": len(followups)
    })
    
    return state


def _build_insight_prompt_from_state(rows, summary, top_preview) -> str:
    # take top 5 rows for brevity
    sample = (top_preview or rows)[:5]
    return (
        "You are an e-commerce analytics assistant. "
        "Given the top products and their revenue, write insights, actions, and follow-ups.\n\n"
        f"Summary: {summary}\n"
        f"Top products (sample): {sample}\n\n"
        "Format your answer in sections called Insights, Actions, and Follow-ups, each as bullet points."
    )
