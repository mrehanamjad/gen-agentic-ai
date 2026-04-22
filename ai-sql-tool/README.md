# 🔍 AI Data Analyst

A production-ready chat-to-SQL application powered by **Groq LLMs**, **PostgreSQL**, **Streamlit**, and **Plotly**. Ask questions in plain English — get instant SQL, results, and visualizations.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Natural Language → SQL** | Converts plain English questions into optimized PostgreSQL queries |
| **Schema Awareness** | Automatically introspects tables, columns, types, PKs, FKs, and row counts |
| **Auto-correction** | If a query fails, the LLM auto-fixes and retries |
| **Smart Visualization** | LLM suggests the best chart type; user can override |
| **Conversational Memory** | Follow-up questions like "now filter by last month" work correctly |
| **Query Explanation** | Every query is explained in plain English for non-technical users |
| **Security Layer** | Blocks DROP, DELETE, UPDATE, INSERT, ALTER — SELECT only |
| **Query Cache** | In-process TTL cache avoids redundant database hits |
| **CSV Export** | Download any result as CSV with one click |
| **Query History** | Sidebar log of all queries with timing and row counts |
| **Basic Auth** | Optional login gate (enable via `.env`) |
| **Streaming-ready** | Groq client supports both streaming and non-streaming |

---

## 🗂️ Project Structure

```
ai_analyst/
├── app.py                    # Main Streamlit application
├── db/
│   ├── connection.py         # SQLAlchemy connection pool manager
│   └── schema_loader.py      # PostgreSQL schema introspection
├── llm/
│   ├── groq_client.py        # Groq API wrapper (streaming + non-streaming)
│   └── prompt_templates.py   # All LLM prompts (single source of truth)
├── services/
│   ├── validator.py          # SQL security validator (SELECT-only policy)
│   ├── sql_generator.py      # NL→SQL + fix + explain + chart suggestion
│   └── query_executor.py     # Safe query execution with timeout + truncation
├── ui/
│   └── components.py         # All Streamlit UI components
├── utils/
│   └── helpers.py            # Cache, CSV export, auth, formatting utilities
├── sample_schema.sql         # Sample e-commerce PostgreSQL schema + seed data
├── .env.example              # Environment variable template
└── requirements.txt
```

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone <repo-url>
cd ai_analyst
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

DB_HOST=localhost
DB_PORT=5432
DB_NAME=analytics_db
DB_USER=postgres
DB_PASSWORD=your_password
```

### 3. Set up the sample database

```bash
psql -U postgres -c "CREATE DATABASE analytics_db;"
psql -U postgres -d analytics_db -f sample_schema.sql
```

### 4. Run the app

```bash
streamlit run app.py
```

Visit `http://localhost:8501`

---

## 🔧 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Your Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `analytics_db` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | *(required)* | Database password |
| `MAX_QUERY_RETRIES` | `2` | LLM auto-fix attempts on failure |
| `QUERY_CACHE_TTL` | `300` | Query cache lifetime in seconds |
| `MAX_ROWS_DISPLAY` | `1000` | Maximum rows returned per query |
| `ENABLE_AUTH` | `false` | Enable login gate |
| `AUTH_USERNAME` | `admin` | Username (when auth enabled) |
| `AUTH_PASSWORD` | *(required)* | Password (when auth enabled) |

---

## 💬 Sample Questions to Try

With the sample e-commerce schema loaded:

```
What are the top 5 products by total revenue?
Show me monthly order counts and revenue for this year
Which customers have spent the most? Show top 10
What is the average order value by customer tier?
Which product categories have the highest profit margin?
How many orders were cancelled vs delivered last month?
Which marketing channel drove the most conversions?
Show me revenue trend by week for the past 3 months
What cities have the most customers?
Which products are low on stock?
```

**Follow-up questions work too:**
```
User:      "Show me top 10 customers by revenue"
Assistant: [shows table]
User:      "Now filter to only premium tier customers"
Assistant: [applies filter using conversation context]
```

---

## 🛡️ Security

The SQL validator runs **before** every query execution and blocks:

- `DROP`, `DELETE`, `TRUNCATE` — data destruction
- `UPDATE`, `INSERT` — data modification
- `ALTER`, `CREATE` — schema changes
- `GRANT`, `REVOKE` — permission changes
- `pg_sleep`, `pg_read_file`, `lo_export` — dangerous PostgreSQL functions
- Stacked statements (`;` injection)

All queries are also subject to a **30-second statement timeout** enforced at the PostgreSQL session level.

---

## 🏗️ Architecture

```
User Input
    │
    ▼
┌─────────────────────┐
│   Streamlit UI      │  ← app.py + ui/components.py
└────────┬────────────┘
         │ question + chat history
         ▼
┌─────────────────────┐
│   SQLGenerator      │  ← services/sql_generator.py
│   (Groq LLM)        │  ← llm/groq_client.py + prompt_templates.py
└────────┬────────────┘
         │ raw SQL
         ▼
┌─────────────────────┐
│   SQLValidator      │  ← services/validator.py
│   (Security Layer)  │  Block destructive queries
└────────┬────────────┘
         │ validated SQL
         ▼
┌─────────────────────┐        ┌──────────────────┐
│   QueryExecutor     │◄──────►│   PostgreSQL     │
│   (+ cache check)   │        │   (SQLAlchemy)   │
└────────┬────────────┘        └──────────────────┘
         │ DataFrame
         ▼
┌─────────────────────┐
│  Explain + Chart    │  ← LLM generates explanation + chart suggestion
│  Suggestion (LLM)   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Plotly Chart +    │  ← ui/components.py
│   Results Table     │
└─────────────────────┘
```

---

## 📦 Dependencies

```
streamlit>=1.35.0       # UI framework
groq>=0.9.0             # Groq LLM API client
sqlalchemy>=2.0.0       # Database ORM / connection pooling
psycopg2-binary>=2.9.9  # PostgreSQL driver
plotly>=5.20.0          # Interactive charts
pandas>=2.2.0           # DataFrame processing
python-dotenv>=1.0.0    # Environment variable management
bcrypt>=4.1.2           # Password hashing (auth)
```

---

## 🔌 Connecting Your Own Database

You can connect to **any PostgreSQL database** — the app will automatically introspect the schema and use it as LLM context.

1. Enter your connection details in the sidebar
2. Click **Connect DB**
3. The schema is loaded automatically
4. Start asking questions about your data

---

## 📈 Production Considerations

For deploying beyond a local setup:

- **Secrets**: Use environment variables or a secrets manager (AWS Secrets Manager, HashiCorp Vault) instead of `.env` files
- **Auth**: Replace the basic username/password auth with OAuth or SSO
- **Cache**: Replace the in-process dict cache with Redis for multi-instance deployments
- **Connection pooling**: The SQLAlchemy pool (size=5, overflow=10) works well for small teams; scale up for higher concurrency
- **Rate limiting**: Add per-user rate limits on the Groq API to control costs
- **Logging**: Add structured logging (structlog or similar) for query auditing
- **Monitoring**: Track query latency, LLM costs, and cache hit rates
