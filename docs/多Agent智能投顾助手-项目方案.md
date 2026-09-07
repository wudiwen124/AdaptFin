# 多 Agent 智能投顾助手 · 可行项目方案（求职向）

> 定位：**用一份能讲深、能演示、有真实数据接入的 Agent 作品，撬动 Agent 应用 / 量化投研 / 后端方向的实习与校招机会。**
>
> 合规边界：本系统定位为“投资研究辅助工具 / 教育模拟”，所有输出带免责声明，不提供“买入/卖出”式指令性建议。

---

## 0. 一句话方案

用 **LangGraph 编排三个各司其职的 Agent**（行情查询 / 研究分析 / 风险测评），以 **Function Calling** 对接 akshare 等真实行情数据，配 **短期会话 + 长期画像两级记忆**，最终由“建议生成器”在风险边界约束下输出**带数据出处、符合用户画像的个性化参考意见**。

---

## 1. 这个项目为什么能帮你找工作

### 1.1 岗位匹配度

| 目标岗位 | 项目展示的能力点 |
|---|---|
| LLM / Agent 应用工程师 | 多 Agent 编排、Function Calling、结构化状态、记忆系统、评测 |
| 量化投研（实习） | 真实行情数据接入、指标计算、投研信息聚合、风险约束建模 |
| 后端开发 | FastAPI、缓存/降级、SQLite 持久化、可测试性设计、部署 |
| 产品/解决方案 | 把模糊需求拆成 MVP、识别合规边界、演示叙事 |

### 1.2 简历上可写的结果（示例，中文）

> 独立设计并实现“多 Agent 智能投顾助手”：LangGraph 编排行情/研究/风险三个子 Agent，经 Function Calling 对接 akshare 真实 A 股行情并实现缓存降级；按用户风险画像与持仓生成带数据来源的个性化分析；跨会话记忆准确率在 10 组评测场景下 ≥90%。

### 1.3 为什么比“套壳聊天机器人”更值钱

1. **有真实数据闭环**：不是纯嘴炮，结论由工具返回的行情/财务数据支撑，可防幻觉。
2. **有工程纵深**：状态、路由、记忆、缓存、降级、评测，每一层都能被追问。
3. **有业务常识**：知道投顾有牌照边界，敢在方案里主动划合规红线——面试官很吃这点。
4. **有可演示性**：3 分钟能演完“测评 → 问行情 → 分析持仓 → 跨会话记住偏好”完整链路。

---

## 2. 目标与范围（先划界，再动手）

### 2.1 MVP 要做什么（做）

- 用户做一次 **8~10 题风险测评**，得到风险等级 C1~C5 与投资期限。
- 用户可查 A 股个股/ETF **实时行情、日 K、估值与财务摘要**。
- 用户可让系统**分析单只标的或整个持仓**，输出带来源、带风险约束的参考意见。
- 系统**记住**用户的风险等级、偏好（行业/风格/期限）、自选与持仓，支持跨会话。

### 2.2 明确不做（第一版砍掉）

- ❌ 自动下单 / 实盘交易对接（合规与成本双重原因）。
- ❌ 实时 tick 级行情（用日频 + 收盘快照足够讲故事）。
- ❌ 自建因子库、回测平台（这是下一个项目的事）。
- ❌ 美股/港股全市场（MVP 只做 A 股，架构预留扩展）。

### 2.3 一句话验收标准

> 新用户 5 分钟内完成：测评 → 问 3 个问题（行情/研报/持仓）→ 隔天再开，系统还记得他的风险等级和持仓，并能给出带约束和来源的分析。

---

## 3. 总体架构

### 3.1 架构图

