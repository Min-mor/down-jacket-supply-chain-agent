"""5 个角色 Agent 的工具集。

每个工具通过闭包绑定到该角色自己的 KnowledgeBase，因此一个 Agent 只能
访问自己分区的知识，从工具层确保知识隔离、不交叉污染。

用 langchain_core.tools.tool 装饰器定义，符合 LangChain 工具协议。
"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from .knowledge_base import KnowledgeBase


# ---------- 客服 FAQ Agent ----------
_STOPWORDS = {
    "怎么", "什么", "的", "了", "吗", "呢", "吧", "啊", "应该", "可以", "请问",
    "我", "你", "他", "一下", "这个", "那个", "是", "有", "没有", "如何", "是否",
    "为什么", "多少", "能不能", "给", "要", "会", "就", "才", "都", "还", "在",
}


def _faq_score(question: str, faq: dict) -> int:
    """统计问题中 2~3 字子串在 FAQ（问题+分类+答案）中出现的次数，用于中文近似匹配。"""
    import re
    text = faq["question"] + faq.get("category", "") + faq["answer"]
    parts = re.split(r"[\s，。？！、,.!?：:；;()（）\"“”]+", question)
    score = 0
    for part in parts:
        if not part:
            continue
        for length in (3, 2):
            for i in range(len(part) - length + 1):
                sub = part[i:i + length]
                if sub in _STOPWORDS:
                    continue
                if sub in text:
                    score += 1
    return score


def build_faq_tools(kb: KnowledgeBase) -> list[Any]:
    @tool
    def search_faq(question: str) -> str:
        """在客服FAQ库中按问题语义检索最相关的常见问答。传入用户完整问题，如“身高170怎么选码”。"""
        faqs = kb.get("faq", [])
        scored = sorted(
            ((_faq_score(question, f), f) for f in faqs),
            key=lambda x: x[0],
            reverse=True,
        )
        hits = [f for score, f in scored if score > 0][:2]
        if not hits:
            return "FAQ 库未找到直接相关的问题，可咨询分类：尺码 / 充绒量保暖 / 清洗保养 / 发货 / 退换货 / 售后。"
        return _fmt_faq(hits)

    @tool
    def list_faq_categories() -> str:
        """列出客服 FAQ 库支持的所有问题分类，用于引导用户。"""
        faqs = kb.get("faq", [])
        cats = sorted({f.get("category", "其他") for f in faqs})
        return "可咨询分类：" + "、".join(cats)

    return [search_faq, list_faq_categories]


# ---------- 商品价格库存 Agent ----------
def build_product_tools(kb: KnowledgeBase) -> list[Any]:
    @tool
    def lookup_product(style_no: str) -> str:
        """按款式编号查询商品信息（含成本价、批发价、零售价、库存、仓库）。style_no 形如 DJ-2601。"""
        style_no = style_no.strip().upper()
        products = kb.get("products", [])
        for p in products:
            if p["style_no"] == style_no:
                return _fmt_product(p)
        return f"未找到款式编号 {style_no}。可用编号：DJ-2601~DJ-2610。"

    @tool
    def search_products(keyword: str) -> str:
        """按名称/分类/羽绒类型关键词搜索在售羽绒服款式。keyword 如：长款、白鹅绒、轻薄、派克服。"""
        keyword = keyword.strip()
        products = kb.get("products", [])
        hits = [
            p for p in products
            if keyword in p["name"] or keyword in p["category"] or keyword in p.get("fill_power", "")
        ]
        if not hits:
            return f"未找到与“{keyword}”匹配的款式。可搜索：长款/短款/白鹅绒/鸭绒/轻薄/派克服/面包服。"
        return "\n".join(_fmt_product(p) for p in hits)

    @tool
    def check_inventory(style_no: str) -> str:
        """查询某款式的库存数量与所在仓库。style_no 形如 DJ-2601。"""
        style_no = style_no.strip().upper()
        products = kb.get("products", [])
        for p in products:
            if p["style_no"] == style_no:
                return f"{p['style_no']} {p['name']}：库存 {p['stock']} 件，存放于 {p['warehouse']}（{p['status']}）。"
        return f"未找到款式编号 {style_no}。"

    @tool
    def get_price(style_no: str) -> str:
        """查询某款式的成本价与批发价（用于采购报价）。style_no 形如 DJ-2601。"""
        style_no = style_no.strip().upper()
        products = kb.get("products", [])
        for p in products:
            if p["style_no"] == style_no:
                return (
                    f"{p['style_no']} {p['name']}：成本价 ¥{p['cost_price']}，"
                    f"批发价 ¥{p['wholesale_price']}，建议零售价 ¥{p['retail_price']}。"
                )
        return f"未找到款式编号 {style_no}。"

    @tool
    def best_price(kind: str) -> str:
        """返回成本价最低或零售价最高的款式，用于"哪个款最便宜/最贵"。kind 传「最低」或「最高」。"""
        products = kb.get("products", [])
        if not products:
            return "无商品数据。"
        if kind == "最高":
            p = max(products, key=lambda x: x["retail_price"])
            return _fmt_product(p) + "\n（零售价最高款）"
        p = min(products, key=lambda x: x["cost_price"])
        return _fmt_product(p) + "\n（成本价最低款）"

    return [lookup_product, search_products, check_inventory, get_price, best_price]


# ---------- 采购制度 Agent ----------
def build_procurement_tools(kb: KnowledgeBase) -> list[Any]:
    @tool
    def get_procurement_flow() -> str:
        """返回完整采购流程（9 步）。"""
        flow = kb.get("procurement_flow", [])
        return "采购流程：\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(flow, 1))

    @tool
    def get_approval_rule(amount: float) -> str:
        """根据单笔采购金额返回对应的审批人权限。amount 为采购金额（元）。"""
        amount = float(amount)
        rules = kb.get("approval_rules", [])
        for r in rules:
            lo, hi = r["min_amount"], r["max_amount"]
            if lo <= amount and (hi is None or amount <= hi):
                return f"单笔采购金额 ¥{amount:,.0f}：需由【{r['approver']}】审批（{r['note']}）。"
        return "金额超出审批规则范围。"

    @tool
    def get_payment_rule(supplier_type: str) -> str:
        """返回付款制度。supplier_type 可为 regular（老供应商）或 new（新供应商）。"""
        rules = kb.get("payment_rules", {})
        supplier_type = supplier_type.strip().lower()
        if "new" in supplier_type:
            return f"新供应商付款：{rules.get('new_supplier')}。"
        return (
            f"常规付款：{rules.get('regular')}。\n"
            f"逾期罚则：{rules.get('overdue_penalty')}。"
        )

    @tool
    def get_discount(quantity: int) -> str:
        """根据单次采购件数返回批发折扣。quantity 为采购件数。"""
        quantity = int(quantity)
        mo = kb.get("minimum_order", {})
        base = f"起订量：{mo.get('per_sku')} 件/SKU（{mo.get('note')}）。"
        discounts = kb.get("discount_rules", [])
        best = None
        for d in discounts:
            if quantity >= d["quantity"]:
                best = d
        if best:
            return base + f"\n单次采购 {quantity} 件，可享【{best['discount']}】（{best['note']}）。"
        return base + f"\n单次采购 {quantity} 件未达 500 件折扣档，按标准批发价结算。"

    @tool
    def get_rebate() -> str:
        """返回年度返利规则。"""
        rb = kb.get("rebate_rules", {})
        return (
            f"年度返利：同一客户年度累计采购达 ¥{rb.get('annual_threshold'):,}"
            f" 返利 {rb.get('rebate_rate')}（{rb.get('note')}）。"
        )

    return [get_procurement_flow, get_approval_rule, get_payment_rule, get_discount, get_rebate]


# ---------- 供应商管理 Agent ----------
def build_supplier_tools(kb: KnowledgeBase) -> list[Any]:
    @tool
    def search_suppliers(category: str) -> str:
        """按类别搜索供应商。category 如：面料、羽绒、辅料、代工、包装；传「供应商/所有/全部」则返回全部。"""
        category = category.strip()
        suppliers = kb.get("suppliers", [])
        if category in ("供应商", "所有", "全部", "有哪些"):
            return "\n".join(_fmt_supplier(s) for s in suppliers)
        hits = [s for s in suppliers if category in s["category"] or category in s["scope"]]
        if not hits:
            return f"未找到“{category}”类供应商。可查：面料/羽绒/辅料/代工/包装。"
        return "\n".join(_fmt_supplier(s) for s in hits)

    @tool
    def get_supplier(name: str) -> str:
        """按供应商名称查询详情（资质、账期、合作状态）。name 如：安徽暖绒。"""
        name = name.strip()
        suppliers = kb.get("suppliers", [])
        for s in suppliers:
            if name in s["name"]:
                return _fmt_supplier(s)
        return f"未找到供应商“{name}”。"

    @tool
    def get_qualification_levels() -> str:
        """返回供应商资质评级标准说明。"""
        levels = kb.get("qualification_levels", {})
        return "\n".join(f"{k}：{v}" for k, v in levels.items())

    return [search_suppliers, get_supplier, get_qualification_levels]


# ---------- 下单审批 Agent ----------
def build_order_tools(kb: KnowledgeBase) -> list[Any]:
    @tool
    def get_order_rule(rule_keyword: str) -> str:
        """按关键词查询下单/审批规则。rule_keyword 如：采购单、审批、加急、修改、取消、到货。"""
        rule_keyword = rule_keyword.strip()
        rules = kb.get("order_rules", [])
        hits = [r for r in rules if rule_keyword in r["rule"] or rule_keyword in r["detail"]]
        if not hits:
            return f"未找到与“{rule_keyword}”相关的下单规则。可查：采购单/审批/加急/修改/取消/到货。"
        return "\n".join(f"{r['id']} {r['rule']}：{r['detail']}" for r in hits)

    @tool
    def list_order_rules() -> str:
        """列出全部下单审批规则。"""
        rules = kb.get("order_rules", [])
        return "\n".join(f"{r['id']} {r['rule']}：{r['detail']}" for r in rules)

    return [get_order_rule, list_order_rules]


# ---------- 格式化辅助 ----------
def _fmt_product(p: dict) -> str:
    return (
        f"{p['style_no']} {p['name']}（{p['category']}，充绒 {p['fill_power']}，"
        f"绒子含量 {p['down_content']}，尺码 {','.join(p['sizes'])}）\n"
        f"  成本价 ¥{p['cost_price']} | 批发价 ¥{p['wholesale_price']} | "
        f"零售价 ¥{p['retail_price']} | 库存 {p['stock']} 件 | {p['warehouse']} | {p['status']}"
    )


def _fmt_supplier(s: dict) -> str:
    return (
        f"{s['id']} {s['name']}（{s['category']}）\n"
        f"  供应范围：{s['scope']} | 资质：{s['qualification']} | "
        f"账期：{s['payment_term']} 天 | {s['cooperation_status']}"
    )


def _fmt_faq(faqs: list[dict]) -> str:
    return "\n".join(f"Q：{f['question']}\nA：{f['answer']}" for f in faqs)
