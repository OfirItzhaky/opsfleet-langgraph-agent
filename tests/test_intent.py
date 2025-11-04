from __future__ import annotations
from src.agent_state import AgentState


def intent_node(state: AgentState) -> AgentState:
    """
    Classify the user query into one of: segment, product, trend, geo.
    Simple keyword-based approach to keep it fast and testable.
    """
    text = (state.user_query or "").lower()

    # geographic patterns
    geo_words = (
        "country",
        "state",
        "city",
        "region",
        "geo",
        "location",
        "by country",
        "by city",
        "where are",
    )
    if any(w in text for w in geo_words):
        state.intent = "geo"
        state.params["intent_rule"] = "geo_keywords"
        return state

    # trends / time series
    trend_words = (
        "trend",
        "over time",
        "by month",
        "by day",
        "daily",
        "weekly",
        "monthly",
        "timeseries",
        "time series",
        "seasonality",
        "evolution",
    )
    if any(w in text for w in trend_words):
        state.intent = "trend"
        state.params["intent_rule"] = "trend_keywords"
        return state

    # product / catalog
    product_words = (
        "product",
        "sku",
        "top products",
        "best sellers",
        "bestsellers",
        "brand",
        "category",
        "top items",
        "top sku",
    )
    if any(w in text for w in product_words):
        state.intent = "product"
        state.params["intent_rule"] = "product_keywords"
        return state

    # customer / segmentation
    segment_words = (
        "customer",
        "users",
        "segment",
        "segmentation",
        "cohort",
        "demographic",
        "by gender",
        "by age",
        "by country of customer",
        "audience",
        "customers by",
    )
    if any(w in text for w in segment_words):
        state.intent = "segment"
        state.params["intent_rule"] = "segment_keywords"
        return state

    # fallback
    state.intent = "trend"
    state.params["intent_rule"] = "fallback_trend"
    return state