```text
┌───────────────────────────── 用户层 ─────────────────────────────┐
│   Streamlit 演示 UI（或 FastAPI + Web 聊天，二选一，后续可切换）   │
└──────────────────────────────────┬────────────────────────────────┘
                                   │ /chat（SSE 流式）
┌──────────────────────────────────▼────────────────────────────────┐
│                        FastAPI 服务层                             │
│  会话入口 → 校验/鉴权(user_id) → 调用编译后的 LangGraph            │
└──────────────────────────────────┬────────────────────────────────┘
                                   │
┌──────────────────────────────────▼────────────────────────────────┐
│              LangGraph 编排层（单图 + Checkpointer）                │
│                                                                   │
│   START → Supervisor(路由) ──┬─→ Market Agent（只查行情）          │
│        │                     ├─→ Research Agent（行情+财务+指标）   │
│        │                     ├─→ Risk Agent（问卷/画像，无数据工具） │
│        │                     └─→ 一般对话 / 持仓聚合(并行 fan-out)  │
│        ▼                                                          │
│   Advisor（建议生成：风险约束 + 数据引用 + 合规话术）               │
│        ▼                                                          │
│   Memory Writer（抽取偏好 → 写长期画像）→ END                      │
└───────────────┬──────────────────────────────┬───────────────────┘
                │  Function Calling / 工具调用   │  读/写画像、持仓
┌───────────────▼──────────────┐   ┌────────────▼──────────────────┐
│   数据/工具层（Pydantic 化）   │   │  记忆层                       │
│  akshare ─┐                  │   │  SqliteSaver（会话短期记忆）    │
│  tushare ─┼─ 统一 DataSource  │   │  Store / SQLite（长期画像）     │
│  baostock ─┤  接口 + 缓存     │   │  user_id → {risk, prefs,       │
│  demo ────┘  + 重试/降级     │   │           holdings, watchlist} │
└──────────────────────────────┘   └────────────────────────────────┘
```

### 3.2 技术选型与理由

| 层 | 选型 | 为什么 |
|---|---|---|
| 编排 | LangGraph | 状态显式、图可观测、支持 checkpointer/store 记忆、原生支持 Send 并行；简历上比裸 LangChain Agent 更能体现工程理解 |
| 数据 | akshare（主）+ demo（兜底） | 免费免 token 起步最快；tushare 需要积分、免费额度低，作为 Phase 2 的备选数据源 |
| 工具协议 | OpenAI 兼容 Function/Tool Calling | Qwen / DeepSeek / GLM 均支持，便宜够用；模型可替换 |
| 记忆 | LangGraph `SqliteSaver` + `Store` | 短期会话走 checkpoint；长期画像走 key-value store，结构简单可解释 |
| 服务 | FastAPI + SSE | 流式输出、接口可测；UI 第一版用 Streamlit 加速 |
| 存储 | SQLite | 单机零运维，面试可讲清 schema；后续可平滑换 PostgreSQL |
| 评测 | pytest + 10~15 条黄金用例 | 证明“不是 demo 完就完”，可量化工具调用成功率与记忆准确率 |

---

## 4. 三个 Agent 的职责拆解（边界清晰是关键）

### 4.1 Market Agent｜行情查询

- **职责**：只负责“取数”，返回结构化行情，不做任何评价。
- **工具**：
  - `get_realtime_quotes(symbols)` → 最新价/涨跌幅/成交额
  - `get_kline(symbol, period, start, end)` → OHLCV
  - `get_index_snapshot()` → 大盘指数快照（用于上下文）
  - `get_etf_quote(symbol)`
- **系统提示词红线**：不解释、不建议、不预测；数据源不可用时如实报告并提示降级模式。
- **为什么单独拆**：工具权限最小化——一个只会取数的 Agent 不可能产生“我觉得会涨”的幻觉结论；同时便于统一缓存与失败处理。

### 4.2 Research Agent｜研究分析

- **职责**：对标的做多维度信息聚合，产出**带数据出处**的研究小结。
- **工具**：Market Agent 的行情工具 + 
  - `get_company_profile(symbol)`（行业、市值、主营业务）
  - `get_financial_summary(symbol)`（近 N 期营收/净利/ROE）
  - `get_valuation(symbol)`（PE/PB/股息率，标注数据日期）
  - `compute_indicators(symbol, kline)`（本地确定性计算 MA20/MA60/RSI/近一年最大回撤）
  - `search_news(symbol)`（新闻标题聚合，仅作信息罗列）
- **输出结构（Pydantic）**：`summary` + `fundamentals` + `valuation` + `trend` + `risks` + `data_as_of` + `sources[]`。
- **为什么单独拆**：研究是最容易堆 Prompt 的部分，独立成 Agent 便于单独迭代提示词、单独评测“是否引用数据”。

### 4.3 Risk Agent｜风险测评

- **职责**：通过问卷产出风险等级 C1~C5、投资期限、以及**建议生成阶段的硬约束**。
- **工具**：无行情工具（边界刻意收缩），只暴露：
  - `submit_risk_answers(answers)` → 评分与画像
  - `get_constraints(risk_level)` → 示例约束：单标的仓位上限、权益类比例上限、回撤提示
- **交互设计（重要工程决策）**：问卷**不在纯聊天里猜**，UI 提供选项按钮；后端按选项分值累加，规则可测，不依赖 LLM 算数。
- **评分示意**（10 题 × 1~6 分）：

