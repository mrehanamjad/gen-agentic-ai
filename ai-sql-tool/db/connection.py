"""
db/connection.py
────────────────
Manages PostgreSQL connections via SQLAlchemy.
Supports both URL-based and component-based configuration.
"""

import os
from typing import Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.pool import QueuePool

load_dotenv()


class DatabaseConnection:
    """Thread-safe PostgreSQL connection manager using SQLAlchemy connection pool."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.host = host or os.getenv("DB_HOST", "localhost")
        self.port = int(port or os.getenv("DB_PORT", 5432))
        self.database = database or os.getenv("DB_NAME", "analytics_db")
        self.username = username or os.getenv("DB_USER", "postgres")
        self.password = password or os.getenv("DB_PASSWORD", "")
        self._engine: Optional[Engine] = None

    # ──────────────────────────────────────────────
    #  Engine
    # ──────────────────────────────────────────────

    def _build_url(self) -> str:
        """Construct a safe PostgreSQL connection URL."""
        db_url = self.database_url
        if db_url:
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return db_url

        pwd = quote_plus(self.password)
        return (
            f"postgresql+psycopg2://{self.username}:{pwd}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def get_engine(self) -> Engine:
        """Return (or lazily create) the SQLAlchemy engine."""
        if self._engine is None:
            db_url = self._build_url()
            connect_args = {}
            if "neon.tech" in db_url and "sslmode" not in db_url:
                connect_args["sslmode"] = "require"

            self._engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,   # detect stale connections
                pool_recycle=3600,    # recycle after 1 hour
                echo=False,
                connect_args=connect_args,
            )
        return self._engine

    # ──────────────────────────────────────────────
    #  Health check
    # ──────────────────────────────────────────────

    def test_connection(self) -> tuple[bool, str]:
        """
        Ping the database.
        Returns (True, version_string) on success or (False, error_message) on failure.
        """
        try:
            with self.get_engine().connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
            return True, version or "Connected"
        except OperationalError as exc:
            return False, f"Connection failed: {exc.orig}"
        except SQLAlchemyError as exc:
            return False, f"SQLAlchemy error: {str(exc)}"

    # ──────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────

    def dispose(self) -> None:
        """Close all pooled connections (call on app shutdown)."""
        if self._engine:
            self._engine.dispose()
            self._engine = None

    # ──────────────────────────────────────────────
    #  Context manager support
    # ──────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.dispose()
