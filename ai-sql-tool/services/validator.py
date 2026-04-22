"""
services/validator.py
──────────────────────
Security layer: validates SQL before execution.
Blocks all destructive operations and enforces SELECT-only policy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ──────────────────────────────────────────────
#  Result type
# ──────────────────────────────────────────────

@dataclass
class ValidationResult:
    is_valid: bool
    cleaned_sql: str          # stripped and normalized
    error: str = ""


# ──────────────────────────────────────────────
#  Dangerous patterns
# ──────────────────────────────────────────────

# Keywords that indicate write/destroy operations
_DESTRUCTIVE_KEYWORDS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bTRUNCATE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bREPLACE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXECUTE\b",
    r"\bCALL\b",
    r"\bDO\b",
    r"\bCOPY\b",
]

# PostgreSQL-specific dangerous patterns
_DANGEROUS_PATTERNS = [
    r"pg_sleep",
    r"pg_read_file",
    r"pg_write_file",
    r"lo_import",
    r"lo_export",
    r"SYSTEM\s*\(",        # system() calls in some extensions
    r";\s*[A-Z]",          # SQL injection via stacked statements
    r"--\s*;",             # comment-based injection
]

_DESTRUCTIVE_RE = re.compile(
    "|".join(_DESTRUCTIVE_KEYWORDS), re.IGNORECASE
)
_DANGEROUS_RE = re.compile(
    "|".join(_DANGEROUS_PATTERNS), re.IGNORECASE
)


# ──────────────────────────────────────────────
#  Validator
# ──────────────────────────────────────────────

class SQLValidator:
    """
    Multi-stage SQL validator:
    1. Strip markdown fences / surrounding whitespace
    2. Reject empty queries
    3. Reject destructive keywords
    4. Reject dangerous patterns
    5. Enforce SELECT-only
    """

    @staticmethod
    def validate(raw_sql: str) -> ValidationResult:
        # ── Stage 1: clean up LLM output ──────────────
        sql = _strip_markdown(raw_sql).strip()

        if not sql:
            return ValidationResult(
                is_valid=False,
                cleaned_sql="",
                error="Empty query received from the model.",
            )

        # ── Stage 2: destructive keywords ─────────────
        match = _DESTRUCTIVE_RE.search(sql)
        if match:
            keyword = match.group(0).upper()
            return ValidationResult(
                is_valid=False,
                cleaned_sql=sql,
                error=(
                    f"Query contains forbidden keyword '{keyword}'. "
                    "Only SELECT queries are allowed."
                ),
            )

        # ── Stage 3: dangerous patterns ───────────────
        if _DANGEROUS_RE.search(sql):
            return ValidationResult(
                is_valid=False,
                cleaned_sql=sql,
                error="Query contains a potentially dangerous pattern and was blocked.",
            )

        # ── Stage 4: must start with SELECT or WITH ───
        first_token = sql.split()[0].upper() if sql.split() else ""
        if first_token not in ("SELECT", "WITH", "EXPLAIN"):
            return ValidationResult(
                is_valid=False,
                cleaned_sql=sql,
                error=(
                    f"Query must start with SELECT (got '{first_token}'). "
                    "Only read-only queries are permitted."
                ),
            )

        return ValidationResult(is_valid=True, cleaned_sql=sql)


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Remove ```sql ... ``` or ``` ... ``` fences from LLM output."""
    # Match optional language specifier after opening fence
    pattern = r"```(?:sql|SQL)?\s*([\s\S]*?)```"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    # If no fences found, return as-is (might already be clean SQL)
    return text.strip()
