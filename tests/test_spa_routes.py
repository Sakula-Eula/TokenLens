import httpx
import pytest

import backend


@pytest.mark.asyncio
async def test_spa_routes_and_api_404_are_separate(tmp_path, monkeypatch):
    root = tmp_path / "app"
    dist = root / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>TokenLens SPA</html>", encoding="utf-8")
    monkeypatch.setattr(backend, "ROOT", root)
    app = backend.create_app(db_path=tmp_path / "test.db", config_path=tmp_path / "config.yaml")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("/", "/dashboard", "/models", "/providers", "/tokens", "/costs",
                     "/requests", "/settings", "/widget"):
            response = await client.get(path)
            assert response.status_code == 200 and "TokenLens SPA" in response.text
        assert (await client.get("/errors")).status_code == 404
        response = await client.get("/api/does-not-exist")
        assert response.status_code == 404 and response.headers["content-type"].startswith("application/json")
