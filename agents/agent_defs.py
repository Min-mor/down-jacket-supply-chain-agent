"""5 个角色 Agent 定义。

每个 Agent 拥有：独立的隔离知识库（kb）、绑定该知识库的工具集（tools）、
专属的追问推荐器（suggestion_provider）。Agent 之间不共享任何知识来源。

dispatch(question)：在 Agent 内部按关键词选择最合适的工具并执行，
返回 (answer, matched_key, tool_used)。
"""
from __future__ import annotations

from typing import Any

from .knowledge_base import KnowledgeBase, create_all_bases
from .suggestions import SuggestionProvider
from . import tools as tool_lib


class SupplyChainAgent:
    def __init__(
        self,
        name: str,
        role: str,
        zone: str,
        kb: KnowledgeBase,
        tools: list[Any],
        dispatch_impl: Any,
        suggestion_provider: SuggestionProvider,
    ):
        self.name = name
        self.role = role
        self.zone = zone
        self.kb = kb
        self.tools = tools
        self.tool_map = {t.name: t for t in tools}
        self._dispatch = dispatch_impl
        self.suggestion_provider = suggestion_provider

    def dispatch(self, question: str) -> dict[str, Any]:
        """在 Agent 内部路由到具体工具并执行。"""
        return self._dispatch(self, question)

    def suggest(self, matched_key: str | None = None, limit: int = 3) -> list[str]:
        return self.suggestion_provider.suggest(matched_key, limit)

    @property
    def meta(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "zone": self.zone,
            "knowledge": self.kb.meta,
            "tools": list(self.tool_map.keys()),
        }


# ---------- 各 Agent 的 dispatch 实现 ----------

def _faq_dispatch(agent: SupplyChainAgent, q: str) -> dict[str, Any]:
    key = _match(q, agent.zone)
    # 用完整问题做语义检索；matched_key 仍用域关键词，保证追问推荐不跳域
    res = _run_tool(agent, "search_faq", q)
    res["matched_key"] = key
    return res


def _product_dispatch(agent: SupplyChainAgent, q: str) -> dict[str, Any]:
    ql = q
    if "最低" in ql or "最便宜" in ql or "性价比" in ql:
        return _run_tool(agent, "best_price", "最低")
    if "最高" in ql or "最贵" in ql:
        return _run_tool(agent, "best_price", "最高")
    if "库存" in ql or "还有多少" in ql or "仓库" in ql:
        return _run_tool(agent, "check_inventory", _extract_style(ql))
    if "批发" in ql or "成本" in ql or "价格" in ql or "报价" in ql or "多少钱" in ql:
        return _run_tool(agent, "get_price", _extract_style(ql))
    if "DJ-" in ql.upper():
        return _run_tool(agent, "lookup_product", _extract_style(ql))
    return _run_tool(agent, "search_products", _match(ql, agent.zone))


def _procurement_dispatch(agent: SupplyChainAgent, q: str) -> dict[str, Any]:
    ql = q
    if "审批" in ql or "金额" in ql or "权限" in ql or "谁批" in ql:
        amount = _extract_amount(ql)
        return _run_tool(agent, "get_approval_rule", amount)
    if "付款" in ql or "账期" in ql or "定金" in ql or "尾款" in ql:
        return _run_tool(agent, "get_payment_rule", "new" if "新供应商" in ql else "regular")
    if "折扣" in ql or "几折" in ql or "件" in ql:
        return _run_tool(agent, "get_discount", _extract_quantity(ql))
    if "返利" in ql or "返点" in ql:
        return _run_tool(agent, "get_rebate", "")
    return _run_tool(agent, "get_procurement_flow", "")


def _supplier_dispatch(agent: SupplyChainAgent, q: str) -> dict[str, Any]:
    ql = q
    if "资质" in ql and ("标准" in ql or "评级" in ql or "怎么分" in ql):
        return _run_tool(agent, "get_qualification_levels", "")
    name = _match_supplier_name(ql)
    if name:
        return _run_tool(agent, "get_supplier", name)
    # 提取更具体的类别关键词，命中则按类别检索
    for cat in ("羽绒供应商", "面料供应商", "辅料供应商", "代工厂", "包装供应商",
                "羽绒", "面料", "辅料", "代工", "包装"):
        if cat in ql:
            return _run_tool(agent, "search_suppliers", cat)
    return _run_tool(agent, "search_suppliers", "供应商")


def _order_dispatch(agent: SupplyChainAgent, q: str) -> dict[str, Any]:
    ql = q
    if "所有" in ql or "全部" in ql or "有哪些" in ql:
        return _run_tool(agent, "list_order_rules", "")
    return _run_tool(agent, "get_order_rule", _match(ql, agent.zone))


