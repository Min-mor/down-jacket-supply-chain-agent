"""API 请求/响应模型。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000, description="用户问题")
    session_id: Optional[str] = Field(default=None, max_length=64, description="会话 ID，缺省则新建")


class ChatResponse(BaseModel):
    session_id: str
    agent: str
    agent_name: str
    answer: str
    suggestions: list[str] = Field(default_factory=list)


class AgentInfo(BaseModel):
    id: str
    name: str
    role: str
    tools: list[str]


class HealthResponse(BaseModel):
    status: str
    env: str
    mode: str
    model: str = ""
