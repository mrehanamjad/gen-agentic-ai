"""
ui/components.py
─────────────────
Reusable Streamlit UI components.
All rendering logic is isolated here — app.py stays clean.
"""

from __future__ import annotations

import json
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.helpers import dataframe_to_csv_bytes, pluralize, truncate_text


# ──────────────────────────────────────────────
#  Chat bubbles
# ──────────────────────────────────────────────

def render_user_message(text: str) -> None:
    with st.chat_message("user"):
        st.markdown(text)


def render_assistant_message(content: str) -> None:
    with st.chat_message("assistant"):
        st.markdown(content)


def render_thinking_spinner(message: str = "Generating SQL…"):
    """Context manager: shows a spinner while the LLM works."""
    return st.spinner(message)


# ──────────────────────────────────────────────
#  SQL display
# ──────────────────────────────────────────────

def render_sql_block(sql: str, execution_time_ms: float = 0.0) -> None:
    """Render generated SQL inside a collapsible with copy support."""
    label = "📋 Generated SQL"
    if execution_time_ms:
        label += f"  ·  ⚡ {execution_time_ms:.0f}ms"
    with st.expander(label, expanded=True):
        st.code(sql, language="sql")


# ──────────────────────────────────────────────
#  Results table
# ──────────────────────────────────────────────

def render_results_table(
    df: pd.DataFrame,
    was_truncated: bool = False,
    max_rows: int = 1000,
) -> None:
    """Display query results with optional truncation warning and download."""
    if df is None or df.empty:
        st.info("Query returned no rows.")
        return

    # Truncation banner
    if was_truncated:
        st.warning(
            f"⚠️ Results capped at {max_rows:,} rows. "
            "Add a LIMIT or filters to see more specific data."
        )

    # Row / column summary
    st.caption(
        f"{pluralize(len(df), 'row')}  ·  "
        f"{pluralize(len(df.columns), 'column')}"
    )

    st.dataframe(df, use_container_width=True, height=320)

    # CSV download
    csv_bytes = dataframe_to_csv_bytes(df)
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_bytes,
        file_name="query_results.csv",
        mime="text/csv",
        key=f"dl_{id(df)}",
    )


# ──────────────────────────────────────────────
#  Visualizations
# ──────────────────────────────────────────────

_CHART_TYPES = ["Auto-detect", "Bar", "Line", "Pie", "Scatter", "Table only"]


def render_visualization(
    df: pd.DataFrame,
    question: str,
    suggestion: Optional[dict] = None,
) -> None:
    """
    Render interactive chart with chart-type selector.
    Uses LLM suggestion as default if available.
    """
    if df is None or df.empty or len(df.columns) < 1:
        return

    # Determine default from suggestion
    default_chart = "Auto-detect"
    if suggestion and suggestion.get("chart_type"):
        ct = suggestion["chart_type"].capitalize()
        if ct in _CHART_TYPES:
            default_chart = ct

    st.subheader("📊 Visualization")

    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        chart_type = st.selectbox(
            "Chart type",
            _CHART_TYPES,
            index=_CHART_TYPES.index(default_chart),
            key=f"ct_{id(df)}",
        )
    with col2:
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        all_cols = df.columns.tolist()
        x_default = suggestion.get("x_column") if suggestion else None
        y_default = suggestion.get("y_column") if suggestion else None

        x_col = st.selectbox(
            "X axis",
            all_cols,
            index=all_cols.index(x_default) if x_default in all_cols else 0,
            key=f"xc_{id(df)}",
        )
    with col3:
        y_col = st.selectbox(
            "Y axis",
            numeric_cols or all_cols,
            index=(
                (numeric_cols or all_cols).index(y_default)
                if y_default in (numeric_cols or all_cols)
                else 0
            ),
            key=f"yc_{id(df)}",
        )

    # Show suggestion reason
    if suggestion and suggestion.get("reason"):
        st.caption(f"💡 {suggestion['reason']}")

    # Resolve auto-detect
    resolved = chart_type
    if chart_type == "Auto-detect":
        resolved = _auto_detect_chart(df, x_col, y_col)

    if resolved == "Table only":
        return  # table was already rendered

    fig = _build_chart(df, resolved, x_col, y_col, question)
    if fig:
        st.plotly_chart(fig, use_container_width=True)