| 总分 | 等级 | 建议画像（示意，非投顾意见） |
|---|---|---|
| 10–19 | C1 保守型 | 权益 ≤30%，偏好货基/债基/宽基 ETF |
| 20–29 | C2 稳健型 | 权益 30–50% |
| 30–39 | C3 平衡型 | 权益 50–70% |
| 40–49 | C4 积极型 | 权益 70–85% |
| 50–60 | C5 激进型 | 权益 ≤100%，单标的 ≤15% |

### 4.4 隐藏的第四个角色：Advisor（建议生成节点）

不单独设 Agent，而是编排图里的一个 **LLM 节点**，避免“每个 Agent 都在给建议”的边界混乱。它拿到三份输入后合成答案：

1. Risk Agent 的约束（仓位上限、期限）；
2. Research/Market 的结构化结果（必须逐条引用）；
3. 长期记忆里的用户偏好与持仓。

输出模板固定为：**结论摘要 → 数据支撑（带日期与来源）→ 与用户画像的适配分析 → 风险提示 → 合规声明**。

---

## 5. LangGraph 编排设计

### 5.1 State 定义（关键代码骨架）

```python
from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages

class AssistantState(TypedDict):
    messages: Annotated[list, add_messages]   # 会话消息（checkpoint 持久化）
    user_id: str
    intent: Literal["quote", "research", "risk", "portfolio", "chat", None]
    risk_profile: dict | None                 # {level, score, horizon}
    holdings: list[dict] | None               # [{symbol, name, qty, cost}]
    tool_results: dict                        # 本次会话工具结果缓存，供引用
    sources: list[str]                        # ["akshare:600519 2026-09-05 15:00"]
    final_answer: str | None
```

### 5.2 图结构

```text
START ──► Supervisor(LLM 路由)
             │
             ├── quote    ──► Market Agent ─┐
             ├── research ──► Research Agent┤
             ├── portfolio─► 持仓fan-out(并行研究每只) ► Research Agent
             ├── risk     ──► Risk Agent（多轮问卷循环）
             └── chat     ──► 通用对话（查画像）
                                │
                                ▼
                       Advisor（约束 + 引用 + 合规话术）
                                │
                                ▼
                        Memory Writer ──► END
```

### 5.3 三个编排细节（面试讲点）

1. **路由层为什么要独立**：Supervisor 只做意图识别与任务分派（可用小模型/规则 + LLM 混合），不参与业务判断；各 Agent 是可独立测试的子图，未来能单独升级。
2. **持仓分析用并行 fan-out**：`Send` API 把每只持仓并发丢给 Research Agent，再汇总进 Advisor——这是 LangGraph 相对串行 Chat Agent 最直观的卖点。
3. **图可回退**：任一 Agent 失败不导致整轮崩溃，Supervisor 捕获后走降级分支（见 6.4），并把失败原因写进 `sources` 供用户知情。

### 5.4 编译骨架

```python
from langgraph.graph import StateGraph, START, END

g = StateGraph(AssistantState)
for node in ("supervisor", "market", "research", "risk",
             "advisor", "memory_writer"):
    g.add_node(node, node_fn[node])

g.add_edge(START, "supervisor")
g.add_conditional_edges(
    "supervisor", route_by_intent,
    {"quote": "market", "research": "research",
     "risk": "risk", "portfolio": "research",
     "chat": "advisor"})          # 简化示例，实际另有回边
g.add_edge("market", "advisor")
g.add_edge("research", "advisor")
g.add_edge("advisor", "memory_writer")
g.add_edge("memory_writer", END)

app = g.compile(
    checkpointer=sqlite_saver,     # 短期：会话历史
    store=profile_store,           # 长期：用户画像/持仓
)
```

---

## 6. Function Calling 接真实行情（核心卖点，需讲透）

### 6.1 数据源选型对比

| 数据源 | 成本/门槛 | 稳定性 | 覆盖 | 结论 |
|---|---|---|---|---|
| akshare | 免费、无 token | 中（爬取聚合，接口会变） | A 股/基金/宏观广 | **MVP 主力** |
| tushare | 需 token，优质接口要积分 | 高（官方 API） | 财务数据强 | **Phase 2 补充**（财务/复权） |
| baostock | 免费 | 高 | 日线/财务，非实时 | 备选/离线 |
| demo 数据 | 无 | 100% | 模拟 | **演示兜底**，必须做 |

