from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.config import load_config, public_providers, save_providers

router = APIRouter()


class ProviderInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: Literal["openai", "anthropic"]
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: str | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False
    upstream_path_mode: Literal["v1", "codex"] = "v1"


class ProviderSettings(BaseModel):
    items: list[ProviderInput]


@router.get("/api/settings/providers")
async def get_providers(request: Request):
    try:
        items = public_providers(request.app.state.config_path)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": items}


@router.put("/api/settings/providers")
async def update_providers(payload: ProviderSettings, request: Request):
    try:
        items = [item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in payload.items]
        save_providers(request.app.state.config_path, items)
        request.app.state.providers = load_config(request.app.state.config_path)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": public_providers(request.app.state.config_path), "restart_required": False}
