# TokenLens MVP 需求分析

---

# 第一部分：背景与定位

## 1. 项目背景

目前本机多个大模型客户端通过 **CC Switch** 统一管理和切换模型 Provider、Base URL、API Key 与模型配置，例如 Codex、Claude Code、CC GUI 等。

现有使用方式解决了"如何切换不同模型平台"的问题，但缺少统一的 API 使用监控能力，主要体现在：

* 无法统一查看不同模型的 Token 消耗。
* 无法快速判断哪个模型使用量最高。
* 无法统计每天、每月的大模型调用次数。
* 第三方中转平台的消费信息分散，需要分别进入平台后台查看。
* Codex、Claude Code 等客户端大量使用流式响应，普通日志工具难以准确统计。
* 无法直观看到请求耗时、失败次数等运行指标。
* 当 Token 使用突然增加时缺少提醒能力。

因此计划开发一个本地运行的轻量级监控工具 **TokenLens**，在不替代 CC Switch 的前提下，对经过 CC Switch 的大模型 API 请求进行统一监控和统计。

---

## 2. 产品定位

TokenLens 是一个：

> 本地运行的多模型 API Token、请求量和调用状态监控工具。

TokenLens 不负责替代 CC Switch。

两者职责划分如下：

| 系统        | 主要职责                                    |
| --------- | --------------------------------------- |
| CC Switch | Provider 管理、API Key 管理、Base URL 配置、模型切换 |
| TokenLens | 请求代理、Token 统计、模型统计、调用日志、延迟统计、Dashboard  |

整体调用关系：

```text
Codex
Claude Code
CC GUI
其他 AI 客户端
      │
      ▼
  CC Switch
      │
      ▼
TokenLens Proxy
      │
      ▼
真实 Provider API
```

例如：

```text
Codex
  ↓
CC Switch
  ↓
http://127.0.0.1:7788
  ↓
TokenLens
  ↓
https://api.xxx.com
```

TokenLens 在请求转发过程中完成监控，不改变客户端原有使用方式。

---

## 3. MVP 目标与成功标准

### 3.1 MVP 目标

MVP 阶段只解决一个核心问题：

> 能够准确记录并展示通过 TokenLens 的大模型 API 调用情况。

MVP 不追求完整的大模型网关能力，而是验证以下闭环：

```text
API 请求
   ↓
TokenLens 接收
   ↓
透明转发
   ↓
流式返回
   ↓
解析 Usage
   ↓
保存数据库
   ↓
Dashboard 展示
```

### 3.2 MVP 成功标准（可测试）

MVP 最终可以概括成：

> 一个运行在 Windows 本地的大模型 API 透明代理与 Token 监控工具，通过部署在 CC Switch 和真实 Provider 之间，在不影响 Codex、Claude Code 等客户端正常流式调用的情况下，实时采集 Provider、Model、Input Token、Output Token、Cache Token、Latency 和请求状态，并通过本地 Dashboard 提供统一的数据统计与调用日志查询能力。

具体成功标准（对应第 23 章验收测试场景）：

1. Codex / Claude Code 能正常通过 TokenLens 调用模型。
2. TokenLens 不明显影响流式输出体验（首字节延迟增量 < 50ms，见第 21.1 节）。
3. 能记录模型名称。
4. 能记录 Input Token。
5. 能记录 Output Token。
6. 能记录 Cache Token（Provider 返回时）。
7. 能记录请求次数。
8. 能记录请求耗时。
9. 能记录成功或失败状态。
10. 用户可以通过网页 Dashboard 查看统计数据。

---

# 第二部分：总体架构

## 4. 系统架构

TokenLens 部署在本机，位于 CC Switch 与真实 Provider 之间：

```text
Codex / Claude Code / CC GUI
            │
            ▼
        CC Switch
            │
            ▼
   TokenLens (127.0.0.1:7788)
   ┌────────┴────────┐
   │  Proxy 转发层    │
   │  Usage 解析层    │
   │  Statistics 层  │
   │  SQLite        │
   │  Dashboard     │
   └────────┴────────┘
            │
            ▼
   真实 Provider API
   (OpenAI Compatible / Anthropic)
```

