# dev_scenarios.py

DEV_SCENARIOS = [
    # --- EASY (should route cleanly, minimal params) ---
    {
        "id": "easy_1_top_products_30d",
        "query": "show me the top revenue products from the last 30 days",
        "expect": {
            "intent": "product",          # intent node should pick product
            "min_insights": 3,            # insight node should give at least 3 bullets
        },
    },
    {
        "id": "easy_2_geo_sales",
        "query": "which countries bought the most last month?",
        "expect": {
            "intent": "geo",
            "min_insights": 3,
        },
    },

#     # --- MEDIUM (needs date/window or dimension handling) ---
    {
        "id": "medium_1_segment_high_value",
        "query": "find high value customers and tell me what they are buying",
        "expect": {
            "intent": "segment",           # should NOT go to geo
            "min_insights": 4,
        },
    },
    {
        "id": "medium_2_trend_by_category",
        "query": "show sales trend for outerwear and coats over the past 90 days",
        "expect": {
            "intent": "trend",
            "min_insights": 3,
        },
    },
#
#     # --- HARD (composite / multiple constraints) ---
    {
        "id": "hard_1_geo_segment_product_mix",
        "query": (
            "compare revenue between US and Canada for men's products and tell me "
            "which brands to stock more this quarter"
        ),
        "expect": {
            "intent": "geo",               # or product+geo, but we expect geo dominant
            "min_insights": 4,
        },
    },
    {
        "id": "hard_2_churnish_behavior",
        "query": (
            "identify customers whose orders have dropped in the last 60 days and "
            "give me actions to re-engage them"
        ),
        "expect": {
            "intent": "segment",           # this is behavior/segment style
            "min_insights": 4,
        },
    },
    {
        "id": "bonus_trend_long",
        "query": "show me monthly sales for all categories and regions, highlight seasonality, and include last year for comparison",
        "expect": {"intent": "trend", "min_insights": 3},
    },
]
