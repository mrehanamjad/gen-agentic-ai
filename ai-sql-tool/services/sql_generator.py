"""
services/sql_generator.py
──────────────────────────
Orchestrates: schema → prompt → Groq → validate → return SQL.
Includes retry-with-correction on failure.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from llm.groq_client import GroqClient
from llm.prompt_templates import (
    build_sql_generation_messages,
    build_sql_fix_messages,
    build_answer_messages,
    build_chart_suggestion_messages,
)
from services.validator import SQLValidator, ValidationResult
from db.schema_loader import SchemaInfo

load_dotenv()

MAX_RETRIES = int(os.getenv("MAX_QUERY_RETRIES", 2))


@dataclass
class GenerationResult:
    sql: str
    is_valid: bool
    validation_error: str = ""
    attempts: int = 1


class SQLGenerator:
    """
    Generates validated SQL from natural language.
    On execution failure, uses LLM to auto-correct and retry.
    """

    def __init__(self, groq_client: GroqClient):
        self.groq = groq_client
        self.validator = SQLValidator()

    # ──────────────────────────────────────────────
    #  Primary generation
    # ──────────────────────────────────────────────

    def generate(
        self,
        question: str,
        schema: SchemaInfo,
        chat_history: Optional[list[dict]] = None,
    ) -> GenerationResult:
        """
        Convert a natural-language question into a validated SQL query.
        Returns a GenerationResult with the SQL and validation status.
        """
        schema_text = schema.to_prompt_text()
        messages = build_sql_generation_messages(
            schema_text=schema_text,
            user_question=question,
            chat_history=chat_history,
        )

        raw = self.groq.complete(messages, temperature=0.05)
        validation = self.validator.validate(raw)

        return GenerationResult(
            sql=validation.cleaned_sql,
            is_valid=validation.is_valid,
            validation_error=validation.error,
            attempts=1,
        )

    # ──────────────────────────────────────────────
    #  Correction after execution failure
    # ──────────────────────────────────────────────

    def fix(
        self,
        question: str,
        failed_sql: str,
        error_message: str,
        schema: SchemaInfo,
    ) -> GenerationResult:
        """
        Ask the LLM to fix a SQL query that failed during execution.
        Called automatically by the query executor on error.
        """
        schema_text = schema.to_prompt_text()
        messages = build_sql_fix_messages(
            schema_text=schema_text,
            original_sql=failed_sql,
            error_message=error_message,
            user_question=question,
        )

        raw = self.groq.complete(messages, temperature=0.05)
        validation = self.validator.validate(raw)

        return GenerationResult(
            sql=validation.cleaned_sql,
            is_valid=validation.is_valid,
            validation_error=validation.error,
            attempts=2,
        )

    # ──────────────────────────────────────────────
    #  Explanation
    # ──────────────────────────────────────────────

    def generate_answer(
        self,
        sql: str,
        question: str,
        df,
    ) -> str:
        """Generate a natural language answer based on query results."""
        if df is None or df.empty:
            result_data = "No results returned."
        else:
            result_data = df.head(20).to_csv(index=False)
            
        messages = build_answer_messages(
            sql=sql,
            user_question=question,
            result_data=result_data,
        )
        return self.groq.complete(messages, temperature=0.3, max_tokens=512)

    # ──────────────────────────────────────────────
    #  Chart suggestion
    # ──────────────────────────────────────────────

    def suggest_chart(
        self,
        columns: list[str],
        sample_rows: list[dict],
        question: str,
    ) -> dict:
        """
        Ask LLM to suggest the best chart type.
        Returns a dict: {chart_type, x_column, y_column, reason}
        Falls back to {"chart_type": "table"} on any error.
        """
        import json

        messages = build_chart_suggestion_messages(
            columns=columns,
            sample_rows=sample_rows,
            user_question=question,
        )
        raw = self.groq.complete(messages, temperature=0.1, max_tokens=128)

        try:
            # Strip any accidental markdown
            clean = raw.strip().strip("```json").strip("```").strip()
            return json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            return {"chart_type": "table", "reason": "Could not parse suggestion."}
