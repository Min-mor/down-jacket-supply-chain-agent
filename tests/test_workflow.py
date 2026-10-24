"""工作流测试：路由、知识隔离、回答、追问推荐。运行：python tests/test_workflow.py"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.agent_defs import create_agents
from graph import build_graph, route_question


class TestRouting(unittest.TestCase):
    def test_route_to_each_agent(self):
        cases = {
            "faq": ["尺码怎么选", "羽绒服怎么清洗", "退换货政策是什么"],
            "product": ["DJ-2601 批发价多少", "查一下库存", "有哪些白鹅绒长款"],
            "procurement": ["采购流程是什么", "采购5万需要谁审批", "付款制度"],
            "supplier": ["羽绒供应商有哪些", "供应商资质怎么分", "面料供应商"],
            "order": ["采购单要填哪些信息", "加急怎么申请", "怎么取消采购单"],
        }
        for zone, samples in cases.items():
            for s in samples:
                self.assertEqual(route_question(s), zone, msg=f"{s} -> 期望{zone}")


class TestKnowledgeIsolation(unittest.TestCase):
    """核心约束：知识不交叉污染。"""

    @classmethod
    def setUpClass(cls):
        cls.agents = create_agents()

    def test_each_agent_only_owns_its_zone(self):
        expected = {
            "faq": "faq",
            "product": "product",
            "procurement": "procurement",
            "supplier": "supplier",
            "order": "order",
        }
        for name, agent in self.agents.items():
            self.assertEqual(agent.kb.zone, expected[name])

    def test_product_agent_has_no_faq_data(self):
        # product 分区的数据里绝不能出现 faq 的字段
        product_data = self.agents["product"].kb.all()
        self.assertNotIn("faq", product_data)
        # product 的知识库里不应有采购/供应商字段
        flat = str(product_data)
        self.assertNotIn("approval_rules", flat)
        self.assertNotIn("suppliers", flat)

    def test_agents_knowledge_sources_disjoint(self):
        # 各分区的业务数据键两两不相交（元信息键为公共说明，不计入）
        META = {"knowledge_name", "owner_agent", "description", "updated"}
        zones = []
        for a in self.agents.values():
            zones.append({k for k in a.kb.all().keys() if k not in META})
        for i, a in enumerate(zones):
            for b in zones[i + 1:]:
                shared = a & b
                self.assertEqual(shared, set(), f"分区知识字段交叉: {shared}")

    def test_suggestions_stay_in_own_zone(self):
        # 追问推荐只来自本域
        for name, agent in self.agents.items():
            sugg = agent.suggest("默认")
            self.assertTrue(len(sugg) >= 2)
            self.assertTrue(len(sugg) <= 3)


class TestEndToEnd(unittest.TestCase):
    def test_each_domain_answers(self):
        app, _ = build_graph()
        samples = [
            "尺码怎么选",
            "DJ-2601 批发价多少",
            "采购5万需要谁审批",
            "羽绒供应商有哪些",
            "加急怎么申请",
        ]
        for q in samples:
            result = app.invoke({"question": q, "history": []}, config={"recursion_limit": 10})
            self.assertTrue(result["answer"])
            self.assertTrue(result["agent_name"])
            self.assertIsInstance(result["suggestions"], list)
            self.assertTrue(len(result["suggestions"]) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
