from fastapi import APIRouter, HTTPException

from backend.statistics import service

router = APIRouter()
VALID_RANGES = ("24h", "7d", "30d")


def _validate_range(range_key: str) -> str:
    if range_key not in VALID_RANGES:
        raise HTTPException(status_code=400, detail="range must be 24h, 7d or 30d")
    return range_key


@router.get("/api/stats/summary")
async def summary(range: str = "24h"):
    return service.summary(_validate_range(range))


@router.get("/api/stats/models")
async def models(range: str = "24h", search: str | None = None, limit: int = 50, offset: int = 0,
                 sort_by: str = "total_tokens", order: str = "desc"):
    try:
        return service.models(_validate_range(range), {"model_contains": search},
                              limit=limit, offset=offset, sort_by=sort_by, order=order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/stats/providers")
async def providers(range: str = "24h", search: str | None = None, limit: int = 50, offset: int = 0,
                    sort_by: str = "total_tokens", order: str = "desc"):
    try:
        return service.providers(_validate_range(range), {"provider_contains": search},
                                 limit=limit, offset=offset, sort_by=sort_by, order=order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/stats/trend")
async def trend(range: str = "24h", provider: str | None = None, model: str | None = None):
    return service.trend(_validate_range(range), {"provider": provider, "model": model})


@router.get("/api/stats/errors")
async def errors(range: str = "24h", provider: str | None = None, model: str | None = None,
                 status: int | None = None, status_group: str | None = None,
                 date_from: str | None = None, date_to: str | None = None):
    filters = {"provider_contains": provider, "model_contains": model, "status": status,
               "status_group": status_group, "date_from": date_from, "date_to": date_to}
    try:
        return service.errors(_validate_range(range), filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
