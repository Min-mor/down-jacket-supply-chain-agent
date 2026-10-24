"""评测脚本：跑一遍评测集，输出路由准确率 + 回答命中率报告。

用法：
    python -m eval.run_eval            # 用当前模式（规则或 LLM）
    DEEPSEEK_API_KEY=xxx python -m eval.run_eval   # 评测 LLM 模式

生产建议把结果上报到 LangSmith/Langfuse 做回归看板；这里输出可读报告。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import build_graph, route_question  # noqa: E402
from llm import get_llm  # noqa: E402


def evaluate(limit: int | None = None):
    from eval.dataset import EVAL_CASES

    cases = EVAL_CASES if limit is None else EVAL_CASES[:limit]
    app, _, llm = build_graph()
    mode = "llm" if llm is not None else "rule"

    route_hits = 0
    answer_hits = 0
    rows = []
    for case in cases:
        q, ez, ec = case["question"], case["expected_zone"], case["answer_contains"]
        pred_zone = route_question(q)
        res = app.invoke({"question": q, "history": []}, config={"recursion_limit": 10})
        route_ok = pred_zone == ez
        answer_ok = ec in res["answer"]
        route_hits += route_ok
        answer_hits += answer_ok
        rows.append((q, ez, pred_zone, route_ok, answer_ok))

    n = len(cases)
    print(f"== Eval 报告 (mode={mode}) ==")
    print(f"样本数: {n}")
    print(f"路由准确率: {route_hits}/{n} = {route_hits / n:.0%}")
    print(f"回答命中率: {answer_hits}/{n} = {answer_hits / n:.0%}")
    print("-" * 60)
    for q, ez, pz, ro, ao in rows:
        flag = "OK" if (ro and ao) else ("~" if (ro or ao) else "X")
        print(f"[{flag}] 期望={ez:<12} 实际路由={pz:<12} 答案命中={ao}  {q}")
    return {"mode": mode, "route_acc": route_hits / n, "answer_acc": answer_hits / n}


if __name__ == "__main__":
    evaluate()
