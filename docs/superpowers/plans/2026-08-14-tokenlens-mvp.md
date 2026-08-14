# TokenLens MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 TokenLens MVP——运行在 Windows 本地的多模型 API 透明代理与 Token 监控工具（Python/FastAPI + Vue3 + SQLite），部署在 CC Switch 与真实 Provider 之间。

**Architecture:** FastAPI 单进程同时承载代理与监控：`/{provider}/v1/*` 路由透明转发至配置的上游 Provider（逐 chunk 透传 SSE，边转发边解析 Usage），落库 SQLite（WAL），`/api/*` 提供统计接口，Vite 构建的 Vue3 前端静态托管并以 5s 轮询刷新。

**Tech Stack:** Python 3.12、FastAPI、httpx（异步转发）、PyYAML、sqlite3 标准库、pytest + pytest-asyncio；前端 Vue 3 + Axios + ECharts + Vite（Node 22）。

**Spec:** `requestment.md`（2026-08-14 重构版，7 大部分 25 章）。计划中的每项要求均引自该文档章节。

## Global Constraints

- Python 3.12（Windows 用 `py -3.12` 创建 venv；venv 内解释器为 `.venv/Scripts/python.exe`）。
- 监听 `127.0.0.1:7788`（spec 第 21.3 节）。
- `base_url` 约定不含 `/v1` 后缀（spec 第 6.6 节），配置中若以 `/v1` 结尾则启动报错。
- 请求体上限 32KB，超出返回 413（spec 第 7.2 节）。
- 上游连接超时 10s；读超时 300s，按"相邻两次收到数据的时间间隔"计时（spec 第 6.4 节）。
- `success = 2xx 且 error_type 为 None`（spec 第 15 章）。
- 绝不落盘：`Authorization`/`x-api-key` 头、API Key、Prompt 正文、模型完整回答（spec 第 21.2 节）。
- 逐 chunk 透传，不缓存完整响应（spec 第 7 章）。
- 转发请求时移除 `Accept-Encoding`，转发响应时移除 `Content-Encoding`（spec 第 6.2 节）。
- 仅 `/v1/chat/completions` 与 `/v1/messages` 产生统计记录，其余 `/{provider}/v1/*` 路径透传不统计（spec 第 6.6 节）。
- 现有 Node.js 原型（`src/`、`test/usage.test.js`、README 中的 ModelMeter）**保留不动**，仅作为 SSE 解析逻辑参考，不参与 Python 实现。
- 提交信息格式：`feat:` / `fix:` / `test:` 前缀 + 简短英文描述。

---

### Task 1: 项目初始化与 FastAPI 骨架

**Files:**
- Create: `requirements.txt`
- Modify: `.gitignore`（追加 Python 条目）
- Create: `pytest.ini`
- Create: `backend/__init__.py`
- Create: `backend/main.py`
- Create: `tests/conftest.py`
- Create: `tests/test_health.py`

**Interfaces:**
- Produces: `backend.create_app(db_path=None, config_path=None, upstream_transport=None) -> FastAPI`，其中 `db_path`/`config_path` 为 `pathlib.Path | None`（默认取仓库根目录下 `data/tokenlens.db` 与 `config.yaml`），`upstream_transport` 为测试注入的 httpx transport；app 挂载 `/health` 路由，`app.state.client` 为共享 `httpx.AsyncClient`，`app.state.providers` 为 `dict[str, ProviderConfig]`（Task 5 填充）。
- Consumes: 无。

- [ ] **Step 1: 初始化 git 仓库**

```bash
cd /e/codex/MAPInfor/MAPInfor && git init
```

- [ ] **Step 2: 创建 venv 并安装依赖**

```bash
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install fastapi==0.115.0 uvicorn==0.30.6 httpx==0.27.2 pyyaml==6.0.2 pytest==8.3.2 pytest-asyncio==0.24.0
```

创建 `requirements.txt`：

```text
fastapi==0.115.0
uvicorn==0.30.6
httpx==0.27.2
pyyaml==6.0.2
pytest==8.3.2
pytest-asyncio==0.24.0
```

- [ ] **Step 3: 追加 .gitignore**

在 `.gitignore` 末尾追加：

```text
__pycache__/
.venv/
.pytest_cache/
frontend/dist/
frontend/node_modules/
*.db
*.db-wal
*.db-shm
```

- [ ] **Step 4: 创建 pytest.ini**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 5: 写失败测试 tests/test_health.py**

```python
import httpx
import pytest

from backend import create_app


@pytest.mark.asyncio
async def test_health(tmp_path):
    app = create_app(db_path=tmp_path / "test.db", config_path=tmp_path / "config.yaml")
    async with httpx.ASGITransport(app=app) as transport:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 6: 运行测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_health.py -v
```

Expected: FAIL（`ModuleNotFoundError: No module named 'backend'`）。

- [ ] **Step 7: 创建 tests/conftest.py（导入路径）**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 8: 实现 backend/__init__.py**

```python
from pathlib import Path

import httpx
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parent.parent


def create_app(db_path: Path | None = None, config_path: Path | None = None,
               upstream_transport=None) -> FastAPI:
    app = FastAPI(title="TokenLens")
    app.state.db_path = db_path or ROOT / "data" / "tokenlens.db"
    app.state.config_path = config_path or ROOT / "config.yaml"
    app.state.client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=300.0),
        follow_redirects=False,
        transport=upstream_transport,
    )
    app.state.providers: dict = {}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
```

- [ ] **Step 9: 实现 backend/main.py**

```python
import uvicorn

from backend import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7788)
```

- [ ] **Step 10: 运行测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_health.py -v
```

Expected: PASS。

- [ ] **Step 11: 手动冒烟**

```bash
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 7788
```

浏览器/curl 访问 `http://127.0.0.1:7788/health` 返回 `{"status":"ok"}`。然后 Ctrl+C 停止。

- [ ] **Step 12: Commit**

```bash
git add requirements.txt .gitignore pytest.ini backend/ tests/ docs/ requestment.md
git commit -m "feat: init FastAPI skeleton with health endpoint"
```

---

### Task 2: Usage 标准模型与非流式解析器

**Files:**
- Create: `backend/usage/__init__.py`
- Create: `backend/usage/model.py`
- Create: `backend/usage/openai_parser.py`
- Create: `backend/usage/anthropic_parser.py`
- Create: `tests/test_usage_parsers.py`

**Interfaces:**
- Produces:
  - `Usage` dataclass：字段 `input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, total_tokens`（均 int，默认 0）；方法 `finalize() -> Usage`（total 为 0 时置为 input+output）；方法 `to_dict() -> dict`。
  - `openai_parser.parse_usage(payload: dict) -> Usage | None`：`usage` 缺失或非 dict 返回 None。
  - `anthropic_parser.parse_usage(payload: dict) -> Usage | None`：同上。
- Consumes: 无。

- [ ] **Step 1: 写失败测试 tests/test_usage_parsers.py**

```python
from backend.usage.model import Usage
from backend.usage.openai_parser import parse_usage as parse_openai
from backend.usage.anthropic_parser import parse_usage as parse_anthropic


def test_openai_full_mapping():
    payload = {
        "usage": {
            "prompt_tokens": 12500,
            "completion_tokens": 3210,
            "total_tokens": 15710,
            "prompt_tokens_details": {"cached_tokens": 8000},
        }
    }
    u = parse_openai(payload)
    assert u == Usage(12500, 3210, 8000, 0, 15710)


def test_openai_total_fallback():
    u = parse_openai({"usage": {"prompt_tokens": 100, "completion_tokens": 50}})
    assert u == Usage(100, 50, 0, 0, 150)


def test_openai_missing_usage_returns_none():
    assert parse_openai({"id": "x"}) is None


def test_anthropic_full_mapping():
    payload = {
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 300,
            "cache_read_input_tokens": 600,
            "cache_creation_input_tokens": 120,
        }
    }
    u = parse_anthropic(payload)
    assert u == Usage(1000, 300, 600, 120, 1300)


def test_anthropic_missing_usage_returns_none():
    assert parse_anthropic({"type": "message"}) is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_usage_parsers.py -v
```

Expected: FAIL（ModuleNotFoundError）。

- [ ] **Step 3: 实现 backend/usage/model.py**

```python
from dataclasses import asdict, dataclass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0

    def finalize(self) -> "Usage":
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens
        return self

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 4: 实现 backend/usage/openai_parser.py**

```python
from backend.usage.model import Usage


