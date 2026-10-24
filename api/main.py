"""FastAPI 服务入口。

端点：
  GET  /healthz         存活探针
  GET  /readyz          就绪探针（含数据库检查）
  GET  {prefix}/agents   员工列表
  POST {prefix}/chat     会话问答（含多轮记忆与落库）

运行：uvicorn api.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.config import settings
from core.db import get_session, init_db
from core.logging import log, set_request_id
from core.memory import append_turn, get_or_create_conversation, load_history

from .deps import get_agents, get_app_graph, get_mode
from .schemas import AgentInfo, ChatRequest, ChatResponse, HealthResponse
from .security import RateLimitMiddleware, check_api_token, setup_cors, validate_input


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    log.info("startup mode=%s env=%s", get_mode(), settings.env)
    yield
    log.info("shutdown")


app = FastAPI(
    title="女装羽绒服供应链智能体",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

setup_cors(app)
app.add_middleware(RateLimitMiddleware)
init_db()  # 幂等建表，保证服务一启动即可用


@app.middleware("http")
async def request_context(request: Request, call_next):
    """为每个请求注入 request_id，并记录访问日志（异常时也能记录）。"""
    set_request_id(request.headers.get("X-Request-Id") or str(uuid.uuid4())[:12])
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        status = getattr(response, "status_code", None) or (500 if response is None else "?")
        log.info("http %s %s -> %s", request.method, request.url.path, status)


@app.get("/healthz", response_model=HealthResponse, tags=["ops"])
def healthz():
    return HealthResponse(status="ok", env=settings.env, mode=get_mode(), model=settings.deepseek_model if get_mode() == "llm" else "")


@app.get("/readyz", tags=["ops"])
def readyz(db: Session = Depends(get_session)):
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "unready", "detail": str(exc)})


@app.get(f"{settings.api_prefix}/agents", response_model=list[AgentInfo], tags=["agents"])
def list_agents(_: None = Depends(check_api_token)):
    return [AgentInfo(id=a.zone, name=a.name, role=a.role, tools=list(a.tool_map.keys()))
            for a in get_agents().values()]


@app.post(f"{settings.api_prefix}/chat", response_model=ChatResponse, tags=["chat"])
def chat(req: ChatRequest, request: Request, db: Session = Depends(get_session)):
    _ = request  # 供鉴权/限流链路扩展
    question = validate_input(req.question)

    conv = get_or_create_conversation(db, req.session_id)
    history = load_history(db, conv.id)

    result = get_app_graph().invoke(
        {"question": question, "history": history},
        config={"recursion_limit": 10},
    )
    answer = result["answer"]
    append_turn(db, conv.id, question, answer, result["agent_name"])

    log.info("chat session=%s agent=%s q_len=%d", conv.id[:8], result["agent_name"], len(question))
    return ChatResponse(
        session_id=conv.id,
        agent=result["agent_id"],
        agent_name=result["agent_name"],
        answer=answer,
        suggestions=result.get("suggestions", []),
    )
