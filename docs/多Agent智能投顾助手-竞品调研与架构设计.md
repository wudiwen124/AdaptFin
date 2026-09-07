# 多 Agent 智能投顾助手 · 竞品调研与完整架构设计

> 调研时间：2026-09-07；数据以当日 GitHub API 为准。
> 用途：先看同类开源项目怎么做，再给本项目定架构、流程与技术栈。本设计面向“找实习/找工作”的求职作品集，同时保证技术可落地、可演示、可讲深。

---

## 0. 调研范围与方法

通过 GitHub API 抓取仓库元数据（star/fork/语言/默认分支/最近推送），精读 10 个代表性项目的 README、架构章节与源码目录树，并抽查官方文档：

| 调研对象 | 热度 | 语言/定位 |
|---|---|---|
| TauricResearch/TradingAgents | 102.8k | 多 Agent LLM 交易框架（Python） |
| OpenBB-finance/OpenBB | 72.7k | 面向分析师与 AI Agent 的开放数据平台 |
| virattt/ai-hedge-fund | 63.3k | AI 对冲基金团队（教育向） |
| UFund-Me/Qbot | 18.5k | AI 量化投研平台（数据→回测→交易全链路） |
| AI4Finance-Foundation/FinRobot | 7.9k | 金融 AI Agent 平台（四层架构） |
| wyh22/multi-agent-trading | 12 | A 股 7-Agent 研究系统（TradingAgents 二次开发） |
| Md-Emon-Hasan/TrueWealth-AI | 8 | LangGraph 9-Agent 金融顾问（对话型） |
| Colin579M/AStock-AI-Agent | 3 | TradingAgents 中文版，Tushare/AkShare |
| Jiangge89/trading-agent | 1 | LangGraph ReAct + 模拟交易 + 人审 |
| rahul-jajala/ai-financial-research-agent | 0 | LangGraph ReAct 单 Agent 研究助手 |

> 说明：star 数只反映传播度，不代表工程质量；分析以“架构与我们的目标相似度”加权，A 股/对话投顾类项目虽小，参考价值反而最高。

---

## 1. 重点竞品逐个拆解

### 1.1 TradingAgents —— 多角色协作的“标准答案”，也是超配典型

**架构**：LangGraph 单图串起约 12 个 LLM 角色，四阶段流水线：分析师团队（基本面/情绪/新闻/技术）→ 多空研究员固定轮次辩论 → 交易员出提案 → 风控三方（激进/中性/保守）辩论 → 组合经理批准 → 模拟交易所。状态用 Pydantic AgentState 贯穿，`propagate(ticker, date)` 为入口，支持断点续跑（SQLite checkpoint）、决策日志记忆（`~/.tradingagents/memory/trading_memory.md`，回测后写反思）、温度/模型配置化。

**技术栈**：Python 3.12、LangGraph、LangChain 工具封装；多 LLM 提供商（OpenAI/Gemini/Claude/DeepSeek/Qwen/GLM/Ollama 等）；数据源以 Finnhub、OpenBB、yfinance 为主，社区中文版换成 Tushare/AkShare/BaoStock。

**优点**：角色分工模仿真实交易台，叙事性强、容易出演示效果；LangGraph 图化后各阶段可插拔；持久化与“复盘反思日志”是亮点。

**不足/对我们的警示**：
- 角色多、每轮几十次 LLM 请求，**成本和延迟高**，不适合实时对话；
- 面向“单标的单日决策”，不是“记住用户是谁、多次对话”的投顾形态；
- 数据新鲜度与“当时能否看到”（PIT）不严格，历史复盘容易未来函数；
- 强观点输出（买/卖/仓位）直接给用户，合规与免责靠文档而非系统结构。

### 1.2 wyh22/multi-agent-trading —— 最贴近我们的 A 股工程化范本

**架构**：基于 TradingAgents 二次开发，明确裁剪为 **7-Agent 两阶段并行**：分析师（行情/新闻情绪/基本面）fan-out 并行 → fan-in → 多空研究员辩论 → Portfolio Manager → **独立 Decision Auditor**。Auditor 发现事实无出处、口径冲突、PIT 越界等问题时，输出 `issue_type / repair_target / instruction` 定向回到 Market/News/Fundamentals 重新取证，有最大审计轮次上限。另有 Conversation Supervisor（多轮会话路由到 Atomic Tools / Specialist / Skill / Deep Research）、共享 Qdrant Hybrid RAG（Dense+BM25+RRF + PIT 过滤）、SQLite 会话与研究版本回滚、FastAPI + Web Chat、Agent Evaluation 与 Outcome Backtest 分离。

