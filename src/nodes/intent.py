from __future__ import annotations

import time
import inflect

from constants.intent_constants import (
    GEO_WORDS,
    TREND_WORDS,
    PRODUCT_WORDS,
    SEGMENT_WORDS,
)
from src.agent_state import AgentState
from src.utils.logging import get_logger

p = inflect.engine()
logger = get_logger(__name__)


def intent_node(state: AgentState) -> AgentState:
    """
    Classify the user query into one of: segment, product, trend, geo.
    Keyword-based so it's fast and testable.
    """
    start_time = time.time()
    text = (state.user_query or getattr(state, "input", "") or "").lower()
    tokens = text.split()

    logger.info("intent_node starting", extra={
        "node": "intent",
        "query": state.user_query,
        "query_length": len(text),
    })

    # 1) geo: token-level match (with singularization)
    normalized_tokens = {p.singular_noun(tok) or tok for tok in tokens}
    geo_matched = GEO_WORDS & normalized_tokens
    if geo_matched:
        return _set_intent_and_log(
            state=state,
            intent="geo",
            rule="geo_keywords",
            start_time=start_time,
            extra={"matched_tokens": list(geo_matched)},
        )

    # 2) trend: substring match
    if any(w in text for w in TREND_WORDS):
        matched = [w for w in TREND_WORDS if w in text]
        return _set_intent_and_log(
            state=state,
            intent="trend",
            rule="trend_keywords",
            start_time=start_time,
            extra={"matched_keywords": matched[:3]},
        )

    # 3) product
    if any(w in text for w in PRODUCT_WORDS):
        matched = [w for w in PRODUCT_WORDS if w in text]
        return _set_intent_and_log(
            state=state,
            intent="product",
            rule="product_keywords",
            start_time=start_time,
            extra={"matched_keywords": matched[:3]},
        )

    # 4) segment
    if any(w in text for w in SEGMENT_WORDS):
        matched = [w for w in SEGMENT_WORDS if w in text]
        return _set_intent_and_log(
            state=state,
            intent="segment",
            rule="segment_keywords",
            start_time=start_time,
            extra={"matched_keywords": matched[:3]},
        )

    # 5) fallback → trend
    return _set_intent_and_log(
        state=state,
        intent="trend",
        rule="fallback_trend",
        start_time=start_time,
    )


def _set_intent_and_log(
    state: AgentState,
    intent: str,
    rule: str,
    start_time: float,
    extra: dict | None = None,
) -> AgentState:
    state.intent = intent
    state.params["intent_rule"] = rule

    duration_ms = (time.time() - start_time) * 1000
    log_data = {
        "node": "intent",
        "intent": intent,
        "rule": rule,
        "duration_ms": round(duration_ms, 2),
    }
    if extra:
        log_data.update(extra)

    # tweak message for fallback
    msg = "intent_node classified"
    if rule == "fallback_trend":
        msg = "intent_node classified (fallback)"

    logger.info(msg, extra=log_data)
    return state
