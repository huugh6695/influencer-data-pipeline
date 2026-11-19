# AI 应用工程化 · 代码案例集

一组从实际项目里整理出来的**脱敏代码片段**，展示四类常见工程做法：数据采集流水线、AI Agent 服务、MCP 协议接入、外部 API 调用。

> 这是案例片段，不是可直接运行的完整项目。部分依赖文件与示例数据未随本仓库提供，见下方「运行说明」。

## 目录

| 目录 | 内容 | 关键点 |
|---|---|---|
| `01_达人库_数据采集` | 单条解析入库、并发队列消费、第二数据源补全、消费群体推断 | 队列状态机、断点续跑、幂等 upsert、推断置信度 |
| `02_微信AI助手` | AI Agent 服务：策略 → 记忆 → 模型 → 渠道 | FastAPI、Channel 抽象、SQLite 记忆、OpenAI 兼容接口 |
| `03_MCP接入` | 最小 MCP Server / Client | stdio + JSON-RPC 2.0 握手 |
| `04_API接入` | 飞书消息图片下载；大模型 chat / vision | PowerShell、urllib、base64 图片 |

## 入口与出口

**微信 AI 助手**
- 入口：`app/main.py` → `create_app()` → `POST /webhook/{channel_name}`
- 处理：`app/core/agent.py` → `Agent.handle()`（策略 → 记忆 → 模型 → 记忆）
- 出口：`runtime.channel.send()` → `app/channels/webhook.py`
- 另有 `GET /health`、`POST /api/send`、`GET /api/outbox`（后两个需要 `X-Admin-Token`）

**MCP**
- 入口：`server.py` 的 `main()` 读 stdin
- 出口：`send()` 写 stdout；`tools/call` 返回 `content[]`

**API 接入**
- 飞书：`feishu_fetch_image.ps1`，入参 `-MessageId`，出口为本地图片文件
- 大模型：`llm_client.py` 的 `chat()` / `vision()`

## 运行说明

**唯一开箱可跑的是 `03_MCP接入`**（纯标准库、无网络请求、无需凭证）：

```
cd 03_MCP接入
python client.py
```

预期输出为 `>>>` / `<<<` 的 JSON-RPC 报文，最后一行 `OK: MCP handshake + tool calls completed`。

**`02_微信AI助手`**：

```
pip install -r requirements.txt
cp .env.example .env          # 按实际情况填写，.env 不要提交
cd 02_微信AI助手
uvicorn app.main:app --host 127.0.0.1 --port 8100
```

默认 `CHANNEL=mock`，回复进入内存发件箱，可用 `GET /api/outbox` 查看；`LLM_BASE_URL` 默认指向本机 Ollama，没有本地模型时消息处理会调用失败。

**`01` 与 `04` 需要自备数据和凭证**：
- `01` 需要 `influencers.db`（含 `crawl_queue` 表）、`nuxt_parse.js`，以及 `data/sample_matched.csv`（列名见 `infer_audience.py`）；输出写到同目录 `data/`，可用 `SAMPLE_DATA_DIR` 覆盖。
- `04` 的飞书脚本需要 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`；`llm_client.py` 需要 `LLM_API_KEY`。

## 未随本仓库提供的文件

- `nuxt_parse.js`（页面解析脚本）、`influencers.db`（业务数据库）
- 向量检索相关 `vec_query.py` / `query.py` / `export.py`
- 填写后的 `.env`、任何真实业务数据与样例 CSV

## 安全与合规

- 凭证一律从环境变量读取，仓库内不含任何密钥；`.env.example` 只列键名，不含值。
- `01` 涉及第三方站点数据访问，此处仅作工程结构演示。实际采集前请确认目标站点的服务条款、robots 及数据使用授权，并自行控制请求频率。
- `02` 是通用 Webhook 服务端示例，不依赖任何特定即时通讯平台的私有协议。
- 同一组 `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` 在 `02`（默认本地 Ollama）与 `04`（默认云端兼容接口）里含义不同，分别运行时按需设置。

## 项目归属与数据说明

- 本仓库代码整理自作者参与的实际项目，此处为**脱敏后的片段**：已移除内部绝对路径、内部系统命名与具体业务选品，保留工程结构与真实第三方服务地址作为数据来源标注。
- `01` 中的 `chanmama.com` / `iesdouyin.com` 是采集链路的数据来源标注，不是接口调用示例；相关代码仅展示队列、解析、入库与推断的实现思路，运行前请自行确认数据使用授权。
- `influencers.db`、示例 CSV、任何真实业务数据与凭证均未包含在本仓库中。

## 说明

- 代码已去除解释性注释，只保留关键路径标注。
- 本副本已做脱敏：移除内部绝对路径与业务命名、改写登录态相关注释、将默认人设改为如实说明 AI 身份。

## 许可证

采用 MIT，见 `LICENSE`。版权行使用通用的 `the author(s)` 写法，GitHub 仓库归属以账号为准；如需写明具体署名，直接改 `LICENSE` 首行即可。
