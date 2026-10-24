# 女装羽绒服供应链智能体 —— FAQ / 采购制度问答工作流

基于 **LangChain + LangGraph** 的多 Agent 问答系统，模拟一家女装羽绒服供应链的
5 位"员工"（Agent），各司其职、知识库物理隔离、互不交叉污染。用户首轮收到
"能问什么"的引导，每轮回答后系统会从当前 Agent 的知识域内推荐 2-3 个相关问题，
输入序号即可"以此类推"持续深入。

---

## 1. 快速开始

```bash
cd 女装羽绒服供应链智能体
pip install -r requirements.txt      # langchain / langgraph
python main.py                        # 进入交互问答
```

运行测试：

```bash
python tests/test_workflow.py
```

## 2. 系统能问什么（首轮引导）

| 员工（Agent） | 分工 | 可问示例 |
|---|---|---|
| 客服FAQ助手 | 售前售后咨询 | 尺码怎么选 / 羽绒服怎么洗 / 发货时效 / 退换货政策 |
| 商品价格库存助手 | 款式/价格/库存 | DJ-2601 批发价多少 / 有哪些白鹅绒长款 / 查一下库存 |
| 采购制度助手 | 采购流程/审批/付款 | 采购流程是什么 / 采购5万谁审批 / 付款折扣制度 |
| 供应商管理助手 | 供应商名录/资质 | 羽绒供应商有哪些 / 供应商资质怎么分 |
| 下单审批助手 | 采购单/审批流 | 采购单要填哪些信息 / 加急怎么申请 / 怎么取消 |

首轮进入时会输出完整引导；每次回答后打印可继续追问的序号列表，输入序号即继续。

## 3. 多 Agent 架构与知识隔离

```
                    ┌────────────────────────────┐
                    │      LangGraph Router      │ 关键词打分 + 强信号词
                    └─────────────┬──────────────┘
        ┌───────┬────────┬────────┼────────┬────────┐
        ▼       ▼        ▼        ▼        ▼
   faq 节点  product  procurement supplier order   ← 5 个独立 Agent 节点
   客服FAQ   商品价格   采购制度   供应商    下单审批
    │       库存       │        │         │
    ▼        ▼         ▼        ▼         ▼
  faq库    product库  policy库  supplier库 order库
  faq.json products   .json    .json     .json
```

**知识隔离机制（硬约束，已用测试锁定）：**

1. **目录级隔离** —— 每个分区一个目录 `knowledge/<zone>/`，Agent 只扫描自己分区。
2. **加载器校验** —— `KnowledgeBase` 按分区加载，JSON 内 `owner_agent` 与分区不匹配
   会直接抛错拦截，防止错放文件被其他 Agent 读到。
3. **工具级隔离** —— 每个 Agent 的工具通过闭包绑定自己的 `KnowledgeBase`，
   工具层只能查到自己分区的数据。
4. **推荐隔离** —— 追问推荐器 `SuggestionProvider` 只从本分区预置候选池产出。

测试 `tests/test_workflow.py` 中 `TestKnowledgeIsolation` 覆盖：
各分区数据键两两不相交、商品 Agent 无 FAQ/采购/供应商数据、推荐不越域。

## 4. 目录结构

```
女装羽绒服供应链智能体/
├── main.py                     # 入口：首轮提示 + 交互循环 + 序号选择
├── graph.py                    # LangGraph 编排：Router 路由 + 5 个 Agent 节点
├── requirements.txt
├── knowledge/                  # 知识库根（按角色物理隔离）
│   ├── faq/faq.json            #   客服FAQ（8 条，含尺码/清洗/发货/退换/售后）
│   ├── product/products.json   #   商品价格库存（10 款：款号/成本价/批发价/库存/仓库）
│   ├── procurement/policy.json #   采购制度（流程/审批权限/付款/折扣/返利）
│   ├── supplier/suppliers.json #   供应商（6 家：资质/账期/合作状态）
│   └── order/order_rules.json  #   下单审批规则（采购单/加急/修改/取消）
├── agents/
│   ├── knowledge_base.py       # 隔离加载器 KnowledgeBase
│   ├── tools.py                # 5 个 Agent 的 @tool 工具集（LangChain 工具协议）
│   ├── agent_defs.py           # SupplyChainAgent 定义与 dispatch
│   └── suggestions.py          # 追问推荐器（按域隔离）
└── tests/test_workflow.py      # 路由/隔离/端到端测试
```

