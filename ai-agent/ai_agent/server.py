"""FastAPI wrapper around the LangChain data verification agent."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from .agent import run_agent
from .settings import load_settings

logger = logging.getLogger("ai_agent.server")

_level_value = os.getenv("AGENT_LOG_LEVEL", "INFO")
try:
    _level = int(_level_value)
except ValueError:
    _level = getattr(logging, _level_value.upper(), logging.INFO)

logger.setLevel(_level)
logger.propagate = True

_log_file = os.getenv("AGENT_LOG_FILE")
if _log_file:
    log_path = Path(_log_file).expanduser()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(_level)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)
    except OSError as exc:
        logging.getLogger("uvicorn.error").warning(
            "Failed to attach agent log file %s: %s", log_path, exc
        )

app = FastAPI(title="Data Verification Agent")

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., description="사용자가 입력한 프롬프트")
    history: Optional[List[dict[str, Any]]] = Field(
        default=None,
        description="이전 대화 메시지 배열. 각 항목은 role/content 키를 포함합니다.",
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="에이전트의 답변")
    intermediate_steps: Optional[List[Any]] = Field(
        default=None,
        description="툴 호출 로그. 디버그 목적일 때만 채워집니다.",
    )


@app.post("/api/agent/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    try:
        settings = load_settings()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        logger.info("[agent] prompt=%s", payload.prompt)
        reply = run_agent(
            payload.prompt,
            history=payload.history,
            settings=settings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent execution failed")
        raise HTTPException(
            status_code=500, detail="Agent execution failed") from exc

    if isinstance(reply, dict):
        output = reply.get("output")
        steps = _serialize_intermediate_steps(reply.get("intermediate_steps"))
        if steps:
            for idx, step in enumerate(steps, start=1):
                tool = step.get("tool")
                tool_input = step.get("tool_input")
                observation = step.get("observation")
                if tool_input:
                    print(tool_input['sql'])
                logger.info(
                    "[agent] step=%s tool=%s input=%s observation=%s",
                    idx,
                    tool,
                    tool_input,
                    observation,
                )
        logger.info("[agent] reply=%s", output)
        return ChatResponse(reply=str(output or ""), intermediate_steps=steps)

    logger.info("[agent] reply=%s", reply)
    return ChatResponse(reply=reply)


def _serialize_intermediate_steps(steps: Any) -> List[Any]:
    if not steps:
        return []

    serialized: List[Any] = []
    for item in steps:
        try:
            action, observation = item
        except (TypeError, ValueError):
            serialized.append(str(item))
            continue

        entry: dict[str, Any] = {
            "observation": observation,
        }

        if getattr(action, "tool", None):
            entry["tool"] = action.tool
        if getattr(action, "tool_input", None):
            entry["tool_input"] = action.tool_input
        if getattr(action, "log", None):
            entry["log"] = action.log

        serialized.append(entry)

    return serialized