**技术栈**：LangGraph（Subgraph + Fan-Out/Fan-In）、Qdrant、SQLite、FastAPI、Docker Compose；数据：BaoStock（OHLCV/估值，PIT 友好）、AKShare/新浪（财务）、巨潮资讯（公告）、财联社/AKShare（宏观与资讯）；LLM 走本地凭据配置。

**优点**：把“为什么多 Agent”“为什么筛选不用 LLM”“为什么加 Auditor”“为什么评测与收益分离”全部写成设计决策文档（含面试指南）；确定性任务全部下沉 Python，LLM 只做语义分析；无自动下单。

**不足**：功能面偏大（Discovery + RAG + 回测 + 会话），两周内照搬不现实；没有“用户画像/风险偏好长期记忆”的投顾属性；交互仍以研究会话为主，不是问卷化 KYC 后的个性化建议。

### 1.3 TrueWealth-AI —— 对话型金融顾问里最值得抄的“安全网”

**架构**：9 个 Agent 的 LangGraph 图，几个关键设计：
- **路由层 0 LLM 调用**：先用规则/regex 判意图，命中不了才走模型；
- **确定性先行**：Portfolio Analyst 用 pandas/numpy 算指标，LLM 只负责解释；
- **Due Diligence Agent**：对生成结果做“是否有数据支撑/引用”核查，只允许一次有界修订；
- **Compliance Officer Agent：0 次 LLM 调用**，纯规则做输入清洗、输出策略检查、追加免责声明；
- **风险表述进人审队列**：命中高风险/无支撑数字时答案不直接出，进 SQLite 队列由人复核；
- **记忆**：短时 buffer + SQLite 再水合 + Chroma 语义召回；全程审计日志；
- **模型网关**：LiteLLM 分 answer/reasoning/classify 三档路由，支持 fallback 与缓存。

**技术栈**：FastAPI + React（前端）、LiteLLM、SQLModel/SQLite、ChromaDB、Docker、GitHub Actions；135 个后端测试宣称 100% 语句/分支覆盖且不碰真实网络。

**优点**：监管合规意识是全部竞品里最强的；规则化审核 + 人审 + 审计日志，非常适合“投顾”语境；测试纪律值得抄。

**不足**：9 个 Agent 偏多，很多角色（Planner/Executor 未接线）是残留；面向美股 yfinance；项目新、star 少、工程结论缺乏评测数据支撑；LiteLLM+多向量库依赖偏重。

### 1.4 Jiangge89/trading-agent —— 人审与模拟交易闭环的干净示范

**架构**：Supervisor（LLM 结构化路由）→ Research Agent / Trading Agent；11 个工具；**确定性风控层**（现金充足、单标的不超 25%、单笔不超 10%、订单 30 分钟过期）在 LLM 之上强制执行；交易必须 `interrupt()` 人工批准才执行；混合检索 pgvector（Dense+全文 BM25+RRF+rerank）；记忆用 `save_note` / `recall_notes` 工具持久化个人研究笔记与偏好。

**优点**：清晰回答“LLM 提议、规则层决定、人来批准”三层边界；RAG 做符号与语义混合检索的动机讲得明白。

**不足**：单用户 CLI/API 原型，无画像体系与多会话个性化；代码量小，评测与运维弱。

### 1.5 FinRobot —— 平台化的分层参考

**架构**：四层：Financial AI Agents / 金融 LLM 算法层 / LLMOps+DataOps / 多源基础模型层；Agent 工作流抽象成 Perception→Brain→Action；Smart Scheduler 里 Director 按任务指标分派、Agent Registration/Adaptor/Task Manager 管理模型与 Agent 生命周期；代码按 `agents / data_source / functional` 组织。

**优点**：分层与“模型即插即用”的思路适合参考；功能函数（analyzer/charting/quant/coding/reportlab）展示了金融 Agent 的通用能力面。

**不足**：偏研究平台而非产品，Perception/Brain/Action 只是概念层；对 A 股与对话个性化覆盖弱；代码以 notebook 教程为主，工程化不及前两者。

### 1.6 ai-hedge-fund —— 正在转型的“基金本体”范式

**架构**：最新版把“AI 对冲基金”重构成 **Fund 为一等公民**：YAML mandate（策略、员工、风险、资金、节奏）描述基金，`aihf --tickers --backtest` 跑周期或回测；LLM 驱动的“alpha 模型”被设计成可插拔、可回测；`hedge_fund/data、brokers、risk、pipeline、llm` 全部用 Protocol 抽象（数据客户端、模拟券商、LLM registry）。

