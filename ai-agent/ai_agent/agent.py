"""LangChain agent that routes prompts to the OpenAI Chat Completions API."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from pathlib import Path
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from .knowledge import fetch_topic_block
from .schema import load_schema_summary
from .settings import AgentSettings, load_settings
from .tools import build_supabase_query_tool

logger = logging.getLogger("ai_agent.agent")

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = PACKAGE_ROOT / "sample"
CURRENT_YEAR = datetime.now().year

DEFAULT_SYSTEM_PROMPT = (
    "당신은 통신 청구 데이터 품질을 검증하는 전문 AI 에이전트입니다. "
    "사용자 요청에 따라 청구서 전수 검증과 개별 고객 청구서 분석을 수행하며, 발견된 이슈에 대한 근거와 후속 조치를 안내합니다.\n"
    "핵심 책임:\n"
    "1. 청구월이 주어지면 해당 월의 모든 청구서를 단계적으로 검증하고 누락된 맥락(도메인, 청구 주기 등)을 먼저 확인합니다.\n"
    "2. 고객번호(customer_id) 또는 고객명으로 특정 청구서를 지정하면 해당 청구서를 중심으로 심층 검증합니다.\n"
    "3. 비정상 데이터가 발견되면 동일/유사 패턴을 가진 추가 사례를 함께 제시해 원인 분석을 돕습니다.\n"
    "4. 데이터를 직접 수정하지 않고, 사용자가 보정용 SQL 템플릿 요청 시 실행은 별도 승인 절차가 필요하니 제안만 결과로 설명하되 실행은 하지 않습니다.\n"
    "항상 SELECT 기반 조회만 사용하며, 검증 단계·근거·판단 기준을 명확히 설명하세요. 결과를 설명할 때에는 표나 목록을 활용하고, 추가 확인이 필요한 부분은 주의사항으로 언급하세요."
    f"사용자가 날짜를 제시하지 않는 경우 답변은 항상 최신 날짜를 기준으로 제공해주세요. 예를들면 9월이라고만 언급한 경우 {CURRENT_YEAR}년을 9월 기준으로 답변을 제공해주세요."
    "사용월은 실제 고객이 사용한 월을 기준으로하며 청구월은 사용한 기간의 익월을 의미합니다."
    "고객 정보는 고객 도메인에 연결된 DB에 존재하며 청구 정보는 청구 도메인에 연결된 DB에 저장되어있어 사용자의 요청에 따라 구분하여 데이터를 조회해야합니다.."
    "테이블 alias를 정의한 뒤에만 컬럼에 사용하고 enum 값은 대문자로 작성합니다."
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

    if cfg.supabase_db_url or cfg.supabase_domains:
        tools.append(build_supabase_query_tool(cfg))

    return tools


def _build_system_prompt(cfg: AgentSettings) -> str:
    sections: List[str] = [DEFAULT_SYSTEM_PROMPT]

    if cfg.supabase_db_url or cfg.supabase_domains:
        tool_guidance = (
            "데이터 품질 관련 질문에 답할 때에는 `query_supabase_sql` 툴을 사용해 최신 데이터를 확인하세요. "
            "툴 호출 시 `domain` 또는 `schema` 파라미터를 지정하면 도메인별 스키마를 정확히 조회할 수 있습니다. "
            "조회 결과를 그대로 나열하기보다는 규칙과 데이터 간의 관계를 분석하여 설명하세요."
        )
        sections.append(tool_guidance)

        domain_summary = cfg.describe_domains()
        if domain_summary:
            sections.append(
                "다음 도메인 구성을 참고해 적절한 스키마를 선택하세요:\n" + domain_summary
            )

    schema = _resolve_prompt_section(
        cfg,
        inline_text=cfg.supabase_schema_summary,
        file_path=cfg.supabase_schema_summary_path,
        label="SUPABASE_SCHEMA_SUMMARY",
        topic="schema_summary",
        query_hint="통신 청구 데이터베이스 스키마 요약",
    )
    if (not schema) and cfg.supabase_db_url and cfg.supabase_schema_autoload:
        schema = _load_autoschema_summary(cfg)
    if not schema:
        schema = _load_default_resource("schema.md")
    if schema:
        sections.append("다음은 주요 테이블 및 칼럼 요약입니다:\n" + schema)

    guidelines = _resolve_prompt_section(
        cfg,
        inline_text=cfg.validation_guidelines,
        file_path=cfg.validation_guidelines_path,
        label="DATA_VALIDATION_GUIDELINES",
        topic="validation_guidelines",
        query_hint="청구 데이터 검증 절차와 핵심 점검 항목",
        fallback_filename="validation.txt",
    )
    if guidelines:
        sections.append("다음 검증 절차를 반드시 참고하세요:\n" + guidelines)

    glossary = _resolve_prompt_section(
        cfg,
        inline_text=cfg.data_glossary,
        file_path=cfg.data_glossary_path,
        label="DATA_GLOSSARY",
        topic="data_glossary",
        query_hint="청구/요금 데이터 용어 정의와 약어 해설",
        fallback_filename="glossary.md",
    )
    if glossary:
        sections.append("용어집/자료사전:\n" + glossary)

    sections.append(
        "모든 답변의 마지막에는 수행한 검증 단계와 추가 확인이 필요한 항목을 bullet 목록으로 정리하세요."
    )

    return "\n\n".join(section for section in sections if section)


def _resolve_prompt_section(
    cfg: AgentSettings,
    *,
    inline_text: Optional[str],
    file_path: Optional[str],
    label: str,
    topic: Optional[str] = None,
    query_hint: Optional[str] = None,
    fallback_filename: Optional[str] = None,
) -> Optional[str]:
    if inline_text and inline_text.strip():
        return inline_text.strip()

    knowledge: Optional[str] = None
    if topic:
        try:
            knowledge = fetch_topic_block(
                cfg,
                topic=topic,
                query_hint=query_hint,
                limit=cfg.knowledge_top_k,
            )
        except Exception as exc:  # noqa: BLE001 - 로깅 후 폴백 사용
            logger.warning("지식 기반 로딩 실패 (%s): %s", topic, exc)
            knowledge = None
    if knowledge:
        return knowledge

    if file_path and file_path.strip():
        try:
            text = Path(file_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"{label} 파일을 읽지 못했습니다: {file_path}") from exc
        return text or None

    if fallback_filename:
        return _load_default_resource(fallback_filename)

    return None


def _load_autoschema_summary(cfg: AgentSettings) -> Optional[str]:
    try:
        summary = load_schema_summary(
            cfg.supabase_db_url,
            schema=cfg.supabase_schema_name,
            max_tables=cfg.supabase_schema_max_tables,
            max_columns=cfg.supabase_schema_max_columns,
            include_views=cfg.supabase_schema_include_views,
        )
    except Exception as exc:  # noqa: BLE001 - 로깅 후 무시
        logger.warning("Supabase 스키마 자동 로딩 실패: %s", exc)
        return None

    return summary.strip() or None


def _load_default_resource(filename: str) -> Optional[str]:
    path = RESOURCE_DIR / filename
    if not path.exists():
        return None

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # noqa: BLE001 - 로깅 후 무시
        logger.warning("기본 리소스(%s)를 읽지 못했습니다: %s", filename, exc)
        return None

    cleaned = text.strip()
    return cleaned or None


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