def _num(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_usage(payload: dict) -> Usage | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    details = usage.get("prompt_tokens_details")
    details = details if isinstance(details, dict) else {}
    return Usage(
        input_tokens=_num(usage.get("prompt_tokens")),
        output_tokens=_num(usage.get("completion_tokens")),
        cache_read_tokens=_num(details.get("cached_tokens")),
        total_tokens=_num(usage.get("total_tokens")),
    ).finalize()
```

- [ ] **Step 5: 实现 backend/usage/anthropic_parser.py**

```python
from backend.usage.model import Usage
from backend.usage.openai_parser import _num


def parse_usage(payload: dict) -> Usage | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    return Usage(
        input_tokens=_num(usage.get("input_tokens")),
        output_tokens=_num(usage.get("output_tokens")),
        cache_read_tokens=_num(usage.get("cache_read_input_tokens")),
        cache_write_tokens=_num(usage.get("cache_creation_input_tokens")),
    ).finalize()
```

- [ ] **Step 6: 运行测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_usage_parsers.py -v
```

Expected: 5 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/usage/ tests/test_usage_parsers.py
git commit -m "feat: add usage model and non-stream parsers"
```

---

### Task 3: SSE 流式解析器

**Files:**
- Create: `backend/usage/stream_parser.py`
- Create: `tests/test_stream_parser.py`

**Interfaces:**
- Produces: `StreamUsageParser(protocol: str)`，`protocol` 为 `"openai"` 或 `"anthropic"`。
  - `feed(text: str) -> Usage | None`：接收一段新到达的文本（可能含不完整行），内部跨 chunk 缓冲，返回**本次新解析出的完整 Usage**（OpenAI 的最终 usage chunk；Anthropic 的 message_start 与 message_delta 合并结果）；无新结果返回 None。
  - `finish() -> Usage | None`：流结束时取累计结果（Anthropic 部分事件也返回）。
  - 属性 `stream_error: str | None`：流中出现 `{"error": ...}` 事件时置为 `error.type` 或 `error.code`（取不到用 `"stream_error"`）。
  - 忽略 `event:`/`id:`/`retry:` 行与 `[DONE]`；单个 data 行 JSON 解析失败时跳过。
- Consumes: `Usage`、`openai_parser.parse_usage`、`anthropic_parser.parse_usage`（Task 2）。

- [ ] **Step 1: 写失败测试 tests/test_stream_parser.py**

```python
from backend.usage.model import Usage
from backend.usage.stream_parser import StreamUsageParser


def test_openai_usage_chunk_split_across_feeds():
    p = StreamUsageParser("openai")
    assert p.feed('data: {"choices":[{"delta":{"content":"你"}}]}\n\nda') is None
    u = p.feed('ta: {"choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}\n\ndata: [DONE]\n\n')
    assert u == Usage(10, 5, 0, 0, 15)
    assert p.finish() == Usage(10, 5, 0, 0, 15)


def test_openai_ignores_non_usage_chunks_and_bad_json():
    p = StreamUsageParser("openai")
    assert p.feed('event: x\ndata: {"choices":[{"delta":{}}]}\n\ndata: not-json\n\ndata: [DONE]\n\n') is None
    assert p.finish() is None


def test_openai_stream_error():
    p = StreamUsageParser("openai")
    p.feed('data: {"error": {"type": "server_error", "message": "boom"}}\n\n')
    assert p.stream_error == "server_error"


def test_anthropic_message_start_and_delta_merge():
    p = StreamUsageParser("anthropic")
    assert p.feed(
        'data: {"type":"message_start","message":{"usage":{"input_tokens":1000,'
        '"cache_read_input_tokens":600,"cache_creation_input_tokens":120}}}\n\n'
    ) is None
    u = p.feed('data: {"type":"message_delta","usage":{"output_tokens":300}}\n\n')
    assert u == Usage(1000, 300, 600, 120, 1300)
    assert p.finish() == Usage(1000, 300, 600, 120, 1300)


def test_anthropic_delta_only():
    p = StreamUsageParser("anthropic")
    p.feed('data: {"type":"message_delta","usage":{"output_tokens":42}}\n\n')
    assert p.finish() == Usage(0, 42, 0, 0, 42)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_stream_parser.py -v
```

Expected: FAIL（ModuleNotFoundError）。

- [ ] **Step 3: 实现 backend/usage/stream_parser.py**

```python
import json

from backend.usage.anthropic_parser import parse_usage as parse_anthropic
from backend.usage.model import Usage
from backend.usage.openai_parser import parse_usage as parse_openai


class StreamUsageParser:
    def __init__(self, protocol: str):
        self.protocol = protocol
        self.stream_error: str | None = None
        self._buffer = ""
        self._openai_usage: Usage | None = None
        self._anthropic_input: Usage | None = None
        self._anthropic_output: Usage | None = None

    def feed(self, text: str) -> Usage | None:
        self._buffer += text
        lines = self._buffer.split("\n")
        self._buffer = lines.pop()
        new_usage = None
        for line in lines:
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            new_usage = self._handle_event(event) or new_usage
        return new_usage

    def _handle_event(self, event: dict) -> Usage | None:
        if "error" in event and isinstance(event["error"], dict):
            err = event["error"]
            self.stream_error = err.get("type") or err.get("code") or "stream_error"
            return None
        if self.protocol == "openai":
            usage = parse_openai(event)
            if usage is not None:
                self._openai_usage = usage
                return usage
            return None
        if event.get("type") == "message_start":
            message = event.get("message") or {}
            usage = parse_anthropic({"usage": message.get("usage")})
            if usage is not None:
                self._anthropic_input = usage
        elif event.get("type") == "message_delta":
            usage = parse_anthropic({"usage": event.get("usage")})
            if usage is not None:
                self._anthropic_output = usage
        return self._merged_anthropic()

    def _merged_anthropic(self) -> Usage | None:
        a, b = self._anthropic_input, self._anthropic_output
        if a is None and b is None:
            return None
        return Usage(
            input_tokens=a.input_tokens if a else 0,
            output_tokens=b.output_tokens if b else 0,
            cache_read_tokens=a.cache_read_tokens if a else 0,
            cache_write_tokens=a.cache_write_tokens if a else 0,
        ).finalize()

    def finish(self) -> Usage | None:
        if self.protocol == "openai":
            return self._openai_usage
        return self._merged_anthropic()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_stream_parser.py -v
```

Expected: 5 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/usage/stream_parser.py tests/test_stream_parser.py
git commit -m "feat: add SSE stream usage parser"
```

---

### Task 4: SQLite 数据库层

**Files:**
- Create: `backend/database/__init__.py`
- Create: `backend/database/database.py`
- Create: `backend/database/queries.py`
- Create: `tests/test_database.py`

**Interfaces:**
- Produces:
  - `init_db(db_path: Path) -> sqlite3.Connection`：建表（schema 与 spec 第 16 章一致）+ WAL，并设为模块全局连接；再次调用时关闭旧连接。
  - `get_connection() -> sqlite3.Connection`。
  - `insert_request(record: dict) -> int`：插入一条记录（键名与 spec 第 10 章一致：`request_id, provider, model, endpoint, stream, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, total_tokens, latency_ms, status_code, success, error_type, created_at`），返回自增 id。
  - `queries.today_summary(date_str: str) -> dict`：键 `requests, success, errors, input_tokens, output_tokens, total_tokens, avg_latency_ms`（按 `created_at` 前缀 `date_str` 过滤）。
  - `queries.group_stats(column: str, date_str: str) -> list[dict]`：`column` 为 `model` 或 `provider`，按 `total_tokens DESC` 排序，每项键 `{column}, requests, input_tokens, output_tokens, total_tokens`。
  - `queries.trend_stats(range_key: str) -> list[dict]`：`range_key` 为 `"24h" | "7d" | "30d"`，每项键 `bucket, total_tokens`；24h 按小时（`substr(created_at,1,13)`），7d/30d 按天（`substr(created_at,1,10)`），时间窗口用 `created_at >= 截止时间` 过滤。
  - `queries.query_requests(filters: dict) -> dict`：返回 `{"items": [record...], "total": n}`；filters 支持 `provider, model, status, date_from, date_to, limit(默认50), offset(默认0)`；record 含全部列（SQLite Row 转 dict）。
- Consumes: 无。

- [ ] **Step 1: 写失败测试 tests/test_database.py**

```python
from datetime import datetime, timedelta

from backend.database import database, queries

SCHEMA_FIELDS = {
    "id", "request_id", "provider", "model", "endpoint", "stream",
    "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
    "total_tokens", "latency_ms", "status_code", "success", "error_type", "created_at",
}


def _record(**overrides):
    rec = {
        "request_id": "req_1", "provider": "provider_a", "model": "gpt-5.6-sol",
        "endpoint": "/v1/chat/completions", "stream": 0,
        "input_tokens": 100, "output_tokens": 50, "cache_read_tokens": 0,
        "cache_write_tokens": 0, "total_tokens": 150, "latency_ms": 800,
        "status_code": 200, "success": 1, "error_type": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    rec.update(overrides)
    return rec


def test_schema_fields(tmp_path):
    conn = database.init_db(tmp_path / "test.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    cols = {r[1] for r in conn.execute("PRAGMA table_info(api_requests)")}
    assert cols == SCHEMA_FIELDS


def test_insert_and_query_with_filters(tmp_path):
    database.init_db(tmp_path / "test.db")
    today = datetime.now().strftime("%Y-%m-%d")
    database.insert_request(_record())
    database.insert_request(_record(
        request_id="req_2", model="claude-sonnet", provider="provider_b",
        status_code=429, success=0, error_type="rate_limit",
        created_at=(datetime.now() - timedelta(days=3)).isoformat(timespec="seconds"),
    ))
    result = queries.query_requests({})
    assert result["total"] == 2 and len(result["items"]) == 2
    assert queries.query_requests({"model": "claude-sonnet"})["total"] == 1
    assert queries.query_requests({"status": 429})["total"] == 1
    assert queries.query_requests({"date_from": today})["total"] == 1
    assert queries.query_requests({"limit": 1, "offset": 1})["items"][0]["request_id"] == "req_1"


def test_summary_and_group_stats(tmp_path):
    database.init_db(tmp_path / "test.db")
    database.insert_request(_record())
    database.insert_request(_record(request_id="req_2", success=0, status_code=500, error_type="server_error"))
    today = datetime.now().strftime("%Y-%m-%d")
    s = queries.today_summary(today)
    assert s["requests"] == 2 and s["errors"] == 1 and s["input_tokens"] == 200
    models = queries.group_stats("model", today)
    assert len(models) == 1 and models[0]["total_tokens"] == 300
    providers = queries.group_stats("provider", today)
    assert providers[0]["provider"] == "provider_a"


def test_trend_buckets(tmp_path):
    database.init_db(tmp_path / "test.db")
    now = datetime.now()
    database.insert_request(_record(request_id="r1", created_at=now.isoformat(timespec="seconds")))
    database.insert_request(_record(request_id="r2", created_at=(now - timedelta(hours=1)).isoformat(timespec="seconds")))
    hours = queries.trend_stats("24h")
    assert len(hours) >= 2
    assert all("bucket" in h and "total_tokens" in h for h in hours)
    days = queries.trend_stats("7d")
    assert len(days) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_database.py -v
```

Expected: FAIL（ModuleNotFoundError）。

- [ ] **Step 3: 实现 backend/database/database.py**

```python
import sqlite3
from pathlib import Path

_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_requests (
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
CREATE INDEX IF NOT EXISTS idx_created_at ON api_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_model ON api_requests(model);
CREATE INDEX IF NOT EXISTS idx_provider ON api_requests(provider);
"""

FIELDS = (
    "request_id", "provider", "model", "endpoint", "stream",
    "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
    "total_tokens", "latency_ms", "status_code", "success", "error_type", "created_at",
)


def init_db(db_path: Path) -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        _conn.close()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.executescript(SCHEMA)
    _conn.commit()
    return _conn


def get_connection() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("database not initialized")
    return _conn


def insert_request(record: dict) -> int:
    conn = get_connection()
    placeholders = ", ".join("?" for _ in FIELDS)
    sql = f"INSERT INTO api_requests ({', '.join(FIELDS)}) VALUES ({placeholders})"
    cur = conn.execute(sql, [record.get(f, 0 if f != "created_at" else "") for f in FIELDS])
    conn.commit()
    return cur.lastrowid
```

- [ ] **Step 4: 实现 backend/database/queries.py**

```python
from datetime import datetime, timedelta

from backend.database.database import get_connection


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


def today_summary(date_str: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) AS requests,
                  COALESCE(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END), 0) AS success,
                  COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS errors,
                  COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens,
                  COALESCE(SUM(total_tokens), 0) AS total_tokens,
                  COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
           FROM api_requests WHERE substr(created_at, 1, 10) = ?""",
        (date_str,),
    ).fetchone()
    return _row_to_dict(row)


def group_stats(column: str, date_str: str) -> list[dict]:
    assert column in ("model", "provider")
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT COALESCE({column}, 'unknown') AS {column},
                   COUNT(*) AS requests,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM api_requests WHERE substr(created_at, 1, 10) = ?
            GROUP BY {column} ORDER BY total_tokens DESC""",
        (date_str,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def trend_stats(range_key: str) -> list[dict]:
    assert range_key in ("24h", "7d", "30d")
    if range_key == "24h":
        since = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
        bucket_expr = "substr(created_at, 1, 13)"
    else:
        days = 7 if range_key == "7d" else 30
        since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        bucket_expr = "substr(created_at, 1, 10)"
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT {bucket_expr} AS bucket, COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM api_requests WHERE created_at >= ?
            GROUP BY bucket ORDER BY bucket""",
        (since,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def query_requests(filters: dict) -> dict:
    where, params = [], []
    if filters.get("provider"):
        where.append("provider = ?")
        params.append(filters["provider"])
    if filters.get("model"):
        where.append("model = ?")
        params.append(filters["model"])
    if filters.get("status") is not None:
        where.append("status_code = ?")
        params.append(int(filters["status"]))
    if filters.get("date_from"):
        where.append("created_at >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("created_at < ?")
        params.append(filters["date_to"])
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    limit = min(int(filters.get("limit", 50)), 200)
    offset = max(int(filters.get("offset", 0)), 0)
    conn = get_connection()
    total = conn.execute(f"SELECT COUNT(*) FROM api_requests{clause}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM api_requests{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {"items": [_row_to_dict(r) for r in rows], "total": total}
```

- [ ] **Step 5: 运行测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_database.py -v
```

Expected: 4 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/database/ tests/test_database.py
git commit -m "feat: add sqlite storage layer with stats queries"
```

---

### Task 5: Provider 配置加载

**Files:**
- Create: `backend/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `ProviderConfig` dataclass：`name, type, base_url, api_key`（`api_key` 可为 None）；`load_config(path: Path) -> dict[str, ProviderConfig]`。校验规则：`type` 必须是 `openai` 或 `anthropic`；`base_url` 去掉尾部 `/` 后不得以 `/v1` 结尾（违反抛 `ValueError` 并注明 provider 名）；文件不存在或空返回 `{}`。
- Consumes: 无。Task 7 起由 `create_app` 调用并放入 `app.state.providers`。

- [ ] **Step 1: 写失败测试 tests/test_config.py**

```python
import pytest
import yaml

from backend.config import ProviderConfig, load_config


def test_load_valid(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({
        "providers": {
            "provider_a": {"type": "openai", "base_url": "https://api.example.com", "api_key": "sk-1"},
            "provider_b": {"type": "anthropic", "base_url": "https://api.anthropic.com/"},
        }
    }), encoding="utf-8")
    cfg = load_config(p)
    assert cfg["provider_a"] == ProviderConfig("provider_a", "openai", "https://api.example.com", "sk-1")
    assert cfg["provider_b"].base_url == "https://api.anthropic.com"
    assert cfg["provider_b"].api_key is None


def test_missing_file_returns_empty(tmp_path):
    assert load_config(tmp_path / "nope.yaml") == {}


def test_reject_v1_suffix(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({
        "providers": {"bad": {"type": "openai", "base_url": "https://api.example.com/v1"}}
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="bad"):
        load_config(p)


def test_reject_unknown_type(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({
        "providers": {"bad": {"type": "gemini", "base_url": "https://x.com"}}
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="bad"):
        load_config(p)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_config.py -v
```

Expected: FAIL（ModuleNotFoundError）。

- [ ] **Step 3: 实现 backend/config.py**

```python
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ProviderConfig:
    name: str
    type: str
    base_url: str
    api_key: str | None = None


def load_config(path: Path) -> dict[str, ProviderConfig]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    providers: dict[str, ProviderConfig] = {}
    for name, item in (raw.get("providers") or {}).items():
        ptype = item.get("type")
        if ptype not in ("openai", "anthropic"):
            raise ValueError(f"provider '{name}': type must be openai or anthropic")
        base_url = str(item.get("base_url", "")).rstrip("/")
        if base_url.endswith("/v1"):
            raise ValueError(f"provider '{name}': base_url must not end with /v1")
        if not base_url:
            raise ValueError(f"provider '{name}': base_url is required")
        providers[name] = ProviderConfig(
            name=name, type=ptype, base_url=base_url,
            api_key=item.get("api_key"),
        )
    return providers
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_config.py -v
```

Expected: 4 PASS。

- [ ] **Step 5: 接入 create_app（修改 backend/__init__.py）**

在 `create_app` 中 `app.state.providers: dict = {}` 之后加入：

```python
    from backend.config import load_config

    app.state.providers = load_config(app.state.config_path)
```

- [ ] **Step 6: Commit**

```bash
git add backend/config.py tests/test_config.py backend/__init__.py
git commit -m "feat: load provider config from yaml"
```

---

### Task 6: 请求预处理（Header 重写 / 注入 / Auth 回退）

**Files:**
- Create: `backend/proxy/__init__.py`
- Create: `backend/proxy/preprocess.py`
- Create: `tests/test_preprocess.py`

**Interfaces:**
- Produces:
  - `forward_request_headers(headers: Mapping[str, str], upstream_host: str) -> dict`：移除 hop-by-hop 头、`host`、`accept-encoding`、`content-length`，其余原样（键转小写），并设置 `host` 为 `upstream_host`（上游 host:port，即 base_url 的 netloc）（spec 第 6.2、6.3 节）。
  - `strip_response_headers(headers: Mapping[str, str]) -> dict`：移除 `content-encoding, content-length, connection, transfer-encoding`，其余原样。
  - `inject_stream_options(body: dict, protocol: str, path: str) -> bool`：仅当 `protocol == "openai"`、`path` 以 `/chat/completions` 结尾、`body.get("stream") is True` 且未带 `include_usage` 时注入 `body["stream_options"]["include_usage"] = True`（保留已有 stream_options 其他键），返回是否修改（spec 第 6.1 节）。
  - `apply_auth_fallback(headers: dict, cfg: ProviderConfig, protocol: str) -> dict`：openai 无 `authorization` 且 `cfg.api_key` 存在时补 `authorization: Bearer {api_key}`；anthropic 无 `x-api-key` 且 `cfg.api_key` 存在时补 `x-api-key`。
- Consumes: `ProviderConfig`（Task 5）。

- [ ] **Step 1: 写失败测试 tests/test_preprocess.py**

```python
from backend.config import ProviderConfig
from backend.proxy.preprocess import (
    apply_auth_fallback, forward_request_headers, inject_stream_options, strip_response_headers,
)

INBOUND = {
    "Host": "127.0.0.1:7788",
    "Authorization": "Bearer sk-abc",
    "Accept-Encoding": "gzip, deflate",
    "Content-Length": "123",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "X-Custom": "v",
}


def test_forward_request_headers():
    out = forward_request_headers(INBOUND, "api.example.com")
    assert out["host"] == "api.example.com"
    assert "accept-encoding" not in out and "content-length" not in out and "connection" not in out
    assert out["authorization"] == "Bearer sk-abc"
    assert out["x-custom"] == "v"


def test_strip_response_headers():
    out = strip_response_headers({
        "content-type": "text/event-stream",
        "content-encoding": "gzip",
        "content-length": "99",
        "connection": "close",
        "transfer-encoding": "chunked",
        "x-request-id": "req_9",
    })
    assert out == {"content-type": "text/event-stream", "x-request-id": "req_9"}


def test_inject_stream_options_only_for_openai_stream():
    body = {"model": "m", "stream": True}
    assert inject_stream_options(body, "openai", "/v1/chat/completions") is True
    assert body["stream_options"] == {"include_usage": True}
    assert inject_stream_options(body, "openai", "/v1/chat/completions") is False
    assert inject_stream_options({"model": "m", "stream": False}, "openai", "/v1/chat/completions") is False
    assert inject_stream_options({"model": "m", "stream": True}, "anthropic", "/v1/messages") is False


def test_inject_preserves_existing_stream_options():
    body = {"model": "m", "stream": True, "stream_options": {"chunk_size": 64}}
    inject_stream_options(body, "openai", "/v1/chat/completions")
    assert body["stream_options"] == {"chunk_size": 64, "include_usage": True}


def test_auth_fallback():
    cfg = ProviderConfig("p", "openai", "https://x.com", "sk-cfg")
    out = apply_auth_fallback({"content-type": "application/json"}, cfg, "openai")
    assert out["authorization"] == "Bearer sk-cfg"
    out = apply_auth_fallback({"authorization": "Bearer sk-client"}, cfg, "openai")
    assert out["authorization"] == "Bearer sk-client"
    out = apply_auth_fallback({"content-type": "application/json"}, ProviderConfig("p", "anthropic", "https://x.com", "ak"), "anthropic")
    assert out["x-api-key"] == "ak"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_preprocess.py -v
```

Expected: FAIL（ModuleNotFoundError）。

- [ ] **Step 3: 实现 backend/proxy/preprocess.py**

```python
from collections.abc import Mapping

from backend.config import ProviderConfig

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
}
REQUEST_STRIP = HOP_BY_HOP | {"host", "accept-encoding", "content-length"}
RESPONSE_STRIP = {"content-encoding", "content-length", "connection", "transfer-encoding"}


def forward_request_headers(headers: Mapping[str, str], upstream_host: str) -> dict:
    out = {k.lower(): v for k, v in headers.items() if k.lower() not in REQUEST_STRIP}
    out["host"] = upstream_host
    return out


def strip_response_headers(headers: Mapping[str, str]) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in RESPONSE_STRIP}


def inject_stream_options(body: dict, protocol: str, path: str) -> bool:
    if protocol != "openai" or not path.endswith("/chat/completions"):
        return False
    if body.get("stream") is not True:
        return False
    stream_options = body.get("stream_options")
    if isinstance(stream_options, dict) and stream_options.get("include_usage") is True:
        return False
    body["stream_options"] = {**(stream_options if isinstance(stream_options, dict) else {}), "include_usage": True}
    return True


def apply_auth_fallback(headers: dict, cfg: ProviderConfig, protocol: str) -> dict:
    if cfg.api_key is None:
        return headers
    if protocol == "openai" and "authorization" not in headers:
        headers["authorization"] = f"Bearer {cfg.api_key}"
    elif protocol == "anthropic" and "x-api-key" not in headers:
        headers["x-api-key"] = cfg.api_key
    return headers
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_preprocess.py -v
```

Expected: 5 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/proxy/ tests/test_preprocess.py
git commit -m "feat: add request preprocessing for header rewrite and usage injection"
```

---

### Task 7: OpenAI 非流式代理端点

**Files:**
- Create: `backend/proxy/forwarder.py`
- Create: `backend/proxy/router.py`
- Modify: `backend/__init__.py`（挂载 router、初始化数据库）
- Create: `tests/test_proxy_openai.py`

**Interfaces:**
- Produces:
  - `forwarder.build_record(*, request_id, provider, model, endpoint, stream, usage, latency_ms, status_code, error_type=None) -> dict`：`usage` 为 `Usage | None`；`success = 200 <= status_code < 300 and error_type is None`；`created_at = datetime.now().isoformat(timespec="seconds")`。
  - `forwarder.forward_non_stream(request, *, client, cfg, provider, protocol, endpoint, body, model, latency_start) -> Response`：非流式转发 + 解析 + 落库；上游连接失败 → 记录 `proxy_connection_error`（502）并返回 502 JSON。
  - `forwarder.forward_passthrough(request, cfg, endpoint, raw_body) -> Response`：无统计透传（不注入、不落库、不做 auth 回退）。
  - `router.proxy_endpoint`：路由 `/{provider}/v1/{rest:path}`（GET/POST/PUT/PATCH/DELETE/OPTIONS/HEAD）。
- Consumes: Task 2 解析器、Task 4 数据库、Task 5 配置、Task 6 预处理。

- [ ] **Step 1: 写失败测试 tests/test_proxy_openai.py**

```python
import json

import httpx
import pytest

from backend import create_app
from backend.database import database, queries

UPSTREAM_OK = {
    "id": "chatcmpl-1", "model": "gpt-5.6-sol",
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}


def _upstream_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/chat/completions" and request.url.host == "api.example.com":
        return httpx.Response(200, json=UPSTREAM_OK, headers={"x-request-id": "req_up_1"})
    return httpx.Response(404, json={"error": {"message": "not found"}})


@pytest.fixture
def app(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "providers:\n  provider_a:\n    type: openai\n    base_url: https://api.example.com\n",
        encoding="utf-8",
    )
    return create_app(
        db_path=tmp_path / "test.db",
        config_path=tmp_path / "config.yaml",
        upstream_transport=httpx.MockTransport(_upstream_handler),
    )


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_openai_non_stream_proxy_and_record(app, client):
    database.init_db(app.state.db_path)
    resp = await client.post(
        "/provider_a/v1/chat/completions",
        json={"model": "gpt-5.6-sol", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["usage"]["total_tokens"] == 15
    rows = queries.query_requests({})["items"]
    assert len(rows) == 1
    rec = rows[0]
    assert rec["provider"] == "provider_a" and rec["model"] == "gpt-5.6-sol"
    assert rec["input_tokens"] == 10 and rec["output_tokens"] == 5 and rec["total_tokens"] == 15
    assert rec["status_code"] == 200 and rec["success"] == 1
    assert rec["request_id"] == "req_up_1"
    assert rec["endpoint"] == "/v1/chat/completions"
    assert rec["stream"] == 0


@pytest.mark.asyncio
async def test_error_status_recorded(app, client):
    def handler(request):
        return httpx.Response(429, json={"error": {"type": "rate_limit_error", "message": "slow down"}})
    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)
    database.init_db(app.state.db_path)
    resp = await client.post("/provider_a/v1/chat/completions", json={"model": "m"})
    assert resp.status_code == 429
    rec = queries.query_requests({})["items"][0]
    assert rec["success"] == 0 and rec["status_code"] == 429 and rec["error_type"] == "rate_limit_error"


@pytest.mark.asyncio
async def test_unknown_provider_404(app, client):
    database.init_db(app.state.db_path)
    resp = await client.post("/nope/v1/chat/completions", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_body_too_large_413(app, client):
    database.init_db(app.state.db_path)
    resp = await client.post("/provider_a/v1/chat/completions", content=b"x" * 40000,
                             headers={"content-type": "application/json"})
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_passthrough_models_without_record(app, client):
    def handler(request):
        return httpx.Response(200, json={"object": "list", "data": []})
    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)
    database.init_db(app.state.db_path)
    resp = await client.get("/provider_a/v1/models")
    assert resp.status_code == 200 and resp.json()["object"] == "list"
    assert queries.query_requests({})["total"] == 0


@pytest.mark.asyncio
async def test_upstream_connect_error_502(app, client):
    def handler(request):
        raise httpx.ConnectError("boom")
    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)
    database.init_db(app.state.db_path)
    resp = await client.post("/provider_a/v1/chat/completions", json={"model": "m"})
    assert resp.status_code == 502
    rec = queries.query_requests({})["items"][0]
    assert rec["success"] == 0 and rec["error_type"] == "proxy_connection_error" and rec["status_code"] == 502
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_proxy_openai.py -v
```

Expected: FAIL（路由不存在，404/AttributeError）。

- [ ] **Step 3: 实现 backend/proxy/forwarder.py**

```python
import json
import time
import uuid
from datetime import datetime

import httpx
from fastapi import Request, Response
from starlette.responses import JSONResponse

from backend.config import ProviderConfig
from backend.database.database import insert_request
from backend.proxy.preprocess import (
    apply_auth_fallback, forward_request_headers, strip_response_headers,
)
from backend.usage.anthropic_parser import parse_usage as parse_anthropic
from backend.usage.model import Usage
from backend.usage.openai_parser import parse_usage as parse_openai


def build_record(*, request_id, provider, model, endpoint, stream, usage: Usage | None,
                 latency_ms, status_code, error_type=None) -> dict:
    u = usage.to_dict() if usage else {}
    return {
        "request_id": request_id,
        "provider": provider,
        "model": model,
        "endpoint": endpoint,
        "stream": 1 if stream else 0,
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cache_read_tokens": u.get("cache_read_tokens", 0),
        "cache_write_tokens": u.get("cache_write_tokens", 0),
        "total_tokens": u.get("total_tokens", 0),
        "latency_ms": latency_ms,
        "status_code": status_code,
        "success": 1 if (200 <= status_code < 300 and error_type is None) else 0,
        "error_type": error_type,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def _parse_usage(protocol: str, payload: dict) -> Usage | None:
    if protocol == "openai":
        return parse_openai(payload)
    return parse_anthropic(payload)


def _error_type_from(payload: dict) -> str | None:
    err = payload.get("error")
    if isinstance(err, dict):
        return err.get("type") or err.get("code") or err.get("message")
    if isinstance(payload.get("type"), dict):
        return payload["type"].get("type") or payload["type"].get("message")
    return None


async def forward_non_stream(request: Request, *, client: httpx.AsyncClient,
                             cfg: ProviderConfig, provider: str, protocol: str,
                             endpoint: str, body: dict | None, model: str | None,
                             latency_start: float) -> Response:
    headers = forward_request_headers(request.headers, httpx.URL(cfg.base_url).netloc)
    headers = apply_auth_fallback(headers, cfg, protocol)
    target = f"{cfg.base_url}{endpoint}"
    if request.url.query:
        target += f"?{request.url.query}"
    content = json.dumps(body).encode("utf-8") if body is not None else None

    def _finish(status_code, error_type, usage=None, request_id=None):
        latency = round((time.perf_counter() - latency_start) * 1000)
        insert_request(build_record(
            request_id=request_id or f"req_{uuid.uuid4().hex[:12]}",
            provider=provider, model=model, endpoint=endpoint,
            stream=False, usage=usage, latency_ms=latency,
            status_code=status_code, error_type=error_type,
        ))

    try:
        upstream = await client.request(request.method, target, headers=headers, content=content)
    except httpx.TransportError as exc:
        _finish(502, "proxy_connection_error")
        return JSONResponse(
            status_code=502,
            content={"error": {"message": f"无法连接上游：{exc}", "type": "proxy_connection_error"}},
        )

    payload = None
    raw = await upstream.aread()
    if raw and "application/json" in (upstream.headers.get("content-type") or ""):
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None

    request_id = (upstream.headers.get("x-request-id")
                  or upstream.headers.get("request-id")
                  or f"req_{uuid.uuid4().hex[:12]}")

    error_type = None
    usage = None
    if upstream.status_code >= 400 and payload is not None:
        error_type = _error_type_from(payload)
    elif upstream.status_code < 300 and payload is not None:
        usage = _parse_usage(protocol, payload)
    _finish(upstream.status_code, error_type, usage, request_id)

    return Response(
        content=raw,
        status_code=upstream.status_code,
        headers=strip_response_headers(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )


async def forward_passthrough(request: Request, cfg: ProviderConfig,
                              endpoint: str, raw_body: bytes) -> Response:
    headers = forward_request_headers(request.headers, httpx.URL(cfg.base_url).netloc)
    target = f"{cfg.base_url}{endpoint}"
    if request.url.query:
        target += f"?{request.url.query}"
    try:
        upstream = await request.app.state.client.request(
            request.method, target, headers=headers, content=raw_body or None,
        )
    except httpx.TransportError as exc:
        return JSONResponse(status_code=502, content={"error": {"message": f"无法连接上游：{exc}"}})
    content = await upstream.aread()
    return Response(
        content=content, status_code=upstream.status_code,
        headers=strip_response_headers(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )
```

- [ ] **Step 4: 实现 backend/proxy/router.py**

```python
import json
import time

from fastapi import APIRouter, HTTPException, Request

from backend.proxy import forwarder

router = APIRouter()

MAX_BODY = 32 * 1024


def _classify(rest: str) -> str | None:
    if rest.startswith("chat/completions"):
        return "openai"
    if rest == "messages":
        return "anthropic"
    return None


@router.api_route("/{provider}/v1/{rest:path}",
                  methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_endpoint(provider: str, rest: str, request: Request):
    state = request.app.state
    cfg = state.providers.get(provider)
    if cfg is None:
        raise HTTPException(status_code=404, detail="provider not found")

    raw_body = b""
    if request.method not in ("GET", "HEAD"):
        async for chunk in request.stream():
            raw_body += chunk
            if len(raw_body) > MAX_BODY:
                raise HTTPException(status_code=413, detail="request body too large")

    protocol = _classify(rest)
    endpoint = f"/v1/{rest}"
    body, model = None, None
    if raw_body:
        if "application/json" not in (request.headers.get("content-type") or ""):
            raise HTTPException(status_code=400, detail="unsupported content-type")
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="invalid json body")
        model = body.get("model") if isinstance(body, dict) else None

    if protocol is None:
        return await forwarder.forward_passthrough(request, cfg, endpoint, raw_body)

    from backend.proxy.preprocess import inject_stream_options

    inject_stream_options(body or {}, protocol, endpoint)
    is_stream = isinstance(body, dict) and body.get("stream") is True

    if is_stream:
        from backend.proxy.stream_proxy import forward_stream
        return await forward_stream(request, cfg, provider, protocol, endpoint, body, model)

    return await forwarder.forward_non_stream(
        request, client=state.client, cfg=cfg, provider=provider,
        protocol=protocol, endpoint=endpoint, body=body, model=model,
        latency_start=time.perf_counter(),
    )
```

- [ ] **Step 5: 修改 backend/__init__.py 挂载路由并初始化数据库**

在 `create_app` 中 `app.state.providers = load_config(...)` 之后加入：

```python
    from backend.database.database import init_db
    from backend.proxy.router import router as proxy_router

    init_db(app.state.db_path)
    app.include_router(proxy_router)
```

- [ ] **Step 6: 运行测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_proxy_openai.py -v
```

Expected: 6 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/proxy/ backend/__init__.py tests/test_proxy_openai.py
git commit -m "feat: add openai non-stream proxy with usage recording"
```

---

### Task 8: OpenAI SSE 流式代理

**Files:**
- Create: `backend/proxy/stream_proxy.py`
- Create: `tests/test_proxy_stream.py`

**Interfaces:**
- Produces: `forward_stream(request, cfg, provider, protocol, endpoint, body, model) -> StreamingResponse`：逐 chunk 透传（`aiter_bytes` 收到即 `yield`），同时用 `StreamUsageParser` 解析；流结束/断连/上游异常时落库一次；断连记录 `client_abort`；上游读异常记录 `upstream_abort`；流中 error 事件记录对应 `error_type`（spec 第 6.5、7.1 节）。
- Consumes: Task 3 解析器、Task 4 数据库、Task 6 预处理、Task 7 `build_record`。

- [ ] **Step 1: 写失败测试 tests/test_proxy_stream.py**

```python
import json

import httpx
import pytest

from backend import create_app
from backend.database import database, queries


def sse_response(chunks, extra_headers=None):
    async def body():
        for c in chunks:
            yield c
    headers = {"content-type": "text/event-stream", **(extra_headers or {})}
    return httpx.Response(200, headers=headers, content=body())


@pytest.fixture
def app(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "providers:\n  provider_a:\n    type: openai\n    base_url: https://api.example.com\n",
        encoding="utf-8",
    )
    return create_app(db_path=tmp_path / "test.db", config_path=tmp_path / "config.yaml")


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _set_upstream(app, handler):
    app.state.client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(connect=10.0, read=300.0),
    )


@pytest.mark.asyncio
async def test_stream_passthrough_and_usage_record(app, client):
    database.init_db(app.state.db_path)

    def handler(request):
        body = json.loads(request.content)
        assert body["stream_options"]["include_usage"] is True
        return sse_response([
            b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n',
            b'data: {"choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}\n\n',
            b'data: [DONE]\n\n',
        ], {"x-request-id": "req_s1"})
    _set_upstream(app, handler)

    resp = await client.post("/provider_a/v1/chat/completions",
                             json={"model": "m", "stream": True})
    assert resp.status_code == 200
    text = resp.text
    assert "Hi" in text and "[DONE]" in text
    rec = queries.query_requests({})["items"][0]
    assert rec["stream"] == 1 and rec["input_tokens"] == 10 and rec["total_tokens"] == 15
    assert rec["success"] == 1 and rec["request_id"] == "req_s1"


@pytest.mark.asyncio
async def test_stream_error_chunk_recorded(app, client):
    database.init_db(app.state.db_path)

    def handler(request):
        return sse_response([b'data: {"error": {"type": "server_error", "message": "boom"}}\n\n'])
    _set_upstream(app, handler)

    resp = await client.post("/provider_a/v1/chat/completions", json={"model": "m", "stream": True})
    assert resp.status_code == 200
    rec = queries.query_requests({})["items"][0]
    assert rec["success"] == 0 and rec["error_type"] == "server_error"


@pytest.mark.asyncio
async def test_stream_upstream_abort_recorded(app, client):
    database.init_db(app.state.db_path)

    def handler(request):
        async def body():
            yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            raise httpx.ReadError("connection lost")
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body())
    _set_upstream(app, handler)

    resp = await client.post("/provider_a/v1/chat/completions", json={"model": "m", "stream": True})
    assert resp.status_code == 200
    rec = queries.query_requests({})["items"][0]
    assert rec["success"] == 0 and rec["error_type"] == "upstream_abort"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_proxy_stream.py -v
```

Expected: FAIL（ImportError，`stream_proxy` 未实现）。

- [ ] **Step 3: 实现 backend/proxy/stream_proxy.py**

```python
import asyncio
import json
import time
import uuid

import httpx
from fastapi import Request
from starlette.responses import StreamingResponse

from backend.config import ProviderConfig
from backend.database.database import insert_request
from backend.proxy.forwarder import build_record
from backend.proxy.preprocess import (
    apply_auth_fallback, forward_request_headers, strip_response_headers,
)
from backend.usage.stream_parser import StreamUsageParser


async def _send_upstream(request: Request, cfg: ProviderConfig, protocol: str,
                         endpoint: str, body: dict) -> httpx.Response | None:
    headers = forward_request_headers(request.headers, httpx.URL(cfg.base_url).netloc)
    headers = apply_auth_fallback(headers, cfg, protocol)
    target = f"{cfg.base_url}{endpoint}"
    if request.url.query:
        target += f"?{request.url.query}"
    try:
        return await request.app.state.client.request(
            request.method, target, headers=headers,
            content=json.dumps(body).encode("utf-8"),
        )
    except httpx.TransportError:
        return None


async def forward_stream(request: Request, cfg: ProviderConfig, provider: str,
                         protocol: str, endpoint: str, body: dict, model: str | None):
    latency_start = time.perf_counter()
    upstream = await _send_upstream(request, cfg, protocol, endpoint, body)
    if upstream is None:
        insert_request(build_record(
            request_id=f"req_{uuid.uuid4().hex[:12]}", provider=provider, model=model,
            endpoint=endpoint, stream=True, usage=None,
            latency_ms=round((time.perf_counter() - latency_start) * 1000),
            status_code=502, error_type="proxy_connection_error",
        ))
        return StreamingResponse(
            iter([json.dumps({"error": {"message": "无法连接上游", "type": "proxy_connection_error"}}).encode()]),
            status_code=502, media_type="application/json",
        )

    parser = StreamUsageParser(protocol)
    state = {"usage": None, "error_type": None, "recorded": False}

    def _record():
        if state["recorded"]:
            return
        state["recorded"] = True
        usage = state["usage"] or parser.finish()
        insert_request(build_record(
            request_id=(upstream.headers.get("x-request-id")
                        or upstream.headers.get("request-id")
                        or f"req_{uuid.uuid4().hex[:12]}"),
            provider=provider, model=model, endpoint=endpoint, stream=True,
            usage=usage,
            latency_ms=round((time.perf_counter() - latency_start) * 1000),
            status_code=upstream.status_code, error_type=state["error_type"],
        ))

    async def generate():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
                usage = parser.feed(chunk.decode("utf-8", errors="ignore"))
                if usage is not None:
                    state["usage"] = usage
                if parser.stream_error is not None:
                    state["error_type"] = parser.stream_error
        except asyncio.CancelledError:
            state["error_type"] = state["error_type"] or "client_abort"
            _record()
            raise
        except httpx.HTTPError:
            state["error_type"] = state["error_type"] or "upstream_abort"
        finally:
            _record()

    return StreamingResponse(
        generate(), status_code=upstream.status_code,
        headers=strip_response_headers(upstream.headers),
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_proxy_stream.py -v
```

Expected: 3 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/proxy/stream_proxy.py tests/test_proxy_stream.py
git commit -m "feat: add openai sse streaming proxy"
```

---

### Task 9: Anthropic /v1/messages 代理

**Files:**
- Create: `tests/test_proxy_anthropic.py`

**Interfaces:**
- Consumes: Task 7 的 `forward_non_stream`（`_parse_usage` 已分发到 `parse_anthropic`）、Task 8 的 `forward_stream`（协议参数化）。
- Produces: 无新接口；本任务验证 anthropic 协议在现有转发链路上工作，包括 `request-id` 响应头、`x-api-key` 回退、`message_start`/`message_delta` 合并。

- [ ] **Step 1: 写失败测试 tests/test_proxy_anthropic.py**

```python
import httpx
import pytest

from backend import create_app
from backend.database import database, queries


def sse_response(chunks, extra_headers=None):
    async def body():
        for c in chunks:
            yield c
    headers = {"content-type": "text/event-stream", **(extra_headers or {})}
    return httpx.Response(200, headers=headers, content=body())


@pytest.fixture
def app(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "providers:\n  provider_b:\n    type: anthropic\n    base_url: https://api.anthropic.com\n    api_key: ak-cfg\n",
        encoding="utf-8",
    )
    return create_app(db_path=tmp_path / "test.db", config_path=tmp_path / "config.yaml")


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_anthropic_non_stream(app, client):
    database.init_db(app.state.db_path)

    def handler(request):
        assert request.headers["x-api-key"] == "ak-cfg"
        assert request.url.host == "api.anthropic.com"
        return httpx.Response(200, headers={"request-id": "req_ant_1"}, json={
            "content": [{"type": "text", "text": "hi"}],
            "usage": {"input_tokens": 100, "output_tokens": 30,
                      "cache_read_input_tokens": 50, "cache_creation_input_tokens": 10},
        })
    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)

    resp = await client.post("/provider_b/v1/messages",
                             json={"model": "claude-sonnet", "max_tokens": 100, "messages": []})
    assert resp.status_code == 200
    rec = queries.query_requests({})["items"][0]
    assert rec["provider"] == "provider_b" and rec["model"] == "claude-sonnet"
    assert rec["input_tokens"] == 100 and rec["cache_read_tokens"] == 50 and rec["cache_write_tokens"] == 10
    assert rec["total_tokens"] == 130 and rec["request_id"] == "req_ant_1"


@pytest.mark.asyncio
async def test_anthropic_stream_merge(app, client):
    database.init_db(app.state.db_path)

    def handler(request):
        return sse_response([
            b'data: {"type":"message_start","message":{"usage":{"input_tokens":1000,"cache_read_input_tokens":600,"cache_creation_input_tokens":120}}}\n\n',
            b'data: {"type":"content_block_delta","delta":{"text":"hello"}}\n\n',
            b'data: {"type":"message_delta","usage":{"output_tokens":300}}\n\n',
            b'data: {"type":"message_stop"}\n\n',
        ])
    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)

    resp = await client.post("/provider_b/v1/messages",
                             json={"model": "claude-sonnet", "max_tokens": 100, "stream": True, "messages": []})
    assert resp.status_code == 200 and "hello" in resp.text
    rec = queries.query_requests({})["items"][0]
    assert rec["input_tokens"] == 1000 and rec["output_tokens"] == 300
    assert rec["cache_read_tokens"] == 600 and rec["cache_write_tokens"] == 120
    assert rec["total_tokens"] == 1300 and rec["success"] == 1


@pytest.mark.asyncio
async def test_anthropic_client_key_priority(app, client):
    database.init_db(app.state.db_path)

    def handler(request):
        assert request.headers["x-api-key"] == "ak-client"
        return httpx.Response(200, json={"content": [], "usage": {"input_tokens": 1, "output_tokens": 1}})
    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)

    await client.post("/provider_b/v1/messages", headers={"x-api-key": "ak-client"},
                      json={"model": "m", "max_tokens": 10, "messages": []})
