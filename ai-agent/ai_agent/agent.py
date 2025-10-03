"""LangChain agent that routes prompts to the OpenAI Chat Completions API."""

from __future__ import annotations

from typing import Iterable, List, Mapping, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .settings import AgentSettings, load_settings

DEFAULT_SYSTEM_PROMPT = (
    "당신은 데이터 검증과 품질 관리 업무를 돕는 전문 AI 에이전트입니다. "
    "사용자가 제시하는 데이터 규칙, 검증 절차, 오류 사례에 대해 명확하고 단계적인 답변을 제공합니다. "
    "결과를 설명할 때에는 필요한 경우 표나 목록을 활용하고, 추가 확인이 필요한 부분은 주의사항으로 언급하세요."
)


def _convert_history(messages: Optional[Iterable[Mapping[str, str]]]) -> List[BaseMessage]:
    """Convert lightweight history dictionaries into LangChain message objects."""

    if not messages:
        return []

    role_map = {
        "user": HumanMessage,
        "assistant": AIMessage,
        "system": SystemMessage,
    }

    converted: List[BaseMessage] = []
    for item in messages:
        role = item.get("role")
        content = item.get("content", "")
        message_cls = role_map.get(role)
        if not message_cls or not content:
            continue
        converted.append(message_cls(content=content))
    return converted


def build_agent_chain(settings: Optional[AgentSettings] = None):
    """Build a LangChain runnable sequence for the data verification agent."""

    cfg = settings or load_settings()

    llm = ChatOpenAI(
        model=cfg.model,
        temperature=cfg.temperature,
        openai_api_key=cfg.openai_api_key,
        openai_api_base=cfg.openai_api_base,
        timeout=cfg.request_timeout,
        # max_output_tokens=cfg.max_output_tokens,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=DEFAULT_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history", optional=True),
            ("human", "{input}"),
        ]
    )

    return prompt | llm | StrOutputParser()


def run_agent(
    prompt: str,
    *,
    history: Optional[Sequence[Mapping[str, str]]] = None,
    settings: Optional[AgentSettings] = None,
) -> str:
    """Execute the agent and return the assistant's reply as plain text."""

    if not prompt or not prompt.strip():
        raise ValueError("프롬프트가 비어 있습니다.")

    runnable = build_agent_chain(settings=settings)
    formatted_history = _convert_history(history)

    return runnable.invoke({"input": prompt.strip(), "history": formatted_history})
