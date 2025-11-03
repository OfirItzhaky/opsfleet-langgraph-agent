import re
from src import sql_templates as st

DATASET = "bigquery-public-data.thelook_ecommerce"


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip()).lower()


def test_segments_builds_sql_and_references_tables():
    sql = st.q_customer_segments(by="country", limit=50)
    s = _norm(sql)
    assert f"from `{DATASET}.orders`" in s
    assert f"join `{DATASET}.users`" in s
    assert "group by country" in s
    assert "limit 50" in s
    assert "date(orders.created_at)" in s


def test_products_builds_sql_and_orders_items_join():
    sql = st.q_top_products(metric="revenue", limit=10)
    s = _norm(sql)
    assert f"from `{DATASET}.order_items`" in s
    assert f"join `{DATASET}.products`" in s
    assert f"join `{DATASET}.orders`" in s
    assert "order by sum(oi.sale_price) desc" in s
    assert "limit 10" in s
    assert "status != 'cancelled'" in s  # at least one cancelled filter present


def test_trend_has_period_and_limit_and_date_guard():
    sql = st.q_sales_trend(grain="month", limit=123)
    s = _norm(sql)
    # our generator uses %y-%m or %Y-%m depending on code;
    # we just check that it's using format_date
    assert "format_date(" in s
    assert f"from `{DATASET}.orders`" in s
    assert "group by period" in s
    assert "order by period" in s
    assert "limit 123" in s
    assert "date(orders.created_at)" in s


def test_geo_uses_user_dimension_and_window_share():
    sql = st.q_geo_sales(level="country", limit=77)
    s = _norm(sql)
    assert f"join `{DATASET}.users`" in s
    assert "revenue_share" in s
    assert "group by country" in s
    assert "limit 77" in s


def test_invalid_inputs_are_handled_gracefully():
    # current code: bad metric → falls back to avg
    sql = st.q_top_products(metric="not_a_metric", limit=5)
    s = _norm(sql)
    assert f"from `{DATASET}.order_items`" in s
    assert "avg(oi.sale_price)" in s

    # current code: bad grain → still returns valid SQL
    sql2 = st.q_sales_trend(grain="quarter", limit=5)
    s2 = _norm(sql2)
    assert f"from `{DATASET}.orders`" in s2
    assert "group by period" in s2