```

- [ ] **Step 2: 运行测试**

```bash
.venv/Scripts/python.exe -m pytest tests/test_proxy_anthropic.py -v
```

Expected: 若 Task 7/8 实现正确则 3 PASS；若失败，按失败信息修正 `forwarder.py` / `stream_proxy.py`（例如 `request-id` 未提取或 `x-api-key` 回退未生效）直至通过。

- [ ] **Step 3: Commit**

```bash
git add tests/test_proxy_anthropic.py backend/proxy/
git commit -m "feat: support anthropic messages proxy with usage merge"
```

---

### Task 10: Monitor API

**Files:**
- Create: `backend/statistics/__init__.py`
- Create: `backend/statistics/service.py`
- Create: `backend/api/__init__.py`
- Create: `backend/api/stats.py`
- Create: `backend/api/requests.py`
- Modify: `backend/__init__.py`（挂载两个 router）
- Create: `tests/test_stats_api.py`

**Interfaces:**
- Produces:
  - `GET /api/stats/summary` → `{"date", "requests", "success", "errors", "error_rate", "input_tokens", "output_tokens", "total_tokens", "avg_latency_ms"}`（error_rate 为 0~100 浮点，保留两位）。
  - `GET /api/stats/models` → `{"items": [{"model", "requests", "input_tokens", "output_tokens", "total_tokens"}]}`
  - `GET /api/stats/providers` → `{"items": [{"provider", "requests", "input_tokens", "output_tokens", "total_tokens"}]}`
  - `GET /api/stats/trend?range=24h|7d|30d` → `{"items": [{"bucket", "total_tokens"}]}`；非法 range 返回 400。
  - `GET /api/requests?provider=&model=&status=&date_from=&date_to=&limit=&offset=` → `{"items": [...], "total", "limit", "offset"}`。
- Consumes: Task 4 `queries`。

- [ ] **Step 1: 写失败测试 tests/test_stats_api.py**

```python
from datetime import datetime

