from fastapi import APIRouter, HTTPException

from backend.database import queries

router = APIRouter()


@router.get("/api/requests")
async def list_requests(provider: str | None = None, model: str | None = None,
                        status: int | None = None, date_from: str | None = None,
                        date_to: str | None = None, success: bool | None = None,
                        provider_contains: str | None = None, model_contains: str | None = None,
                        status_group: str | None = None,
                        limit: int = 50, offset: int = 0):
    limit = max(1, min(limit, 200))
    try:
        result = queries.query_requests({
            "provider": provider, "model": model, "provider_contains": provider_contains,
            "model_contains": model_contains, "status": status, "status_group": status_group,
            "date_from": date_from, "date_to": date_to, "success": success,
            "limit": limit, "offset": offset,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result["limit"] = limit
    result["offset"] = offset
    return result


@router.get("/api/requests/{record_id}")
async def request_detail(record_id: int):
    item = queries.get_request(record_id)
    if item is None:
        raise HTTPException(status_code=404, detail="request record not found")
    return item
