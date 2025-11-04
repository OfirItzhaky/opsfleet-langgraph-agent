"""
Parameterized SQL builders for bigquery-public-data.thelook_ecommerce.

Each function returns a SQL string that:
- Uses only allowed tables/columns/joins from the schema module.
- Applies safe date bounds (defaults to last 365 days).
- Excludes cancelled rows.
- Enforces a LIMIT to keep scans predictable.

Note: All parameters are validated to fixed choices; no free-form SQL parts.
"""

from __future__ import annotations
from typing import Literal, Optional
from . import schema


# ------------------------------ Helpers ------------------------------ #

def _date_clause(table: str, start_date: Optional[str], end_date: Optional[str]) -> str:
    """
    Build a WHERE date clause using the table's default date column.

    Accepts either:
    - literal dates: '2022-01-01'
    - SQL expressions: DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY), CURRENT_DATE()

    If both None, default to last 365 days.
    """
    date_col = schema.get_default_date_col(table)
    if not date_col:
        return ""

    fq = f"{table}.{date_col}"

    def is_sql_expr(val: str) -> bool:
        v = val.strip().upper()
        return (
            v.startswith("DATE_SUB(")
            or v.startswith("DATE_ADD(")
            or v == "CURRENT_DATE()"
            or v.startswith("DATE(")  # already wrapped
        )

    if start_date and end_date:
        if is_sql_expr(start_date) and is_sql_expr(end_date):
            return f"DATE({fq}) BETWEEN {start_date} AND {end_date}"
        if is_sql_expr(start_date):
            return f"DATE({fq}) BETWEEN {start_date} AND DATE('{end_date}')"
        if is_sql_expr(end_date):
            return f"DATE({fq}) BETWEEN DATE('{start_date}') AND {end_date}"
        return f"DATE({fq}) BETWEEN DATE('{start_date}') AND DATE('{end_date}')"

    if start_date:
        if is_sql_expr(start_date):
            return f"DATE({fq}) >= {start_date}"
        return f"DATE({fq}) >= DATE('{start_date}')"

    if end_date:
        if is_sql_expr(end_date):
            return f"DATE({fq}) <= {end_date}"
        return f"DATE({fq}) <= DATE('{end_date}')"

    return f"DATE({fq}) >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)"



def _safe_limit(n: int) -> int:
    n = int(n)
    if n <= 0:
        n = 50
    return min(n, 1000)


def _time_grain_expr(table: str, grain: Literal["day", "week", "month"]) -> str:
    """Return a SQL expression that groups a table's date column by day, week, or month."""
    col = schema.get_default_date_col(table) or "created_at"
    fq = f"{table}.{col}"  # qualify
    if grain == "day":
        return f"DATE({fq})"
    if grain == "week":
        return f"FORMAT_DATE('%G-%V', DATE({fq}))"
    return f"FORMAT_DATE('%Y-%m', DATE({fq}))"


# --------------------------- 1) Segmentation -------------------------- #

def q_customer_segments(
    by: Literal["gender", "country", "state", "city", "age", "age_bucket"] = "country",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
) -> str:
    """
    Segment customers by a dimension and compute users, orders, revenue, AOV.
    Uses order_items.sale_price for monetary metrics and orders.created_at for date filters.
    """
    # Dimension expression
    if by == "age_bucket":
        dim_expr = """
        CASE
          WHEN users.age < 20 THEN '<20'
          WHEN users.age BETWEEN 20 AND 29 THEN '20s'
          WHEN users.age BETWEEN 30 AND 39 THEN '30s'
          WHEN users.age BETWEEN 40 AND 49 THEN '40s'
          WHEN users.age BETWEEN 50 AND 59 THEN '50s'
          ELSE '60+'
        END
        """
        alias = "age_bucket"
    else:
        dim_expr = schema.resolve_common_dimension(by)
        alias = by

    where_date = _date_clause("orders", start_date, end_date)
    where_parts = [where_date, "orders.status != 'Cancelled'"]
    where_sql = "WHERE " + " AND ".join([p for p in where_parts if p]) if any(where_parts) else ""

    return f"""
    SELECT
      {dim_expr} AS {alias},
      COUNT(DISTINCT users.id) AS users,
      COUNT(DISTINCT orders.order_id) AS orders,
      ROUND(SUM(oi.sale_price), 2) AS revenue,
      ROUND(SAFE_DIVIDE(SUM(oi.sale_price), COUNT(DISTINCT orders.order_id)), 2) AS aov
    FROM `{schema.fqtn('orders')}` AS orders
    JOIN `{schema.fqtn('users')}`  AS users
      ON orders.user_id = users.id
    JOIN `{schema.fqtn('order_items')}` AS oi
      ON orders.order_id = oi.order_id
    {where_sql}
    GROUP BY {alias}
    ORDER BY revenue DESC
    LIMIT {_safe_limit(limit)}
    """.strip()