**优点**：Protocol/接口化抽象、mandate 配置化、测试随模块（test_* 和源码同目录）都很工程化；教育免责声明前置。

**不足**：面向美股与“基金运行”，不是自然人投顾对话；需要 Financial Datasets 付费 API，国内不可直接落地；alpha 模型输出强信号，对普通用户不友好。

### 1.7 OpenBB / Qbot / 其他

- **OpenBB**：定位“开放数据平台”，**一次接入数据源、Python/REST/CLI/MCP 多入口消费**；提供 Agent 的 HTTP 契约接入与参考 Agent（Rita）。对我们的启示：数据层要抽象成可独立复用的服务，未来可用 MCP 暴露给任意 Agent/IDE。但整体上手成本高，不适合做求职 MVP 底座。
- **Qbot**：数据→策略→回测→模拟→实盘全链路，附 Qlib 与模型动物园。启示是“反例”：全栈量化平台工程量大得离谱，求职项目应聚焦**投顾对话 + 画像记忆 + 评测**，回测只做扩展点。
- **TradingAgents-CN / AStock-AI-Agent 系**：证明 A 股化的常见做法只是“换数据源 + 中文 Prompt”。同质化严重——这正是我们做**对话式投顾 + 风险画像 + 记忆 + 合规审计**的差异化机会。
- **rahul-jajala**：最小 ReAct 单 Agent + 4 工具 + Streamlit + JSON 会话跟踪 + MCP Server。启示：入门简单、适合做底座实验，但无并行、无审计、无画像，回答了“为什么要多 Agent 图”。

---

## 2. 调研提炼：8 条反复出现的工程共识

跨项目看，能稳定成立的设计原则只有这几条（后文架构全部落实它们）：

1. **确定性计算与 LLM 叙事分离**：指标、评分、风控上限、日期守卫全部交给 Python；LLM 只做工具选择、语义分析与解释（ai-hedge-fund、TrueWealth、jiangge89、wyh22 四家同向）。
2. **路由/主管与执行 Agent 分离**：Supervisor 负责分派与上下文汇总，执行者单职责（jiangge89、wyh22、TrueWealth）。
3. **独立审核与有界修订**：决策者不能给自己当裁判；Auditor/Due Diligence 检查引用、口径、事实方向，只允许有限轮修订（wyh22、TrueWealth）。
4. **合规用规则而非提示词兜底**：免责声明、违规表述过滤、敏感问题转人审，用 0-LLM 规则实现（TrueWealth、ai-hedge-fund、TradingAgents disclaimer）。
5. **数据层与 Agent 层解耦**：多数据源抽象、缓存、重试、降级、数据日期标注（PIT），是稳定性的真正来源（OpenBB、wyh22、ai-hedge-fund data protocol）。
6. **模型分档**：路由/分类用便宜快模型，深度分析/总结用强模型；统一走可替换网关（TrueWealth LiteLLM 三档、FinRobot Director、TradingAgents deep/quick think）。
7. **记忆分层**：会话 checkpoint（恢复上下文）与跨会话事实库（画像/笔记/复盘）分开存、分开召回（jiangge89 notes、TradingAgents memory log、TrueWealth 双层）。
8. **评测与收益分离**：Agent 质量看路由/引用/工具轨迹是否达标，不能拿涨跌当工程指标；回测只在历史数据下做且必须 PIT 安全（wyh22、ai-hedge-fund）。

---

## 3. 本项目完整架构

### 3.1 定位修正（调研后的差异化）

竞品大多做“一次性的个股研究/交易决策”，少数对话型项目又缺 A 股数据与画像记忆。本项目差异化定位：

> **中文对话式投顾助手**：A 股真实数据 + 用户风险画像（KYC）+ 两级记忆 + 规则化合规审计，输出“带证据、按用户画像约束的参考分析”，而不是“买/卖信号机”。

### 3.2 Agent 数量：从你设想的 3 个，调整为 5 个角色

