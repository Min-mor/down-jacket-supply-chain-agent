"""API 安全层：CORS、限流、输入校验、提示注入防护、网关令牌。"""
from __future__ import annotations

import time

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.logging import log


# ---------- 提示注入防护（轻量启发式；生产建议接入专用护栏模型） ----------
_INJECTION_MARKERS = [
    "忽略", "无视", "不用管", "忘记", "覆盖", "改掉", "当作", "假装你是",
    "system prompt", "system_prompt", "提示词", "系统指令", "角色扮演",
    "ignore previous", "disregard", "you are now", "act as",
]


def injection_risk(text: str) -> str | None:
    """检测明显的提示注入意图；命中返回风险描述，否则 None。"""
    low = text.lower()
    for marker in _INJECTION_MARKERS:
        if marker in text or marker in low:
            return f"检测到疑似提示注入特征：{marker}"
    return None


def validate_input(question: str) -> str:
    """校验并规范化输入；不合法抛 HTTPException。"""
    q = (question or "").strip()
    if not q:
        raise HTTPException(status_code=422, detail="问题不能为空")
    if len(q) > 1000:
        raise HTTPException(status_code=422, detail="问题过长（>1000 字符）")
    risk = injection_risk(q)
    if risk:
        log.warning("prompt_injection_blocked: %s", risk)
        raise HTTPException(status_code=400, detail="输入包含不被允许的内容，请正常提问")
    # 去除不可见控制字符，避免日志/存储污染
    q = "".join(ch for ch in q if ch.isprintable() or ch in "\n\t")
    return q


# ---------- 网关令牌（可选） ----------
def check_api_token(request: Request) -> None:
    if settings.api_token:
        provided = request.headers.get("X-API-Token", "")
        if provided != settings.api_token:
            raise HTTPException(status_code=401, detail="Unauthorized")


# ---------- 限流（单进程内存滑动窗口；多实例生产用 Redis） ----------
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, per_minute: int | None = None):
        super().__init__(app)
        self.per_minute = per_minute if per_minute is not None else settings.rate_limit_per_minute
        self._hits: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        if self.per_minute > 0:
            ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "?")
            ip = ip.split(",")[0].strip()
            now = time.time()
            window = self._hits.setdefault(ip, [])
            cutoff = now - 60
            window[:] = [t for t in window if t > cutoff]
            if len(window) >= self.per_minute:
                log.warning("rate_limited ip=%s", ip)
                raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
            window.append(now)
        return await call_next(request)


# ---------- CORS ----------
def setup_cors(app) -> None:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
