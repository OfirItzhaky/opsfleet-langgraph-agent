# src/utils/sql_guardrails.py
from typing import Tuple, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)

# words/constructs we never want to see from the LLM
MALICIOUS_PATTERNS = [
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\btruncate\b",
    r"\bcreate\b",
    r"\bmerge\b",
    r"\bgrant\b",
    r"\brevoke\b",
]

# things that often signal “more than one statement” or hidden payload
SUSPICIOUS_PATTERNS = [
    r";\s*--",     # statement terminator + comment
    r";\s*$",      # trailing semicolon (we can allow but flag)
    r"/\*.*?\*/",  # block comments
]


def validate_dynamic_sql(sql: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Very lightweight guard:
    - reject obvious DML / DDL / privilege statements
    - reject clearly suspicious multi-statement/comment payloads
    - otherwise accept

    Returns (ok, info)
    ok=False → info["reason"] tells you why.
    """
    s = (sql or "").strip()
    if not s:
        return False, {"reason": "empty_sql"}

    lowered = s.lower()

    # 1) hard-block obviously destructive stuff
    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, lowered):
            return False, {"reason": "forbidden_keyword_detected", "pattern": pattern}

    # 2) soft-block common injection-ish shapes
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, s, flags=re.DOTALL):
            return False, {"reason": "suspicious_construct", "pattern": pattern}

    # 3) single-statement quick check (avoid "select ...; drop table ...")
    # if there is more than one ';' it's safer to drop it
    if s.count(";") > 1:
        return False, {"reason": "multiple_statements"}

    # if we got here, we accept
    return True, {"reason": "ok"}
