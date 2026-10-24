"""依赖注入：应用级单例（graph / agents / llm），避免每个请求重建。"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from graph import build_graph


@lru_cache(maxsize=1)
def get_graph():
    """构建并缓存 (compiled_graph, agents, llm)。"""
    return build_graph()


def get_app_graph():
    return get_graph()[0]


def get_agents() -> dict[str, Any]:
    return get_graph()[1]


def get_llm():
    return get_graph()[2]


def get_mode() -> str:
    return "llm" if get_llm() is not None else "rule"
