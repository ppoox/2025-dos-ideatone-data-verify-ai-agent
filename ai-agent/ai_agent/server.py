"""FastAPI wrapper around the LangChain data verification agent."""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from .agent import run_agent
from .settings import load_settings

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


@app.post("/api/agent/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    try:
        settings = load_settings()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        reply = run_agent(
            payload.prompt, history=payload.history, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail="Agent execution failed") from exc

    return ChatResponse(reply=reply)