def _auto_detect_chart(df: pd.DataFrame, x_col: str, y_col: str) -> str:
    """Heuristic chart selection when the user picks Auto-detect."""
    if len(df) <= 10:
        return "Bar"
    numeric_count = len(df.select_dtypes(include="number").columns)
    if numeric_count >= 2:
        return "Scatter"
    if len(df) <= 30:
        return "Bar"
    return "Line"


def _build_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_col: str,
    title: str,
) -> Optional[go.Figure]:
    """Build a Plotly figure for the given chart type."""
    short_title = truncate_text(title, 60)
    try:
        if chart_type == "Bar":
            return px.bar(
                df, x=x_col, y=y_col, title=short_title,
                template="plotly_white", color_discrete_sequence=["#4F8EF7"],
            )
        elif chart_type == "Line":
            return px.line(
                df, x=x_col, y=y_col, title=short_title,
                template="plotly_white", markers=True,
                color_discrete_sequence=["#4F8EF7"],
            )
        elif chart_type == "Pie":
            return px.pie(
                df, names=x_col, values=y_col, title=short_title,
                template="plotly_white",
            )
        elif chart_type == "Scatter":
            return px.scatter(
                df, x=x_col, y=y_col, title=short_title,
                template="plotly_white",
                color_discrete_sequence=["#4F8EF7"],
            )
    except Exception as exc:
        st.warning(f"Could not render {chart_type} chart: {exc}")
    return None


# ──────────────────────────────────────────────
#  Explanation panel
# ──────────────────────────────────────────────

def render_answer(answer: str) -> None:
    if answer and answer != "Answer unavailable.":
        st.info(answer, icon="💡")


# ──────────────────────────────────────────────
#  Error display
# ──────────────────────────────────────────────

def render_error(message: str, retry_info: str = "") -> None:
    st.error(f"❌ {message}")
    if retry_info:
        st.caption(retry_info)


# ──────────────────────────────────────────────
#  Schema sidebar
# ──────────────────────────────────────────────

def render_schema_preview(schema_info) -> None:
    """Render a collapsible schema tree in the sidebar."""
    if not schema_info or not schema_info.tables:
        st.info("No schema loaded.")
        return

    for table in schema_info.tables:
        row_label = (
            f" (~{table.row_count:,} rows)" if table.row_count is not None else ""
        )
        with st.expander(f"📄 {table.name}{row_label}", expanded=False):
            for col in table.columns:
                flags = []
                if col.is_primary_key:
                    flags.append("🔑")
                if col.is_foreign_key:
                    flags.append("🔗")
                flag_str = " ".join(flags)
                st.markdown(
                    f"`{col.name}` — *{col.data_type}* {flag_str}",
                    unsafe_allow_html=False,
                )


# ──────────────────────────────────────────────
#  Query history
# ──────────────────────────────────────────────

def render_query_history(history: list[dict]) -> None:
    """Render saved query history with copy-to-clipboard SQL."""
    if not history:
        st.info("No queries saved yet.")
        return

    for i, entry in enumerate(reversed(history)):
        with st.expander(
            f"[{entry['timestamp']}] {truncate_text(entry['question'], 60)}",
            expanded=False,
        ):
            st.code(entry["sql"], language="sql")
            st.caption(
                f"{pluralize(entry['row_count'], 'row')}  ·  "
                f"{entry['execution_time_ms']:.0f}ms"
            )


# ──────────────────────────────────────────────
#  Status badges
# ──────────────────────────────────────────────

def status_badge(connected: bool) -> str:
    return "🟢 Connected" if connected else "🔴 Disconnected"
