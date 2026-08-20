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
async def models(range: str = "24h"):
    return service.models(_validate_range(range))


@router.get("/api/stats/providers")
async def providers(range: str = "24h"):
    return service.providers(_validate_range(range))


@router.get("/api/stats/trend")
async def trend(range: str = "24h"):
    return service.trend(_validate_range(range))


@router.get("/api/stats/errors")
async def errors(range: str = "24h"):
    return service.errors(_validate_range(range))
