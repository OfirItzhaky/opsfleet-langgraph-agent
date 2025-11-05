from __future__ import annotations

import time
import inflect

from constants.intent_constants import GEO_WORDS, TREND_WORDS, PRODUCT_WORDS, SEGMENT_WORDS
from src.agent_state import AgentState
from src.utils.logging import get_logger

p = inflect.engine()
logger = get_logger(__name__)


def intent_node(state: AgentState) -> AgentState:
    """
    Classify the user query into one of: segment, product, trend, geo.
    Simple keyword-based approach to keep it fast and testable.
    """
    start_time = time.time()
    text = (state.user_query or getattr(state, "input", "") or "").lower()
    
    logger.info("intent_node starting", extra={
        "node": "intent",
        "query": state.user_query,
        "query_length": len(text)
    })
    
    tokens = text.split()

    # geo: normalize plurals (countries -> country, cities -> city, etc.)
    normalized_tokens = {p.singular_noun(tok) or tok for tok in tokens}

    if GEO_WORDS & normalized_tokens:
        state.intent = "geo"
        state.params["intent_rule"] = "geo_keywords"
        duration_ms = (time.time() - start_time) * 1000
        logger.info("intent_node classified", extra={
            "node": "intent",
            "intent": "geo",
            "rule": "geo_keywords",
            "matched_tokens": list(GEO_WORDS & normalized_tokens),
            "duration_ms": round(duration_ms, 2)
        })
        return state

    if any(w in text for w in TREND_WORDS):
        state.intent = "trend"
        state.params["intent_rule"] = "trend_keywords"
        duration_ms = (time.time() - start_time) * 1000
        matched = [w for w in TREND_WORDS if w in text]
        logger.info("intent_node classified", extra={
            "node": "intent",
            "intent": "trend",
            "rule": "trend_keywords",
            "matched_keywords": matched[:3],  # Limit to first 3
            "duration_ms": round(duration_ms, 2)
        })
        return state


    if any(w in text for w in PRODUCT_WORDS):
        state.intent = "product"
        state.params["intent_rule"] = "product_keywords"
        duration_ms = (time.time() - start_time) * 1000
        matched = [w for w in PRODUCT_WORDS if w in text]
        logger.info("intent_node classified", extra={
            "node": "intent",
            "intent": "product",
            "rule": "product_keywords",
            "matched_keywords": matched[:3],
            "duration_ms": round(duration_ms, 2)
        })
        return state


    if any(w in text for w in SEGMENT_WORDS):
        state.intent = "segment"
        state.params["intent_rule"] = "segment_keywords"
        duration_ms = (time.time() - start_time) * 1000
        matched = [w for w in SEGMENT_WORDS if w in text]
        logger.info("intent_node classified", extra={
            "node": "intent",
            "intent": "segment",
            "rule": "segment_keywords",
            "matched_keywords": matched[:3],
            "duration_ms": round(duration_ms, 2)
        })
        return state

    # fallback
    state.intent = "trend"
    state.params["intent_rule"] = "fallback_trend"
    duration_ms = (time.time() - start_time) * 1000
    logger.info("intent_node classified (fallback)", extra={
        "node": "intent",
        "intent": "trend",
        "rule": "fallback_trend",
        "duration_ms": round(duration_ms, 2)
    })
    return state
