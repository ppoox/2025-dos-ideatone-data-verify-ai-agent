"""Utilities to retrieve knowledge snippets from Supabase/PostgreSQL vector tables."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence

import psycopg
from openai import OpenAI
from psycopg import rows, sql

from .settings import AgentSettings, DatabaseDomainSettings

logger = logging.getLogger("ai_agent.knowledge")


@lru_cache(maxsize=1)
def _get_openai_client(api_key: str, base_url: str) -> OpenAI:
    """Cache OpenAI client construction to avoid redundant HTTP sessions."""

    return OpenAI(api_key=api_key, base_url=base_url)


def _embed_text(settings: AgentSettings, text: str) -> Optional[List[float]]:
    if not text:
        return None

    try:
        client = _get_openai_client(
            settings.openai_api_key, settings.openai_api_base)
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=text,
        )
    except Exception as exc:  # noqa: BLE001 - 로그 후 None 반환
        logger.warning("임베딩 생성 실패: %s", exc)
        return None

    if not response.data:
        return None

    embedding = response.data[0].embedding
    if isinstance(embedding, Iterable):
        return list(embedding)
    return None


def fetch_topic_documents(
    settings: AgentSettings,
    *,
    topic: Optional[str],
    query_hint: Optional[str],
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return knowledge documents using pgvector similarity search."""

    domain_info = _resolve_domain(settings)
    if not domain_info:
        return []

    table_ident = _resolve_table_identifier(settings, domain_info)
    if table_ident is None:
        return []

    topic_col = sql.Identifier(settings.knowledge_topic_column)
    content_col = sql.Identifier(settings.knowledge_content_column)
    embed_col = sql.Identifier(settings.knowledge_embedding_column)
    meta_col = (
        sql.Identifier(settings.knowledge_metadata_column)
        if settings.knowledge_metadata_column
        else None
    )

    query_limit = limit or settings.knowledge_top_k
    embedding = _embed_text(settings, query_hint or (topic or ""))

    conditions: List[sql.Composed] = []
    params: Dict[str, Any] = {"limit": query_limit}

    if topic:
        conditions.append(
            sql.SQL("{column} = %(topic)s").format(column=topic_col)
        )
        params["topic"] = topic

    base = sql.SQL(
        "SELECT {topic_col} AS topic, {content_col} AS content"
    ).format(topic_col=topic_col, content_col=content_col)

    if meta_col is not None:
        base += sql.SQL(", {meta_col} AS metadata").format(meta_col=meta_col)

    base += sql.SQL(" FROM {table}").format(table=table_ident)

    if conditions:
        base += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)

    order_clause = sql.SQL("")
    if embedding is not None:
        params["embedding_vector"] = _format_vector_literal(embedding)
        order_clause = sql.SQL(
            ' ORDER BY {embed_col} <-> %(embedding_vector)s::vector'
        ).format(
            embed_col=embed_col
        )
    elif conditions:
        order_clause = sql.SQL(" ORDER BY {topic_col} ASC").format(
            topic_col=topic_col)

    query = base + order_clause + sql.SQL(" LIMIT %(limit)s")
    conn_uri = domain_info.connection_uri or settings.supabase_db_url
    if not conn_uri:
        logger.warning("지정된 도메인에 대한 연결 문자열을 찾을 수 없습니다.")
        return []
    try:
        with psycopg.connect(conn_uri, autocommit=True) as conn:
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute(query, params)
                rows_data = cur.fetchall()
    except psycopg.Error as exc:  # noqa: BLE001 - 로그 후 빈 리스트
        logger.warning("지식 베이스 조회 실패: %s", exc)
        return []

    return rows_data


def fetch_topic_block(
    settings: AgentSettings,
    *,
    topic: Optional[str],
    query_hint: Optional[str],
    limit: Optional[int] = None,
) -> Optional[str]:
    """Convert knowledge documents into a prompt-friendly string."""

    documents = fetch_topic_documents(
        settings,
        topic=topic,
        query_hint=query_hint,
        limit=limit,
    )
    if not documents:
        return None

    parts: List[str] = []
    for item in documents:
        content = (item or {}).get("content")
        if not content:
            continue
        metadata = item.get("metadata") if isinstance(item, dict) else None
        header = _format_metadata(metadata)
        if header:
            parts.append(f"[{header}]\n{content}")
        else:
            parts.append(str(content))

    return "\n\n".join(parts) if parts else None


def _resolve_domain(settings: AgentSettings) -> Optional[DatabaseDomainSettings]:
    try:
        return settings.get_knowledge_domain()
    except ValueError as exc:
        logger.warning("지식 도메인을 확인할 수 없습니다: %s", exc)
        return None


def _resolve_table_identifier(
    settings: AgentSettings,
    domain_info: DatabaseDomainSettings,
) -> Optional[sql.Composable]:
    table_name = settings.knowledge_table
    if not table_name:
        return None

    schema = settings.knowledge_schema or domain_info.schema

    if schema:
        return sql.Identifier(schema, table_name)
    return sql.Identifier(table_name)


def _format_metadata(metadata: Any) -> Optional[str]:
    if metadata is None:
        return None

    if isinstance(metadata, dict):
        pairs = [f"{key}={metadata[key]}" for key in sorted(metadata)]
        return ", ".join(pairs) if pairs else None

    if isinstance(metadata, str):
        text = metadata.strip()
        if not text:
            return None
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return text
        return _format_metadata(decoded)

    return str(metadata)


def _format_vector_literal(values: Sequence[float]) -> str:
    formatted = ",".join(_format_float(val) for val in values)
    return f"[{formatted}]"


def _format_float(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    text = f"{number:.12g}"
    return text