import httpx
import pytest

from backend import create_app
from backend.database import database


def _record(**overrides):
    rec = {
        "request_id": "req_1", "provider": "provider_a", "model": "gpt-5.6-sol",
        "endpoint": "/v1/chat/completions", "stream": 0,
        "input_tokens": 100, "output_tokens": 50, "cache_read_tokens": 0,
        "cache_write_tokens": 0, "total_tokens": 150, "latency_ms": 800,
        "status_code": 200, "success": 1, "error_type": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    rec.update(overrides)
    return rec


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=tmp_path / "test.db", config_path=tmp_path / "config.yaml")


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_summary(app, client):
    database.init_db(app.state.db_path)
    database.insert_request(_record())
    database.insert_request(_record(request_id="req_2", success=0, status_code=500, error_type="server_error"))
    resp = await client.get("/api/stats/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requests"] == 2 and data["errors"] == 1
    assert data["input_tokens"] == 200 and data["total_tokens"] == 300
    assert data["error_rate"] == 50.0


@pytest.mark.asyncio
async def test_models_and_providers(app, client):
    database.init_db(app.state.db_path)
    database.insert_request(_record())
    database.insert_request(_record(request_id="req_2", model="claude-sonnet", provider="provider_b",
                                    total_tokens=50, input_tokens=30, output_tokens=20))
    models = (await client.get("/api/stats/models")).json()["items"]
    assert models[0]["model"] == "gpt-5.6-sol" and models[0]["total_tokens"] == 150
    providers = (await client.get("/api/stats/providers")).json()["items"]
    assert len(providers) == 2


