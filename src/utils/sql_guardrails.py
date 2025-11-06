# src/utils/sql_guardrails.py
from typing import Tuple, Optional, Set, Dict, Any
import logging

from sqlglot import parse_one, exp

logger = logging.getLogger(__name__)

# sensible defaults you can import from config instead
DEFAULT_ALLOWED_TABLES: Set[str] = {"orders", "order_items", "products", "users"}
DEFAULT_FORBIDDEN_KEYWORDS = {"insert", "update", "delete", "drop", "alter", "create", "merge", "truncate"}
DEFAULT_MAX_LIMIT = 10000  # adjust to your cost appetite


def _extract_table_names(tree: exp.Expression) -> Set[str]:
    """Return the set of plain table names (last identifier) referenced in the AST."""
    tables = set()
    for t in tree.find_all(exp.Table):
        # t.this can be Identifier or a dotted path; get last part
        try:
            name_parts = [p.name for p in t.find_all(exp.Identifier)]
            if name_parts:
                tables.add(name_parts[-1].lower())
        except Exception:
            continue
    return tables


def _extract_limit_value(tree: exp.Expression) -> Optional[int]:
    """Return numeric LIMIT if present and is a literal integer, otherwise None."""
    lim = tree.find(exp.Limit)
    if not lim:
        return None
    # sqlglot represents LIMIT as exp.Limit(this=exp.Literal(10)) in many cases
    val = None
    try:
        # in some dialect forms limit.this may be a numeric literal expression
        lit = lim.this
        if isinstance(lit, exp.Literal):
            val = int(lit.name)
    except Exception:
        val = None
    return val


def _extract_column_names(tree: exp.Expression) -> Set[str]:
    """Collect simple column identifiers used in SELECT / WHERE / GROUP BY etc."""
    cols = set()
    for c in tree.find_all(exp.Column):
        try:
            # column could be table.col or just col; take last identifier
            idents = [p.name for p in c.find_all(exp.Identifier)]
            if idents:
                cols.add(idents[-1].lower())
        except Exception:
            continue
    return cols


def validate_dynamic_sql(
    sql: str,
    allowed_tables: Set[str] = DEFAULT_ALLOWED_TABLES,
    max_limit: int = DEFAULT_MAX_LIMIT,
    forbidden_keywords: Set[str] = DEFAULT_FORBIDDEN_KEYWORDS,
    allowed_columns: Optional[Set[str]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Parse and validate an LLM-generated SQL string.
    Returns (ok: bool, info: dict). If ok is False, info contains 'reason'.
    If ok is True, info contains metadata: {"tables": [...], "limit": int, "columns": [...]}.
    """

    sql_small = (sql or "").strip()
    if not sql_small:
        return False, {"reason": "empty_sql"}

    lowered = sql_small.lower()
    # quick check for destructive keywords before trying to parse
    if any(k in lowered for k in forbidden_keywords):
        return False, {"reason": "forbidden_keyword_detected"}

    # Parse with sqlglot – try BigQuery first, then fall back to ANSI for simple queries
    try:
        tree = parse_one(sql_small, read="bigquery")
    except Exception as e_bigquery:
        logger.warning("sql_guardrails: bigquery parse error, trying ansi", exc_info=True)
        try:
            tree = parse_one(sql_small, read="ansi")
        except Exception as e_ansi:
            logger.warning("sql_guardrails: ansi parse error too", exc_info=True)
            return False, {
                "reason": "parse_error",
                "detail": f"bigquery: {str(e_bigquery)}; ansi: {str(e_ansi)}",
            }

    # Extract and validate tables
    tables = _extract_table_names(tree)
    if not tables:
        return False, {"reason": "no_table_found"}
    unknown_tables = {t for t in tables if t not in allowed_tables}
    if unknown_tables:
        return False, {"reason": "unknown_tables", "tables": list(unknown_tables)}

    # Limit checks
    limit_val = _extract_limit_value(tree)
    if limit_val is None:
        return False, {"reason": "missing_limit"}
    if limit_val > max_limit:
        return False, {
            "reason": "limit_exceeds_max",
            "limit": limit_val,
            "max": max_limit,
        }

    # Optional: validate columns if allowed_columns provided
    columns = _extract_column_names(tree)
    if allowed_columns is not None:
        bad_cols = {c for c in columns if c not in allowed_columns}
        if bad_cols:
            return False, {"reason": "forbidden_columns", "columns": list(bad_cols)}

    # All checks passed
    return True, {
        "tables": list(tables),
        "limit": limit_val,
        "columns": list(columns),
    }