| 原始设想 | 最终角色 | 调整理由（来自调研） |
|---|---|---|
| 行情查询 Agent | **Market Agent**（行情域） | 保留：只取数、不评价，工具权限最小化 |
| 研究分析 Agent | **Research Agent**（研究域，内部 3 个并行子分析师） | 保留并增强：基本面/技术面/资讯情绪并行 fan-out，参照 TradingAgents/wyh22 |
| 风险测评 Agent | **Risk Agent**（测评域 + 硬约束输出） | 保留并重定义：问卷评分是规则，LLM 只做对话引导 |
| — | **Advisor Agent**（建议合成） | 新增：三家竞品都说明“汇总与建议”是独立职责，不应让研究 Agent 顺手给建议 |
| — | **Auditor（Guardian）节点** | 新增：独立事实/引用/合规审计 + 有界修订（wyh22 Auditor、TrueWealth Due Diligence 的直接启示） |

> 为什么不再扩到 9~12 个角色：TrueWealth 有未接线残留角色，TradingAgents 延迟成本不可用于对话；对“投顾对话”这个目标，5 个角色已是成本、可解释性、评测难度的平衡点。多空辩论、基金经理决策等只作为后续研究扩展，不进 MVP 主链路。

### 3.3 总体架构图

```text
┌──────────────────────────── 用户接入层 ───────────────────────────┐
│  Streamlit 快速演示 UI        FastAPI + SSE（流式聊天，主服务）       │
└──────────────────────────────────┬─────────────────────────────────┘
                                   │ POST /v1/chat (SSE)  user_id + session_id
┌──────────────────────────────────▼─────────────────────────────────┐
│                        服务层（FastAPI）                            │
│  鉴权(user_id) · 限流 · 请求/响应审计日志 · 可选人审队列 API          │
└──────────────────────────────────┬─────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────┐
│                     编排层：LangGraph 单图                           │
│                                                                     │
│  START → Supervisor(两段路由)                                        │
│            ├─ 规则预筛(关键词/实体) → 小模型意图兜底(结构化输出)        │
│            │                                                        │
│            ├─ quote   ────► Market Agent                            │
│            ├─ research────► Research Agent(Subgraph)                │
│            │                 ├─ Fundamentals 子分析师                │
│            │                 ├─ Technical 子分析师                   │
│            │                 └─ News/Sentiment 子分析师  (fan-out)   │
│            │                        └─────► fan-in 汇总              │
│            ├─ risk    ────► Risk Agent（问卷多轮 / 评分 / 硬约束）    │
│            ├─ portfolio────► 持仓列表 → Research fan-out（每只并行）  │
│            └─ chat / memory ──► 画像问答 / 偏好抽取                   │
│                      │                                              │
│                      ▼                                              │
│              Advisor Agent（画像注入 + 风险约束 + 引用合成）          │
│                      ▼                                              │
│              Auditor（审计：出处/口径/PIT/推断冒充事实/越权表述）      │
│                  │ 发现问题 → 定向回修（≤N 轮）                      │
│                  ▼                                                  │
│              Compliance 闸门（0-LLM 规则：免责声明/敏感词/转人审）    │
│                  ▼                                                  │
│              Memory Writer（画像/偏好/笔记写入） → END               │
└──────────────┬──────────────────────────────┬──────────────────────┘
               │  Function Calling / 工具       │  checkpoint / store
┌──────────────▼───────────────┐   ┌────────────▼─────────────────────┐
│ 工具层（Pydantic schema）      │   │ 记忆层                           │
│ Market 工具 · Research 工具   │   │ SqliteSaver（会话历史）           │
│ Risk 约束工具 · Memory 工具   │   │ SQLite Store（画像/持仓/偏好/笔记） │
└──────────────┬───────────────┘   └──────────────────────────────────┘
┌──────────────▼───────────────┐
│ 数据层：DataSource 抽象       │
│  akshare(主力) baostock(日线) │
│  tushare(可选) demo(兜底)    │
│  缓存 TTL · 重试 · 降级 · PIT │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ 模型网关：OpenAI 兼容多提供商 │
│ router: 快/便宜   deep: 强    │
└──────────────────────────────┘
```

### 3.4 分层职责表

| 层 | 内容 | 关键设计 |
|---|---|---|
| 接入层 | Streamlit / FastAPI+SSE | 演示用 Streamlit；主交付 FastAPI，端点可测、可接任意前端 |
| 服务层 | `/v1/chat`、`/v1/risk/questionnaire`、`/v1/review`、`/v1/history` | 审计日志每个请求落库；命中风险规则可进人审队列 |
| 编排层 | LangGraph StateGraph | Supervisor 路由、Subgraph fan-out/fan-in、有界审计回修、checkpoint |
| Agent 层 | Market / Research / Risk / Advisor | 角色单一职责；Research 内部并行子分析师 |
| 审计层 | Auditor + Compliance 闸门 | Auditor 可回修；Compliance 纯规则、0-LLM |
| 工具层 | Function Calling 工具集 | 每个工具 pydantic schema + docstring；结果 schema 校验 |
| 数据层 | DataSource 抽象 + 缓存 | akshare/baostock/tushare/demo；TTL 缓存、重试、降级、PIT 标注 |
| 记忆层 | 短期 checkpoint + 长期 Store | 画像/持仓/偏好/笔记；结构化字段带时间戳 |
| 模型层 | 多提供商网关 | 路由用小模型，研究/建议用强模型；API key 可配 |
| 基建 | config、日志、Docker、CI | pydantic-settings、structlog、pytest、docker-compose |

