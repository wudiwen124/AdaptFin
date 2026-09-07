# 多 Agent 智能投顾助手（求职向项目）

面向 Agent 应用 / 量化投研 / 后端方向的求职作品。

## 当前进度（2026-09-07）

- ✅ **P0 仓库骨架**：pyproject / 配置 / 领域 schema / LangGraph State 契约 / SQLite 画像存储雏形
- ✅ **P1 数据层**：DataSource 抽象 + demo 兜底 + akshare/baostock/tushare 适配（延迟导入）+ TTL 缓存 + 重试降级
- ✅ **确定性模块**：本地技术指标（MA/RSI/回撤/波动）、风险问卷评分 C1~C5 与约束
- ✅ **Function Calling 工具集**（Market 域 7 个工具，失败返回 `{"error": ...}`）
- ✅ **P2 编排已跑通**：Supervisor（规则预筛 + 便宜模型兜底）→ Market Agent / Research 并行 fan-out（Send+三分析师）/ Risk 问卷流 → Advisor → Auditor → Memory
- ✅ 真实 LLM 联调通过（智谱 GLM，OpenAI 兼容 Function Calling）
- ✅ **P3 完成**：Auditor 证据级审计（数字/日期出处）、持仓/偏好自动记忆、FastAPI+SSE 服务层与审计日志
- ✅ **P4-1 评测**：9 条黄金用例 + single/fixed/supervisor 三架构对照（离线报告在 `results/benchmark_report.md`）
- ✅ **P4-2 Streamlit UI**：测评表单 / 持仓管理 / 聊天（`app/ui/streamlit_app.py`）
- ✅ **P4-3 Docker 部署文件**（本机无 Docker，未实际构建）
- ✅ **P5-A 记忆可用**：facts/偏好/持仓注入 Advisor（读侧）、SqliteSaver 持久会话、跨轮证据清理
- ✅ **P5-B 回答补强**：名称→代码解析、证据缺口反问、最近对话注入
- ✅ **P5-C 真实评测**：GLM 跑 Supervisor 4 用例（`results/benchmark_real_supervisor.md`）
- ✅ **P6-A 指代消解**：线程级实体注册表，“它/走势呢”→ 自动解析标的后再取数（`orchestration/entities.py`）
- ✅ **P6-B 真实全量评测**：GLM 跑 Supervisor 9 用例，intent/免责 9/9（`results/benchmark_real_supervisor_full.md`）
- ✅ **P7-A 评测归零**：逐用例明细导出 → 定位失败为评测 checkpoint 污染；修复后真实 9/9（含内容）
- ✅ **P7-C LLM 偏好抽取**：规则覆盖不到的表达，低置信度丢弃
- ✅ **P7-D CI**：GitHub Actions（Python 3.11/3.12 + pytest）
- ✅ **P8-A 语义记忆召回**：同义词组 + 子串混合召回（换说法也能命中），向量接入点预留
- ✅ **P8-B 文档化**：全项目文件说明 + 执行记录逐阶段文件清单
- ✅ **P9-A 向量接入已启用**：SiliconFlow `BAAI/bge-m3`（1024 维）写侧存向量 + 读侧混合召回；真实请求验证通过
- ✅ **P10-A 真实三架构抽样**：single/fixed 各 3 用例 + supervisor 全 9（`results/benchmark_real_three_arch.md`）
- ✅ **P10-B UI 手测清单**：`docs/UI_E2E清单.md`
- ✅ **P11-A 数据导出/删除保护**：导出 JSON + 删除前自动备份（`data/backups/`）
- ✅ 91 个单元测试通过（LLM/网络路径全部离线 mock）
- ✅ **P12-A 三架构真实全量**：single 内容 1/9、fixed 5/9、supervisor 9/9（`results/benchmark_real_three_arch_full.md`）
- ✅ **P12-B 真实财务源**：akshare 业绩报表（600519 验证：ROE 16.75 / 毛利率 89.56）
- ✅ **P13-A 真实公告源**：巨潮 cninfo 公告（标题/日期/链接）
- ✅ **P13-B PIT 守卫**：识别研究截止日，Auditor 拦截晚于截止日的工具数据
- ✅ **P14-A 历史 K 线源头截断**：as_of 直接锁进工具请求，晚数据不进证据区
- ✅ **P14-B 公告时延核查**：cninfo 快照停在 2023-12（“最新公告”源需另选）
- ✅ **P15-A 最新公告源**：切换东方财富个股公告（600519 验证至 2026-08-15）
- ✅ **P16-A 时间硬校验**：公告 published_at / 财务报告期 ≤ as_of，晚于截止日即拦截
- ✅ **P16-B UI 端到端冒烟**：6 条核心链路离线全 PASS（`scripts/ui_e2e_smoke.py`）
- ✅ 105 个单元测试通过（LLM/网络路径全部离线 mock）
- ✅ **体验修复**：聊完自动刷新侧栏（持仓即时更新）、内部工具标签转“东方财富公告/行情数据源”、聊天区窄栏居中、用户消息右侧/回答左侧气泡（DeepSeek 风格）
- ⏳ P17：浏览器视觉手测（UI_E2E清单）、备份恢复/软删除
- ✅ **Docker 构建/启动验证通过**：Docker Desktop + 数据目录 `D:\25328\DockerDesktopWSL` + 国内镜像源；`docker compose up --build` 后 http://localhost:8001/docs 可访问（清单：[docs/Docker方案1-执行清单.md](docs/Docker方案1-执行清单.md)）

## 快速开始

```bash
python -m pip install -e ".[dev]"     # 基础依赖 + 测试
python -m pytest                      # 105 个离线单测
python scripts/embed_backfill.py      # 给存量记忆补向量（启用 embedder 后执行一次）
python scripts/demo_cli.py 600519     # demo 数据链路冒烟：行情 → 技术指标
python scripts/chat_cli.py            # P2 对话 CLI（需要 .env 里的 LLM key）
python -m pip install -e ".[server]"  # 服务层依赖
python -m uvicorn advisor.service.app:create_app --factory --port 8001   # FastAPI + SSE
python -m pip install -e ".[ui]"      # 演示 UI 依赖
python -m streamlit run app/ui/streamlit_app.py          # Streamlit 演示
python scripts/run_benchmark.py --arch all               # 三架构对照（离线）
python scripts/run_benchmark.py --arch supervisor --real --limit 4  # 真实 GLM 基准
python scripts/run_benchmark.py --arch supervisor --real            # 真实全 9 用例
docker compose up --build                                # 容器部署（需 Docker）
```

接真实行情时安装数据源依赖并配置 `.env`（参考 `.env.example`）：

```bash
python -m pip install -e ".[data]"
# .env: ADVISOR_SOURCES_PRIORITY=akshare,baostock
```

## 文档

- 📌 **竞品调研 + 完整架构/流程/技术栈设计（最新）**：[docs/多Agent智能投顾助手-竞品调研与架构设计.md](docs/多Agent智能投顾助手-竞品调研与架构设计.md)
- 📄 初版可行方案（求职包装视角）：[docs/多Agent智能投顾助手-项目方案.md](docs/多Agent智能投顾助手-项目方案.md)
- 📓 **从 0 到 P3 的完整执行记录（含问题/解决/原因）**：[docs/执行记录.md](docs/执行记录.md)

> 定位说明：本项目为“研究辅助 / 教育模拟”性质，不构成证券投资建议；不接入实盘交易。
