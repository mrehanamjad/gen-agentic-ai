"""
app.py
───────
AI Data Analyst — Main Streamlit Application
Chat-to-SQL powered by Groq LLMs + PostgreSQL + Plotly

Run with:  streamlit run app.py
"""

from __future__ import annotations

import os
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

# ── Internal imports ─────────────────────────────────────────────────────────
from db.connection import DatabaseConnection
from db.schema_loader import SchemaLoader, SchemaInfo
from llm.groq_client import GroqClient
from services.sql_generator import SQLGenerator
from services.query_executor import QueryExecutor
from services.validator import SQLValidator
from utils.helpers import (
    get_cached_result, cache_result, clear_cache,
    format_query_history_entry, check_credentials,
)
from ui.components import (
    render_user_message, render_assistant_message,
    render_sql_block, render_results_table, render_visualization,
    render_answer, render_error, render_schema_preview,
    render_query_history, status_badge,
)

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
#  Page config (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=os.getenv("APP_TITLE", "AI Data Analyst"),
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
#  Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Clean chat bubble styling */
    .stChatMessage { border-radius: 12px; }

    /* Code blocks */
    .stCodeBlock { font-size: 0.85rem; }

    /* Sidebar section headers */
    .sidebar-section {
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #888;
        margin: 1.2rem 0 0.4rem 0;
    }

    /* Status pill */
    .status-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* Remove extra top margin on main content */
    .block-container { padding-top: 1.5rem; }

    /* Download button alignment */
    .stDownloadButton { margin-top: 0.5rem; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Session state initialization
# ─────────────────────────────────────────────────────────────────────────────

def init_session_state() -> None:
    defaults = {
        "authenticated": os.getenv("ENABLE_AUTH", "false").lower() != "true",
        "chat_history": [],          # list of message dicts for display
        "llm_history": [],           # subset passed to LLM for context
        "query_history": [],         # saved query log
        "db_connection": None,       # DatabaseConnection instance
        "schema_info": None,         # SchemaInfo instance
        "groq_client": None,         # GroqClient instance
        "sql_generator": None,       # SQLGenerator instance
        "query_executor": None,      # QueryExecutor instance
        "db_connected": False,
        "groq_connected": False,
        # DB form values (persisted across reruns)
        "db_url": os.getenv("DATABASE_URL", ""),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": int(os.getenv("DB_PORT", 5432)),
        "db_name": os.getenv("DB_NAME", "analytics_db"),
        "db_user": os.getenv("DB_USER", "postgres"),
        "db_password": os.getenv("DB_PASSWORD", ""),
        "groq_api_key": os.getenv("GROQ_API_KEY", ""),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ─────────────────────────────────────────────────────────────────────────────
#  Authentication wall
# ─────────────────────────────────────────────────────────────────────────────

def render_auth_wall() -> bool:
    """Show login form if auth is enabled. Returns True when authenticated."""
    if st.session_state.authenticated:
        return True

    st.title("🔐 AI Data Analyst")
    st.subheader("Sign in to continue")

    with st.form("auth_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if submitted:
        if check_credentials(username, password):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid credentials.")

    return False


# ─────────────────────────────────────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        st.title("🔍 AI Data Analyst")
        st.caption("Chat-to-SQL • Powered by Groq")
        st.divider()

        # ── Groq Config ─────────────────────────────
        st.markdown('<p class="sidebar-section">⚡ Groq API</p>', unsafe_allow_html=True)

        groq_key = st.text_input(
            "API Key",
            value=st.session_state.groq_api_key,
            type="password",
            placeholder="gsk_...",
            key="groq_key_input",
        )
        st.session_state.groq_api_key = groq_key

        if st.button("Connect Groq", use_container_width=True, key="btn_groq"):
            _connect_groq(groq_key)

        if st.session_state.groq_connected:
            st.success(status_badge(True))
        elif groq_key:
            st.warning("Groq not tested — click Connect.")

        # ── Database Config ──────────────────────────
        st.markdown('<p class="sidebar-section">🗄️ PostgreSQL</p>', unsafe_allow_html=True)

        with st.expander("Connection Settings", expanded=not st.session_state.db_connected):
            conn_mode = st.radio("Connection Mode", ["Connection String", "Parameters"], horizontal=True)

            if conn_mode == "Connection String":
                st.session_state.db_url = st.text_input(
                    "Database URL",
                    value=st.session_state.db_url,
                    type="password",
                    placeholder="postgresql://user:password@host/db",
                )
                # Clear parameter-based connection when overriding by URL, just to be safe
                # though `DatabaseConnection` uses URL first if truthy.
            else:
                # Need to clear db_url so DatabaseConnection falls back to parameters
                st.session_state.db_url = ""
                st.session_state.db_host = st.text_input("Host", value=st.session_state.db_host)
                st.session_state.db_port = st.number_input(
                    "Port", value=st.session_state.db_port, min_value=1, max_value=65535
                )
                st.session_state.db_name = st.text_input("Database", value=st.session_state.db_name)
                st.session_state.db_user = st.text_input("User", value=st.session_state.db_user)
                st.session_state.db_password = st.text_input(
                    "Password", value=st.session_state.db_password, type="password"
                )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Connect DB", use_container_width=True, key="btn_db"):
                _connect_database()
        with col2:
            if st.button("Refresh Schema", use_container_width=True, key="btn_schema"):
                _refresh_schema()

        if st.session_state.db_connected:
            st.success(status_badge(True))
        else:
            st.info("Configure and connect your database.")

        # ── Schema Preview ───────────────────────────
        if st.session_state.schema_info:
            st.markdown('<p class="sidebar-section">🗂️ Schema</p>', unsafe_allow_html=True)
            render_schema_preview(st.session_state.schema_info)

        # ── Tools ────────────────────────────────────
        st.markdown('<p class="sidebar-section">🛠️ Tools</p>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                st.session_state.llm_history = []
                st.rerun()
        with col2:
            if st.button("Clear Cache", use_container_width=True):
                n = clear_cache()
                st.toast(f"Cleared {n} cached queries.")

        # ── Query History ─────────────────────────────
        if st.session_state.query_history:
            st.markdown('<p class="sidebar-section">📜 Query History</p>', unsafe_allow_html=True)
            render_query_history(st.session_state.query_history[-20:])


# ─────────────────────────────────────────────────────────────────────────────
#  Connection helpers
# ─────────────────────────────────────────────────────────────────────────────

def _connect_groq(api_key: str) -> None:
    if not api_key:
        st.sidebar.error("Please enter a Groq API key.")
        return
    try:
        client = GroqClient(api_key=api_key)
        ok, msg = client.ping()
        if ok:
            st.session_state.groq_client = client
            st.session_state.groq_connected = True
            st.session_state.sql_generator = SQLGenerator(client)
            st.sidebar.success(msg)
        else:
            st.session_state.groq_connected = False
            st.sidebar.error(msg)
    except Exception as exc:
        st.session_state.groq_connected = False
        st.sidebar.error(str(exc))


def _connect_database() -> None:
    try:
        conn = DatabaseConnection(
            database_url=st.session_state.db_url,
            host=st.session_state.db_host,
            port=st.session_state.db_port,
            database=st.session_state.db_name,
            username=st.session_state.db_user,
            password=st.session_state.db_password,
        )
        ok, msg = conn.test_connection()
        if ok:
            st.session_state.db_connection = conn
            st.session_state.db_connected = True
            st.session_state.query_executor = QueryExecutor(conn.get_engine())
            # Auto-load schema
            _load_schema(conn)
            st.sidebar.success("Database connected!")
        else:
            st.session_state.db_connected = False
            st.sidebar.error(msg)
    except Exception as exc:
        st.session_state.db_connected = False
        st.sidebar.error(str(exc))


def _load_schema(conn: DatabaseConnection) -> None:
    try:
        loader = SchemaLoader(conn.get_engine())
        st.session_state.schema_info = loader.load()
    except Exception as exc:
        st.sidebar.warning(f"Schema load failed: {exc}")


def _refresh_schema() -> None:
    if not st.session_state.db_connection:
        st.sidebar.warning("Connect to a database first.")
        return
    _load_schema(st.session_state.db_connection)
    st.sidebar.success("Schema refreshed.")
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  Main chat area
# ─────────────────────────────────────────────────────────────────────────────

def render_main() -> None:
    st.title("💬 Ask Your Data")
    st.caption(
        "Ask questions in plain English. "
        "The AI will generate SQL, run it, and visualize results."
    )

    # ── Readiness check ───────────────────────────────
    ready = st.session_state.db_connected and st.session_state.groq_connected
    if not ready:
        _render_onboarding()
        return

    # ── Chat history display ──────────────────────────
    for message in st.session_state.chat_history:
        _render_history_message(message)

    # ── Input ─────────────────────────────────────────
    if prompt := st.chat_input(
        "e.g. What are the top 10 customers by revenue this year?",
        disabled=not ready,
    ):
        _handle_user_message(prompt)


def _render_onboarding() -> None:
    """Friendly onboarding cards when not yet connected."""
    st.info(
        "👈 **Get started:** Connect Groq API and your PostgreSQL database in the sidebar.",
        icon="ℹ️",
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **1️⃣ Connect Groq**
        Enter your Groq API key and click *Connect Groq*.
        """)
    with col2:
        st.markdown("""
        **2️⃣ Connect Database**
        Enter your PostgreSQL credentials and click *Connect DB*.
        """)
    with col3:
        st.markdown("""
        **3️⃣ Ask Anything**
        Type a question like *"Show me monthly sales trends"*.
        """)


def _render_history_message(message: dict) -> None:
    """Re-render a historical chat message with all its artifacts."""
    if message["role"] == "user":
        render_user_message(message["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(message.get("text", ""))
            if message.get("sql"):
                render_sql_block(message["sql"], message.get("execution_time_ms", 0))
            if message.get("dataframe") is not None:
                df = message["dataframe"]
                render_results_table(df, message.get("was_truncated", False))
                if not df.empty and message.get("chart_suggestion"):
                    render_visualization(df, message["content_question"], message.get("chart_suggestion"))
            if message.get("answer"):
                render_answer(message["answer"])
            if message.get("error"):
                render_error(message["error"])


# ─────────────────────────────────────────────────────────────────────────────
#  Core question handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_user_message(question: str) -> None:
    """Full pipeline: question → SQL → execute → explain → visualize."""

    # 1. Display user message
    render_user_message(question)
    st.session_state.chat_history.append({"role": "user", "content": question})

    schema: SchemaInfo = st.session_state.schema_info
    generator: SQLGenerator = st.session_state.sql_generator
    executor: QueryExecutor = st.session_state.query_executor

    with st.chat_message("assistant"):
        if schema is None:
            render_error("No database schema loaded. Please check your DB connection or click 'Refresh Schema'.")
            _append_error_message(question, "No database schema loaded.")
            return

        # ── 2. Generate SQL ───────────────────────────
        with st.spinner("🧠 Generating SQL…"):
            try:
                gen_result = generator.generate(
                    question=question,
                    schema=schema,
                    chat_history=st.session_state.llm_history,
                )
            except RuntimeError as exc:
                render_error(str(exc))
                _append_error_message(question, str(exc))
                return

        if not gen_result.is_valid:
            render_error(gen_result.validation_error)
            _append_error_message(question, gen_result.validation_error)
            return

        sql = gen_result.sql

        # ── 3. Cache check ────────────────────────────
        cached_df = get_cached_result(sql)
        if cached_df is not None:
            st.caption("⚡ *Result from cache*")
            _finalize_response(question, sql, cached_df, False, 0, generator, schema)
            return

        # ── 4. Execute ────────────────────────────────
        with st.spinner("⚙️ Executing query…"):
            exec_result = executor.execute(sql)

        # ── 5. Auto-retry on execution failure ────────
        if not exec_result.success:
            with st.spinner("🔧 Query failed — asking AI to fix it…"):
                try:
                    fix_result = generator.fix(
                        question=question,
                        failed_sql=sql,
                        error_message=exec_result.error,
                        schema=schema,
                    )
                except RuntimeError as exc:
                    render_error(str(exc))
                    _append_error_message(question, str(exc))
                    return

            if fix_result.is_valid:
                exec_result = executor.execute(fix_result.sql)
                sql = fix_result.sql   # use corrected SQL
                if not exec_result.success:
                    render_error(exec_result.error, "Auto-fix also failed.")
                    _append_error_message(question, exec_result.error)
                    return
            else:
                render_error(exec_result.error)
                _append_error_message(question, exec_result.error)
                return

        # ── 6. Cache successful result ─────────────────
        if exec_result.dataframe is not None:
            cache_result(sql, exec_result.dataframe)

        # ── 7. Render result ───────────────────────────
        _finalize_response(
            question, sql,
            exec_result.dataframe,
            exec_result.was_truncated,
            exec_result.execution_time_ms,
            generator, schema,
        )


def _finalize_response(
    question: str,
    sql: str,
    df,
    was_truncated: bool,
    execution_time_ms: float,
    generator: SQLGenerator,
    schema: SchemaInfo,
) -> None:
    """Render SQL, table, chart, explanation; save to history."""

    # SQL block
    render_sql_block(sql, execution_time_ms)

    # Results table
    render_results_table(df, was_truncated)

    # Chart suggestion + visualization
    chart_suggestion = None
    if df is not None and not df.empty:
        with st.spinner("📊 Suggesting visualization…"):
            try:
                chart_suggestion = generator.suggest_chart(
                    columns=df.columns.tolist(),
                    sample_rows=df.head(5).to_dict("records"),
                    question=question,
                )
            except Exception:
                chart_suggestion = {"chart_type": "bar"}

        render_visualization(df, question, chart_suggestion)

    # Answer Generation
    answer = ""
    with st.spinner("📖 Analyzing results to generate an answer…"):
        try:
            answer = generator.generate_answer(sql, question, df)
        except Exception:
            answer = "Answer unavailable."
    
    render_answer(answer)

    # ── Summary message ───────────────────────────────
    row_info = f"{len(df):,} rows" if df is not None else "no data"
    summary = f"✅ Query returned **{row_info}** in {execution_time_ms:.0f}ms."
    st.markdown(summary)

    # ── Persist to session state ───────────────────────
    history_entry = {
        "role": "assistant",
        "text": summary,
        "sql": sql,
        "execution_time_ms": execution_time_ms,
        "dataframe": df,
        "was_truncated": was_truncated,
        "chart_suggestion": chart_suggestion,
        "answer": answer,
        "content_question": question,
        "error": "",
    }
    st.session_state.chat_history.append(history_entry)

    # LLM context (lightweight — no DataFrames)
    st.session_state.llm_history.append({
        "role": "user",
        "content": question,
        "sql": sql,
    })
    st.session_state.llm_history.append({
        "role": "assistant",
        "content": summary,
        "sql": sql,
    })

    # Query history log
    if df is not None:
        st.session_state.query_history.append(
            format_query_history_entry(
                question, sql, len(df), execution_time_ms
            )
        )


def _append_error_message(question: str, error: str) -> None:
    st.session_state.chat_history.append({
        "role": "assistant",
        "text": "",
        "sql": "",
        "execution_time_ms": 0,
        "dataframe": None,
        "was_truncated": False,
        "chart_suggestion": None,
        "answer": "",
        "content_question": question,
        "error": error,
    })


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    init_session_state()

    if not render_auth_wall():
        return   # blocked by auth wall

    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
