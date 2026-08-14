from fastapi import APIRouter

from backend.database import queries

router = APIRouter()


@router.get("/api/requests")
async def list_requests(provider: str | None = None, model: str | None = None,
                        status: int | None = None, date_from: str | None = None,
                        date_to: str | None = None, limit: int = 50, offset: int = 0):
    result = queries.query_requests({
        "provider": provider, "model": model, "status": status,
        "date_from": date_from, "date_to": date_to, "limit": limit, "offset": offset,
    })
    result["limit"] = limit
    result["offset"] = offset
    return result
