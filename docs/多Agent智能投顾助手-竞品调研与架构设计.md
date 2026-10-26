# 金融 Agent 项目调研与设计参考

调研时间：2026-09-07。以下仓库信息和 star 数只代表当时的页面状态，后续可能变化。

## 调研目的

当时准备做的原型只有行情、研究和风险三个 Agent。实际比较其他项目后，发现金融类 Agent 的主要问题不只在于模型能力，还包括数据时效、工具权限、用户记忆、输出审计和异常降级。调研用于确定哪些结构应该保留，哪些功能第一版可以不做。

## 仓库概况

| 项目 | 当时 star | 主要方向 |
|---|---:|---|
| TauricResearch/TradingAgents | 102.8k | 多角色交易研究 |
| OpenBB-finance/OpenBB | 72.7k | 金融数据平台 |
| virattt/ai-hedge-fund | 63.3k | AI 基金模拟 |
| UFund-Me/Qbot | 18.5k | 量化投研平台 |
| AI4Finance-Foundation/FinRobot | 7.9k | 金融 Agent 平台 |
| wyh22/multi-agent-trading | 12 | A 股多 Agent 研究 |
| Md-Emon-Hasan/TrueWealth-AI | 8 | 对话式金融顾问 |
| Colin579M/AStock-AI-Agent | 3 | A 股版 TradingAgents |
| Jiangge89/trading-agent | 1 | 研究与模拟交易 |
| rahul-jajala/ai-financial-research-agent | 0 | 单 Agent 研究助手 |

star 数主要用于筛选阅读对象，不代表代码质量。A 股和对话投顾类小项目对本项目更直接，因此阅读 README 和源码的时间更多。

## 各项目的主要做法

### TradingAgents

项目用 LangGraph 串起分析师、研究员、交易员、风控和组合经理等角色。分析师从基本面、新闻、情绪和技术面收集信息，多空双方按固定轮次讨论，最后生成交易提案和组合决定。状态贯穿整个流程，支持断点续跑和决策记忆。

值得借鉴的是角色边界、状态传递和 checkpoint。直接照搬的主要问题是成本：一场完整研究会调用很多次模型，而且流程面向单标的和单日决策，没有用户画像、风险问卷和长期对话记忆。它也会直接输出买卖与仓位意见，与本项目的合规边界不同。

### wyh22/multi-agent-trading

这是 TradingAgents 的 A 股改造版，流程改成分析师并行、多空讨论、组合经理和独立 Decision Auditor。审计发现事实无来源、口径冲突或时点越界时，会把问题发回对应的数据节点重新取证，并限制最大审计轮次。项目还使用 Qdrant 做混合检索，SQLite 保存会话和研究版本，FastAPI 提供网页对话。

这个项目对 AdaptFin 影响最大。Agent 不必把所有步骤都交给模型，确定性计算可以下沉到 Python；审计发现的问题需要指出具体节点和原因，不能只返回一句“重新回答”。

它的功能面也比较大，包括 RAG、版本回滚、回测和复杂研究子图。个人项目如果全部照搬，开发周期会失控，因此 AdaptFin 只保留与对话投顾直接相关的部分。

### TrueWealth-AI

项目有多个 LangGraph Agent，但很多关键步骤不是由 LLM 完成：

- 常见意图先通过规则判断，未命中才调用分类模型。
- 组合指标使用 pandas/numpy 计算。
- 合规检查使用固定规则，检查输入、输出和免责声明。
- Due Diligence 节点核查回答是否有数据依据，并限制修订次数。
- 高风险或无依据的回答可以进入人工复核队列。

它体现了“模型负责语言，代码负责确定规则”的拆分方式。缺点是角色数量偏多，部分节点像预留接口；美股数据和较多基础设施也不适合直接作为 A 股项目的基础。

### Jiangge89/trading-agent

这个项目把流程分为 Supervisor、Research/Trading Agent、确定性风控和人工批准。模型可以提出交易建议，但现金、单标的仓位和订单有效期等限制由代码强制执行，真正执行前还要通过 `interrupt()` 等待用户确认。

这种做法对“建议”和“执行”的边界很明确。AdaptFin 不接交易，但同样保留模型提议、规则检查和用户确认的层次，例如风险测评必须由用户作答，风险和合规约束不能由模型随意放宽。

### FinRobot

FinRobot 将金融 Agent、模型算法、数据与运维分层，并提供分析、图表和报告等工具。它更像研究平台，适合观察大型系统中的模块划分和 Agent 注册方式。

对本项目来说，这层平台化抽象暂时没有必要。SQLite、本地工具和单服务已经足够支撑当前规模，过早增加任务调度器、Agent 注册中心和模型适配层会增加维护成本。

### ai-hedge-fund

新版把基金配置、数据客户端、模拟券商、风险控制和模型注册拆成多种接口，基金行为由配置描述，可在历史数据上运行。大量使用 Protocol 和可替换实现，适合持续扩展。

这个方向面向基金模拟和美股数据，和普通用户对话投顾不同。可借鉴的是数据客户端和模型客户端要易于替换，不必在业务节点里直接依赖某个供应商。

