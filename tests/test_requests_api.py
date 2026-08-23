from datetime import datetime

import httpx
import pytest

from backend import create_app
from backend.database import database


@pytest.fixture
async def client(tmp_path):
    app = create_app(db_path=tmp_path / "test.db", config_path=tmp_path / "config.yaml")
    database.insert_request({
        "request_id": "req_detail", "provider": "provider-a", "model": "gpt-test",
        "endpoint": "/v1/chat/completions", "stream": 1, "input_tokens": 10,
        "output_tokens": 5, "cache_read_tokens": 3, "cache_write_tokens": 2,
        "total_tokens": 15, "latency_ms": 900, "status_code": 200, "success": 1,
        "error_type": None, "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_request_detail_and_not_found(client):
    listed = (await client.get("/api/requests")).json()["items"][0]
    response = await client.get(f"/api/requests/{listed['id']}")
    assert response.status_code == 200
    item = response.json()
    assert item["request_id"] == "req_detail" and item["cache_write_tokens"] == 2
    assert item["cost"] is not None and item["cost"]["priced"] == 0
    assert not ({"authorization", "api_key", "prompt", "response"} & item.keys())
    assert (await client.get("/api/requests/999999")).status_code == 404


@pytest.mark.asyncio
async def test_request_status_group_and_contains(client):
    response = await client.get("/api/requests", params={"model_contains": "gpt", "status_group": "2xx"})
    assert response.status_code == 200 and response.json()["total"] == 1
    assert (await client.get("/api/requests", params={"status_group": "3xx"})).status_code == 400
