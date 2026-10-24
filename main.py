"""女装羽绒服供应链智能体 —— 采购制度 / FAQ 问答工作流入口。

运行：python main.py

- 首轮输出"你可以问什么"引导提示。
- 每一轮回答后，会从当前 Agent 的知识域内给出 2-3 个相关问题，输入序号即可继续，
  也可以自由输入新问题；输入「结束/退出/exit/quit」停止。
"""
from __future__ import annotations

import sys

from graph import build_graph

WELCOME = r"""
===============================================================
   女装羽绒服供应链智能体 ｜ FAQ & 采购制度问答工作流
===============================================================
【你可以问的问题】系统由 5 位员工（Agent）分工协作，各自只负责
自己的知识域，知识库相互隔离、不交叉污染：

  1. 客服 FAQ —— 尺码怎么选 / 充绒量保暖 / 清洗保养 / 发货时效
                 / 退换货政策 / 钻绒售后
  2. 商品价格库存 —— 查某款（如 DJ-2601）成本价、批发价、库存
                 / 有哪些长款/白鹅绒/轻薄款
  3. 采购制度 —— 采购流程 / 不同金额的审批权限 / 付款制度
                 / 起订量 / 折扣返利
  4. 供应商管理 —— 羽绒/面料/辅料/代工/包装供应商 / 资质评级
  5. 下单审批 —— 采购单要填什么 / 加急怎么申请 / 修改取消
---------------------------------------------------------------
直接输入你的问题即可，例如：「DJ-2601 批发价多少」「采购5万谁审批」
每次回答后我会给你 2-3 个相关问题，输入序号可继续深入。
输入「结束」退出。
"""


def main() -> None:
    from llm import get_llm
    app, agents, llm = build_graph()
    mode = "LLM 模式（DeepSeek，真 tool calling）" if llm is not None else "规则模式（未配置 DEEPSEEK_API_KEY，可离线运行）"
    print(WELCOME)
    print(f"◆ 当前运行模式：{mode}\n")

    history: list[tuple[str, str]] = []
    last_suggestions: list[str] = []

    while True:
        if last_suggestions:
            print("可以继续问：")
            for i, s in enumerate(last_suggestions, 1):
                print(f"  [{i}] {s}")
            prompt_hint = f"输入序号或新问题"
        else:
            prompt_hint = "请输入问题"

        try:
            raw = input(f"\n> {prompt_hint}：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break

        if raw in ("结束", "退出", "exit", "quit", "q"):
            print("已退出。")
            break

        # 支持输入序号复用推荐问题
        if raw.isdigit() and last_suggestions:
            n = int(raw) - 1
            if 0 <= n < len(last_suggestions):
                raw = last_suggestions[n]

        question = raw
        history.append((question, ""))
        result = app.invoke(
            {"question": question, "history": history},
            config={"recursion_limit": 10},
        )

        answer = result["answer"]
        agent_name = result["agent_name"]
        history[-1] = (question, answer)

        print("-" * 60)
        print(f"【{agent_name}】")
        print(answer)
        print("-" * 60)
        last_suggestions = result["suggestions"]

    sys.exit(0)


if __name__ == "__main__":
    main()