# ---------- 工具执行辅助 ----------
def _run_tool(agent: SupplyChainAgent, tool_name: str, arg: Any) -> dict[str, Any]:
    fn = agent.tool_map.get(tool_name)
    if fn is None:
        return {"answer": f"[{agent.name}] 工具不存在: {tool_name}", "matched_key": None, "tool": tool_name}
    try:
        # 无参工具传空 dict；单参工具按参数名传 kwargs（符合 LangChain 工具协议，
        # 对 str/float/int 等类型都稳定）
        schema = getattr(fn, "args_schema", None)
        fields = getattr(schema, "model_fields", None) or {}
        if not fields:
            kwargs: dict[str, Any] = {}
        else:
            first_field = next(iter(fields))
            kwargs = {first_field: arg}
        result = fn.invoke(kwargs)
        if hasattr(result, "content"):
            result = result.content
    except Exception as exc:  # noqa: BLE001
        result = f"[{agent.name}] 执行失败: {exc}"
    return {"answer": str(result), "matched_key": _key_of(agent.zone, str(arg)), "tool": tool_name}


# ---------- 关键词与参数提取 ----------
_AGENT_ZONE_KEYWORDS = {
    "faq": ["尺码", "清洗", "保养", "发货", "退换", "售后", "钻绒", "质量问题", "怎么选"],
    "product": ["价格", "成本", "批发", "库存", "仓库", "款式", "DJ-", "羽绒", "充绒", "在售",
                "鹅绒", "鸭绒", "长款", "短款", "面包服", "派克服", "轻暖", "保暖", "轻薄"],
    "procurement": ["采购", "审批", "付款", "折扣", "返利", "起订", "流程", "账期", "制度"],
    "supplier": ["供应商", "资质", "代工", "面料", "辅料", "账期", "合作"],
    "order": ["下单", "采购单", "加急", "修改", "取消", "审批流", "提交"],
}


def _match(question: str, zone: str) -> str:
    """返回与 zone 关键词匹配到的第一个关键词，用于后续问题推荐与工具参数。"""
    for kw in _AGENT_ZONE_KEYWORDS.get(zone, []):
        if kw in question:
            return kw
    return "默认"


def _extract_style(question: str) -> str:
    up = question.upper()
    idx = up.find("DJ-")
    if idx == -1:
        return "DJ-2601"
    return up[idx: idx + 7]


def _extract_amount(question: str) -> float:
    import re
    nums = re.findall(r"\d+(?:\.\d+)?", question)
    if not nums:
        return 10000.0
    val = float(nums[0])
    # 中文金额单位：万 → ×10000，千 → ×1000
    if "万" in question:
        val *= 10000
    elif "千" in question:
        val *= 1000
    return val


def _extract_quantity(question: str) -> int:
    import re
    nums = re.findall(r"\d+", question)
    return int(nums[0]) if nums else 1000


def _key_of(zone: str, arg: str) -> str:
    return arg if arg and arg != "默认" else "默认"


def _match_supplier_name(question: str) -> str | None:
    from .knowledge_base import create_all_bases
    suppliers = create_all_bases()["supplier"].get("suppliers", [])
    for s in suppliers:
        if s["name"] in question:
            return s["name"]
    return None


# ---------- Agent 工厂 ----------
def create_agents() -> dict[str, SupplyChainAgent]:
    bases = create_all_bases()
    agents: dict[str, SupplyChainAgent] = {}

    agents["faq"] = SupplyChainAgent(
        name="客服FAQ助手",
        role="售前售后咨询",
        zone="faq",
        kb=bases["faq"],
        tools=tool_lib.build_faq_tools(bases["faq"]),
        dispatch_impl=_faq_dispatch,
        suggestion_provider=SuggestionProvider("faq"),
    )
    agents["product"] = SupplyChainAgent(
        name="商品价格库存助手",
        role="款式/价格/库存查询",
        zone="product",
        kb=bases["product"],
        tools=tool_lib.build_product_tools(bases["product"]),
        dispatch_impl=_product_dispatch,
        suggestion_provider=SuggestionProvider("product"),
    )
    agents["procurement"] = SupplyChainAgent(
        name="采购制度助手",
        role="采购流程/审批/付款制度",
        zone="procurement",
        kb=bases["procurement"],
        tools=tool_lib.build_procurement_tools(bases["procurement"]),
        dispatch_impl=_procurement_dispatch,
        suggestion_provider=SuggestionProvider("procurement"),
    )
    agents["supplier"] = SupplyChainAgent(
        name="供应商管理助手",
        role="供应商名录/资质",
        zone="supplier",
        kb=bases["supplier"],
        tools=tool_lib.build_supplier_tools(bases["supplier"]),
        dispatch_impl=_supplier_dispatch,
        suggestion_provider=SuggestionProvider("supplier"),
    )
    agents["order"] = SupplyChainAgent(
        name="下单审批助手",
        role="采购单生成/审批流",
        zone="order",
        kb=bases["order"],
        tools=tool_lib.build_order_tools(bases["order"]),
        dispatch_impl=_order_dispatch,
        suggestion_provider=SuggestionProvider("order"),
    )
    return agents
