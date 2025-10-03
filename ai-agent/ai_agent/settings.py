"""Configuration helpers for the LangChain-based data verification agent."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field


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

    def validate(self) -> None:
        """Ensure critical values are present."""

        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되어야 합니다.")


@lru_cache(maxsize=1)
def load_settings() -> AgentSettings:
    """Load settings once, allowing other modules to import without side effects."""

    load_dotenv()
    settings = AgentSettings()
    settings.validate()
    return settings
