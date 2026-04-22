"""
utils/helpers.py
─────────────────
General-purpose utilities used across the application.
"""

from __future__ import annotations

import hashlib
import io
import os
import time
from functools import lru_cache
from typing import Any, Optional

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

CACHE_TTL = int(os.getenv("QUERY_CACHE_TTL", 300))


# ──────────────────────────────────────────────
#  Query cache (in-process, time-based)
# ──────────────────────────────────────────────

_query_cache: dict[str, tuple[Any, float]] = {}


def cache_key(sql: str) -> str:
    """SHA-256 fingerprint of a SQL string."""
    return hashlib.sha256(sql.encode()).hexdigest()


def get_cached_result(sql: str) -> Optional[pd.DataFrame]:
    """Return cached DataFrame if fresh, else None."""
    key = cache_key(sql)
    if key in _query_cache:
        df, stored_at = _query_cache[key]
        if time.time() - stored_at < CACHE_TTL:
            return df
        del _query_cache[key]
    return None


def cache_result(sql: str, df: pd.DataFrame) -> None:
    """Store a DataFrame result with the current timestamp."""
    _query_cache[cache_key(sql)] = (df, time.time())


def clear_cache() -> int:
    """Flush the entire query cache. Returns number of entries cleared."""
    count = len(_query_cache)
    _query_cache.clear()
    return count


# ──────────────────────────────────────────────
#  DataFrame → CSV download
# ──────────────────────────────────────────────

def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to UTF-8 CSV bytes for Streamlit download."""
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8")
    return buf.getvalue()


# ──────────────────────────────────────────────
#  Query history (session-scoped)
# ──────────────────────────────────────────────

def format_query_history_entry(
    question: str,
    sql: str,
    row_count: int,
    execution_time_ms: float,
) -> dict:
    """Build a standardized history entry dict."""
    return {
        "timestamp": time.strftime("%H:%M:%S"),
        "question": question,
        "sql": sql,
        "row_count": row_count,
        "execution_time_ms": execution_time_ms,
    }


# ──────────────────────────────────────────────
#  Basic auth
# ──────────────────────────────────────────────

def check_credentials(username: str, password: str) -> bool:
    """
    Simple credentials check against .env values.
    In production, replace with a proper identity provider.
    """
    expected_user = os.getenv("AUTH_USERNAME", "admin")
    expected_pass = os.getenv("AUTH_PASSWORD", "")
    return username == expected_user and password == expected_pass


# ──────────────────────────────────────────────
#  Misc
# ──────────────────────────────────────────────

def truncate_text(text: str, max_len: int = 120) -> str:
    """Truncate a string and append '…' if it exceeds max_len."""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """Return '{count} row(s)' with proper pluralization."""
    word = singular if count == 1 else (plural or singular + "s")
    return f"{count:,} {word}"