## 5. 示例数据（编造，演示用）

商品库（节选）：

| 款号 | 名称 | 充绒量 | 成本价 | 批发价 | 零售价 | 库存 | 仓库 |
|---|---|---|---|---|---|---|---|
| DJ-2601 | 女士长款白鹅绒羽绒服 | 250g 90白鹅绒 | ¥260 | ¥360 | ¥599 | 1200 | 华东仓 |
| DJ-2607 | 女士轻薄便携羽绒服 | 90g 90鸭绒 | ¥120 | ¥175 | ¥299 | 1500 | 华南仓 |
| DJ-2609 | 女士法式连帽过膝羽绒服 | 300g 95白鹅绒 | ¥350 | ¥470 | ¥799 | 280 | 华北仓 |

采购制度（节选）：审批权限按金额分级（1万内→采购主管、1~5万→部门经理、
5~20万→总监、20万以上→总经理）；常规付款首付30%定金、尾款70%货到验收后30天；
起订 200 件/SKU；500 件 95 折、1000 件 9 折、5000 件 85 折；年度累计 100 万返利 2%。

## 6. LLM 增强模式（DeepSeek · 真 tool calling）

当前工程支持两种运行模式，**未配置 Key 也能跑**：

| 模式 | 触发条件 | 路由 | Agent 执行 |
|---|---|---|---|
| 规则模式（默认，可离线） | 未设 `DEEPSEEK_API_KEY` | 关键词打分 + 强信号词 | 确定性 dispatch（@tool 协议） |
| LLM 模式（真智能体） | 设置了 `DEEPSEEK_API_KEY` | LLM 意图分类（`with_structured_output`） | `create_agent` 工具调用图（LLM 决定调哪个工具 → ToolNode 执行 → 生成回答） |

启用 LLM 模式：

```bash
# 方法一：环境变量
export DEEPSEEK_API_KEY=sk-xxx        # 从 https://platform.deepseek.com 获取
python main.py

# 方法二：复制示例配置再填
cp .env.example .env                  # 在 .env 里填 DEEPSEEK_API_KEY，然后：
# 需先安装依赖，并可用 python-dotenv 自动加载 .env（或手动 export）
pip install -r requirements.txt
```

`llm.py` 负责读环境变量并创建 `ChatOpenAI`（DeepSeek 为 OpenAI 兼容接口）。`.env` 已加入
`.gitignore`，不会把 Key 提交到仓库。两种模式下，5 个 Agent 的知识隔离与追问推荐机制
保持一致。

## 7. 设计说明与技术要点

- **编排层**：`graph.py` 用 LangGraph `StateGraph` 构建，`router` 节点做条件路由到
  5 个 Agent 节点，每个节点输出 `answer` + `matched_key` + `suggestions`。
- **路由**：配置 Key 时优先用 LLM `with_structured_output` 做意图分类，解析失败/未配置
  时自动降级到「强信号词 + 关键词打分」，保证始终可用。
- **工具调用**：配置 Key 时每个 Agent 用 `create_agent(model, agent.tools)` 构建工具调用图
  （ReAct 循环 + ToolNode）；未配置时用确定性 dispatch。两种路径都走 LangChain `@tool` 协议。
- **知识隔离**：无论 LLM 还是规则模式，5 个 Agent 各自绑定独立 KnowledgeBase，工具层
  只能访问自己分区的数据，不交叉污染。
- **中文检索**：FAQ 采用中文 2~3 字子串打分匹配，保证"身高170怎么选码"这类
  口语追问也能命中答案。

## 8. 已验证项

- ✅ 路由：5 个域的典型问题均路由到正确 Agent（规则与 LLM 双路径）
- ✅ 隔离：各分区业务数据键两两不相交、无交叉污染
- ✅ 端到端：每个域均能返回答案 + 追问推荐
- ✅ 多轮追问链：输入序号可"以此类推"持续深入

---

## 9. 生产级服务（FastAPI + 持久化 + 安全 + 评测 + 部署）

工程已从"CLI + 单文件"升级为可部署的多 Agent 服务，C 端界面也已改接后端 API。