## 5. 请求处理流程

每次请求经过 8 个环节：

```text
1. 接收请求（解析 {provider} 路由与请求体 model 字段）
   ↓
2. 请求预处理（重写 Header、注入 stream_options）
   ↓
3. 转发上游
   ↓
4. 流式/非流式透传响应
   ↓
5. 边转发边解析 Usage
   ↓
6. 落库 SQLite
   ↓
7. 统计聚合
   ↓
8. Dashboard 展示
```

核心原则：**转发优先，解析其次**。解析失败绝不能影响转发（例如 Usage 解析异常时丢弃统计、照常透传）。

## 6. 关键设计决策

以下决策是本次需求评审中确认的技术关键点，实现时必须遵守：

### 6.1 流式 Usage 自动注入

OpenAI Compatible 协议的流式响应默认**不返回 usage**，必须请求体携带 `stream_options: {"include_usage": true}` 才会在最后一个 chunk 中返回。

TokenLens 的决策：

> 当检测到请求体 `stream=true` 且未携带 `stream_options.include_usage` 时，自动注入该参数后再转发上游。

注入规则：

* 仅对 OpenAI Compatible 协议的 `/v1/chat/completions` 生效。
* 仅修改 `stream_options` 字段，请求体其余部分保持不变。
* Anthropic 协议流式默认返回 usage（`message_start` 与 `message_delta` 事件），无需注入。
* 上游不支持该参数的极少数情况：注入后若返回错误，按原样透传错误并记录（不重试）。

### 6.2 gzip 协商

客户端若携带 `Accept-Encoding: gzip`，上游会返回压缩内容，TokenLens 无法解析 JSON 提取 usage。

TokenLens 的决策：

> 转发请求时移除入站 `Accept-Encoding` 头，上游返回明文；转发响应时移除响应 `Content-Encoding` 头，保证客户端收到的内容与协商一致。

理由：TokenLens 与客户端、上游之间均为本地回环/局域网传输，明文传输的性能影响可忽略。

### 6.3 Header 重写规则

请求转发至上游时：

| 处理方式 | Header                                  |
| ---- | --------------------------------------- |
| 重写   | `Host` → 上游主机名                            |
| 移除   | `Accept-Encoding`（见 6.2）、`Content-Length`（按转发 body 重算） |
| 移除   | hop-by-hop 头：`Connection`、`Keep-Alive`、`Proxy-Authenticate`、`Proxy-Authorization`、`TE`、`Trailer`、`Transfer-Encoding`、`Upgrade` |
| 原样转发 | 其余所有 Header（含 `Authorization`）              |

响应转发至客户端时：移除 `Content-Encoding`、`Content-Length`、`Connection`、`Transfer-Encoding`（由 HTTP 框架重算），其余原样转发。

### 6.4 超时策略

| 超时类型 | 默认值  | 说明              |
| ---- | ---- | --------------- |
| 连接超时 | 10s  | 上游连接建立超时，超时返回 502 |
| 读超时  | 300s | 覆盖长流式响应，可在配置中修改 |

读超时按"相邻两次收到数据的时间间隔"计时，而不是请求总时长，避免长流式请求被误杀。

### 6.5 断连与流中错误

* **客户端中断**：立即取消上游请求，记录 `success=false`、`error_type=client_abort`，`status_code` 记录为已收到的状态码（或 499）。
* **流中 error chunk**：OpenAI 协议可能在流中返回 `{"error": ...}` 事件，此时记录 `error_type` 为错误对象中的 type 或 code，继续透传至流结束。
* **上游中途断开**：透传已收到的内容并正常结束响应流，同时记录 `error_type=upstream_abort`。

### 6.6 路径拼接与透传范围

* 配置中 `base_url` 约定**不含** `/v1` 后缀（例如 `https://api.example.com`）。
* 路由 `/{provider}/v1/*` 拼接为 `{base_url}/v1/*`，Query String 原样保留。
* `/{provider}/` 下的**所有路径均透传**（例如 `/v1/models`），但仅 `/v1/chat/completions` 与 `/v1/messages` 产生统计记录。
* 未匹配任何 provider 前缀的路径返回 404。