@pytest.mark.asyncio
async def test_trend_and_bad_range(app, client):
    database.init_db(app.state.db_path)
    database.insert_request(_record())
    assert (await client.get("/api/stats/trend", params={"range": "24h"})).status_code == 200
    assert (await client.get("/api/stats/trend", params={"range": "9d"})).status_code == 400


@pytest.mark.asyncio
async def test_requests_endpoint(app, client):
    database.init_db(app.state.db_path)
    database.insert_request(_record())
    database.insert_request(_record(request_id="req_2", model="claude-sonnet"))
    resp = await client.get("/api/requests", params={"model": "claude-sonnet", "limit": 10})
    data = resp.json()
    assert data["total"] == 1 and data["items"][0]["request_id"] == "req_2"
    assert "authorization" not in data["items"][0]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/Scripts/python.exe -m pytest tests/test_stats_api.py -v
```

Expected: FAIL（404，路由未挂载）。

- [ ] **Step 3: 实现 backend/statistics/service.py**

```python
from datetime import datetime

from backend.database import queries


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def summary() -> dict:
    s = queries.today_summary(today())
    s["date"] = today()
    s["error_rate"] = round(s["errors"] / s["requests"] * 100, 2) if s["requests"] else 0.0
    return s


def models() -> dict:
    return {"items": queries.group_stats("model", today())}


