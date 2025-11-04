from src.nodes.sqlgen import sqlgen_node
from src.agent_state import AgentState


def test_sqlgen_customer_segments():
    s = AgentState(
        intent="segment",
        template_id="q_customer_segments",
        params={"by": "country", "limit": 50},
    )
    out = sqlgen_node(s)
    assert "from `bigquery-public-data.thelook_ecommerce.orders`" in out.last_sql.lower()
    assert "group by country" in out.last_sql.lower()
    assert out.params.get("sqlgen_status") == "ok"


def test_sqlgen_top_products():
    s = AgentState(
        intent="product",
        template_id="q_top_products",
        params={"metric": "revenue", "limit": 10},
    )
    out = sqlgen_node(s)
    sql = out.last_sql.lower()
    assert "from `bigquery-public-data.thelook_ecommerce.order_items`" in sql
    assert "join `bigquery-public-data.thelook_ecommerce.products`" in sql
    assert "order by sum(oi.sale_price) desc" in sql


def test_sqlgen_trend_defaults_dates():
    # plan gave fancy date strings -> sqlgen should normalize to template defaults
    s = AgentState(
        intent="trend",
        template_id="q_sales_trend",
        params={
            "grain": "month",
            "start_date": "DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)",
            "end_date": "CURRENT_DATE()",
            "limit": 123,
        },
    )
    out = sqlgen_node(s)
    sql = out.last_sql.lower()
    assert "from `bigquery-public-data.thelook_ecommerce.orders`" in sql
    assert "group by period" in sql
    # we don't assert exact date text because template will use its own default


def test_sqlgen_geo():
    s = AgentState(
        intent="geo",
        template_id="q_geo_sales",
        params={"level": "city", "limit": 77},
    )
    out = sqlgen_node(s)
    sql = out.last_sql.lower()
    assert "join `bigquery-public-data.thelook_ecommerce.users`" in sql
    assert "group by city" in sql


def test_sqlgen_unknown_template_raises():
    s = AgentState(intent="trend", template_id="not_a_template", params={})
    raised = False
    try:
        sqlgen_node(s)
    except ValueError:
        raised = True
    assert raised
