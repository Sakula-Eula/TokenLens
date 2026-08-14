from fastapi import APIRouter, HTTPException

from backend.statistics import service

router = APIRouter()


@router.get("/api/stats/summary")
async def summary():
    return service.summary()


@router.get("/api/stats/models")
async def models():
    return service.models()


@router.get("/api/stats/providers")
async def providers():
    return service.providers()


@router.get("/api/stats/trend")
async def trend(range: str = "24h"):
    if range not in ("24h", "7d", "30d"):
        raise HTTPException(status_code=400, detail="range must be 24h, 7d or 30d")
    return service.trend(range)