def providers() -> dict:
    return {"items": queries.group_stats("provider", today())}


def trend(range_key: str) -> dict:
    return {"items": queries.trend_stats(range_key)}
```

- [ ] **Step 4: 实现 backend/api/stats.py 与 backend/api/requests.py**

`backend/api/stats.py`：

```python
from fastapi import APIRouter, HTTPException

from backend.statistics import service

router = APIRouter()


@router.get("/api/stats/summary")
async def summary():
    return service.summary()


@router.get("/api/stats/models")
async def models():
    return service.models()


@router.get("/api/stats/providers")
async def providers():
    return service.providers()


@router.get("/api/stats/trend")
async def trend(range: str = "24h"):
    if range not in ("24h", "7d", "30d"):
        raise HTTPException(status_code=400, detail="range must be 24h, 7d or 30d")
    return service.trend(range)
```

`backend/api/requests.py`：

```python
from fastapi import APIRouter

from backend.database import queries

router = APIRouter()


@router.get("/api/requests")
async def list_requests(provider: str | None = None, model: str | None = None,
                        status: int | None = None, date_from: str | None = None,
                        date_to: str | None = None, limit: int = 50, offset: int = 0):
    result = queries.query_requests({
        "provider": provider, "model": model, "status": status,
        "date_from": date_from, "date_to": date_to, "limit": limit, "offset": offset,
    })
    result["limit"] = limit
    result["offset"] = offset
    return result
