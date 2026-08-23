import json

import httpx
import pytest

from backend import create_app
from backend.database import database, queries

UPSTREAM_OK = {
    "id": "resp_up_1",
    "model": "gpt-5.6-terra",
    "usage": {
        "input_tokens": 12500,
        "input_tokens_details": {"cached_tokens": 8000},
        "output_tokens": 3210,
        "total_tokens": 15710,
    },
}


def _upstream_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/responses" and request.url.host == "api.example.com":
        return httpx.Response(200, json=UPSTREAM_OK, headers={"x-request-id": "req_resp_1"})
    return httpx.Response(404, json={"error": {"message": "not found"}})


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
async def test_responses_non_stream_proxy_and_record(app, client):
    database.init_db(app.state.db_path)
    resp = await client.post(
        "/provider_a/v1/responses",
        json={"model": "gpt-5.6-terra", "input": "hi"},
    )
    assert resp.status_code == 200
    assert resp.json()["usage"]["total_tokens"] == 15710
    rows = queries.query_requests({})["items"]
    assert len(rows) == 1
    rec = rows[0]
    assert rec["provider"] == "provider_a" and rec["model"] == "gpt-5.6-terra"
    assert rec["input_tokens"] == 12500 and rec["output_tokens"] == 3210
    assert rec["cache_read_tokens"] == 8000 and rec["total_tokens"] == 15710
    assert rec["endpoint"] == "/v1/responses" and rec["stream"] == 0
    assert rec["status_code"] == 200 and rec["success"] == 1
    assert rec["request_id"] == "req_resp_1"




@pytest.mark.asyncio
async def test_responses_stream_completed_record(app, client):
    database.init_db(app.state.db_path)

    def handler(request):
        body = json.loads(request.content)
        assert body["stream"] is True
        # Responses API 流式不需要 stream_options 注入，usage 在 response.completed 里
        assert "stream_options" not in body
        return sse_response([
            b'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"Hi"}\n\n',
            b'event: response.completed\ndata: {"type":"response.completed","response":{"id":"resp_1","usage":{"input_tokens":10,"input_tokens_details":{"cached_tokens":4},"output_tokens":5,"total_tokens":15}}}\n\n',
        ], {"x-request-id": "req_resp_stream"})

    app.state.client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(timeout=10.0, connect=10.0, read=300.0),
    )
    resp = await client.post("/provider_a/v1/responses", json={"model": "m", "stream": True})
    assert resp.status_code == 200
    assert "Hi" in resp.text
    rec = queries.query_requests({})["items"][0]
    assert rec["stream"] == 1 and rec["endpoint"] == "/v1/responses"
    assert rec["input_tokens"] == 10 and rec["output_tokens"] == 5
    assert rec["cache_read_tokens"] == 4 and rec["total_tokens"] == 15
    assert rec["success"] == 1 and rec["request_id"] == "req_resp_stream"


@pytest.mark.asyncio
async def test_responses_error_status_recorded(app, client):
    def handler(request):
        return httpx.Response(429, json={"error": {"type": "rate_limit_error", "message": "slow down"}})

    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)
    database.init_db(app.state.db_path)
    resp = await client.post("/provider_a/v1/responses", json={"model": "m"})
    assert resp.status_code == 429
    rec = queries.query_requests({})["items"][0]
    assert rec["success"] == 0 and rec["status_code"] == 429
    assert rec["error_type"] == "rate_limit_error"


@pytest.mark.asyncio
async def test_responses_auth_fallback(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "providers:\n  provider_a:\n    type: openai\n"
        "    base_url: https://api.example.com\n    api_key: sk-fallback\n",
        encoding="utf-8",
    )
    app = create_app(db_path=tmp_path / "test.db", config_path=tmp_path / "config.yaml")

    def handler(request):
        assert request.headers.get("authorization") == "Bearer sk-fallback"
        return httpx.Response(200, json=UPSTREAM_OK)

    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)
    database.init_db(app.state.db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/provider_a/v1/responses", json={"model": "m"})
    assert resp.status_code == 200
    assert queries.query_requests({})["total"] == 1


@pytest.mark.asyncio
async def test_responses_unknown_provider_404(app, client):
    database.init_db(app.state.db_path)
    resp = await client.post("/nope/v1/responses", json={})
    assert resp.status_code == 404
    assert queries.query_requests({})["total"] == 0


@pytest.mark.asyncio
async def test_codex_mode_strips_v1_and_records_responses_usage(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "providers:\n  codex:\n    type: openai\n"
        "    base_url: https://chatgpt.example.com/backend-api/codex\n"
        "    upstream_path_mode: codex\n",
        encoding="utf-8",
    )

    def handler(request):
        assert request.url.path == "/backend-api/codex/responses"
        assert request.url.host == "chatgpt.example.com"
        return httpx.Response(200, json=UPSTREAM_OK, headers={"x-request-id": "req_codex_1"})

    app = create_app(
        db_path=tmp_path / "test.db",
        config_path=tmp_path / "config.yaml",
        upstream_transport=httpx.MockTransport(handler),
    )
    database.init_db(app.state.db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/codex/v1/responses", json={"model": "gpt-5.6-terra", "input": "hi"})
    assert resp.status_code == 200
    rec = queries.query_requests({})["items"][0]
    assert rec["provider"] == "codex" and rec["endpoint"] == "/responses"
    assert rec["request_id"] == "req_codex_1"
    assert rec["input_tokens"] == 12500 and rec["output_tokens"] == 3210
    assert rec["cache_read_tokens"] == 8000 and rec["total_tokens"] == 15710
    assert rec["status_code"] == 200 and rec["success"] == 1
