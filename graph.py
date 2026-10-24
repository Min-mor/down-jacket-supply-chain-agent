"""LangGraph 编排层（LLM 增强版）。

路由与 Agent 执行分两级：
- Router：优先用 LLM 做意图分类（结构化输出），解析失败或未配置 Key 时
  自动降级到关键词打分。
- Agent 节点：配置了 LLM 时用 create_react_agent 做「真 tool calling」
  （LLM 决定调用哪个工具 → ToolNode 执行 → 生成最终回答）；未配置 Key 时
  降级到确定性的 dispatch（内部仍走 LangChain @tool 协议）。

无论哪种模式，5 个 Agent 的知识库隔离、追问推荐机制都保持不变。
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph

from agents.agent_defs import _AGENT_ZONE_KEYWORDS, _match, create_agents
from llm import get_llm

AgentId = Literal["faq", "product", "procurement", "supplier", "order"]
AGENT_IDS: tuple[AgentId, ...] = ("faq", "product", "procurement", "supplier", "order")


class SupplyState(TypedDict):
    question: str        # 用户本轮问题
    agent_name: str      # 命中的 Agent 显示名
    agent_id: str        # 命中的 Agent 分区 id（faq/product/...）
    answer: str          # 该 Agent 的回答
    matched_key: str     # 匹配到的知识域关键词
    suggestions: list[str]  # 推荐的相关性问题
    history: list[tuple[str, str]]  # 历史问答（question, answer）


# =========================================================
# 路由：LLM 意图识别 + 关键词兜底
# =========================================================
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
    """规则路由（兜底）：先查强信号词，再按关键词打分选最高分区。"""
    ql = question
    for kw, zone in STRONG_ROUTE.items():
        if kw in ql:
            return zone
    scores: dict[str, int] = {}
    for zone, kws in _AGENT_ZONE_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in ql)
        scores[zone] = score
    best = max(scores, key=lambda z: scores[z])
    return best if scores[best] > 0 else "faq"


def make_llm_router(llm):
    """构造 LLM 意图识别路由；无 LLM 时退化为规则路由。"""
    from pydantic import BaseModel, Field

    class RouteIntent(BaseModel):
        agent_id: AgentId = Field(
            description="把用户问题归类到最合适的员工：faq=售前售后咨询, "
                        "product=款式/价格/库存, procurement=采购制度, "
                        "supplier=供应商, order=下单审批"
        )

    structured = llm.with_structured_output(RouteIntent) if llm else None

    def llm_route(question: str) -> str:
        if structured is None:
            return route_question(question)
        try:
            intent = structured.invoke(question)
            zone = intent.agent_id
            return zone if zone in AGENT_IDS else route_question(question)
        except Exception:  # noqa: BLE001 —— 解析失败/超时等一律降级
            return route_question(question)

    return llm_route


def make_router_node(route_fn):
    fn = RunnableLambda(lambda state: {"agent_name": route_fn(state["question"])})

    def router(state: SupplyState) -> dict[str, Any]:
        return fn.invoke(state)

    return router


# =========================================================
# Agent 节点：LLM tool calling / 规则 dispatch 双模式
# =========================================================
def _extract_answer(messages: list[Any]) -> str:
    """从 React 循环的消息里取最后的文本回答。"""
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
    if messages:
        return str(getattr(messages[-1], "content", ""))
    return "（无回复）"


def make_agent_node(agent, react_app=None):
    """react_app 为 None 时走规则 dispatch（无 Key 降级）。"""
    def node(state: SupplyState) -> dict[str, Any]:
        question = state["question"]
        history = state.get("history") or []
        if react_app is not None:
            # 多轮上下文：历史 + 当前问题一起喂给 LLM 工具调用图
            msgs = []
            for q, a in history:
                msgs.append(HumanMessage(content=q))
                if a:
                    from langchain_core.messages import AIMessage
                    msgs.append(AIMessage(content=a))
            msgs.append(HumanMessage(content=question))
            result = react_app.invoke({"messages": msgs})
            answer = _extract_answer(result.get("messages", []))
            key = _match(question, agent.zone)
        else:
            res = agent.dispatch(question)
            answer, key = res["answer"], res["matched_key"]
        return {
            "agent_name": agent.name,
            "agent_id": agent.zone,
            "answer": answer,
            "matched_key": key,
            "suggestions": agent.suggest(key),
        }
    return node


def build_graph():
    """构建并编译完整 StateGraph（LLM 增强 + 无 Key 自动降级）。"""
    agents = create_agents()
    llm = get_llm()
    route_fn = make_llm_router(llm)

    # 配置 Key 时，为每个 Agent 预建工具调用图（各自绑定自己的工具集）
    react_apps: dict[str, Any] = {}
    if llm is not None:
        for zone, agent in agents.items():
            react_apps[zone] = create_agent(llm, agent.tools)

    g = StateGraph(SupplyState)
    g.add_node("router", make_router_node(route_fn))
    for zone, agent in agents.items():
        g.add_node(zone, make_agent_node(agent, react_apps.get(zone)))

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        lambda state: state["agent_name"],
        {zone: zone for zone in agents},
    )
    for zone in agents:
        g.add_edge(zone, END)

    return g.compile(), agents, llm


def run_query(question: str) -> dict[str, Any]:
    """对外入口：给定问题，返回回答与推荐问题。"""
    app, _, _ = build_graph()
    result = app.invoke(
        {"question": question, "history": []},
        config={"recursion_limit": 10},
    )
    return result