---

# 第三部分：功能需求

## 7. API 透明代理

支持客户端通过 TokenLens 请求真实模型 API。

例如：

```text
POST /openai/v1/chat/completions
```

TokenLens 转发至：

```text
https://真实Provider/v1/chat/completions
```

同时保证：

* Request Body 基本保持不变（唯一的例外是 6.1 节的 `stream_options` 自动注入）。
* Header 按第 6.3 节规则重写与转发。
* HTTP 状态码正确返回。
* Provider 错误信息正确返回。
* 支持普通响应。
* 支持 SSE / Streaming 流式响应，**逐 chunk 透传，不缓存完整响应**。

错误实现：

```text
Provider
   ↓
TokenLens 等待完整回答
   ↓
客户端
```

这种方式会破坏实时输出体验。

正确方式：

```text
Provider
   │
   ├── chunk 1 ──→ TokenLens ──→ Client
   ├── chunk 2 ──→ TokenLens ──→ Client
   ├── chunk 3 ──→ TokenLens ──→ Client
   └── chunk N ──→ TokenLens ──→ Client
```

### 7.1 SSE 解析细节

流式解析在转发的同时进行，遵循以下规则：

* **分块缓冲**：`data:` 行可能跨多个网络 chunk 到达，解析器必须将不完整的行保留在缓冲区，收到换行符后再处理完整行。
* **`[DONE]` 标记**：收到 `data: [DONE]` 表示流正常结束，停止解析。
* **事件类型**：仅解析 `data:` 行，忽略 `event:`、`id:`、`retry:` 等字段；每个 `data:` 行是一个独立 JSON。
* **usage 位置（OpenAI）**：携带 `include_usage` 时，usage 出现在最后一个 chunk（`finish_reason=stop` 且携带 `usage` 字段）；流中其他 chunk 的 usage 为 null。
* **usage 位置（Anthropic）**：`message_start` 事件携带 `input_tokens` 与 cache 字段，`message_delta` 事件携带 `output_tokens`；合并两者得到完整 usage。
* **解析失败**：单个 chunk JSON 解析失败或字段缺失时跳过该 chunk，不中断转发。
* **`data:` 行解析成功的标志**：仅当 JSON 中含 `usage` 或 `message_delta`/`message_start` 事件时触发统计落库。

### 7.2 请求体读取

TokenLens 需要读取请求体以提取 `model` 字段（用于统计落库）。

* 读取后**原样转发**，不修改除 `stream_options` 以外的任何字段。
* 请求体大小上限 32MB（超出返回 413），与 Anthropic / Claude Code 客户端限制一致，足以容纳长对话与图片附件（由最初 32KB 放宽）。

## 8. 协议支持

MVP 支持两套协议：

```text
OpenAI Compatible Adapter
Anthropic Adapter
```

### 8.1 OpenAI Compatible 协议

支持：

```text
/v1/chat/completions
```

兼容类似：

* OpenAI Compatible Provider
* DeepSeek
* OpenRouter
* 硅基流动
* 其他兼容 OpenAI API 的第三方平台

第一阶段不要求针对每家平台开发独立 Adapter，统一按照 OpenAI Compatible 协议处理。

### 8.2 Anthropic 协议

考虑 Claude Code 使用场景，同时支持：

```text
/v1/messages
```

两套协议即可覆盖 MVP 的主要需求。

## 9. Usage 解析与标准化

内部不直接依赖 OpenAI 或 Anthropic 的字段命名，定义统一的 Usage 标准模型：

```python
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
```

### 9.1 字段映射表

| 统一字段 | OpenAI 协议 | Anthropic 协议 |
| ---- | ---- | ---- |
| `input_tokens` | `usage.prompt_tokens` | `usage.input_tokens`（`message_start` 事件） |
| `output_tokens` | `usage.completion_tokens` | `usage.output_tokens`（`message_delta` 事件） |
| `cache_read_tokens` | `usage.prompt_tokens_details.cached_tokens` | `usage.cache_read_input_tokens` |
| `cache_write_tokens` | （无对应字段） | `usage.cache_creation_input_tokens` |
| `total_tokens` | `usage.total_tokens` | 同左 |