### 9.1 新增目录

```
core/                  # 基础设施层
├── config.py          #   pydantic-settings 统一配置（.env / 环境变量）
├── logging.py         #   JSON Lines 结构化日志 + 每请求 request_id
├── db.py              #   SQLAlchemy ORM：Conversation / Message，幂等建表
└── memory.py          #   会话记忆：建会话 / 载历史 / 追加落库 / 组装 LLM 消息
api/                   # 服务层
├── main.py            #   FastAPI：/healthz /readyz /agents /chat
├── schemas.py         #   ChatRequest / ChatResponse / AgentInfo / Health
├── security.py        #   提示注入防护、输入校验、限流、CORS、网关令牌
└── deps.py            #   应用级单例（graph/agents/llm 只建一次）
eval/                  # 评测
├── dataset.py         #   18 条评测用例（5 域覆盖 + 口语追问）
└── run_eval.py        #   路由准确率 + 回答命中率报告
Dockerfile / docker-compose.yml / .github/workflows/ci.yml
tests/test_api.py      # FastAPI 集成测试
```

### 9.2 API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 存活探针（返回 `mode`：llm / rule） |
| GET | `/readyz` | 就绪探针（含数据库连通检查） |
| GET | `/api/v1/agents` | 员工（Agent）列表（配置 `API_TOKEN` 时需带 `X-API-Token`） |
| POST | `/api/v1/chat` | 会话问答。`{question, session_id?}` → 多轮记忆 + 落库 + 追问推荐 |

交互式文档：`/docs`（Swagger）。

### 9.3 安全与稳健性

- **提示注入防护**：启发式检测「忽略/无视/系统指令/扮演」等特征，命中返回 400（建议生产接护栏模型）。
- **输入校验**：空输入 / 超长 / 不可打印字符清洗。
- **限流**：单进程内存滑动窗口（默认 60 次/分/IP，按 `X-Forwarded-For` 取源 IP）。
- **网关令牌**：设置 `API_TOKEN` 后 `/agents` 等需 `X-API-Token`。
- **CORS**：按 `cors_origins` 白名单放行（C 端页面跨域调用）。
- **可观测**：JSON 结构化日志，每次请求带 `request_id`，便于链路追踪。

### 9.4 运行服务

```bash
# 本地开发
uvicorn api.main:app --host 0.0.0.0 --port 8000

# 生产推荐：多 worker + 生产环境配置
ENV=prod uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

配置项见 `.env.example`（`DEEPSEEK_API_KEY`、`DATABASE_URL`、`API_TOKEN`、
`RATE_LIMIT_PER_MINUTE`、`CORS_ORIGINS`、`ENV` 等）。

### 9.5 Docker 部署

```bash
cp .env.example .env        # 填好配置
docker compose up --build   # 起服务（含健康检查，数据挂载到 ./data）
```

### 9.6 CI（GitHub Actions）

`.github/workflows/ci.yml`：push / PR 时自动跑 `pytest`（16 项）+ 评测（18 例），
保证回归不破。

### 9.7 评测与回归

```bash
python -m pytest -q          # 16 项单元 + 集成测试
python -m eval.run_eval      # 评测：路由准确率 + 回答命中率
```

当前基线（rule 模式）：**路由准确率 100%（18/18）、回答命中率 100%（18/18）**。

### 9.8 C 端界面对接后端

`c端问答界面/女装羽绒服供应链问答助手.html` 现在默认调用后端
`POST {API_BASE}/chat`（`API_BASE` 默认 `http://localhost:8000/api/v1`），
会话 ID 存 `localStorage` 实现跨轮记忆；后端不可达时自动降级为内置规则引擎（离线演示）。

### 9.9 上生产前的建议清单

- [ ] 配置真实 `DEEPSEEK_API_KEY`，切到 LLM 模式并复跑评测
- [ ] `DATABASE_URL` 换 Postgres（当前默认 SQLite 仅适合单机演示）
- [ ] 限流迁移到 Redis（多实例共享），网关令牌交给正式鉴权
- [ ] 提示注入防护接入专用护栏模型
- [ ] 接入 LangSmith / Langfuse 做链路追踪与评测看板
- [ ] 前端 API 地址通过部署环境注入（`window.AGENT_API_BASE`），并走 HTTPS