### 3.5 State 设计（LangGraph）

```python
class Claim(TypedDict):
    text: str
    kind: Literal["FACT", "CALCULATION", "INFERENCE", "CONDITIONAL"]  # 调研自 wyh22
    source: str | None          # 工具名 + 数据日期，如 "akshare:quote 600519@2026-09-04"

class AssistantState(TypedDict):
    messages: Annotated[list, add_messages]     # 会话（checkpoint 持久化）
    user_id: str
    intent: Literal["quote", "research", "portfolio", "risk", "chat"]
    risk_profile: RiskProfile | None            # {level C1..C5, score, horizon}
    holdings: list[Holding] | None
    research_results: list[ResearchReport]      # fan-out 产物，带 claims
    audit_issues: list[AuditIssue] | None       # Auditor 输出，可回修
    audit_round: int                            # 有界：max_audit_rounds=2
    compliance: ComplianceResult | None         # 0-LLM 闸门结果
    final_answer: str | None
```

Claim 四分类让 Auditor 能用确定性规则检查“推断是否被重述为事实”，这正是调研里最值得吸收的防幻觉结构。

---

## 4. 完整流程设计

### 4.1 主会话流程（单次请求）

```text
用户消息
  → 1 服务层：校验 user_id、落审计日志
  → 2 Supervisor 两段路由（规则 → 小模型结构化输出）
  → 3 分支执行：
        quote      → Market Agent（1 次取数）
        research   → Research Subgraph（3 分析师并行 → fan-in）
        portfolio  → 读画像持仓 → Research Subgraph per 标的（Send 并行）
        risk       → Risk Agent（问卷交互：答题 → 规则评分 → 写画像）
        chat       → 直接到 Advisor（只聊偏好/常识，不触发数据工具）
  → 4 Advisor：注入 risk_profile + holdings + prefs，按模板合成
       （结论摘要 → 证据(带日期/来源) → 画像适配 → 风险提示 → 免责）
  → 5 Auditor 审计：
        a) 每条数值是否有 tool source？  无 → 回修 or 删改
        b) FACT 是否实为 INFERENCE？     是 → 回修
        c) 是否出现 > as_of 日期的数据？ 是 → 回修（PIT 守卫）
        d) 是否给出“买入/卖出”指令？    是 → 合规改写
        回修最多 2 轮，仍不过 → 降级为“无法给出可靠结论 + 原因”
  → 6 Compliance 闸门（0-LLM）：追加免责、命中敏感规则 → 进人审队列
  → 7 Memory Writer：抽取偏好/持仓/新事实 → SQLite Store（带时间戳）
  → 8 SSE 流式返回（含 tools 轨迹、来源标注、degraded/compliance 状态）
```

### 4.2 冷启动（KYC）流程

```text
新用户 → 系统引导 → Risk Agent 逐题问卷（UI 按钮，避免 LLM 解析歧义）
  → 规则评分 10 题×1~6 → C1~C5 + 投资期限
  → 生成 constraints: {max_single_position, max_equity_ratio, horizon_note}
  → Memory Writer 写画像 → Advisor 输出“账户级参考框架”而非荐股
```

### 4.3 持仓分析并行流程（体现 LangGraph Send 价值）

```text
“分析我的持仓”
  → Supervisor 识别 portfolio
  → 从 Store 读 holdings（避免用户重复输入）
  → Send 为每只标的派发 Research 任务（并行，节流并发=3）
  → 各自产出 ResearchReport + claims
  → Advisor 按 risk_profile 计算集中度/相关约束（确定性）
  → Auditor 全量核对 → Compliance → 输出组合级结论
```

### 4.4 记忆召回流程

```text
新请求进入
  → checkpoint 载入本会话历史（短期）
  → Store 载入 user profile（风险/期限/偏好/持仓/notes）
  → Advisor prompt 注入画像摘要
  → 若用户问“我之前说过/上次的分析” → Memory 工具 recall_notes 检索
  → 结束后 Memory Writer 增量更新（不做整表覆盖）
```

