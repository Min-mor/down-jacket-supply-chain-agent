"""LangGraph 编排层。

- Router 节点：基于关键词打分，把用户问题路由到 5 个 Agent 之一。
- 每个 Agent 一个节点：调用该 Agent 的 dispatch（内部走 LangChain @tool 协议），
  并基于匹配域生成"接下来可以问"的相关性问题。
- StateGraph 有向图：router → 命中 Agent → END。

架构符合 LangChain/LangGraph 原生范式：State 驱动 + 条件路由 + 工具协议。
生产环境可将 Router 的规则打分替换为 LLM（如 ChatOpenAI）意图分类，
本工程为可离线运行、确定性的演示实现。
"""
from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from agents.agent_defs import _AGENT_ZONE_KEYWORDS, create_agents


class SupplyState(TypedDict):
    question: str        # 用户本轮问题
    agent_name: str      # 命中的 Agent
    answer: str          # 该 Agent 的回答
    matched_key: str     # 匹配到的知识域关键词
    suggestions: list[str]  # 推荐的相关性问题
    history: list[tuple[str, str]]  # 历史问答（question, answer）


# 高区分度强信号词：命中即直接路由，避免与弱关键词撞车
STRONG_ROUTE = {
    "供应商": "supplier",
    "采购单": "order",
    "下单": "order",
    "加急": "order",
    "取消采购": "order",
    "审批流": "order",
}


def route_question(question: str) -> str:
    """路由：先查强信号词，再按关键词打分选最高分区。"""
    ql = question
    for kw, zone in STRONG_ROUTE.items():
        if kw in ql:
            return zone
    scores: dict[str, int] = {}
    for zone, kws in _AGENT_ZONE_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in ql)
        scores[zone] = score
    best = max(scores, key=lambda z: scores[z])
    # 无命中（全为 0）时落到客服 FAQ，并提供帮助引导
    return best if scores[best] > 0 else "faq"


def make_router_node():
    fn = RunnableLambda(lambda state: {"agent_name": route_question(state["question"])})
    def router(state: SupplyState) -> dict[str, Any]:
        return fn.invoke(state)
    return router


def make_agent_node(agent):
    def node(state: SupplyState) -> dict[str, Any]:
        res = agent.dispatch(state["question"])
        suggestions = agent.suggest(res["matched_key"])
        return {
            "agent_name": agent.name,
            "answer": res["answer"],
            "matched_key": res["matched_key"],
            "suggestions": suggestions,
        }
    return node


def build_graph():
    """构建并编译完整 StateGraph。"""
    agents = create_agents()

    g = StateGraph(SupplyState)

    g.add_node("router", make_router_node())
    for zone, agent in agents.items():
        g.add_node(zone, make_agent_node(agent))

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        lambda state: state["agent_name"],
        {zone: zone for zone in agents},  # agent_name=zone 时路由到对应节点
    )
    for zone in agents:
        g.add_edge(zone, END)

    return g.compile(), agents


def run_query(question: str) -> dict[str, Any]:
    """对外入口：给定问题，返回回答与推荐问题。"""
    app, _ = build_graph()
    result = app.invoke(
        {"question": question, "history": []},
        config={"recursion_limit": 10},
    )
    return result
