"""LLM 配置层。

从环境变量读取 DeepSeek 配置，创建 LangChain ChatOpenAI 客户端。
未配置 DEEPSEEK_API_KEY 时返回 None，上层据此降级到规则路由（可离线运行）。
"""
from __future__ import annotations

import os

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()


def has_key() -> bool:
    return bool(DEEPSEEK_API_KEY)


def get_llm():
    """返回配置好的 ChatOpenAI（DeepSeek 兼容接口）；无 Key 时返回 None。"""
    if not has_key():
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        base_url=DEEPSEEK_BASE_URL,
        api_key=DEEPSEEK_API_KEY,
        temperature=0,
        max_tokens=600,
    )