### 4.5 降级与异常流程

```text
akshare 调用失败
  → 缓存命中？返回并标注 freshness
  → 重试 2 次（仅网络错误）
  → 切 baostock/tushare（按配置优先级）
  → 仍失败 → demo 数据源 + 明示“演示数据模式”
  → Market Agent 如实报告降级；Advisor 不允许把降级数据当真实数据引用
```

---

## 5. 完整技术栈（调研佐证版）

| 层 | 选型 | 理由与佐证 |
|---|---|---|
| 语言/环境 | Python 3.11+，uv 或 poetry | 生态一致性；竞品均 Python |
| 编排 | **LangGraph**（StateGraph + Send + checkpoint） | TradingAgents/wyh22/TrueWealth/jiangge89 全用它；状态显式、子图与回修可表达 |
| Agent 形态 | 子图 + 节点；研究用 fan-out/fan-in | wyh22 analyst_subgraph、TradingAgents analyst_execution |
| 会话/短期记忆 | LangGraph `SqliteSaver`（thread_id=user_id+session） | TradingAgents checkpoint resume；jiangge89 会话恢复 |
| 长期记忆 | SQLite Store：user profile / holdings / notes / facts | jiangge89 save_note/recall_notes + TrueWealth 双层记忆；字段带时间戳可审计 |
| 语义记忆/检索 | SQLite FTS5（MVP）→ pgvector/Chroma/Qdrant（P2） | jiangge89 混合检索动机：ticker 是精确匹配问题；MVP 不必上向量库 |
| 模型网关 | OpenAI 兼容客户端 + 分档配置 | TrueWealth LiteLLM 三档、TradingAgents deep/quick、FinRobot Director；国内 DeepSeek/Qwen/GLM 均兼容 |
| 默认模型 | router=GLM-4-Flash/Qwen-turbo；deep=DeepSeek-chat/Qwen-plus | 求职项目成本敏感；全部走 .env 可替换 |
| 工具层 | langchain-core `@tool` + pydantic v2 schema | 全项目统一 docstring 即 schema；结果校验防脏数据 |
| 行情/历史 | **akshare 主力 + baostock 日线** | akshare 覆盖广免 token；baostock 稳定、PIT 友好（wyh22 数据边界表） |
| 财务/公告/资讯 | akshare/新浪财务、巨潮公告、财联社快讯 | 均免费；统一 DataSource 抽象，tushare(可选) 同接口 |
| 兜底数据 | demo_source（内置样例） | 无网/接口挂演示必须可用（所有竞品演示翻车点） |
| 指标计算 | pandas + numpy 本地实现（MA/RSI/回撤/波动） | 确定性；不引入 TA-Lib 等编译依赖 |
| 后端 | FastAPI + sse-starlette + pydantic v2 | TrueWealth/wyh22/jiangge89 均 FastAPI；SSE 流式是 Agent 演示标配 |
| 演示 UI | Streamlit（首版）；React 可后补 | rahul 证明 Streamlit 成本最低；TrueWealth 的 React 太重，不作为 MVP |
| 数据库 | SQLite + SQLModel/SQLAlchemy（可选） | 零运维；审计/画像/队列一张库搞定 |
| 观测 | structlog + 中间件指标 + 可选 LangSmith | wyh22 Supervisor Trace 用 LangSmith；面试讲“每次工具调用可回放” |
| 测试 | pytest + respx(HTTP mock)；评测 JSONL | TrueWealth 100% 覆盖做法；wyh22 评测数据集做法 |
| 评测 | 黄金用例 + Agent 指标（路由/引用/PIT/完成率）+ 可选回测 | 评测与收益分离（见 §8） |
| 部署 | Docker Compose；CI=compile+import smoke+pytest+build | wyh22 CI 命令可直接借鉴 |
| 合规 | 规则表：免责模板、敏感词、仓位越界、指令性表述 | TrueWealth Compliance Officer 0-LLM；可进人审队列 |

---

## 6. Agent 角色详设

### 6.1 Market Agent（行情查询）

- 工具：`get_realtime_quote(symbol)`、`get_kline(symbol, period, as_of)`、`get_index_snapshot()`、`get_etf_quote(symbol)`。
- 系统提示红线：只回事实 + 数据时间；不解释、不建议、不预测；失败如实报告。
- 数据日期强制注入返回结构：`{data_as_of: ...}`，供 PIT 检查。