### 9.2 计算规则

* `total_tokens` 优先使用 Provider 返回值；未提供时计算 `input_tokens + output_tokens`。
* 不同 Provider 对 Cache Token 的定义可能不同，数据库中 Cache Read / Cache Write **单独保存**，不强制参与 total 计算。
* MVP Dashboard 展示时 Cache Read 与 Cache Write 合并显示为 `Cache Token`，后续版本再细分。

这样以后增加其他 Provider 时不会影响 Dashboard。

## 10. 请求记录

每次大模型调用生成一条 Request Record。

至少记录：

```text
request_id
provider
model

input_tokens
output_tokens
cache_read_tokens
cache_write_tokens
total_tokens

latency_ms

status_code
success
error_type

stream

created_at
```

建议数据结构：

```json
{
  "request_id": "req_xxx",
  "provider": "openai-compatible",
  "model": "gpt-5.6-sol",
  "input_tokens": 12500,
  "output_tokens": 3210,
  "cache_read_tokens": 8000,
  "cache_write_tokens": 1200,
  "total_tokens": 15710,
  "latency_ms": 8420,
  "status_code": 200,
  "success": true,
  "error_type": null,
  "stream": true,
  "created_at": "2026-08-14T09:00:00"
}
```

字段说明：

* `request_id`：优先取 Provider 响应中的 request id；未返回时 TokenLens 生成 `req_` 前缀的 UUID。
* `created_at`：请求开始时间（而非结束时间），保证日志顺序与请求顺序一致。
* 流式请求在流结束后（或断连时）一次性落库，避免多次写入。

## 11. Token 统计

* Input Token：优先读取 Provider 响应中返回的 Usage 数据（映射规则见第 9 章）。
* Output Token：同上。
* Total Token：见 9.2 节计算规则。
* Cache Token：见 9.2 节，数据库单独保存 cache_read / cache_write。

## 12. Dashboard

MVP 提供一个简单 Web Dashboard。

访问：

```text
http://127.0.0.1:7788/dashboard
```

### 12.1 数据刷新机制

前端采用**轮询**方式刷新数据：

* 每 5~10 秒调用一次 Monitor API 拉取统计数据。
* 不引入 WebSocket，MVP 保持简单；实时推送留到 V0.3。

### 12.2 首页指标

首页至少显示四个指标：

```text
┌────────────┬────────────┬────────────┬────────────┐
│ 今日请求数 │ 今日Token  │ Input Token│ OutputToken│
│    256     │   3.41M    │   2.73M    │   680K    │
└────────────┴────────────┴────────────┴────────────┘
```

### 12.3 模型使用排行

展示：

```text
今日模型使用量

gpt-5.6-sol       1.82M
claude-sonnet     0.91M
gpt-5.6-tera      0.42M
deepseek-chat     0.26M
```

排序依据：

```text
total_tokens DESC
```

### 12.4 Provider 使用排行

展示：

```text
Provider

Provider A      1.82M Token
Provider B      1.17M Token
Provider C      0.42M Token
```

便于发现主要 API 消耗来源。

### 12.5 Token 趋势

Dashboard 展示过去一定时间内 Token 消耗趋势。

例如：

```text
Token Usage

09:00   12K
10:00   48K
11:00   91K
12:00   34K
13:00   108K
```

MVP 可提供：

```text
最近24小时
最近7天
最近30天
```

三个时间范围。

### 12.6 延迟与错误概览

Dashboard 显示：

```text
平均请求耗时
今日错误数
错误率
```

例如：

```text
今日请求：382

成功：374
失败：8

错误率：2.09%
```

## 13. 请求日志

提供基础调用日志页面。

例如：

| 时间    | Provider   |         Model | Input | Output | Total | Latency | Status |
| ----- | ---------- | ------------: | ----: | -----: | ----: | ------: | ------ |
| 09:12 | provider-a |   gpt-5.6-sol |   12K |     3K |   15K |    8.2s | 200    |
| 09:08 | provider-b | claude-sonnet |    8K |     1K |    9K |    4.1s | 200    |
| 09:03 | provider-a |   gpt-5.6-sol |    2K |      0 |    2K |    1.2s | 429    |

