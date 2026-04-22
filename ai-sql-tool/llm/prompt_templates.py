"""
llm/prompt_templates.py
────────────────────────
All LLM prompts live here — single source of truth.
Changing a prompt changes the model's behavior everywhere.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
#  SQL GENERATION
# ──────────────────────────────────────────────────────────────────────────────

SQL_SYSTEM_PROMPT = """\
You are an expert PostgreSQL data analyst with deep knowledge of SQL optimization.
Your role is to convert natural language questions into precise, efficient SQL queries.

STRICT RULES:
1. ONLY generate SELECT queries. Never produce DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, or any DDL/DML.
2. Always qualify table names with their schema (e.g., public.orders).
3. Use proper JOINs when relationships exist instead of subqueries where possible.
4. Add meaningful column aliases for readability (e.g., COUNT(*) AS total_orders).
5. Use LIMIT 1000 by default unless the user asks for all rows.
6. For date comparisons, use ISO format (YYYY-MM-DD) and PostgreSQL date functions.
7. Handle NULLs explicitly when they affect results (COALESCE, IS NULL).
8. Prefer CTEs (WITH clauses) for complex multi-step logic.
9. Output ONLY the raw SQL query — no markdown fences, no explanation, no preamble.

RESPONSE FORMAT: Raw SQL only. Nothing else.
"""

def build_sql_generation_messages(
    schema_text: str,
    user_question: str,
    chat_history: list[dict] | None = None,
) -> list[dict]:
    """
    Build the full message list for SQL generation.
    Injects schema as system context and preserves recent conversation
    so the model can handle follow-up questions.
    """
    messages: list[dict] = [
        {"role": "system", "content": SQL_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"AVAILABLE SCHEMA:\n{schema_text}",
        },
    ]

    # Inject last N turns for conversational context (avoid token bloat)
    MAX_HISTORY_TURNS = 6
    if chat_history:
        relevant = [
            m for m in chat_history
            if m.get("role") in ("user", "assistant") and m.get("sql")
        ][-MAX_HISTORY_TURNS:]
        for turn in relevant:
            # Summarize previous turns so the model has follow-up context
            messages.append({
                "role": "user",
                "content": turn["content"],
            })
            if turn.get("sql"):
                messages.append({
                    "role": "assistant",
                    "content": turn["sql"],
                })

    messages.append({"role": "user", "content": user_question})
    return messages


# ──────────────────────────────────────────────────────────────────────────────
#  SQL ERROR CORRECTION
# ──────────────────────────────────────────────────────────────────────────────

SQL_FIX_SYSTEM_PROMPT = """\
You are an expert PostgreSQL debugger.
You will receive a SQL query that failed, along with the error message and the database schema.
Fix the SQL query so it runs correctly.

STRICT RULES:
1. Keep the original intent of the query.
2. Only fix what's broken — do not rewrite unnecessarily.
3. ONLY generate SELECT queries.
4. Output ONLY the corrected raw SQL query — no explanation, no markdown.
"""

def build_sql_fix_messages(
    schema_text: str,
    original_sql: str,
    error_message: str,
    user_question: str,
) -> list[dict]:
    return [
        {"role": "system", "content": SQL_FIX_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"SCHEMA:\n{schema_text}\n\n"
                f"ORIGINAL QUESTION: {user_question}\n\n"
                f"FAILED SQL:\n{original_sql}\n\n"
                f"ERROR:\n{error_message}\n\n"
                "Please provide the corrected SQL query."
            ),
        },
    ]


# ──────────────────────────────────────────────────────────────────────────────
#  QUERY EXPLANATION
# ──────────────────────────────────────────────────────────────────────────────

ANSWER_SYSTEM_PROMPT = """\
You are a friendly data analyst. 
The user asked a question, a SQL query was executed on their data, and the results are provided.
Your job is to answer the user's question directly in a natural, concise, and clear way using the provided result data.
- Provide the final answer (e.g. "The total revenue in January was $50,000.").
- Be concise (1-2 short paragraphs max).
- Written in plain English.
- If the result data is empty, state that no data was found.
"""

def build_answer_messages(
    sql: str,
    user_question: str,
    result_data: str,
) -> list[dict]:
    return [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Original question: \"{user_question}\"\n\n"
                f"SQL query:\n```sql\n{sql}\n```\n\n"
                f"Result data sample:\n{result_data}\n\n"
                "Please answer the user's question directly based on these results."
            ),
        },
    ]


# ──────────────────────────────────────────────────────────────────────────────
#  CHART SUGGESTION
# ──────────────────────────────────────────────────────────────────────────────

CHART_SUGGESTION_SYSTEM_PROMPT = """\
You are a data visualization expert.
Given a SQL query result's column names and a sample of data,
recommend the single best chart type from: bar, line, pie, scatter, table.

Reply with ONLY a JSON object in this exact format (no markdown):
{"chart_type": "bar", "x_column": "month", "y_column": "revenue", "reason": "one sentence"}
"""

def build_chart_suggestion_messages(
    columns: list[str],
    sample_rows: list[dict],
    user_question: str,
) -> list[dict]:
    # Limit sample to avoid token waste
    sample = sample_rows[:5]
    return [
        {"role": "system", "content": CHART_SUGGESTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User question: {user_question}\n"
                f"Result columns: {columns}\n"
                f"Sample data: {sample}"
            ),
        },
    ]
