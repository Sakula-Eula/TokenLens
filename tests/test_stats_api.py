from datetime import datetime, timedelta

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
    database.insert_request(_record(cache_read_tokens=20, cache_write_tokens=10))
    database.insert_request(_record(
        request_id="req_2", success=0, status_code=500, error_type="server_error",
        cache_read_tokens=3,
    ))
    resp = await client.get("/api/stats/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requests"] == 2 and data["errors"] == 1
    assert data["input_tokens"] == 200 and data["total_tokens"] == 300
    assert data["cache_read_tokens"] == 23 and data["cache_write_tokens"] == 10
    assert data["cache_tokens"] == 33 and data["range"] == "24h"
    assert data["error_rate"] == 50.0


@pytest.mark.asyncio
async def test_models_and_providers(app, client):
    database.init_db(app.state.db_path)
    database.insert_request(_record())
    database.insert_request(_record(request_id="req_2", model="claude-sonnet", provider="provider_b",
                                    total_tokens=50, input_tokens=30, output_tokens=20))
    models = (await client.get("/api/stats/models", params={"range": "7d"})).json()["items"]
    assert models[0]["model"] == "gpt-5.6-sol" and models[0]["total_tokens"] == 150
    providers = (await client.get("/api/stats/providers", params={"range": "7d"})).json()["items"]
    assert len(providers) == 2


@pytest.mark.asyncio
async def test_trend_and_bad_range(app, client):
    database.init_db(app.state.db_path)
    database.insert_request(_record())
    assert (await client.get("/api/stats/trend", params={"range": "24h"})).status_code == 200
    assert (await client.get("/api/stats/trend", params={"range": "9d"})).status_code == 400
    assert (await client.get("/api/stats/summary", params={"range": "9d"})).status_code == 400
    assert (await client.get("/api/stats/models", params={"range": "9d"})).status_code == 400
    assert (await client.get("/api/stats/providers", params={"range": "9d"})).status_code == 400


@pytest.mark.asyncio
async def test_range_is_shared_and_errors_endpoint(app, client):
    database.init_db(app.state.db_path)
    now = datetime.now()
    database.insert_request(_record(request_id="recent_error", success=0, status_code=429,
                                    error_type="rate_limit"))
    database.insert_request(_record(request_id="old_error", success=0, status_code=500,
                                    error_type="server_error",
                                    created_at=(now - timedelta(hours=25)).isoformat(timespec="seconds")))
    summary = (await client.get("/api/stats/summary", params={"range": "24h"})).json()
    models = (await client.get("/api/stats/models", params={"range": "24h"})).json()["items"]
    errors = (await client.get("/api/stats/errors", params={"range": "24h"})).json()
    assert summary["requests"] == 1 and models[0]["requests"] == 1
    assert errors == {
        "errors": 1, "total_requests": 1, "error_rate": 100.0,
        "by_status": [{"status_code": 429, "count": 1}],
        "by_type": [{"error_type": "rate_limit", "count": 1}],
    }
    assert (await client.get("/api/stats/errors", params={"range": "invalid"})).status_code == 400


@pytest.mark.asyncio
async def test_requests_endpoint(app, client):
    database.init_db(app.state.db_path)
    database.insert_request(_record())
    database.insert_request(_record(request_id="req_2", model="claude-sonnet", success=0, status_code=500))
    resp = await client.get("/api/requests", params={"model": "claude-sonnet", "limit": 10})
    data = resp.json()
    assert data["total"] == 1 and data["items"][0]["request_id"] == "req_2"
    assert "authorization" not in data["items"][0]
    successful = (await client.get("/api/requests", params={"success": "true"})).json()
    failed = (await client.get("/api/requests", params={"success": "false"})).json()
    assert successful["total"] == 1 and failed["total"] == 1


@pytest.mark.asyncio
async def test_requests_endpoint_clamps_limit(app, client):
    database.init_db(app.state.db_path)
    database.insert_request(_record())
    database.insert_request(_record(request_id="req_2"))

    too_small = (await client.get("/api/requests", params={"limit": -1})).json()
    assert too_small["limit"] == 1 and len(too_small["items"]) == 1

    too_large = (await client.get("/api/requests", params={"limit": 999})).json()
    assert too_large["limit"] == 200 and len(too_large["items"]) == 2
