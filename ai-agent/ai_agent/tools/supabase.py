"""LangChain tool for querying Supabase-hosted PostgreSQL databases."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import psycopg
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field


def _normalize_sql(sql: str) -> str:
    return sql.strip().rstrip(";")


def _ensure_select(sql: str) -> str:
    cleaned = _normalize_sql(sql)
    if not cleaned.lower().startswith("select"):
        msg = "Supabase SQL tool은 SELECT 쿼리만 허용합니다."
        raise ValueError(msg)
    return cleaned


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, memoryview):
        return value.tobytes().hex()
    return value


def _rows_to_dicts(columns: list[str], raw_rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in raw_rows:
        entry = {col: _serialize_value(row[idx]) for idx, col in enumerate(columns)}
        results.append(entry)
    return results


class SupabaseQueryInput(BaseModel):
    sql: str = Field(
        ..., description="반드시 SELECT로 시작하는 SQL 문. 예: SELECT * FROM events WHERE status = %(status)s"
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="psycopg의 명명된 자리표시자를 사용하는 쿼리 파라미터. 예: {'status': 'active'}",
    )
    limit: Optional[int] = Field(
        default=None,
        description="쿼리에 LIMIT가 없을 경우 적용할 최대 행 수. 지정하지 않으면 기본값을 사용합니다.",
    )


def build_supabase_query_tool(connection_uri: str, *, default_limit: int = 100) -> StructuredTool:
    """Return a LangChain tool that executes read-only queries against Supabase."""

    if not connection_uri:
        msg = "Supabase/PostgreSQL 연결 문자열이 비어 있습니다."
        raise ValueError(msg)

    def _run(sql: str, params: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> str:
        cleaned = _ensure_select(sql)

        effective_limit = limit or default_limit
        query = cleaned
        if " limit " not in cleaned.lower() and "\nlimit " not in cleaned.lower():
            # 절대 0 이하의 limit는 허용하지 않음
            if effective_limit is None or effective_limit <= 0:
                effective_limit = default_limit
            query = f"{cleaned} LIMIT {effective_limit}"

        try:
            with psycopg.connect(connection_uri, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
        except psycopg.Error as exc:  # noqa: BLE001 - 변환하여 노출
            diag = getattr(exc, "diag", None)
            sqlstate = getattr(diag, "sqlstate", None) if diag else None
            message = getattr(exc, "pgerror", None) or sqlstate or str(exc)
            raise RuntimeError(f"Supabase 쿼리 실행 실패: {message}") from exc

        payload = {
            "columns": columns,
            "rows": _rows_to_dicts(columns, rows),
            "row_count": len(rows),
        }
        return json.dumps(payload, ensure_ascii=False)

    return StructuredTool.from_function(
        func=_run,
        name="query_supabase_sql",
        description=(
            "Supabase에 호스팅된 PostgreSQL 데이터베이스에서 읽기 전용 SELECT 쿼리를 실행합니다. "
            "psycopg 명명된 파라미터를 사용할 수 있으며, 반환값은 JSON 문자열입니다."
        ),
        args_schema=SupabaseQueryInput,
    )
