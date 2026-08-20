from fastapi import APIRouter, HTTPException

from backend.database import cost_queries

router = APIRouter()


def _call(function, *args):
    try:
        return function(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/costs/summary")
async def summary(period: str = "today"):
    return _call(cost_queries.summary, period)


@router.get("/api/costs/trend")
async def trend(period: str = "month"):
    return _call(cost_queries.trend, period)


@router.get("/api/costs/models")
async def models(period: str = "month", limit: int = 50):
    return _call(cost_queries.grouped, "model", period, limit)


@router.get("/api/costs/providers")
async def providers(period: str = "month", limit: int = 50):
    return _call(cost_queries.grouped, "provider", period, limit)


@router.get("/api/costs/unpriced")
async def unpriced(period: str = "month"):
    return _call(cost_queries.unpriced, period)
