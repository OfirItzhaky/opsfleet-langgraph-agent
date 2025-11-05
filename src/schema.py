"""
Schema registry for bigquery-public-data.thelook_ecommerce.

This module centralizes table metadata (PKs, FKs, join paths, date columns)
so downstream nodes (planner/sqlgen) can reason about allowed columns and
compose *safe* SQL without free-form introspection.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

DATASET = "bigquery-public-data.thelook_ecommerce"


@dataclass(frozen=True)
class Table:
    name: str                      # short name (e.g., "orders")
    fqtn: str                      # fully qualified "project.dataset.table"
    pk: str                        # primary key (or business-unique)
    columns: Set[str]              # whitelisted columns we allow the agent to use
    date_cols: Tuple[str, ...]     # date/datetime columns allowed for filtering/grouping
    default_date_col: str          # which date col to use when caller didn't specify


# ---- Tables (trimmed to the columns we actually need) ----
TABLES: Dict[str, Table] = {
    "orders": Table(
        name="orders",
        fqtn=f"{DATASET}.orders",
        pk="order_id",
        columns={
            "order_id",
            "user_id",
            "status",    # real column name in the dataset
            "created_at",
            "shipped_at",
            "delivered_at",
            "returned_at",
            "num_of_item",
        },
        date_cols=("created_at", "delivered_at", "returned_at", "shipped_at"),
        default_date_col="created_at",
    ),
    "order_items": Table(
        name="order_items",
        fqtn=f"{DATASET}.order_items",
        pk="id",  # order_items has an id column; joins use order_id/product_id
        columns={
            "id",
            "order_id",
            "user_id",
            "product_id",
            "inventory_item_id",
            "status",
            "created_at",
            "shipped_at",
            "delivered_at",
            "returned_at",
            "sale_price",
        },
        date_cols=("created_at", "shipped_at", "delivered_at", "returned_at"),
        default_date_col="created_at",
    ),
    "products": Table(
        name="products",
        fqtn=f"{DATASET}.products",
        pk="id",
        columns={
            "id",
            "name",             # real column — NOT product_name
            "brand",
            "department",
            "category",
            "cost",
            "retail_price",
            "sku",
            "distribution_center_id",
        },
        # static catalog table
        date_cols=(),
        default_date_col="",  # not applicable
    ),
    "users": Table(
        name="users",
        fqtn=f"{DATASET}.users",
        pk="id",
        columns={
            "id",
            "first_name",
            "last_name",
            "email",
            "age",
            "gender",
            "state",
            "city",
            "country",
            "street_address",
            "postal_code",
            "created_at",
        },
        date_cols=("created_at",),
        default_date_col="created_at",
    ),
}

# ---- Canonical join paths (whitelisted only) ----
# Each tuple is: (left_table, right_table, left_key, right_key)
JOINS: List[Tuple[str, str, str, str]] = [
    ("orders", "users", "user_id", "id"),
    ("order_items", "orders", "order_id", "order_id"),
    ("order_items", "users", "user_id", "id"),
    ("order_items", "products", "product_id", "id"),
]

# Dimensions we commonly allow the agent to group by (across the tables above).
# These are validated per table in allowlist checks.
COMMON_DIMENSIONS: Dict[str, str] = {
    # users
    "gender": "users.gender",
    "country": "users.country",
    "state": "users.state",
    "city": "users.city",
    "age": "users.age",

    # products
    "brand": "products.brand",
    "department": "products.department",
    "category": "products.category",
    "product_name": "products.name",  # <-- fixed to real column
}

# ------------------------ Helpers ------------------------ #
def get_table(name: str) -> Table:
    if name not in TABLES:
        raise KeyError(f"Unknown table: {name}. Known: {sorted(TABLES)}")
    return TABLES[name]


def fqtn(name: str) -> str:
    """Return fully qualified table name for a short table name."""
    return get_table(name).fqtn


def allowed_columns(table: str) -> Set[str]:
    """Return the whitelist of allowed columns on a table."""
    return set(get_table(table).columns)


def has_column(table: str, col: str) -> bool:
    return col in allowed_columns(table)


def get_default_date_col(table: str) -> Optional[str]:
    col = get_table(table).default_date_col
    return col or None


def get_date_cols(table: str) -> Tuple[str, ...]:
    return get_table(table).date_cols


def list_joins_from(table: str) -> List[Tuple[str, str, str, str]]:
    """Return join specs where the given table appears on the left or right."""
    out = []
    for lt, rt, lk, rk in JOINS:
        if lt == table or rt == table:
            out.append((lt, rt, lk, rk))
    return out


def join_allowed(left_table: str, right_table: str, left_key: str, right_key: str) -> bool:
    return (left_table, right_table, left_key, right_key) in JOINS or \
           (right_table, left_table, right_key, left_key) in JOINS


def resolve_common_dimension(dim: str) -> str:
    """
    Map a friendly dimension name to a fully-qualified column reference.
    Raises if the dimension is not allowed.
    """
    if dim not in COMMON_DIMENSIONS:
        raise ValueError(
            f"Unsupported dimension '{dim}'. Allowed: {sorted(COMMON_DIMENSIONS)}"
        )
    return COMMON_DIMENSIONS[dim]


def ensure_dims_exist(requested_dims: List[str]) -> List[str]:
    """
    Validate a list of requested dimensions (friendly names) and return their
    fully-qualified column expressions.
    """
    return [resolve_common_dimension(d) for d in requested_dims]


def validate_metrics(table: str, requested_cols: List[str]) -> None:
    """
    Ensure requested metric columns exist on the table (used by sqlgen guardrails).
    """
    cols = allowed_columns(table)
    missing = [c for c in requested_cols if c not in cols]
    if missing:
        raise ValueError(
            f"Metrics not allowed on {table}: {missing}. Allowed: {sorted(cols)}"
        )
