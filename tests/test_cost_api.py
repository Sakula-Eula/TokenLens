from datetime import datetime

import httpx
import pytest

from backend import create_app
from backend.database import database


def _record(model="gpt-5.6-sol", provider="openai"):
    return {"request_id": model, "provider": provider, "model": model,
            "endpoint": "/v1/chat/completions", "stream": 0, "input_tokens": 1000,
            "output_tokens": 500, "cache_read_tokens": 0, "cache_write_tokens": 0,
            "total_tokens": 1500, "latency_ms": 100, "status_code": 200, "success": 1,
            "error_type": None, "created_at": datetime.now().isoformat(timespec="seconds")}


@pytest.fixture
async def client(tmp_path):
    app = create_app(db_path=tmp_path / "cost.db", config_path=tmp_path / "config.yaml")
    database.insert_request(_record())
    database.insert_request(_record("unpriced-private", "private"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_cost_summary_groups_trend_and_unpriced(client):
    summary = (await client.get("/api/costs/summary", params={"period": "today"})).json()
    assert summary["requests"] == 2 and summary["priced_requests"] == 1
    assert summary["unpriced_requests"] == 1 and summary["total_cost_micros"] > 0
    assert len((await client.get("/api/costs/models")).json()["items"]) == 2
    assert len((await client.get("/api/costs/providers")).json()["items"]) == 2
    assert (await client.get("/api/costs/trend")).json()["items"]
    assert (await client.get("/api/costs/unpriced")).json()["items"][0]["model"] == "unpriced-private"
    assert (await client.get("/api/costs/summary", params={"period": "year"})).status_code == 400


@pytest.mark.asyncio
async def test_pricing_crud_and_preview_does_not_reprice_history(client):
    initial = (await client.get("/api/pricing/rules")).json()["items"]
    before = (await client.get("/api/costs/summary")).json()["total_cost_micros"]
    payload = {"name": "Private", "provider": "private", "model_pattern": "unpriced-*",
               "match_type": "glob", "input_price_cny": "1", "output_price_cny": "2",
               "cache_read_price_cny": "0.1", "cache_write_price_cny": "1.25",
               "input_includes_cache": True, "priority": 500, "enabled": True}
    preview = await client.post("/api/pricing/rules/preview", json=payload)
    assert preview.status_code == 200 and preview.json()["items"][0]["model"] == "unpriced-private"
    created = await client.post("/api/pricing/rules", json=payload)
    assert created.status_code == 201
    item = created.json()
    assert item["input_price_cny"] == "1" and len(initial) + 1 == len((await client.get("/api/pricing/rules")).json()["items"])
    payload["input_price_cny"] = "3.5"
    assert (await client.put(f"/api/pricing/rules/{item['id']}", json=payload)).status_code == 200
    assert (await client.get("/api/costs/summary")).json()["total_cost_micros"] == before
    assert (await client.delete(f"/api/pricing/rules/{item['id']}")).status_code == 204