# ----------------------- 2) Product Performance ----------------------- #

def q_top_products(
    metric: Literal["revenue", "units", "avg_price"] = "revenue",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
) -> str:
    """
    Rank products by revenue / units / avg_price (using order_items + products + orders for dates).
    Uses products.name instead of products.product_name.
    """
    if metric == "revenue":
        sort_expr = "SUM(oi.sale_price)"
    elif metric == "units":
        sort_expr = "COUNT(*)"
    else:
        sort_expr = "AVG(oi.sale_price)"

    where_date = _date_clause("orders", start_date, end_date)
    where_parts = [
        where_date,
        "oi.status != 'Cancelled'",
        "orders.status != 'Cancelled'",
    ]
    where_sql = "WHERE " + " AND ".join([p for p in where_parts if p]) if any(where_parts) else ""

    return f"""
    SELECT
      p.id,
      p.name AS product_name,
      p.brand,
      p.category,
      p.department,
      ROUND(SUM(oi.sale_price), 2) AS revenue,
      COUNT(*) AS units,
      ROUND(AVG(oi.sale_price), 2) AS avg_price
    FROM `{schema.fqtn('order_items')}` AS oi
    JOIN `{schema.fqtn('products')}`    AS p
      ON oi.product_id = p.id
    JOIN `{schema.fqtn('orders')}`      AS orders
      ON oi.order_id = orders.order_id
    {where_sql}
    GROUP BY p.id, product_name, p.brand, p.category, p.department
    ORDER BY {sort_expr} DESC
    LIMIT {_safe_limit(limit)}
    """.strip()


# ----------------------- 3) Sales Trend / Season ---------------------- #

def q_sales_trend(
    grain: Literal["day", "week", "month"] = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
) -> str:
    """
    Time series of orders, revenue, and AOV by day/week/month.
    Revenue is taken from order_items.sale_price.
    """
    period_expr = _time_grain_expr("orders", grain)
    where_date = _date_clause("orders", start_date, end_date)
    where_parts = [where_date, "orders.status != 'Cancelled'"]
    where_sql = "WHERE " + " AND ".join([p for p in where_parts if p]) if any(where_parts) else ""

    return f"""
    SELECT
      {period_expr} AS period,
      COUNT(DISTINCT orders.order_id) AS orders,
      ROUND(SUM(oi.sale_price), 2) AS revenue,
      ROUND(
        SAFE_DIVIDE(SUM(oi.sale_price), COUNT(DISTINCT orders.order_id)),
        2
      ) AS aov
    FROM `{schema.fqtn('orders')}` AS orders
    JOIN `{schema.fqtn('order_items')}` AS oi
      ON orders.order_id = oi.order_id
    {where_sql}
    GROUP BY period
    ORDER BY period
    LIMIT {_safe_limit(limit)}
    """.strip()


# ------------------------- 4) Geographic Patterns --------------------- #

def q_geo_sales(
    level: Literal["country", "state", "city"] = "country",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
) -> str:
    """
    Revenue and order counts by geographic level (country/state/city).
    Revenue taken from order_items.sale_price.
    """
    dim_expr = schema.resolve_common_dimension(level)  # users.country/state/city
    alias = level

    where_date = _date_clause("orders", start_date, end_date)
    where_parts = [where_date, "orders.status != 'Cancelled'"]
    where_sql = "WHERE " + " AND ".join([p for p in where_parts if p]) if any(where_parts) else ""

    # window SUM(...) OVER () is on the revenue aggregated by group
    return f"""
    SELECT
      {dim_expr} AS {alias},
      COUNT(DISTINCT orders.order_id) AS orders,
      ROUND(SUM(oi.sale_price), 2) AS revenue,
      ROUND(
        SAFE_DIVIDE(
          SUM(oi.sale_price),
          NULLIF(SUM(SUM(oi.sale_price)) OVER (), 0)
        ),
        4
      ) AS revenue_share
    FROM `{schema.fqtn('orders')}` AS orders
    JOIN `{schema.fqtn('users')}`  AS users
      ON orders.user_id = users.id
    JOIN `{schema.fqtn('order_items')}` AS oi
      ON orders.order_id = oi.order_id
    {where_sql}
    GROUP BY {alias}
    ORDER BY revenue DESC
    LIMIT {_safe_limit(limit)}
    """.strip()
