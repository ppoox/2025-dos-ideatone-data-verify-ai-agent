"""LangChain agent that routes prompts to the OpenAI Chat Completions API."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from pathlib import Path
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from .settings import AgentSettings, load_settings
from .tools import build_supabase_query_tool

DEFAULT_SYSTEM_PROMPT = (
    "당신은 데이터 검증과 품질 관리 업무를 돕는 전문 AI 에이전트입니다. "
    "사용자가 제시하는 데이터 규칙, 검증 절차, 오류 사례에 대해 명확하고 단계적인 답변을 제공합니다. "
    "결과를 설명할 때에는 필요한 경우 표나 목록을 활용하고, 추가 확인이 필요한 부분은 주의사항으로 언급하세요."
    "사용자가 날짜를 제시하지 않는 경우 답변은 항상 최신 날짜를 기준으로 제공해주세요. 예를들면 9월이라고 언급한 경우 2025년을 9월 기준으로 답변을 제공해주세요."
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


def build_agent_chain(
    settings: Optional[AgentSettings] = None,
    *,
    return_intermediate_steps: bool = False,
):
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

    tools = _build_tools(cfg)
    system_prompt = _build_system_prompt(cfg)

    require_steps = return_intermediate_steps or cfg.return_intermediate_steps

    if tools:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=system_prompt),
                MessagesPlaceholder(
                    variable_name="chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_openai_tools_agent(llm, tools, prompt)
        return AgentExecutor(
            agent=agent,
            tools=tools,
            return_intermediate_steps=require_steps,
        )

    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
        ]
    )

    return prompt | llm | StrOutputParser()


def _build_tools(cfg: AgentSettings) -> List[BaseTool]:
    tools: List[BaseTool] = []

    if cfg.supabase_db_url:
        tools.append(
            build_supabase_query_tool(
                cfg.supabase_db_url,
                default_limit=cfg.supabase_default_limit,
            )
        )

    return tools


def _build_system_prompt(cfg: AgentSettings) -> str:
    sections: List[str] = [DEFAULT_SYSTEM_PROMPT]

    if cfg.supabase_db_url:
        sections.append(
            "데이터 품질 관련 질문에 답할 때 데이터베이스 조회가 필요하면 반드시 `query_supabase_sql` 툴을 호출하여 최신 정보를 확인하세요. "
            "조회 결과를 그대로 복사하지 말고 규칙과 데이터 간의 관계를 분석해 설명하세요."
        )

    schema = _resolve_prompt_section(
        cfg.supabase_schema_summary,
        cfg.supabase_schema_summary_path,
        "SUPABASE_SCHEMA_SUMMARY",
    )
    if schema:
        sections.append("다음은 주요 테이블 및 칼럼 요약입니다:\n" + schema)

    guidelines = _resolve_prompt_section(
        cfg.validation_guidelines,
        cfg.validation_guidelines_path,
        "DATA_VALIDATION_GUIDELINES",
    )
    if guidelines:
        sections.append("다음 검증 절차를 반드시 참고하세요:\n" + guidelines)

    sections.append(
        "모든 답변의 마지막에는 수행한 검증 단계와 추가 확인이 필요한 항목을 bullet 목록으로 정리하세요."
    )

    return "\n\n".join(section for section in sections if section)


def _resolve_prompt_section(
    inline_text: Optional[str],
    file_path: Optional[str],
    label: str,
) -> Optional[str]:
    if inline_text and inline_text.strip():
        return inline_text.strip()

    if file_path and file_path.strip():
        try:
            text = Path(file_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"{label} 파일을 읽지 못했습니다: {file_path}") from exc
        return text or None

    return None


def _extract_output_text(result: Any) -> str:
    if isinstance(result, dict):
        output = result.get("output")
        if isinstance(output, str):
            return output
        if output is not None:
            return str(output)
        return ""

    if isinstance(result, str):
        return result

    return str(result)


def run_agent(
    prompt: str,
    *,
    history: Optional[Sequence[Mapping[str, str]]] = None,
    settings: Optional[AgentSettings] = None,
    include_steps: bool = False,
) -> Union[str, Dict[str, Any]]:
    """Execute the agent and return the assistant's reply as plain text."""

    if not prompt or not prompt.strip():
        raise ValueError("프롬프트가 비어 있습니다.")

    cfg = settings or load_settings()

    runnable = build_agent_chain(
        settings=cfg,
        return_intermediate_steps=include_steps,
    )
    formatted_history = _convert_history(history)

    inputs = {"input": prompt.strip(), "chat_history": formatted_history}
    result = runnable.invoke(inputs)

    want_steps = include_steps or cfg.return_intermediate_steps

    if want_steps:
        if isinstance(result, dict) and "intermediate_steps" in result:
            return result
        return {
            "output": _extract_output_text(result),
            "intermediate_steps": [],
        }

    return _extract_output_text(result)
