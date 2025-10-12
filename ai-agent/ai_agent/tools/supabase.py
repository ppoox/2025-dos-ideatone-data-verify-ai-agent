"""LangChain tool for querying Supabase-hosted PostgreSQL databases."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

import psycopg
from psycopg import sql as pg_sql
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from ..settings import AgentSettings, DatabaseDomainSettings

logger = logging.getLogger("ai_agent.tools.supabase")


def _normalize_sql(sql: str) -> str:
    return sql.strip().rstrip(";")


def _ensure_select(sql: str) -> str:
    cleaned = _normalize_sql(sql)
    lowered = cleaned.lower()
    if lowered.startswith("with "):
        if " select " not in f" {lowered} ":
            raise ValueError("WITH 절에는 반드시 SELECT가 포함되어야 합니다.")
    elif not lowered.startswith("select"):
        raise ValueError("Supabase SQL tool은 SELECT 또는 WITH로 시작하는 읽기 전용 쿼리만 허용합니다.")

    if ";" in cleaned:
        raise ValueError("여러 문장을 포함한 SQL은 허용되지 않습니다.")

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
    domain: Optional[str] = Field(
        default=None,
        description="조회 대상 도메인. 설정된 도메인이 없으면 기본 연결을 사용합니다.",
    )
    schema_name: Optional[str] = Field(
        default=None,
        alias="schema",
        description="스키마를 직접 지정하고 싶을 때 사용합니다. 미지정 시 도메인의 기본 스키마가 적용됩니다.",
    )

    model_config = {
        "populate_by_name": True,
    }


def build_supabase_query_tool(settings: AgentSettings) -> StructuredTool:
    """Return a LangChain tool that executes read-only queries against Supabase."""

    connection_uri = settings.supabase_db_url
    if not connection_uri and not settings.supabase_domains:
        msg = "Supabase/PostgreSQL 연결 문자열이 비어 있습니다."
        raise ValueError(msg)

    default_limit = settings.supabase_default_limit
    log_path = _prepare_log_path(settings.nl2sql_log_path)

    def _run(
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        domain: Optional[str] = None,
        schema_name: Optional[str] = None,
    ) -> str:
        cleaned = _ensure_select(sql)

        domain_info = _resolve_domain(settings, domain)
        target_schema = schema_name or domain_info.schema or settings.supabase_schema_name

        conn_uri = domain_info.connection_uri or connection_uri
        if not conn_uri:
            raise ValueError(
                "Supabase/PostgreSQL 연결 문자열이 설정되지 않았습니다. 도메인 구성을 확인하세요."
            )

        effective_limit = limit or default_limit
        query = cleaned
        if " limit " not in cleaned.lower() and "\nlimit " not in cleaned.lower():
            # 절대 0 이하의 limit는 허용하지 않음
            if effective_limit is None or effective_limit <= 0:
                effective_limit = default_limit
            query = f"{cleaned} LIMIT {effective_limit}"

        try:
            with psycopg.connect(conn_uri, autocommit=True) as conn:
                with conn.cursor() as cur:
                    if target_schema:
                        cur.execute(
                            pg_sql.SQL("SET search_path TO {}" ).format(
                                pg_sql.Identifier(target_schema)
                            )
                        )
                    cur.execute(query, params)
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
        except psycopg.Error as exc:  # noqa: BLE001 - 변환하여 노출
            diag = getattr(exc, "diag", None)
            sqlstate = getattr(diag, "sqlstate", None) if diag else None
            message = getattr(exc, "pgerror", None) or sqlstate or str(exc)
            raise RuntimeError(f"Supabase 쿼리 실행 실패: {message}") from exc

        payload = {
            "domain": domain_info.domain,
            "schema": target_schema,
            "executed_sql": query,
            "columns": columns,
            "rows": _rows_to_dicts(columns, rows),
            "row_count": len(rows),
            "limit_applied": " limit " in query.lower() or "\nlimit " in query.lower(),
        }

        _log_query(
            log_path=log_path,
            sql=cleaned,
            executed_sql=query,
            domain=domain_info,
            schema=target_schema,
            params=params,
            row_count=len(rows),
        )
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


def _resolve_domain(settings: AgentSettings, domain: Optional[str]) -> DatabaseDomainSettings:
    try:
        return settings.get_domain(domain)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def _prepare_log_path(raw_path: Optional[str]) -> Optional[Path]:
    if not raw_path:
        return None

    path = Path(raw_path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # noqa: BLE001 - 로거로만 알림
        logger.warning("NL2SQL 로그 디렉터리를 생성하지 못했습니다: %s", exc)
        return None
    return path


def _serialize_params(params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not params:
        return None
    return {key: _serialize_value(value) for key, value in params.items()}


def _log_query(
    *,
    log_path: Optional[Path],
    sql: str,
    executed_sql: str,
    domain: DatabaseDomainSettings,
    schema: Optional[str],
    params: Optional[Dict[str, Any]],
    row_count: int,
) -> None:
    if not log_path:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": domain.domain,
        "schema": schema,
        "sql": sql,
        "executed_sql": executed_sql,
        "params": _serialize_params(params),
        "row_count": row_count,
    }

    try:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:  # noqa: BLE001 - 로거로만 알림
        logger.warning("NL2SQL 로그 기록 실패 (%s): %s", log_path, exc)