### 6.2 统一数据源抽象（面试常问“接口挂了怎么办”）

```python
class DataSource(Protocol):
    def realtime_quote(self, symbol: str) -> dict: ...
    def kline(self, symbol: str, period: str) -> list[dict]: ...
    def financial_summary(self, symbol: str) -> dict: ...

# datasources/akshare_source.py / tushare_source.py / demo_source.py
# 由 config 决定启用顺序：akshare → demo；tushare 有 token 时自动插入中间
```

每个 Agent 只依赖 `DataSource` 接口，不直接 import akshare——这是“可测试”和“可降级”的前提。

### 6.3 工具清单示例（docstring 即 LLM 看到的 schema）

```python
from langchain_core.tools import tool

@tool
def get_realtime_quote(symbol: str) -> str:
    """获取 A 股个股或 ETF 的最新行情。
    Args:
        symbol: 6 位证券代码，如 "600519" 贵州茅台、"510300" 沪深300ETF。
    Returns:
        JSON 字符串：最新价、涨跌幅、成交额、行情时间。
    只返回事实数据，不包含任何评价。"""
    row = datasource.realtime_quote(symbol)
    return json.dumps(row, ensure_ascii=False)

@tool
def compute_trend_indicators(symbol: str, kline: list[dict]) -> str:
    """基于本地 K 线数据确定性计算 MA20/MA60/RSI(14)/年化波动/近一年最大回撤。
    返回指标 JSON；本工具不做涨跌预测。"""
    ...
```

要点：**指标计算放本地函数而非让 LLM 心算**——确定性、可单测、杜绝“9.87 < 9.90 这种幻觉算错”。

### 6.4 缓存、重试与降级（工程感所在）

1. **缓存**：实时行情 TTL 60s、日 K 按日缓存、财务数据 TTL 1 天；同一次会话内 `tool_results` 复用，避免重复请求。
2. **重试**：网络类错误退避重试 2 次；解析类错误不重试（重试无用）。
3. **降级链**：akshare 失败 → 尝试 tushare → demo 数据，并在回复中明示“⚠ 当前为演示数据模式”。
4. **结果校验**：工具返回后做 schema 校验（价格 >0、时间非空），不合格直接标记失败，不让脏数据进入生成。

---

## 7. Memory 记忆设计（两级，能回答“用户怎么被记住”）

### 7.1 短期记忆：会话 checkpoint

- LangGraph `SqliteSaver` 持久化每轮 `messages` 与 state，支持多轮追问（“刚才说的那只是哪个？”）。
- thread_id 由 `user_id + session_id` 组成。

### 7.2 长期记忆：用户画像 Store

以 `user_id` 为 key 的 JSON Profile：

```json
{
  "user_id": "u_001",
  "risk": {"level": "C3", "score": 34, "updated_at": "2026-09-05"},
  "prefs": {
    "interest": ["消费", "宽基ETF", "高股息"],
    "horizon": "1-3年",
    "style_note": "厌恶频繁交易",
    "self_reported_knowledge": "入门"
  },
  "holdings": [{"symbol": "600519", "name": "贵州茅台", "qty": 100, "cost": 1450}],
  "watchlist": ["510300", "159915"],
  "facts": ["用户提到 2026 年有出国计划，资金 9 月前不能长期占用"],
  "updated_at": "2026-09-05T12:00:00+08:00"
}
```

### 7.3 记忆何时写入（Memory Writer 规则）

- 风险测评完成 → 写 `risk`；
- 用户明确说“关注 X / 不喜欢 Y / 持有了 Z / 一年内要用钱” → 结构化抽取后写入 `prefs` / `holdings` / `facts`；
- 持仓变化类消息用**追加 + 时间戳**，不覆盖历史（可审计）。

### 7.4 召回方式

每次 Advisor 生成前，把 Profile 关键字段注入系统提示词作为“用户上下文”；模糊偏好（如“我之前提过的目标行业”）在 Phase 2 用向量检索 `facts` 支持语义召回。MVP 阶段 JSON 字段匹配已足够演示。

### 7.5 面试讲点

- 为什么 checkpoint 和 Store 分开：一个是“对话上下文”，一个是“跨会话事实”，混在一起会互相污染。
- 隐私边界：所有数据本地 SQLite，无第三方上传；可在设置里一键清除画像。

---

## 8. 个性化建议的生成约束（防“乱给建议”）

Advisor 的 prompt 注入三层约束：