支持按照以下条件过滤：

```text
Provider
Model
Status
时间
```

MVP 可以暂时不实现复杂全文搜索。

## 14. 延迟监控

每次请求记录：

```text
request_start_time
request_end_time
```

计算：

```text
latency_ms =
request_end_time
-
request_start_time
```

* 流式请求的 `latency_ms` 定义为从请求开始到最后一个 chunk 到达的时间。
* MVP Dashboard 显示平均请求耗时。

后续可以扩展：

```text
TTFT
P50
P95
P99
```

但这些不是 MVP 必须项。

## 15. 错误监控

TokenLens 应记录 Provider 返回的错误状态。

主要包括：

```text
400
401
403
404
408
429
500
502
503
504
```

数据库至少保存：

```text
status_code
success
error_type
```

其中 `success` 判定规则：HTTP 状态码为 2xx 且流正常结束（未断连、无流中错误）时为 true。

MVP Dashboard 显示：

```text
今日错误数
错误率
```

---

# 第四部分：数据设计

## 16. SQLite 数据库设计

MVP 使用 SQLite。

核心表：

```text
api_requests
```

建议结构：

```sql
CREATE TABLE api_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    request_id TEXT,

    provider TEXT NOT NULL,
    model TEXT,

    endpoint TEXT,

    stream BOOLEAN DEFAULT 0,

    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,

    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,

    total_tokens INTEGER DEFAULT 0,

    latency_ms INTEGER,

    status_code INTEGER,
    success BOOLEAN,

    error_type TEXT,

    created_at DATETIME NOT NULL
);
```

为查询增加索引：

```sql
CREATE INDEX idx_created_at
ON api_requests(created_at);

CREATE INDEX idx_model
ON api_requests(model);

CREATE INDEX idx_provider
ON api_requests(provider);
```

补充要求：

* 启用 SQLite **WAL 模式**，避免多客户端并发调用时的写锁冲突（SQLite 默认串行写，WAL 下读写不互斥）。
* 数据库文件位置：程序目录下 `data/tokenlens.db`。
* 字段定义与第 10 章请求记录保持一致，任何新增字段必须两处同步更新。

## 17. Provider 配置设计

MVP 不做复杂 Provider 管理系统，使用简单 YAML 配置即可。

配置文件位置：程序目录下 `config.yaml`。

例如：

```yaml
providers:

  provider_a:
    type: openai
    base_url: https://api.example.com
    api_key: xxx

  provider_b:
    type: anthropic
    base_url: https://api.anthropic.com
    api_key: xxx
```

规则：

* `base_url` 约定**不含** `/v1` 后缀（见 6.6 节路径拼接）。
* `api_key` 明文存储于本机配置文件，仅本机可读；转发后绝不写入日志与数据库。
* 配置在**启动时加载一次**，修改后重启 TokenLens 生效（MVP 不做热加载）。
* TokenLens 路由：

```text
/provider_a/v1/chat/completions
/provider_b/v1/messages
```

分别转发到对应 Provider。

## 17.1 CC Switch 集成

TokenLens MVP 不修改 CC Switch 本身。

采用：

> 修改 Provider Base URL

的方式接入。

原本：

```text
https://provider.example.com
```

修改为：

```text
http://127.0.0.1:7788/provider_a
```

TokenLens 再将请求转发至：

```text
https://provider.example.com
```

因此：

```text
CC Switch
     ↓
TokenLens
     ↓
真实 Provider
```

用户仍然通过 CC Switch 完成模型切换。

---

# 第五部分：接口设计

## 18. Proxy API

TokenLens 后端使用 FastAPI。

核心 API 可以划分为两类。

### 18.1 Proxy API

```text
POST /{provider}/v1/chat/completions

POST /{provider}/v1/messages
```

负责真正的大模型请求转发。

其他 `/{provider}/v1/*` 路径同样透传，但不产生统计记录（见 6.6 节）。

### 18.2 Monitor API

```text
GET /api/stats/summary
```

返回：

```json
{
  "requests": 328,
  "input_tokens": 2710000,
  "output_tokens": 630000,
  "total_tokens": 3340000,
  "errors": 5
}
```

