"""Configuration helpers for the LangChain-based data verification agent."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field


def _getenv_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


class AgentSettings(BaseModel):
    """Runtime configuration loaded from environment variables."""

    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_api_base: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    )
    model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
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
    validation_guidelines: Optional[str] = Field(
        default_factory=lambda: os.getenv("DATA_VALIDATION_GUIDELINES")
    )
    validation_guidelines_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("DATA_VALIDATION_GUIDELINES_PATH")
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


@lru_cache(maxsize=1)
def load_settings() -> AgentSettings:
    """Load settings once, allowing other modules to import without side effects."""

    load_dotenv()
    settings = AgentSettings()
    settings.validate()
    return settings