### 6.2 Research Agent（研究分析，内部 3 个并行子分析师）

| 子分析师 | 输入/工具 | 输出 |
|---|---|---|
| Fundamentals | 财务摘要、估值、行业对比 | 基本面要点 + claims(FACT) |
| Technical | K 线 → 本地指标（MA20/60、RSI、回撤） | 趋势判断 + claims(CALCULATION) |
| News/Sentiment | 公告/快讯聚合（可选情绪打分规则） | 事件摘要 + claims(INFERENCE 显式标注) |

> 3 个子分析师共享 Market Agent 的数据工具（工具复用，Agent 角色不复用），fan-out 并发跑，fan-in 汇成一份带 claims 的 ResearchReport。

### 6.3 Risk Agent（风险测评 + 硬约束）

- 10 题问卷，每题选项 1~6 分；评分纯规则（可单测：满分/零分/边界）。
- 输出 `RiskProfile` 与 `Constraints`：例如 C1~C5 对应权益比例上限、单标的仓位上限、期限提示。
- 对话引导由 LLM 负责（解释题目、安抚措辞），但**分数与等级永不经过 LLM 计算**。

### 6.4 Advisor Agent（建议合成）

- 输入：risk_profile + holdings + prefs + research_results + tool_results + sources。
- 输出固定模板：结论摘要 → 证据（每条带工具与日期）→ 画像适配（为何符合/不符合你的风险等级）→ 风险提示 → 免责声明。
- 三条硬性注入约束：合规层 > 风险层 > 引用层。

### 6.5 Auditor（审计回修）

- 检查项（尽量规则化，LLM 只做语义辅助判断）：
  1. 数值无 source → 要求补引用或删除；
  2. `kind` 标签与表述不符（推断写成事实）→ 改写；
  3. 数据日期 > as_of / 研究截止日 → 回 Market 重取；
  4. 评级与证据方向冲突、前后数字不一致 → 回 Advisor；
  5. 出现“买入/卖出/立即”等指令性表述 → 交 Compliance。
- 回修上限 2 轮；超限输出“暂无法可靠回答 + 失败原因”，而不是硬编。

### 6.6 Compliance 闸门（节点而非 Agent）

- 0-LLM 规则：免责追加、指令性词检测、未完成测评却输出个股建议 → 降级为引导测评、高风险话题（单只高波动标的满仓讨论等）→ 人审队列。
- 人审队列只是 API + SQLite 表（`review_queue`），不要求真实前端，但接口与表结构必须存在（面试可讲）。

---

## 7. 记忆与存储 Schema（SQLite）

```sql
-- 用户画像（长期）
users(user_id PK, created_at, risk_level, risk_score, horizon, prefs_json, updated_at)
holdings(user_id, symbol, name, qty, cost, updated_at, PK(user_id, symbol))
notes(user_id, note_type, content, ticker, created_at)     -- FTS5 索引
facts(user_id, fact_text, confidence, created_at)          -- 可审计事实

-- 会话与审计
threads(thread_id PK, user_id, created_at)
messages(thread_id, msg_seq, role, content, tool_calls_json, created_at)
audit_log(request_id PK, user_id, intent, nodes, latency_ms, degraded, compliance, created_at)
review_queue(id PK, request_id, reason, original_answer, status, reviewer_verdict, created_at)
```

记忆写入原则：**增量 + 时间戳，不覆盖历史**（用户改风险等级也保留旧值可查）。召回优先级：当前会话 checkpoint > 画像结构化字段 > FTS 笔记 > （P2）向量语义。

---

## 8. 评测方案（评测与收益分离）

### 8.1 Agent 评测（工程指标）

维护 15~20 条黄金用例 JSONL，覆盖：意图路由、单标的问答、持仓组合、风险约束改写、降级提示、跨会话记忆、指令性表述拦截。指标：

- Routing 准确率：意图是否被分到正确分支；
- Grounding：最终回答里每个数字能否在上游 tool result 找到；
- PIT：是否出现晚于 as_of 的数据；
- Completion：是否在 N 轮审计内给出合格回答；
- 调用成本/延迟：每次请求的模型调用次数与耗时。

### 8.2 三架构对照实验（加分项，直接借鉴 wyh22）

同一数据集跑三种配置并出对比报告：

1. 单 Agent + 全量工具；
2. 固定串行流水线；
3. 本文的动态 Supervisor 图。

输出 `raw_runs.jsonl + per_case.csv + summary`，证明“动态图的路由与引用质量/成本”为什么更好。这一实验在面试里是独一份的实证材料。