模型统计：

```text
GET /api/stats/models
```

Provider 统计：

```text
GET /api/stats/providers
```

趋势：

```text
GET /api/stats/trend?range=24h|7d|30d
```

请求日志：

```text
GET /api/requests?provider=&model=&status=&from=&to=
```

支持分页参数 `limit`（默认 50）与 `offset`。

---

# 第六部分：技术架构与非功能需求

## 19. 技术架构

推荐：

```text
TokenLens
│
├── backend
│   │
│   ├── FastAPI
│   │
│   ├── Proxy
│   │
│   ├── Provider Adapter
│   │
│   ├── Usage Parser
│   │
│   ├── Statistics
│   │
│   └── SQLite
│
└── frontend
    │
    ├── Vue 3
    ├── Axios
    └── ECharts
```

## 20. 后端模块划分

建议结构：

```text
backend/
│
├── main.py
│
├── proxy/
│   ├── router.py
│   ├── stream_proxy.py
│   └── request_forwarder.py
│
├── providers/
│   ├── base.py
│   ├── openai.py
│   └── anthropic.py
│
├── usage/
│   ├── parser.py
│   ├── openai_parser.py
│   └── anthropic_parser.py
│
├── models/
│   └── usage.py
│
├── database/
│   ├── database.py
│   └── models.py
│
├── statistics/
│   └── service.py
│
└── api/
    ├── stats.py
    └── requests.py
```

其中：

```text
proxy
```

只负责：

> 请求转发。

```text
providers
```

负责：

> 不同 API 协议差异。

```text
usage
```

负责：

> 将不同 Provider 的 Usage 转换为 TokenLens 统一格式。

## 21. 非功能需求

### 21.1 性能指标

* 代理引入的**首字节延迟增量 < 50ms**（本地回环场景下流式体验无感知）。
* chunk 转发**不做全量缓冲**，单个 chunk 在解析后立即透传。
* Dashboard 轮询间隔 5~10 秒，Monitor API 响应时间 < 200ms（SQLite 单表万级记录场景）。

### 21.2 隐私设计

TokenLens 的定位应坚持：

> Local First。

默认所有数据保存在：

```text
本机 SQLite
```

MVP 默认不保存：

```text
Prompt 正文
模型完整回答
Authorization Header
API Key
```

日志只保留：

```text
Provider
Model
Token
时间
Latency
Status
```

避免因为监控工具本身产生新的隐私问题。

尤其是：

```text
Authorization: Bearer sk-xxxx
```

绝不能写入日志。

### 21.3 Windows 运行方式

MVP 第一阶段甚至可以直接：

```bash
python main.py
```

运行。

启动：

```text
TokenLens Backend
          ↓
127.0.0.1:7788
```

浏览器：

```text
http://127.0.0.1:7788
```

第二阶段再加入：

```text
PySide6 / pystray
```

实现 Windows 系统托盘。

最终：

```text
TokenLens.exe
```

---

# 第七部分：范围与路线

## 22. MVP 范围界定

### 22.1 必须实现

MVP 第一阶段实现：

* API 透明代理（第 7 章）
* OpenAI Compatible 协议支持（第 8.1 节）
* Anthropic 协议支持（第 8.2 节）
* 请求记录与 Token 统计（第 10、11 章）
* Dashboard 与请求日志（第 12、13 章）
* SQLite 数据存储（第 16 章）
* Provider YAML 配置（第 17 章）

### 22.2 暂不实现

为了控制开发范围，以下功能不进入第一版：

* 不替代 CC Switch。
* 不开发模型切换。
* 不开发复杂 API Key 管理。
* 不做账号系统。
* 不做云端同步。
* 不做多人协作。
* 不做权限管理。
* 不做完整 OpenTelemetry。
* 不做 Prompt 内容分析。
* 不保存完整 Prompt。
* 不保存完整模型回答。
* 不做复杂预算策略。
* 不做自动限流。
* 不做模型自动降级。
* 不做多设备同步。
* 不做移动端 App。

这样可以显著降低 MVP 复杂度。

## 23. 验收测试场景

