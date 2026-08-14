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
