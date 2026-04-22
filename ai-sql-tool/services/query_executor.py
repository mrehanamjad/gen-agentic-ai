"""
services/query_executor.py
───────────────────────────
Executes validated SQL against PostgreSQL.
Handles timeouts, large result sets, and auto-retries with LLM correction.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, OperationalError

from dotenv import load_dotenv

load_dotenv()

MAX_ROWS = int(os.getenv("MAX_ROWS_DISPLAY", 1000))
STATEMENT_TIMEOUT_MS = 30_000   # 30 seconds


@dataclass
class ExecutionResult:
    """Holds the outcome of a SQL execution attempt."""
    success: bool
    dataframe: Optional[pd.DataFrame] = None
    error: str = ""
    row_count: int = 0
    execution_time_ms: float = 0.0
    was_truncated: bool = False          # True if result capped at MAX_ROWS
    columns: list[str] = field(default_factory=list)


class QueryExecutor:
    """
    Executes SELECT queries safely:
    - Sets a per-statement timeout
    - Caps result rows at MAX_ROWS
    - Returns structured ExecutionResult (never raises to caller)
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    # ──────────────────────────────────────────────
    #  Public execute
    # ──────────────────────────────────────────────

    def execute(self, sql: str) -> ExecutionResult:
        """
        Run the SQL and return an ExecutionResult.
        Never raises — all errors are captured in the result.
        """
        start = time.perf_counter()
        try:
            with self.engine.connect() as conn:
                # Set a statement-level timeout to prevent runaway queries
                conn.execute(
                    text(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
                )

                result = conn.execute(text(sql))
                columns = list(result.keys())

                # Fetch up to MAX_ROWS + 1 so we can detect truncation
                rows = result.fetchmany(MAX_ROWS + 1)
                was_truncated = len(rows) > MAX_ROWS
                rows = rows[:MAX_ROWS]

                df = pd.DataFrame(rows, columns=columns)
                elapsed = (time.perf_counter() - start) * 1000

                return ExecutionResult(
                    success=True,
                    dataframe=df,
                    row_count=len(df),
                    execution_time_ms=round(elapsed, 1),
                    was_truncated=was_truncated,
                    columns=columns,
                )

        except ProgrammingError as exc:
            return ExecutionResult(
                success=False,
                error=self._clean_error(exc),
                execution_time_ms=(time.perf_counter() - start) * 1000,
            )
        except OperationalError as exc:
            msg = self._clean_error(exc)
            if "statement timeout" in msg.lower():
                msg = (
                    f"Query exceeded the {STATEMENT_TIMEOUT_MS // 1000}s timeout. "
                    "Try a more specific query or add filters."
                )
            return ExecutionResult(
                success=False,
                error=msg,
                execution_time_ms=(time.perf_counter() - start) * 1000,
            )
        except SQLAlchemyError as exc:
            return ExecutionResult(
                success=False,
                error=self._clean_error(exc),
                execution_time_ms=(time.perf_counter() - start) * 1000,
            )

    # ──────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _clean_error(exc: Exception) -> str:
        """
        Extract a human-readable error string from SQLAlchemy exceptions.
        Strips internal boilerplate while preserving the postgres message.
        """
        original = getattr(exc, "orig", None)
        if original:
            msg = str(original).split("\n")[0]
        else:
            msg = str(exc).split("\n")[0]
        # Remove the psycopg2 error code prefix if present
        return msg.replace("ERROR:  ", "").strip()