### OpenBB、Qbot 和其他项目

OpenBB 的核心是统一数据接口，同时提供 Python、REST、CLI 和 MCP 等访问方式。它的数据层设计值得参考，但完整平台不适合作为小项目底座。

Qbot 覆盖数据、策略、回测、模拟和实盘，功能完整，也说明全栈量化平台的工程范围很大。AdaptFin 因此不把回测和策略研究放进第一版。

TradingAgents-CN、AStock-AI-Agent 等项目通常以 TradingAgents 为骨架，替换 A 股数据源和中文提示词。单纯换数据源不足以形成独立设计，用户画像、风险测评、记忆和审计更符合本项目的目标。

rahul-jajala 的单 Agent 原型结构简单，适合快速验证工具调用和 Streamlit 展示，但缺少并行研究、长期记忆和输出审计。

## 调研得到的设计原则

### 1. 确定性逻辑不要交给模型

技术指标、问卷评分、仓位约束和日期比较都有唯一答案，应该由代码完成。模型负责选择工具、解释结果和组织语言。这样可以做单元测试，也减少模型算术波动。

### 2. 路由和执行分开

Supervisor 只判断请求类型和需要的上下文，Market、Research、Risk 各自处理业务。所有请求都经过同一张大图不等于所有节点都要执行，固定跑全套研究会产生不必要的调用。

### 3. 审计节点不能由生成节点兼任

Advisor 生成回答后再由 Auditor 检查。审计只检查有明确规则的内容，例如免责声明、数字来源和日期边界；发现问题时允许有限次数回修，避免形成无限循环。

### 4. 数据层要处理失败

真实行情接口会超时、限流、改字段或暂时不可用。只写一个 `akshare.query()` 包装函数不够，需要统一的来源接口、缓存、重试、降级和来源标记。demo 数据源同样承担实际职责，它保证测试和离线演示不依赖外部服务。

### 5. 模型按任务分档

意图分类可以使用较小、较快的模型，复杂研究和最终回答使用能力更强的模型。模型地址和名称通过环境变量配置，避免业务代码绑定单一供应商。

### 6. 会话和长期画像分开

会话状态需要保存消息、问卷进度和中间结果，长期画像只需要用户风险等级、持仓、偏好和历史记录。两者用途不同，放在同一个大 JSON 中会导致覆盖和清理问题。

### 7. 评测指标和投资收益分开

项目需要评测路由是否正确、回答是否有证据、是否带风险声明、失败能否降级，而不是用几天的股票涨跌判断系统能力。收益回测需要严格的历史时点和交易成本假设，不属于当前版本。

## 对 AdaptFin 架构的影响

原始设想是三个 Agent 加 LangGraph。最终实现保留了三个业务域，并增加了 Supervisor、Advisor、Auditor 和 Memory Writer。具体变化如下：

| 原设想 | 实际实现 | 原因 |
|---|---|---|
| 研究、行情、风险三个 Agent | 再增加 Supervisor、Advisor 和规则节点 | 请求分派、最终回答和审计需要独立边界 |
| 直接调用 akshare/tushare | 统一 DataSource 层 | 便于缓存、重试、降级和替换来源 |
| 用提示词约束风险 | 问卷评分和仓位上限由代码计算 | 避免模型自行放宽风险条件 |
| 聊天历史当记忆 | checkpoint 加用户画像存储 | 会话上下文和长期资料的生命周期不同 |
| 只输出投资建议 | 输出带证据的参考分析 | 数据可能过时，项目也不具备投顾资质 |
| 只验证功能能跑 | 增加夹具测试和三架构评测 | 需要知道错误发生在哪一层，以及多节点是否真的有用 |

## 最终选择

- 编排：LangGraph `StateGraph`、`Send`、checkpoint。
- 模型：OpenAI 兼容网关，router 与 deep 两档配置。
- 数据：demo、akshare、baostock、tushare 适配器，统一缓存和降级。
- 存储：SQLite 保存画像与会话，偏好事实保存 embedding。
- 服务：FastAPI + SSE，Streamlit 用于本地演示。
- 测试：pytest，模型和网络路径使用 fake gateway。

这个方案没有追求最多 Agent 或最多功能。第一版要实现的是可以解释、可以测试、断网仍能演示的投顾研究流程。

## 参考链接

- [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)
- [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot)
- [wyh22/multi-agent-trading](https://github.com/wyh22/multi-agent-trading)
- [Md-Emon-Hasan/TrueWealth-AI](https://github.com/Md-Emon-Hasan/TrueWealth-AI)
- [Jiangge89/trading-agent](https://github.com/Jiangge89/trading-agent)
- [rahul-jajala/ai-financial-research-agent](https://github.com/rahul-jajala/ai-financial-research-agent)
- [Colin579M/AStock-AI-Agent](https://github.com/Colin579M/AStock-AI-Agent)
- [UFund-Me/Qbot](https://github.com/UFund-Me/Qbot)
- [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB)