1. **合规层**（最高优先级）：不预测收益、不给“买入/卖出/持有”指令；只给“研究观点 + 用户可自行决策的参考结构”，结尾固定免责声明。
2. **风险层**：C1~C2 用户不输出个股激进策略；所有仓位建议 ≤ 该风险等级上限。
3. **引用层**：每个数字必须来自 `tool_results` 或 `sources`；无数据支撑的观点必须明说“这是公开信息的定性归纳，非数据结论”。

**输出模板示例**：

> 关于贵州茅台（600519）的现状：最新价 X（来源 akshare，2026-09-05），近一年最大回撤 Y%，PE 为 Z（数据日期……）。
> 按您的 C3 平衡型画像与“厌恶频繁交易”偏好，若该标的已占组合超 15%，可考虑再平衡思路，而非追加减仓动作。
> 以上为研究辅助信息，不构成投资建议；市场有风险，决策需自行判断。

---

## 9. 工程化与测试（拉开与其他候选人差距）

- **单元测试**：数据源 wrapper（mock 返回）、指标计算（已知数值断言）、风险评分（满分/零分边界）。
- **集成测试**：用 demo 数据源编译完整图，跑通“测评→查行情→分析持仓→跨会话召回”主链路。
- **黄金用例集（10~15 条）**：覆盖意图路由、防幻觉引用、风险约束、降级提示，人工标注期望行为后做回归。
- **可观测**：结构化日志记录每次工具调用耗时/成功与否；LangSmith（免费额度）记录 trace。
- **配置化**：模型名、TTL、数据源优先级全部走 `configs/settings.yaml`，演示时切 demo 数据一键完成。

---

## 10. 落地里程碑（按周）

| 阶段 | 内容 | 产出 | 预估 |
|---|---|---|---|
| P0 | 需求与数据源调研、风险问卷定稿 | 问卷 + schema | 0.5 天 |
| P1 | DataSource 抽象 + akshare 封装 + 缓存降级 + demo 源 | 可测试的数据层 | 2~3 天 |
| P2 | 行情/研究工具 + 指标计算 + 工具单测 | Function Calling 跑通 | 2 天 |
| P3 | 三个 Agent + LangGraph 单图 + Advisor | 命令行能跑完整链路 | 3~4 天 |
| P4 | Risk Agent 问卷交互 + 两级记忆 + 画像更新 | 跨会话记忆生效 | 2 天 |
| P5 | Streamlit/FastAPI + 流式输出 + 持仓并行分析 | 可演示 UI | 2~3 天 |
| P6 | 黄金用例评测 + README + 演示脚本 + 简历素材 | 交付物 | 2 天 |

总计 **约 2 周全职**，业余时间 **3~4 周**；若时间紧，砍 P5 的 FastAPI、砍 P6 评测，核心图必须先稳。

---

## 11. 建议仓库结构

```text
multi-agent-advisor/
├─ README.md / pyproject.toml / .env.example
├─ configs/settings.yaml          # 模型、数据源优先级、TTL
├─ app/
│  ├─ main.py                     # FastAPI + /chat(SSE)、/risk/questionnaire
│  └─ ui/streamlit_app.py         # 演示 UI
├─ src/advisor/
│  ├─ graph/{state,supervisor,memory,builder}.py
│  ├─ graph/agents/{market,research,risk,advisor}.py
│  ├─ tools/{market_data,indicators,risk_model}.py
│  ├─ datasources/{base,akshare,tushare,demo}.py
│  ├─ schemas/  prompts/  store/
│  └─ utils/{config,cache,logging}.py
├─ tests/                         # 单测 + 图集成 + 黄金用例
├─ data/                          # 本地缓存、示例持仓
└─ demo/                          # 演示脚本与截图
```

---

## 12. 面试演示脚本（3~4 分钟）

1. **开场 30s**：一句话定位 + 架构图（为什么三个 Agent、为什么图编排）。
2. **场景 A（意图路由 + 行情）**：问“贵州茅台今天收盘怎么样？”→ 看到 Market Agent 取数、来源标注。
3. **场景 B（风险约束）**：切到 C2 稳健画像，再问同一只股票 → Advisor 输出明显更保守、带上限提示。
4. **场景 C（持仓 + 并行）**：“分析我的持仓” → 3 只标的 fan-out 并行取数后汇总。
5. **场景 D（记忆）**：说“我还是学生，钱 2 年不用” → 隔天问“按我的情况，宽基和个股怎么分配参考结构” → 系统引用画像。
6. **收尾 20s**：把 akshare 接口手动掐断 → 展示降级提示。收在“真实系统里稳定性同样重要”。

