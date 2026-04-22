"""
db/schema_loader.py
────────────────────
Introspects a PostgreSQL database and produces a structured schema
representation suitable for embedding into LLM prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


# ──────────────────────────────────────────────
#  Data classes
# ──────────────────────────────────────────────

@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    default: Optional[str]
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_ref: Optional[str] = None   # e.g. "orders.id"


@dataclass
class TableInfo:
    name: str
    schema: str
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count: Optional[int] = None
    sample_values: dict[str, list] = field(default_factory=dict)


@dataclass
class SchemaInfo:
    tables: list[TableInfo] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)   # human-readable FK strings

    def to_prompt_text(self) -> str:
        """
        Render the schema as a compact text block for LLM context.
        Keeps token usage low while preserving all structural info.
        """
        lines: list[str] = ["### DATABASE SCHEMA\n"]

        for tbl in self.tables:
            row_info = f"  (~{tbl.row_count:,} rows)" if tbl.row_count is not None else ""
            lines.append(f"TABLE: {tbl.schema}.{tbl.name}{row_info}")
            for col in tbl.columns:
                flags = []
                if col.is_primary_key:
                    flags.append("PK")
                if col.is_foreign_key:
                    flags.append(f"FK→{col.foreign_key_ref}")
                if not col.nullable:
                    flags.append("NOT NULL")
                flag_str = f"  [{', '.join(flags)}]" if flags else ""
                lines.append(f"  - {col.name}: {col.data_type}{flag_str}")
            lines.append("")

        if self.relationships:
            lines.append("### RELATIONSHIPS")
            lines.extend(f"  {r}" for r in self.relationships)
            lines.append("")

        return "\n".join(lines)


# ──────────────────────────────────────────────
#  Loader
# ──────────────────────────────────────────────

class SchemaLoader:
    """Loads and caches PostgreSQL schema metadata."""

    def __init__(self, engine: Engine, target_schema: str = "public"):
        self.engine = engine
        self.target_schema = target_schema
        self._cache: Optional[SchemaInfo] = None

    # ──────────────────────────────────────────────

    def load(self, force_refresh: bool = False) -> SchemaInfo:
        """Return cached schema or refresh from the database."""
        if self._cache is None or force_refresh:
            self._cache = self._introspect()
        return self._cache

    def invalidate_cache(self) -> None:
        self._cache = None

    # ──────────────────────────────────────────────
    #  Internal introspection
    # ──────────────────────────────────────────────

    def _introspect(self) -> SchemaInfo:
        inspector = inspect(self.engine)
        schema_info = SchemaInfo()

        table_names = inspector.get_table_names(schema=self.target_schema)

        for table_name in table_names:
            table_info = self._load_table(inspector, table_name)
            schema_info.tables.append(table_info)

        # Build human-readable FK relationship strings
        schema_info.relationships = self._extract_relationships(inspector, table_names)

        return schema_info

    def _load_table(self, inspector, table_name: str) -> TableInfo:
        columns_raw = inspector.get_columns(table_name, schema=self.target_schema)
        pk_cols = set(
            inspector.get_pk_constraint(table_name, schema=self.target_schema)
            .get("constrained_columns", [])
        )
        fk_map: dict[str, str] = {}
        for fk in inspector.get_foreign_keys(table_name, schema=self.target_schema):
            for local_col, ref_col in zip(
                fk["constrained_columns"], fk["referred_columns"]
            ):
                referred_table = fk.get("referred_table", "?")
                referred_schema = fk.get("referred_schema") or self.target_schema
                fk_map[local_col] = f"{referred_schema}.{referred_table}.{ref_col}"

        columns: list[ColumnInfo] = []
        for col in columns_raw:
            col_name = col["name"]
            columns.append(
                ColumnInfo(
                    name=col_name,
                    data_type=str(col["type"]),
                    nullable=col.get("nullable", True),
                    default=str(col["default"]) if col.get("default") is not None else None,
                    is_primary_key=col_name in pk_cols,
                    is_foreign_key=col_name in fk_map,
                    foreign_key_ref=fk_map.get(col_name),
                )
            )

        # Approximate row count (fast, uses pg statistics)
        row_count = self._estimate_row_count(table_name)

        return TableInfo(
            name=table_name,
            schema=self.target_schema,
            columns=columns,
            row_count=row_count,
        )

    def _estimate_row_count(self, table_name: str) -> Optional[int]:
        """Use pg_class statistics for a fast, non-blocking row estimate."""
        try:
            query = text(
                "SELECT reltuples::BIGINT FROM pg_class "
                "WHERE relname = :table AND relnamespace = "
                "(SELECT oid FROM pg_namespace WHERE nspname = :schema)"
            )
            with self.engine.connect() as conn:
                result = conn.execute(
                    query, {"table": table_name, "schema": self.target_schema}
                )
                row = result.fetchone()
                if row and row[0] >= 0:
                    return int(row[0])
        except SQLAlchemyError:
            pass
        return None

    def _extract_relationships(
        self, inspector, table_names: list[str]
    ) -> list[str]:
        """Build human-readable FK relationship descriptions."""
        relationships: list[str] = []
        for table_name in table_names:
            for fk in inspector.get_foreign_keys(table_name, schema=self.target_schema):
                local_cols = ", ".join(fk["constrained_columns"])
                ref_table = fk.get("referred_table", "?")
                ref_cols = ", ".join(fk.get("referred_columns", ["?"]))
                relationships.append(
                    f"{self.target_schema}.{table_name}({local_cols}) "
                    f"→ {self.target_schema}.{ref_table}({ref_cols})"
                )
        return relationships
