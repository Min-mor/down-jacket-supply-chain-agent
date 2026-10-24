"""评测数据集。

每条：question（问题）、expected_zone（期望路由到的 Agent）、
answer_contains（回答里应包含的文本片段，用于校验答案质量）。

覆盖 5 个域，包含口语化追问，用于衡量路由准确率与回答命中率。
"""
from __future__ import annotations

EVAL_CASES: list[dict[str, str]] = [
    # ---- 客服 FAQ ----
    {"question": "尺码怎么选", "expected_zone": "faq", "answer_contains": "155-160cm"},
    {"question": "羽绒服怎么清洗", "expected_zone": "faq", "answer_contains": "手洗"},
    {"question": "身高170应该选什么码", "expected_zone": "faq", "answer_contains": "160-165"},
    {"question": "退换货政策", "expected_zone": "faq", "answer_contains": "7天"},
    # ---- 商品价格库存 ----
    {"question": "DJ-2601 批发价多少", "expected_zone": "product", "answer_contains": "360"},
    {"question": "DJ-2607 库存还有多少", "expected_zone": "product", "answer_contains": "1500"},
    {"question": "有哪些白鹅绒长款", "expected_zone": "product", "answer_contains": "白鹅绒"},
    {"question": "哪个款成本价最低", "expected_zone": "product", "answer_contains": "DJ-2607"},
    # ---- 采购制度 ----
    {"question": "采购流程是什么", "expected_zone": "procurement", "answer_contains": "需求提出"},
    {"question": "采购5万谁审批", "expected_zone": "procurement", "answer_contains": "部门经理"},
    {"question": "付款制度", "expected_zone": "procurement", "answer_contains": "定金"},
    {"question": "采购1000件打几折", "expected_zone": "procurement", "answer_contains": "9折"},
    # ---- 供应商 ----
    {"question": "羽绒供应商有哪些", "expected_zone": "supplier", "answer_contains": "安徽暖绒"},
    {"question": "供应商资质怎么分", "expected_zone": "supplier", "answer_contains": "五星"},
    {"question": "面料供应商", "expected_zone": "supplier", "answer_contains": "杭州织羽"},
    # ---- 下单审批 ----
    {"question": "采购单要填哪些信息", "expected_zone": "order", "answer_contains": "款号"},
    {"question": "加急怎么申请", "expected_zone": "order", "answer_contains": "加急"},
    {"question": "怎么取消采购单", "expected_zone": "order", "answer_contains": "取消"},
]
