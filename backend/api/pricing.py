from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.database.database import get_connection
from backend.pricing import service

router = APIRouter()


class PricingRuleInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str | None = Field(default=None, max_length=80)
    model_pattern: str = Field(min_length=1, max_length=160)
    match_type: Literal["exact", "glob"]
    input_price_cny: Decimal = Field(default=Decimal("0"), ge=0)
    output_price_cny: Decimal = Field(default=Decimal("0"), ge=0)
    cache_read_price_cny: Decimal = Field(default=Decimal("0"), ge=0)
    cache_write_price_cny: Decimal = Field(default=Decimal("0"), ge=0)
    input_includes_cache: bool = False
    priority: int = Field(default=0, ge=-10000, le=10000)
    enabled: bool = True
    source_note: str | None = Field(default=None, max_length=500)


def _data(item: PricingRuleInput) -> dict:
    return item.model_dump() if hasattr(item, "model_dump") else item.dict()


@router.get("/api/pricing/rules")
async def rules():
    return {"items": [service.public_rule(rule) for rule in service.list_rules(get_connection())]}


@router.post("/api/pricing/rules", status_code=201)
async def create(item: PricingRuleInput):
    try:
        return service.create_rule(get_connection(), _data(item))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/pricing/rules/{rule_id}")
async def update(rule_id: int, item: PricingRuleInput):
    try:
        result = service.update_rule(get_connection(), rule_id, _data(item))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="pricing rule not found")
    return result


@router.delete("/api/pricing/rules/{rule_id}", status_code=204)
async def delete(rule_id: int):
    if not service.delete_rule(get_connection(), rule_id):
        raise HTTPException(status_code=404, detail="pricing rule not found")


@router.post("/api/pricing/rules/preview")
async def preview(item: PricingRuleInput):
    try:
        return {"items": service.preview_rule(get_connection(), _data(item))}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
