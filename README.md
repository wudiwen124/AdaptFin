# AdaptFin

AdaptFin 是一个面向 A 股的中文投资研究助手。用户可以通过网页完成风险测评、查询行情、分析个股与持仓，并在后续对话中继续使用自己的风险等级、偏好和持仓记录。

项目采用 LangGraph 组织多个执行节点，行情、财务和公告数据通过工具调用获取；模型生成的内容还会经过规则审计。系统只提供研究参考，不接入实盘交易，也不输出指令性买卖建议。

## 主要功能

- 支持股票、ETF 和主要指数的行情、日 K、估值、财务摘要及公告查询。
- 研究任务会分别处理基本面、技术面和资讯信息，最后结合用户风险画像生成回答。
- 内置 10 题风险测评，风险等级和仓位约束由 Python 规则计算。
- 用户可以维护持仓；对话中提到的持仓和偏好会写入本地记忆。
- 支持多轮指代消解、跨会话检查和基于 `BAAI/bge-m3` 的语义记忆召回。
- 工具返回的数据会保留来源，审计节点检查数字出处、免责声明、指令性表述和时点越界。
- 提供 Streamlit 网页、FastAPI/SSE 接口、命令行脚本和 Docker 部署方式。

## 架构

主流程由 `Supervisor` 判断请求类型，再进入对应的处理分支：

```text
用户请求
  -> Supervisor
     -> Market       行情查询
     -> Research     基本面 / 技术面 / 资讯并行研究
     -> Risk         风险问卷、评分和约束
     -> Portfolio    读取持仓后并行研究
     -> Chat         普通对话
  -> Advisor          结合画像、记忆和证据生成回答
  -> Auditor          规则审计，必要时有限次数回修
  -> Memory Writer    写入持仓、偏好和会话状态
```

当前实现中，Market、Research、Risk、Advisor 和 Supervisor 是五个 LLM 角色；研究角色内部包含三个并行分析师。Auditor 和 Memory Writer 是规则或存储节点，不调用大模型。

数据和记忆分别存放在 SQLite 中：

- `data/advisor.db`：用户画像、持仓、风险历史、偏好记忆和审计记录。
- `data/checkpoints.db`：LangGraph 会话状态，用于恢复多轮对话。

## 运行环境

- Python 3.11 或 3.12
- Windows、macOS 或 Linux
- 使用真实行情时需要网络
- 使用对话功能需要一个兼容 OpenAI Chat Completions 的模型服务

复制 `.env.example` 为 `.env`，填写模型地址、密钥和模型名。`.env` 已在 `.gitignore` 中，不要提交到仓库。

```dotenv
LLM_API_KEY=your-key
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ADVISOR_ROUTER_MODEL=glm-4-flash
ADVISOR_DEEP_MODEL=glm-4.5
ADVISOR_SOURCES_PRIORITY=demo
```

默认使用 `demo` 数据源，便于离线运行。需要真实行情时安装数据依赖，并把数据源改成 `akshare,baostock`：

```bash
python -m pip install -e ".[data]"
```

如果启用向量记忆，还需要配置 `EMBED_API_KEY`、`EMBED_BASE_URL`、`ADVISOR_MEMORY_EMBEDDER` 和 `ADVISOR_EMBED_MODEL`。

## 启动

安装基础依赖：

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

命令行检查数据链路：

```bash
python scripts/demo_cli.py 600519
```

启动网页：

```bash
python -m pip install -e ".[ui]"
python -m streamlit run app/ui/streamlit_app.py
```

启动 API：

```bash
python -m pip install -e ".[server]"
python -m uvicorn advisor.service.app:create_app --factory --port 8001
```

API 文档位于 `http://localhost:8001/docs`。端口被占用时可以换成其他端口。

Windows 下也可以双击 `启动AdaptFin.bat`，脚本会启动 Streamlit 并打开浏览器。

## 使用 Docker

项目包含 `Dockerfile` 和 `docker-compose.yml`，容器内服务监听 `8001` 端口：

```bash
docker compose up --build
```

启动后访问 `http://localhost:8001/docs`。Compose 会读取本地 `.env`，并将 `./data` 挂载到容器中，容器更新不会清除用户数据。

## 评测

仓库包含 105 个离线测试，模型和网络请求均使用 mock：

```bash
python -m pytest -q
```

`scripts/run_benchmark.py` 使用 9 条固定用例比较三种实现：单 Agent、固定流水线和当前 Supervisor 编排。真实模型的一次全量结果如下：

| 架构 | 完成 | 免责声明 | 内容有据 | 平均 LLM 调用 |
|---|---:|---:|---:|---:|
| single | 9/9 | 4/9 | 1/9 | 1.67 |
| fixed | 9/9 | 8/9 | 5/9 | 3.78 |
| supervisor | 9/9 | 9/9 | 9/9 | 3.00 |

完整结果见 `results/benchmark_real_three_arch_full.md`。该评测关注路由、完成率、合规和内容依据，不代表投资收益。

## 文档

- [竞品调研与架构设计](docs/多Agent智能投顾助手-竞品调研与架构设计.md)
- [项目设计说明](docs/多Agent智能投顾助手-项目方案.md)
- [开发记录](docs/执行记录.md)
- [文件索引](docs/项目文件说明.md)
- [新手项目讲解](docs/给新手的项目讲解.txt)
- [简历项目描述](docs/简历项目描述.md)
- [UI 测试清单](docs/UI_E2E清单.md)
- [Docker 安装记录](docs/Docker方案1-执行清单.md)

## 已知限制

- 当前主要覆盖 A 股，港股和美股尚未完整接入。
- 新闻和部分数据能力仍依赖 `demo` 数据源；真实接口可能受网络、限流和数据发布时间影响。
- 审计可以检查可计算的数字、日期和固定风险表述，不能保证所有语义推断都正确。
- 当前没有账号体系，`user_id` 主要用于本地数据隔离，不适合直接作为多租户服务上线。
- 风险测评、仓位约束和回答内容均属于研究辅助，不构成证券投资建议。
