import pytest
from src import schema


def test_tables_exist_and_pks():
    for t in ("orders", "order_items", "products", "users"):
        tbl = schema.get_table(t)
        assert tbl.pk
        assert tbl.fqtn.endswith(t)


def test_core_columns_present():
    assert schema.has_column("orders", "order_id")
    assert schema.has_column("orders", "status")          # <- replaced order_total
    assert schema.has_column("order_items", "sale_price")
    assert schema.has_column("products", "brand")
    assert schema.has_column("users", "country")


def test_date_cols_and_defaults():
    assert "created_at" in schema.get_date_cols("orders")
    assert schema.get_default_date_col("orders") == "created_at"
    assert schema.get_default_date_col("products") is None  # N/A


def test_whitelisted_joins():
    assert schema.join_allowed("orders", "users", "user_id", "id")
    assert schema.join_allowed("order_items", "orders", "order_id", "order_id")
    assert schema.join_allowed("order_items", "products", "product_id", "id")


def test_common_dimensions_mapping():
    cols = schema.ensure_dims_exist(["country", "brand"])
    assert cols == ["users.country", "products.brand"]

    with pytest.raises(ValueError):
        schema.ensure_dims_exist(["not_a_dim"])
