import json

import httpx
import pytest

from backend import create_app
from backend.database import database, queries
from backend.proxy.forwarder import build_record

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


def test_build_record_preserves_request_start_time():
    record = build_record(
        request_id="req_start", provider="provider_a", model="m",
        endpoint="/v1/chat/completions", stream=False, usage=None,
        latency_ms=10, status_code=200, created_at="2026-08-14T09:00:00",
    )
    assert record["created_at"] == "2026-08-14T09:00:00"


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
async def test_large_body_under_limit_is_forwarded(app, client):
    database.init_db(app.state.db_path)
    # 1MB 请求体（远超旧版 32KB 上限，模拟 Claude Code 长对话请求）
    body = {"model": "gpt-5.6-sol",
            "messages": [{"role": "user", "content": "x" * (1024 * 1024)}]}
    resp = await client.post(
        "/provider_a/v1/chat/completions",
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["usage"]["total_tokens"] == 15
    assert queries.query_requests({})["total"] == 1


@pytest.mark.asyncio
async def test_body_too_large_413(app, client):
    database.init_db(app.state.db_path)
    # 超过 32MB 上限才返回 413（32 * 1024 * 1024 + 1）
    resp = await client.post("/provider_a/v1/chat/completions",
                             content=b"x" * (32 * 1024 * 1024 + 1),
                             headers={"content-type": "application/json"})
    assert resp.status_code == 413
    assert queries.query_requests({})["total"] == 0


@pytest.mark.asyncio
async def test_passthrough_models_auth_fallback(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "providers:\n  provider_a:\n    type: openai\n"
        "    base_url: https://api.example.com\n    api_key: sk-fallback\n",
        encoding="utf-8",
    )
    app = create_app(db_path=tmp_path / "test.db", config_path=tmp_path / "config.yaml")

    def handler(request):
        assert request.headers.get("authorization") == "Bearer sk-fallback"
        return httpx.Response(200, json={"object": "list", "data": [{"id": "gpt-5.6-sol"}]})

    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)
    database.init_db(app.state.db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/provider_a/v1/models")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["id"] == "gpt-5.6-sol"
    assert queries.query_requests({})["total"] == 0


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
async def test_non_dict_json_body_400_without_record(app, client):
    database.init_db(app.state.db_path)
    resp = await client.post(
        "/provider_a/v1/chat/completions",
        content=b"[1, 2, 3]",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400
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