### 8.3 收益回测（仅扩展）

若做 PIT-safe 历史研究，评级后 N 日收益、方向命中率只作为“回测报告”，明确不写入“Agent 更准”的结论；MVP 阶段不做。

---

## 9. 与原始方案的映射与关键改动点

| 原始设想 | 终稿做法 | 为什么改 |
|---|---|---|
| 三个 Agent | 5 个角色（3 域 + Advisor + Auditor/Compliance） | 调研：建议合成与审计独立才能防自说自话（wyh22/TrueWealth） |
| Function Calling 接 akshare/tushare | DataSource 抽象 + 多源 + 缓存 + demo 兜底 | OpenBB/wyh22：稳定性靠抽象层，不靠单个源 |
| LangGraph 编排 | Supervisor 两段路由 + Subgraph fan-out + 审计回修图 | TradingAgents/wyh22：图的价值在并行与回退 |
| Memory 记住偏好持仓 | checkpoint + Store + notes/facts，带时间戳 | jiangge89/TrueWealth：两级分离、可审计召回 |
| 给个性化投资建议 | 输出“画像约束下的参考分析 + 证据 + 免责”，高风险转人审 | 合规差异点：指令性建议在规则层拦截（TrueWealth） |
| — | 确定性计算与 LLM 分离（指标/评分/风控规则） | 8 条共识第 1 条，最被低估也最好讲 |
| — | 模型分档网关 | 求职项目要省钱也要性能（TrueWealth/FinRobot） |
| — | 三架构对照评测 | 让“多 Agent 更好”从口号变成实验数据 |

---

## 10. 落地里程碑（约 2 周全职 / 3~4 周业余）

| 阶段 | 内容 | 关键产出 |
|---|---|---|
| P0 | 定 State/Claim/工具 schema；搭仓库与 CI | 可编译骨架 + 数据模型单测 |
| P1 | DataSource：akshare/baostock/demo + 缓存重试降级 | 数据层测试通过（不碰网） |
| P2 | 工具层 + 指标计算；Market/Research 单跑 | Function Calling 跑通，指标有断言 |
| P3 | Supervisor 路由 + Research Subgraph fan-out + Advisor | 命令行能回答单标的/持仓问题 |
| P4 | Risk 问卷 + 画像 Store + Memory Writer + 召回 | 冷启动与跨会话记忆闭环 |
| P5 | Auditor + Compliance + 人审队列 + FastAPI/SSE | 审计回修可见，端点全通 |
| P6 | 黄金用例评测 + 三架构实验 + Streamlit + README + 面试材料 | 演示脚本、评测报告、简历素材 |

---

## 11. 竞品启示对照表（写 README/面试用）

| 我们做的 | 对标谁 | 我们比它强在哪 |
|---|---|---|
| 对话式 KYC + 画像记忆 | TradingAgents/FinRobot | 它们是“一次性研究”，我们记住用户 |
| A 股多源 + demo 兜底 | TradingAgents-CN/AStock 系 | 不只换数据源，有抽象层、PIT、评测 |
| Auditor + 0-LLM Compliance | TrueWealth-AI | 规模更小、全链路可两周落地，有 A 股数据 |
| 确定性计算与 LLM 分离 | ai-hedge-fund/wyh22 | 贯穿指标/评分/风控全部数值路径 |
| 三架构对照评测 | wyh22 | 复制其实验思路到对话投顾场景 |

---

## 12. 参考链接

- [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)（Apache-2.0）
- [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)（MIT，教育用途）
- [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot)（Apache-2.0）
- [wyh22/multi-agent-trading](https://github.com/wyh22/multi-agent-trading)（Apache-2.0，基于 TradingAgents，含 NOTICE）
- [Md-Emon-Hasan/TrueWealth-AI](https://github.com/Md-Emon-Hasan/TrueWealth-AI)（MIT）
- [Jiangge89/trading-agent](https://github.com/Jiangge89/trading-agent)
- [rahul-jajala/ai-financial-research-agent](https://github.com/rahul-jajala/ai-financial-research-agent)
- [Colin579M/AStock-AI-Agent](https://github.com/Colin579M/AStock-AI-Agent)
- [UFund-Me/Qbot](https://github.com/UFund-Me/Qbot)
- [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB)
- OpenBB Docs：MCP Server、Agents Integration、Agent Rita

> 复用注意：若后续直接 fork 或摘抄 Apache-2.0/MIT 代码，保留 LICENSE 与 NOTICE 声明；本设计仅引用架构思路，不复制实现。