---

## 13. 简历写法（中英 bullets）

**中文版**：
> 多 Agent 智能投顾助手｜LangGraph · Function Calling · akshare
> - 设计并实现 LangGraph 状态图编排“行情查询/研究分析/风险测评”三 Agent，Supervisor 意图路由 + Advisor 统一生成，持仓分析经 Send API 并行取数，较串行方案响应时间下降约 60%（P3 数据支撑可写）。
> - 封装 akshare 真实 A 股行情与财务接口为 Pydantic 化 Function Calling 工具，实现 TTL 缓存、重试与 demo 数据降级，杜绝 LLM 心算指标（指标全部本地确定性计算）。
> - 基于 SqliteSaver + LangGraph Store 设计两级记忆：会话 checkpoint 与跨会话用户画像（风险等级/偏好/持仓），画像字段级更新可审计。
> - 落地 8 题风险测评 → C1~C5 画像 → 建议生成硬约束（仓位上限、期限适配），输出固定合规话术模板。
> - pytest 构建 15 条黄金用例：路由、引用来源、风险约束、降级场景；工具成功率与跨会话记忆准确率纳入回归。

**英文版（要点）**：
> Multi-Agent Investment Research Assistant · LangGraph · Tool Calling · akshare
> - Built a 3-agent LangGraph orchestration (quote / research / risk) with intent routing and constraint-aware answer synthesis.
> - Exposed real A-share data via Function Calling tools with caching, retry and demo fallback; deterministic local indicator computation.
> - Implemented two-tier memory: SQLite checkpoints for sessions and a persistent user profile store for risk level, preferences and holdings.
> - Shipped 15 golden-scenario regression tests covering routing, source grounding, risk constraints and graceful degradation.

---

## 14. 面试高频追问与应答要点

| 追问 | 应答要点 |
|---|---|
| 为什么不用单 Agent + 一堆工具？ | 单一职责与权限边界：取数 Agent 无评价权、测评 Agent 无取数权，从结构上减少幻觉与越权；子图可独立升级评测 |
| 图编排比普通 Agent 强在哪？ | 状态显式可查、路由可控可回退、支持 Send 并行与 checkpoint；失败可定位到节点 |
| akshare 不稳定怎么办？ | 数据源抽象 + 缓存 + 重试 + demo 降级 + 来源标注；稳定性是接口问题不是 LLM 问题 |
| 怎么防 LLM 编数据？ | 指标本地计算、工具结果 schema 校验、生成要求逐条引用 sources、无数据则明说 |
| 记忆为什么这么设计？ | 短期（checkpoint）与长期（profile store）分开，避免对话上下文污染事实画像；结构化字段利于审计与召回 |
| 有合规问题吗？ | 有，主动说明：不提供指令性投顾建议、固定免责声明、数据本地化、产品定位研究辅助/教育 |
| 下一步扩展？ | RAG 研报库、模拟持仓回测、数据源上 tushare 财务、向量化语义记忆、多轮组合再平衡对话 |

---

## 15. 风险与可行性评估

| 风险 | 等级 | 缓解 |
|---|---|---|
| akshare 接口变更/限频 | 中 | 抽象层 + 缓存 + 双源 + demo 兜底 |
| 无网络演示环境 | 中高 | demo 数据源是**必做项**，不是备选 |
| LLM 输出不稳定 | 中 | 工具 schema 校验、固定输出模板、黄金用例回归 |
| 范围失控（想做回测/全市场） | 高 | 2.2 的“不做清单”写进 README，硬性砍 |
| 面试讲不清 | 中 | 每阶段产出“一页讲稿”：为什么这么设计 + 一个 trade-off |

结论：技术栈全部有成熟生态，无算法/算力瓶颈，**可行性高**。真正的风险在范围管理，所以 MVP 以“图能跑、数真实、人记得住、话敢合规”为四条硬线。

---

## 16. 后续扩展（写进“Roadmap”但别在第一版做）

- 研报 RAG：抓公开研报/公告做检索增强；
- 模拟交易与组合回撤追踪，反哺画像；
- tushare Pro 财务口径升级 + 复权处理；
- 语义记忆（向量化 facts）+ LangMem；
- 港股/美股源扩展、移动端；
- 多轮“再平衡建议”对话，与行情联动主动提醒。

---

> 文档版本：v1.0（2026-09-05）。定位面向求职作品集，若用于商业投顾服务，需补充持牌合规与数据授权评估。
