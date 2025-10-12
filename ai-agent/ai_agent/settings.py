"""Configuration helpers for the LangChain-based data verification agent."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, model_validator


def _getenv_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------------------
# Domain-aware database settings
# --------------------------------------------------------------------------------------


class DatabaseDomainSettings(BaseModel):
    """Schema and optional connection info for a specific business domain."""

    domain: str = Field(..., description="도메인 식별자 (예: billing, usage)")
    schema: str = Field(..., description="해당 도메인의 기본 스키마 이름")
    connection_uri: Optional[str] = Field(
        default=None,
        description=(
            "도메인 전용 PostgreSQL 연결 문자열. 지정하지 않으면 SUPABASE_DB_URL을 사용합니다."
        ),
    )
    description: Optional[str] = Field(
        default=None,
        description="도메인에 대한 짧은 설명 (프롬프트 참고용).",
    )


class AgentSettings(BaseModel):
    """Runtime configuration loaded from environment variables."""

    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_api_base: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    )
    model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    embedding_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )
    temperature: float = Field(default_factory=lambda: float(os.getenv("OPENAI_TEMPERATURE", 0.2)))
    max_output_tokens: Optional[int] = Field(
        default_factory=lambda: (
            int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS"))
            if os.getenv("OPENAI_MAX_OUTPUT_TOKENS")
            else None
        )
    )
    request_timeout: int = Field(default_factory=lambda: int(os.getenv("OPENAI_TIMEOUT_SECONDS", 60)))
    supabase_db_url: Optional[str] = Field(default_factory=lambda: os.getenv("SUPABASE_DB_URL"))
    supabase_default_limit: int = Field(
        default_factory=lambda: int(os.getenv("SUPABASE_DEFAULT_LIMIT", 100))
    )
    supabase_schema_summary: Optional[str] = Field(
        default_factory=lambda: os.getenv("SUPABASE_SCHEMA_SUMMARY")
    )
    supabase_schema_summary_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("SUPABASE_SCHEMA_SUMMARY_PATH")
    )
    data_glossary: Optional[str] = Field(
        default_factory=lambda: os.getenv("DATA_GLOSSARY")
    )
    data_glossary_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("DATA_GLOSSARY_PATH")
    )
    validation_guidelines: Optional[str] = Field(
        default_factory=lambda: os.getenv("DATA_VALIDATION_GUIDELINES")
    )
    validation_guidelines_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("DATA_VALIDATION_GUIDELINES_PATH")
    )
    nl2sql_log_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("AGENT_NL2SQL_LOG_FILE", "logs/nl2sql.log")
    )
    return_intermediate_steps: bool = Field(
        default_factory=lambda: _getenv_bool("AGENT_RETURN_INTERMEDIATE_STEPS", False)
    )
    supabase_schema_autoload: bool = Field(
        default_factory=lambda: _getenv_bool("SUPABASE_SCHEMA_AUTOLOAD", False)
    )
    supabase_schema_name: str = Field(
        default_factory=lambda: os.getenv("SUPABASE_SCHEMA_NAME", "public")
    )
    supabase_schema_max_tables: int = Field(
        default_factory=lambda: int(os.getenv("SUPABASE_SCHEMA_MAX_TABLES", 20))
    )
    supabase_schema_max_columns: int = Field(
        default_factory=lambda: int(os.getenv("SUPABASE_SCHEMA_MAX_COLUMNS", 15))
    )
    supabase_schema_include_views: bool = Field(
        default_factory=lambda: _getenv_bool("SUPABASE_SCHEMA_INCLUDE_VIEWS", False)
    )
    supabase_domain_config: Optional[str] = Field(
        default_factory=lambda: os.getenv("SUPABASE_DOMAIN_CONFIG")
    )
    supabase_domains: Dict[str, DatabaseDomainSettings] = Field(
        default_factory=dict,
        description="도메인 이름(domain) → DatabaseDomainSettings 매핑",
    )
    knowledge_domain: Optional[str] = Field(
        default_factory=lambda: os.getenv("SUPABASE_KNOWLEDGE_DOMAIN")
    )
    knowledge_schema: Optional[str] = Field(
        default_factory=lambda: os.getenv("SUPABASE_KNOWLEDGE_SCHEMA")
    )
    knowledge_table: Optional[str] = Field(
        default_factory=lambda: os.getenv("SUPABASE_KNOWLEDGE_TABLE")
    )
    knowledge_topic_column: str = Field(
        default_factory=lambda: os.getenv("SUPABASE_KNOWLEDGE_TOPIC_COLUMN", "topic")
    )
    knowledge_content_column: str = Field(
        default_factory=lambda: os.getenv("SUPABASE_KNOWLEDGE_CONTENT_COLUMN", "content")
    )
    knowledge_embedding_column: str = Field(
        default_factory=lambda: os.getenv("SUPABASE_KNOWLEDGE_EMBEDDING_COLUMN", "embedding")
    )
    knowledge_metadata_column: Optional[str] = Field(
        default_factory=lambda: os.getenv("SUPABASE_KNOWLEDGE_METADATA_COLUMN")
    )
    knowledge_top_k: int = Field(
        default_factory=lambda: int(os.getenv("SUPABASE_KNOWLEDGE_TOP_K", 3))
    )

    @model_validator(mode="after")
    def _load_domain_config(self) -> "AgentSettings":
        """Parse SUPABASE_DOMAIN_CONFIG JSON into structured settings."""

        raw = self.supabase_domain_config
        if not raw:
            return self

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "SUPABASE_DOMAIN_CONFIG 환경 변수는 JSON 배열 형식이어야 합니다."
            ) from exc

        if not isinstance(payload, list):
            raise ValueError(
                "SUPABASE_DOMAIN_CONFIG 값은 도메인 설정 객체 배열이어야 합니다."
            )

        domains: Dict[str, DatabaseDomainSettings] = {}
        for item in payload:
            try:
                domain_cfg = DatabaseDomainSettings.model_validate(item)
            except ValidationError as exc:
                raise ValueError(
                    f"SUPABASE_DOMAIN_CONFIG 파싱 실패: {exc}"  # noqa: EM101
                ) from exc

            key = domain_cfg.domain.lower()
            if key in domains:
                raise ValueError(
                    f"SUPABASE_DOMAIN_CONFIG에 중복된 도메인 '{domain_cfg.domain}'이 존재합니다."
                )
            domains[key] = domain_cfg

        self.supabase_domains = domains
        return self

    def validate(self) -> None:
        """Ensure critical values are present."""

        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되어야 합니다.")
        if self.supabase_default_limit <= 0:
            raise ValueError("SUPABASE_DEFAULT_LIMIT 값은 1 이상이어야 합니다.")
        if self.supabase_schema_max_tables <= 0:
            raise ValueError("SUPABASE_SCHEMA_MAX_TABLES 값은 1 이상이어야 합니다.")
        if self.supabase_schema_max_columns <= 0:
            raise ValueError("SUPABASE_SCHEMA_MAX_COLUMNS 값은 1 이상이어야 합니다.")
        if not self.supabase_db_url and not self.supabase_domains:
            raise ValueError(
                "SUPABASE_DB_URL 또는 SUPABASE_DOMAIN_CONFIG 중 하나는 반드시 설정되어야 합니다."
            )
        if self.knowledge_top_k <= 0:
            raise ValueError("SUPABASE_KNOWLEDGE_TOP_K 값은 1 이상이어야 합니다.")

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def get_domain(self, domain: Optional[str]) -> DatabaseDomainSettings:
        """Return configured domain metadata (default when domain is None)."""

        if domain:
            entry = self.supabase_domains.get(domain.lower())
            if entry:
                return entry
            raise ValueError(f"알 수 없는 도메인입니다: {domain}")

        if not self.supabase_db_url:
            if self.supabase_domains:
                first_key = sorted(self.supabase_domains)[0]
                return self.supabase_domains[first_key]
            raise ValueError(
                "기본 도메인 정보를 찾을 수 없습니다. SUPABASE_DOMAIN_CONFIG 에서 domain을 명시하세요."
            )

        return DatabaseDomainSettings(
            domain="default",
            schema=self.supabase_schema_name,
            connection_uri=self.supabase_db_url,
            description="기본 연결",
        )

    def describe_domains(self) -> Optional[str]:
        """Render a human-readable summary for prompt conditioning."""

        lines = []
        for key in sorted(self.supabase_domains):
            info = self.supabase_domains[key]
            snippet = info.description or ""
            lines.append(
                f"- {info.domain}: schema `{info.schema}`{f' — {snippet}' if snippet else ''}"
            )

        if not lines and self.supabase_db_url:
            lines.append(
                f"- default: schema `{self.supabase_schema_name}` (기본 연결)"
            )

        if not lines:
            return None

        header = "도메인별 기본 스키마 정보"
        return header + "\n" + "\n".join(lines)

    def get_knowledge_domain(self) -> Optional[DatabaseDomainSettings]:
        """Return DB settings for the knowledge vector table, if configured."""

        if not self.knowledge_table:
            return None

        return self.get_domain(self.knowledge_domain)


@lru_cache(maxsize=1)
def load_settings() -> AgentSettings:
    """Load settings once, allowing other modules to import without side effects."""

    load_dotenv()
    settings = AgentSettings()
    settings.validate()
    return settings
