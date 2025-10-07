"""Helpers to introspect the Supabase/PostgreSQL schema for prompt conditioning."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

import psycopg


SCHEMA_QUERY = """
SELECT
    c.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    t.table_type
FROM information_schema.columns AS c
JOIN information_schema.tables AS t
    ON c.table_name = t.table_name
    AND c.table_schema = t.table_schema
WHERE c.table_schema = %s
ORDER BY c.table_name, c.ordinal_position
"""


def load_schema_summary(
    connection_uri: str,
    *,
    schema: str = "public",
    max_tables: int = 20,
    max_columns: int = 20,
    include_views: bool = False,
) -> str:
    """Fetch the database schema metadata and return a compact summary string."""

    if not connection_uri:
        raise ValueError("connection_uri must be provided")

    if max_tables <= 0 or max_columns <= 0:
        raise ValueError("max_tables and max_columns must be positive integers")

    tables = _load_schema_cached(
        connection_uri,
        schema,
        max_tables,
        max_columns,
        include_views,
    )

    lines: List[str] = []
    for table, info in tables.items():
        table_type, columns = info
        column_parts = []
        for name, data_type, nullable in columns[:max_columns]:
            suffix = "?" if nullable else ""
            column_parts.append(f"{name} {data_type}{suffix}")

        if len(columns) > max_columns:
            column_parts.append(f"… (+{len(columns) - max_columns} more columns)")

        type_label = "view" if table_type.lower() == "view" else "table"
        lines.append(f"- {table} ({type_label}): {', '.join(column_parts)}")

    if not lines:
        return ""

    if len(tables) >= max_tables:
        lines.append("- … (additional tables omitted)")

    header = f"스키마 `{schema}` 요약"
    return header + "\n" + "\n".join(lines)


@lru_cache(maxsize=8)
def _load_schema_cached(
    connection_uri: str,
    schema: str,
    max_tables: int,
    max_columns: int,
    include_views: bool,
) -> Dict[str, Tuple[str, List[Tuple[str, str, bool]]]]:
    allowed_types: Iterable[str]
    if include_views:
        allowed_types = ("BASE TABLE", "VIEW")
    else:
        allowed_types = ("BASE TABLE",)

    with psycopg.connect(connection_uri, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_QUERY, (schema,))
            rows = cur.fetchall()

    tables: Dict[str, Tuple[str, List[Tuple[str, str, bool]]]] = {}
    for table_name, column_name, data_type, is_nullable, table_type in rows:
        if table_type not in allowed_types:
            continue
        if table_name not in tables:
            if len(tables) >= max_tables:
                # Skip remaining tables once the limit is reached.
                continue
            tables[table_name] = (table_type, [])

        nullable = str(is_nullable).lower() == "yes"
        tables[table_name][1].append((column_name, data_type, nullable))

    return tables
