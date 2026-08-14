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