MVP 完成时需通过以下场景测试（对应第 3.2 节成功标准）：

| # | 场景 | 预期结果 |
| - | ---- | ---- |
| 1 | 非流式 `chat/completions` 请求经代理转发 | 响应内容与直连一致，usage 正确落库 |
| 2 | 流式 `chat/completions` 请求经代理转发 | 客户端逐字输出无卡顿，首字节延迟增量 < 50ms |
| 3 | 流式请求未携带 `include_usage` | TokenLens 自动注入，最后一个 chunk 的 usage 正确记录 |
| 4 | Anthropic `/v1/messages` 流式请求 | `message_start` + `message_delta` 合并后的 usage 正确 |
| 5 | Provider 返回 429 / 500 | 错误状态码与 error_type 正确记录，Dashboard 错误率正确 |
| 6 | 客户端中断流式请求 | 上游请求被取消，记录 `client_abort`，TokenLens 不崩溃 |
| 7 | 请求体含 `Accept-Encoding: gzip` | 上游返回明文被正确解析，客户端收到的响应正常 |
| 8 | Dashboard 统计数字 | 与 SQLite 中的记录聚合结果一致 |
| 9 | 日志与数据库检查 | 无 Authorization 头、无 API Key、无 Prompt 正文 |
| 10 | TokenLens 重启 | 历史数据完整保留，统计正常 |
| 11 | CC Switch 指向 TokenLens 后 | Codex / Claude Code 正常工作，模型切换不受影响 |

## 24. 风险清单

| 风险 | 等级 | 说明与对策 |
| ---- | ---- | ---- |
| SSE 流式解析 | 高 | 分块缓冲、`[DONE]`、错误 chunk 等边界情况多，需要通过单元测试和端到端场景覆盖边界行为 |
| 多协议 Usage 字段差异 | 中 | 不同 Provider 字段命名不一致。对策：统一 Usage 标准模型（第 9 章）+ 独立 adapter 隔离 |
| 代理引入延迟 | 中 | 对策：逐 chunk 透传不做全量缓冲，性能指标见 21.1 |
| 上游超时/断连边界 | 中 | 对策：6.4 超时策略 + 6.5 断连处理 |
| SQLite 并发写 | 低 | 本地单用户但多客户端并发。对策：WAL 模式 |
| `include_usage` 注入兼容性 | 低 | 极少数 Provider 可能报错。对策：错误按原样透传并记录，不重试 |

## 25. 版本演进路线

MVP 验证成功后加入：

### V0.2

**费用统计（基础版已实现）**：模型价格规则和请求费用快照按人民币统计 `input cost + output cost + cache read cost + cache write cost`，展示今日消费、本月消费、模型消费排行、Provider 消费排行及未定价用量。阶梯价、账单对账和费用修正仍属于后续能力。

**项目来源**：支持 Codex、Claude Code、DocMind、RAG System 等来源区分。例如请求 Header `X-TokenLens-Client: codex`，最终可以分析"Codex 今天用了 3.2M Token"。

**预算提醒**：支持每日 Token 上限、每日费用上限、月度费用上限，达到 80% / 100% 触发 Windows 通知。

### V0.3

增加可观测性指标：

```text
TTFT
Tokens / Second
P50 Latency
P95 Latency
P99 Latency
429 次数
5xx 次数
```

进一步向真正的：

> LLM Observability

演进。

### 整体路线

```text
V0.1
API Proxy
+
Usage Monitor
+
Dashboard

          ↓

V0.2
Cost
+
Budget
+
Client / Project

          ↓

V0.3
TTFT
+
TPS
+
错误分析
+
告警

          ↓

V1.0
完整 Local LLM Observability Platform
```

因此第一版一定要控制住范围。

### MVP 核心闭环

```text
CC Switch
     ↓
TokenLens Proxy
     ↓
Provider
     ↓
Usage
     ↓
SQLite
     ↓
Dashboard
```

MVP 最关键的四个技术点只有：

```text
1. HTTP 透明代理

2. SSE Streaming 透明转发

3. 多协议 Usage 标准化

4. SQLite + Dashboard 统计
```

只要这四件事情做好，这个 MVP 就已经成立。
