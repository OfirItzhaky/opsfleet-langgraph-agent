"""
Smoke test for BQ helper + SQL templates.

Run:
  python -m src.dev_smoke_bq
"""

import logging
from .clients.bq_helper import BQHelper
from . import sql_templates as st

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

def main():
    bq = BQHelper()  # uses default ADC creds and public dataset

    # 1) Segments
    sql1 = st.q_customer_segments(by="country", limit=10)
    print("\n-- Segments (country) --")
    print("Dry-run bytes:", f"{bq.dry_run(sql1):,}")
    df1 = bq.execute_safe(sql1, preview_limit=10)
    print(df1.head())

    # 2) Products
    sql2 = st.q_top_products(metric="revenue", limit=10)
    print("\n-- Top products (revenue) --")
    print("Dry-run bytes:", f"{bq.dry_run(sql2):,}")
    df2 = bq.execute_safe(sql2, preview_limit=10)
    print(df2.head())

    # 3) Trend
    sql3 = st.q_sales_trend(grain="month", limit=24)
    print("\n-- Sales trend (month) --")
    print("Dry-run bytes:", f"{bq.dry_run(sql3):,}")
    df3 = bq.execute_safe(sql3, preview_limit=24)
    print(df3.head())

    # 4) Geo
    sql4 = st.q_geo_sales(level="city", limit=10)
    print("\n-- Geo (city) --")
    print("Dry-run bytes:", f"{bq.dry_run(sql4):,}")
    df4 = bq.execute_safe(sql4, preview_limit=10)
    print(df4.head())

if __name__ == "__main__":
    main()
