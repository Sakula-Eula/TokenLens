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
        timeout=httpx.Timeout(timeout=10.0, connect=10.0, read=300.0),
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
async def test_stream_closes_upstream_response_after_completion(app, client):
    captured = {}

    def handler(request):
        response = sse_response([b'data: [DONE]\n\n'])
        captured["response"] = response
        return response

    _set_upstream(app, handler)
    response = await client.post("/provider_a/v1/chat/completions", json={"model": "m", "stream": True})
    assert response.status_code == 200
    assert captured["response"].is_closed


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


@pytest.mark.asyncio
async def test_stream_http_error_records_error_type(app, client):
    database.init_db(app.state.db_path)

    def handler(request):
        return httpx.Response(
            429,
            headers={"content-type": "application/json"},
            content=b'{"error":{"type":"rate_limit_error","message":"slow"}}',
        )
    _set_upstream(app, handler)

    resp = await client.post("/provider_a/v1/chat/completions", json={"model": "m", "stream": True})
    assert resp.status_code == 429
    assert resp.json()["error"]["type"] == "rate_limit_error"
    rec = queries.query_requests({})["items"][0]
    assert rec["success"] == 0 and rec["status_code"] == 429 and rec["error_type"] == "rate_limit_error"
