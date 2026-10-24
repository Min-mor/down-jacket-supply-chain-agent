"""LLM 配置层。

统一从 core.config.Settings（环境变量 / .env）读取 DeepSeek 配置，创建
LangChain ChatOpenAI 客户端。未配置 DEEPSEEK_API_KEY 时返回 None，上层
据此降级到规则路由（可离线运行）。
"""
from __future__ import annotations

from core.config import settings


def has_key() -> bool:
    return bool(settings.deepseek_api_key)


def get_llm():
    """返回配置好的 ChatOpenAI（DeepSeek 兼容接口）；无 Key 时返回 None。"""
    if not has_key():
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        api_key=settings.deepseek_api_key,
        temperature=0,
        max_tokens=600,
    )
