import httpx
import pytest

from backend import create_app


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "providers:\n  alpha:\n    type: openai\n    base_url: https://api.example.com\n    api_key: secret-value\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def app(tmp_path, config_path):
    async def upstream(request):
        return httpx.Response(200, json={"data": []})

    return create_app(
        db_path=tmp_path / "test.db",
        config_path=config_path,
        upstream_transport=httpx.MockTransport(upstream),
    )


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_settings_never_return_api_key(client):
    response = await client.get("/api/settings/providers")
    assert response.status_code == 200
    provider = response.json()["items"][0]
    assert provider["has_api_key"] is True
    assert "api_key" not in provider
    assert "secret-value" not in response.text


@pytest.mark.asyncio
async def test_update_preserves_api_key_and_hot_loads_provider(client, config_path, app):
    response = await client.put("/api/settings/providers", json={"items": [
        {"name": "alpha", "type": "openai", "base_url": "https://new.example.com"},
        {"name": "beta", "type": "anthropic", "base_url": "https://api.anthropic.com", "api_key": "new-secret"},
        {"name": "gamma", "type": "responses", "base_url": "https://api.openai.com"},
    ]})
    assert response.status_code == 200
    assert response.json()["restart_required"] is False
    saved = config_path.read_text(encoding="utf-8")
    assert "secret-value" in saved and "new-secret" in saved
    assert "secret-value" not in response.text and "new-secret" not in response.text
    assert set(app.state.providers) == {"alpha", "beta", "gamma"}
    assert app.state.providers["gamma"].type == "responses"

    proxy_response = await client.get("/beta/v1/models")
    assert proxy_response.status_code == 200
    assert proxy_response.json() == {"data": []}


@pytest.mark.asyncio
async def test_update_saves_and_returns_upstream_path_mode(client, config_path):
    response = await client.put("/api/settings/providers", json={"items": [
        {"name": "alpha", "type": "openai", "base_url": "https://api.example.com"},
        {"name": "beta", "type": "anthropic", "base_url": "https://api.anthropic.com", "upstream_path_mode": "codex"},
    ]})
    assert response.status_code == 200
    saved = config_path.read_text(encoding="utf-8")
    assert "upstream_path_mode: codex" in saved
    items = {i["name"]: i for i in response.json()["items"]}
    assert items["beta"]["upstream_path_mode"] == "codex"
    assert items["alpha"]["upstream_path_mode"] == "v1"


@pytest.mark.asyncio
async def test_update_rejects_invalid_provider(client):
    response = await client.put("/api/settings/providers", json={"items": [
        {"name": "bad/name", "type": "openai", "base_url": "https://api.example.com/v1"},
    ]})
    assert response.status_code == 400
