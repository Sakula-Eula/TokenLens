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
                                         timeout=httpx.Timeout(timeout=10.0, connect=10.0, read=300.0))


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
async def test_scenario_6_client_abort(env):
    chunks = [b'data: {"choices":[{"delta":{"content":"x"}}]}\n\n'] * 100
    gate = asyncio.Event()

    async def body():
        yield chunks[0]
        await gate.wait()  # 流中阻塞，给断连取消留出真实挂起点
        for c in chunks[1:]:
            yield c

    set_upstream(env, lambda r: httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=body()))

    # httpx 0.27.2 的 ASGITransport 会缓冲完整响应、无法传达中途断连；
    # 这里按 ASGI 协议模拟客户端断开：首个 body chunk 发出后 receive()
    # 返回 http.disconnect，等价于 uvicorn 在客户端断开时取消流式响应任务。
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http",
        "path": "/provider_a/v1/chat/completions",
        "raw_path": b"/provider_a/v1/chat/completions",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json"), (b"host", b"test")],
        "client": ("127.0.0.1", 123), "server": ("test", 80),
        "root_path": "", "app": env,
    }
    body_sent = asyncio.Event()
    req_msgs = iter([
        {"type": "http.request", "body": b'{"model": "m", "stream": true}', "more_body": True},
        {"type": "http.request", "body": b"", "more_body": False},
    ])

    async def receive():
        try:
            return next(req_msgs)
        except StopIteration:
            await body_sent.wait()  # 等首个 chunk 已发给客户端 -> 客户端断开
            return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            body_sent.set()

    await asyncio.wait_for(env(scope, receive, send), timeout=5)
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
