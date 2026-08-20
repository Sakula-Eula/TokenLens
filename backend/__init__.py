from pathlib import Path

import httpx
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parent.parent


def create_app(db_path: Path | None = None, config_path: Path | None = None,
               upstream_transport=None) -> FastAPI:
    app = FastAPI(title="TokenLens")
    app.state.db_path = db_path or ROOT / "data" / "tokenlens.db"
    app.state.config_path = config_path or ROOT / "config.yaml"
    app.state.client = httpx.AsyncClient(
        timeout=httpx.Timeout(timeout=10.0, connect=10.0, read=300.0),
        follow_redirects=False,
        transport=upstream_transport,
    )
    app.state.providers: dict = {}

    from backend.config import load_config

    app.state.providers = load_config(app.state.config_path)

    from backend.database.database import init_db
    from backend.proxy.router import router as proxy_router

    init_db(app.state.db_path)
    app.include_router(proxy_router)

    from backend.api.requests import router as requests_router
    from backend.api.settings import router as settings_router
    from backend.api.stats import router as stats_router

    app.include_router(stats_router)
    app.include_router(requests_router)
    app.include_router(settings_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    from starlette.responses import FileResponse
    from starlette.staticfiles import StaticFiles

    dist = ROOT / "frontend" / "dist"
    if (dist / "index.html").exists():
        async def frontend_app():
            return FileResponse(dist / "index.html")

        for route_path in ("/", "/dashboard", "/models", "/providers", "/tokens",
                           "/requests", "/errors", "/settings", "/widget"):
            app.add_api_route(route_path, frontend_app, methods=["GET"], include_in_schema=False)
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

    return app