```

（`from`/`to` 为 Python 保留字，故参数名用 `date_from`/`date_to`，与 queries 层 filters 键一致。）

- [ ] **Step 5: 挂载路由（修改 backend/__init__.py）**

在 `app.include_router(proxy_router)` 之后加入：

```python
    from backend.api.requests import router as requests_router
    from backend.api.stats import router as stats_router

    app.include_router(stats_router)
    app.include_router(requests_router)
```

- [ ] **Step 6: 运行测试确认通过**

```bash
.venv/Scripts/python.exe -m pytest tests/test_stats_api.py -v
```

Expected: 4 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/statistics/ backend/api/ backend/__init__.py tests/test_stats_api.py
git commit -m "feat: add monitor api for stats and request logs"
```

---

### Task 11: Dashboard 前端（Vue 3 + ECharts + 轮询）

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/api.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/views/DashboardView.vue`
- Create: `frontend/src/views/RequestsView.vue`
- Modify: `backend/__init__.py`（静态托管 + `/dashboard` 路由）

**Interfaces:**
- Consumes: Task 10 的 Monitor API 响应结构。
- Produces: `npm run build` 产物 `frontend/dist/`；`GET /` 与 `GET /dashboard` 返回 SPA；轮询间隔常量 `POLL_INTERVAL_MS = 5000`（spec 第 12.1 节，5~10 秒）。

- [ ] **Step 1: 创建 frontend/package.json**

```json
{
  "name": "tokenlens-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "dependencies": {
    "axios": "^1.7.0",
    "echarts": "^5.5.0",
    "vue": "^3.4.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: 创建 frontend/vite.config.js 与 frontend/index.html**

`vite.config.js`：

```js
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: { outDir: "dist" },
});
```

`index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>TokenLens</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

- [ ] **Step 3: 创建 frontend/src/main.js 与 frontend/src/api.js**

`main.js`：

```js
import { createApp } from "vue";
import App from "./App.vue";

createApp(App).mount("#app");
```

`api.js`：

```js
import axios from "axios";

export const POLL_INTERVAL_MS = 5000;
const http = axios.create({ baseURL: "/", timeout: 10000 });

export async function fetchSummary() {
  return (await http.get("/api/stats/summary")).data;
}
export async function fetchModels() {
  return (await http.get("/api/stats/models")).data;
}
export async function fetchProviders() {
  return (await http.get("/api/stats/providers")).data;
}
export async function fetchTrend(range) {
  return (await http.get("/api/stats/trend", { params: { range } })).data;
}
export async function fetchRequests(params) {
  return (await http.get("/api/requests", { params })).data;
}
```

- [ ] **Step 4: 创建 frontend/src/App.vue**

```vue
<script setup>
import { ref } from "vue";
import DashboardView from "./views/DashboardView.vue";
import RequestsView from "./views/RequestsView.vue";

const tab = ref("dashboard");
</script>

<template>
  <div class="app">
    <header>
      <h1>TokenLens</h1>
      <nav>
        <button :class="{ active: tab === 'dashboard' }" @click="tab = 'dashboard'">Dashboard</button>
        <button :class="{ active: tab === 'requests' }" @click="tab = 'requests'">Requests</button>
      </nav>
    </header>
    <main>
      <DashboardView v-if="tab === 'dashboard'" />
      <RequestsView v-else />
    </main>
  </div>
</template>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: #f5f6f8; color: #1f2937; }
.app { max-width: 1100px; margin: 0 auto; padding: 16px; }
header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
h1 { font-size: 20px; margin: 0; }
nav button { margin-left: 8px; padding: 6px 16px; border: 1px solid #d1d5db; border-radius: 6px; background: #fff; cursor: pointer; }
nav button.active { background: #2563eb; color: #fff; border-color: #2563eb; }
</style>
```

- [ ] **Step 5: 创建 frontend/src/views/DashboardView.vue**

```vue
<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import { POLL_INTERVAL_MS, fetchModels, fetchProviders, fetchSummary, fetchTrend } from "../api";

const summary = ref({ requests: 0, total_tokens: 0, input_tokens: 0, output_tokens: 0, errors: 0, error_rate: 0, avg_latency_ms: 0 });
const models = ref([]);
const providers = ref([]);
const range = ref("24h");
const chartEl = ref(null);
let chart = null;
let timer = null;

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

async function refresh() {
  try {
    summary.value = await fetchSummary();
    models.value = (await fetchModels()).items;
    providers.value = (await fetchProviders()).items;
    const trend = await fetchTrend(range.value);
    chart.setOption({
      xAxis: { type: "category", data: trend.items.map((t) => t.bucket) },
      yAxis: { type: "value" },
      series: [{ type: "line", smooth: true, areaStyle: {}, data: trend.items.map((t) => t.total_tokens) }],
      tooltip: { trigger: "axis" },
    });
  } catch { /* 后端未就绪时静默，下一轮重试 */ }
}

function maxTokens(list) {
  return Math.max(1, ...list.map((x) => x.total_tokens));
}

onMounted(() => {
  chart = echarts.init(chartEl.value);
  refresh();
  timer = setInterval(refresh, POLL_INTERVAL_MS);
});
onBeforeUnmount(() => {
  clearInterval(timer);
  chart.dispose();
});
watch(range, refresh);
</script>

<template>
  <div>
    <div class="cards">
      <div class="card"><div class="label">今日请求数</div><div class="value">{{ summary.requests }}</div></div>
      <div class="card"><div class="label">今日Token</div><div class="value">{{ fmt(summary.total_tokens) }}</div></div>
      <div class="card"><div class="label">Input Token</div><div class="value">{{ fmt(summary.input_tokens) }}</div></div>
      <div class="card"><div class="label">Output Token</div><div class="value">{{ fmt(summary.output_tokens) }}</div></div>
      <div class="card"><div class="label">今日错误</div><div class="value">{{ summary.errors }}（{{ summary.error_rate }}%）</div></div>
      <div class="card"><div class="label">平均耗时</div><div class="value">{{ (summary.avg_latency_ms / 1000).toFixed(1) }}s</div></div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2>Token Trend</h2>
        <select v-model="range">
          <option value="24h">最近24小时</option>
          <option value="7d">最近7天</option>
          <option value="30d">最近30天</option>
        </select>
      </div>
      <div ref="chartEl" style="height: 260px"></div>
    </div>

    <div class="panel">
      <h2>Model Usage</h2>
      <div v-for="m in models" :key="m.model" class="bar-row">
        <span class="bar-name">{{ m.model }}</span>
        <div class="bar-track"><div class="bar-fill" :style="{ width: (m.total_tokens / maxTokens(models) * 100) + '%' }"></div></div>
        <span class="bar-value">{{ fmt(m.total_tokens) }}</span>
      </div>
    </div>

    <div class="panel">
      <h2>Provider Usage</h2>
      <div v-for="p in providers" :key="p.provider" class="bar-row">
        <span class="bar-name">{{ p.provider }}</span>
        <div class="bar-track"><div class="bar-fill provider" :style="{ width: (p.total_tokens / maxTokens(providers) * 100) + '%' }"></div></div>
        <span class="bar-value">{{ fmt(p.total_tokens) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 16px; }
.card { background: #fff; border-radius: 8px; padding: 12px; }
.label { color: #6b7280; font-size: 12px; }
.value { font-size: 20px; font-weight: 600; margin-top: 4px; }
.panel { background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; }
h2 { font-size: 15px; margin: 0 0 12px; }
.bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.bar-name { width: 160px; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { flex: 1; background: #e5e7eb; border-radius: 4px; height: 12px; }
.bar-fill { background: #2563eb; border-radius: 4px; height: 12px; }
.bar-fill.provider { background: #059669; }
.bar-value { width: 80px; text-align: right; font-size: 13px; }
</style>
```

- [ ] **Step 6: 创建 frontend/src/views/RequestsView.vue**

```vue
<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { POLL_INTERVAL_MS, fetchRequests } from "../api";

const filters = ref({ provider: "", model: "", status: "" });
const page = ref(1);
const data = ref({ items: [], total: 0 });
let timer = null;

async function refresh() {
  const params = { limit: 50, offset: (page.value - 1) * 50 };
  for (const k of ["provider", "model"]) if (filters.value[k]) params[k] = filters.value[k];
  if (filters.value.status !== "") params.status = Number(filters.value.status);
  try {
    data.value = await fetchRequests(params);
  } catch { /* 下一轮重试 */ }
}

onMounted(() => {
  refresh();
  timer = setInterval(refresh, POLL_INTERVAL_MS * 2);
});
onBeforeUnmount(() => clearInterval(timer));
watch(filters, () => { page.value = 1; refresh(); }, { deep: true });
watch(page, refresh);
</script>

<template>
  <div class="panel">
    <div class="filters">
      <input v-model="filters.provider" placeholder="Provider" />
      <input v-model="filters.model" placeholder="Model" />
      <select v-model="filters.status">
        <option value="">全部状态</option>
        <option value="200">200</option>
        <option value="429">429</option>
        <option value="500">500</option>
      </select>
      <span class="total">共 {{ data.total }} 条</span>
      <button :disabled="page <= 1" @click="page--">上一页</button>
      <button :disabled="page * 50 >= data.total" @click="page++">下一页</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>时间</th><th>Provider</th><th>Model</th><th>Input</th><th>Output</th>
          <th>Total</th><th>Latency</th><th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in data.items" :key="r.id">
          <td>{{ r.created_at }}</td>
          <td>{{ r.provider }}</td>
          <td>{{ r.model }}</td>
          <td>{{ r.input_tokens }}</td>
          <td>{{ r.output_tokens }}</td>
          <td>{{ r.total_tokens }}</td>
          <td>{{ (r.latency_ms / 1000).toFixed(1) }}s</td>
          <td :class="r.success ? 'ok' : 'bad'">{{ r.status_code }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.panel { background: #fff; border-radius: 8px; padding: 16px; }
.filters { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
input, select, button { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; }
.total { margin-left: auto; color: #6b7280; font-size: 13px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid #e5e7eb; }
.ok { color: #059669; }
.bad { color: #dc2626; }
</style>
```

- [ ] **Step 7: 安装依赖并构建**

```bash
cd frontend && npm install && npm run build
```

Expected: 构建成功，产物在 `frontend/dist/`。

- [ ] **Step 8: 后端静态托管（修改 backend/__init__.py）**

在 `create_app` 末尾、`return app` 之前加入：

```python
    from starlette.responses import FileResponse
    from starlette.staticfiles import StaticFiles

    dist = ROOT / "frontend" / "dist"
    if (dist / "index.html").exists():
        @app.get("/dashboard", include_in_schema=False)
        async def dashboard():
            return FileResponse(dist / "index.html")

        app.mount("/", StaticFiles(directory=dist, html=True), name="static")
```

（`ROOT` 与 `Path` 已在模块顶部定义。挂载放在所有 `include_router` 之后，保证 `/api/*` 与 `/{provider}/v1/*` 优先匹配。）

- [ ] **Step 9: 手动验证前端**

```bash
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 7788
```

浏览器打开 `http://127.0.0.1:7788/` 与 `/dashboard`：看到 TokenLens 页面，指标卡片显示 0（无数据）；确认 5 秒内页面自动刷新（打开浏览器 DevTools Network 面板观察 `/api/stats/summary` 轮询请求）。然后停止服务。

- [ ] **Step 10: Commit**

```bash
git add frontend/ backend/__init__.py
git commit -m "feat: add vue dashboard with polling and charts"
```

---

### Task 12: 端到端验收测试

**Files:**
- Create: `tests/e2e/test_acceptance.py`

**Interfaces:**
- Consumes: 全部已实现接口。
- Produces: 自动化覆盖 spec 第 23 章验收场景 1~8、10；场景 9、11 为手动清单。

- [ ] **Step 1: 写失败测试 tests/e2e/test_acceptance.py**

```python
"""spec 第 23 章验收场景 1~8、10 的自动化验证（场景 9、11 见手动清单）。"""

import asyncio
import json

import httpx
import pytest

from backend import create_app
from backend.database import database, queries


def sse(chunks, extra_headers=None):
    async def body():
        for c in chunks:
            yield c
    headers = {"content-type": "text/event-stream", **(extra_headers or {})}
    return httpx.Response(200, headers=headers, content=body())


@pytest.fixture
def env(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "providers:\n  provider_a:\n    type: openai\n    base_url: https://api.example.com\n",
        encoding="utf-8",
    )
    app = create_app(db_path=tmp_path / "test.db", config_path=tmp_path / "config.yaml")
    database.init_db(app.state.db_path)
    return app


@pytest.fixture
async def client(env):
    transport = httpx.ASGITransport(app=env)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def set_upstream(app, handler):
    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                         timeout=httpx.Timeout(connect=10.0, read=300.0))


@pytest.mark.asyncio
async def test_scenario_1_non_stream(env, client):
    set_upstream(env, lambda r: httpx.Response(200, json={
        "model": "m", "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}}))
    resp = await client.post("/provider_a/v1/chat/completions", json={"model": "m"})
    assert resp.status_code == 200
    assert queries.query_requests({})["items"][0]["total_tokens"] == 6


@pytest.mark.asyncio
async def test_scenario_2_3_stream_with_injection(env, client):
    chunks = [
        b'data: {"choices":[{"delta":{"content":"a"}}]}\n\n',
        b'data: {"choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":3,"completion_tokens":1,"total_tokens":4}}\n\n',
        b'data: [DONE]\n\n',
    ]
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return sse(chunks)
    set_upstream(env, handler)

    resp = await client.post("/provider_a/v1/chat/completions", json={"model": "m", "stream": True})
    assert resp.status_code == 200 and "a" in resp.text
    assert captured["body"]["stream_options"]["include_usage"] is True
    rec = queries.query_requests({})["items"][0]
    assert rec["total_tokens"] == 4 and rec["success"] == 1


@pytest.mark.asyncio
async def test_scenario_5_error_status(env, client):
    set_upstream(env, lambda r: httpx.Response(429, json={"error": {"type": "rate_limit_error"}}))
    resp = await client.post("/provider_a/v1/chat/completions", json={"model": "m"})
    assert resp.status_code == 429
    rec = queries.query_requests({})["items"][0]
    assert rec["success"] == 0 and rec["error_type"] == "rate_limit_error"


@pytest.mark.asyncio
async def test_scenario_6_client_abort(env, client):
    chunks = [b'data: {"choices":[{"delta":{"content":"x"}}]}\n\n'] * 100
    set_upstream(env, lambda r: sse(chunks))

    async with client.stream("POST", "/provider_a/v1/chat/completions",
                             json={"model": "m", "stream": True}) as resp:
        async for _ in resp.aiter_bytes():
            break  # 立即断开
        await resp.aclose()
    await asyncio.sleep(0.1)  # 等待服务端取消与落库
    rec = queries.query_requests({})["items"][0]
    assert rec["success"] == 0 and rec["error_type"] == "client_abort"


@pytest.mark.asyncio
async def test_scenario_7_gzip_stripped(env, client):
    captured = {}

    def handler(request):
        captured["accept_encoding"] = request.headers.get("accept-encoding")
        return httpx.Response(200, json={"model": "m", "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    set_upstream(env, handler)

    resp = await client.post("/provider_a/v1/chat/completions",
                             headers={"accept-encoding": "gzip"},
                             json={"model": "m"})
    assert resp.status_code == 200
    assert "accept-encoding" not in captured  # TokenLens 已移除
    assert "content-encoding" not in resp.headers
    assert queries.query_requests({})["items"][0]["total_tokens"] == 2


@pytest.mark.asyncio
async def test_scenario_8_dashboard_consistency(env, client):
    set_upstream(env, lambda r: httpx.Response(200, json={
        "model": "m", "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}))
    await client.post("/provider_a/v1/chat/completions", json={"model": "m"})
    summary = (await client.get("/api/stats/summary")).json()
    db_rows = queries.query_requests({})["items"]
    assert summary["requests"] == len(db_rows) == 1
    assert summary["total_tokens"] == sum(r["total_tokens"] for r in db_rows)


@pytest.mark.asyncio
async def test_scenario_10_restart_persistence(env, client):
    set_upstream(env, lambda r: httpx.Response(200, json={
        "model": "m", "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}))
    await client.post("/provider_a/v1/chat/completions", json={"model": "m"})
    first = queries.query_requests({})["total"]
    # 模拟重启：重新 init_db 同一文件
    database.init_db(env.state.db_path)
    assert queries.query_requests({})["total"] == first == 1
```

- [ ] **Step 2: 运行测试**

```bash
.venv/Scripts/python.exe -m pytest tests/e2e/test_acceptance.py -v
```

Expected: 7 PASS（若场景 6 的断连记录未实现，修正 `stream_proxy.py` 的 `asyncio.CancelledError` 分支直至通过）。

- [ ] **Step 3: 运行全量测试**

```bash
.venv/Scripts/python.exe -m pytest -v
```

Expected: 全部 PASS（约 38 个测试）。

- [ ] **Step 4: 手动验收清单（spec 第 23 章场景 9、11）**

1. 启动：`.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 7788`。
2. 场景 11：在 CC Switch 中把任一 Provider 的 Base URL 改为 `http://127.0.0.1:7788/provider_a`，用 Codex / Claude Code 正常对话，确认流式输出无卡顿、Dashboard 出现记录。
3. 场景 9：打开 `data/tokenlens.db`（或调用 `/api/requests`），确认记录中无 Authorization 头、无 API Key、无 Prompt 正文。

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/
git commit -m "test: add e2e acceptance scenarios for mvp"
```

---

## 完成标准

- 全部 pytest 通过（约 38 个）。
- `python main.py`（或 uvicorn 命令）启动后：`/health` 正常；Dashboard 可访问；CC Switch 指向 `http://127.0.0.1:7788/{provider}` 后 Codex/Claude Code 可用（手动场景 11）。
- 无任何测试/实现代码写入 Authorization、API Key、Prompt 内容（隐私约束）。
