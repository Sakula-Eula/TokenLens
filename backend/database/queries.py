from datetime import datetime, timedelta

from backend.database.database import get_connection


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


RANGE_KEYS = ("12h", "24h", "last24h", "7d", "30d")
GROUP_SORT_FIELDS = {
    "requests", "input_tokens", "output_tokens", "cache_tokens",
    "total_tokens", "total_cost_micros", "avg_latency_ms", "errors", "error_rate",
}


def range_since(range_key: str) -> str:
    """Return the lower bound used by all statistics queries."""
    assert range_key in RANGE_KEYS
    now = datetime.now()
    if range_key == "24h":
        return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    if range_key in ("12h", "last24h"):
        hours = 12 if range_key == "12h" else 24
        return (now - timedelta(hours=hours)).isoformat(timespec="seconds")
    return (now - timedelta(days=int(range_key[:-1]))).isoformat(timespec="seconds")


def _summary(where: str, params: tuple | list) -> dict:
    conn = get_connection()
    row = conn.execute(
        f"""SELECT COUNT(*) AS requests,
                   COALESCE(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END), 0) AS success,
                   COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS errors,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                   COALESCE(SUM((SELECT total_cost_micros FROM request_costs c WHERE c.request_row_id = api_requests.id)), 0) AS total_cost_micros,
                   COALESCE(SUM(CASE WHEN COALESCE((SELECT priced FROM request_costs c WHERE c.request_row_id = api_requests.id), 0) = 0 THEN 1 ELSE 0 END), 0) AS unpriced_requests
            FROM api_requests WHERE {where}""",
        params,
    ).fetchone()
    return _row_to_dict(row)


def today_summary(date_str: str) -> dict:
    """Legacy calendar-day summary retained for callers outside the HTTP API."""
    return _summary("substr(created_at, 1, 10) = ?", (date_str,))


def range_summary(range_key: str) -> dict:
    return _summary("created_at >= ?", (range_since(range_key),))


def _escape_like(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filter_clause(filters: dict, *, force_failure: bool = False) -> tuple[str, list]:
    where, params = [], []
    if filters.get("provider"):
        where.append("provider = ?")
        params.append(filters["provider"])
    if filters.get("provider_contains"):
        where.append("provider LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(filters['provider_contains'])}%")
    if filters.get("model"):
        where.append("model = ?")
        params.append(filters["model"])
    if filters.get("model_contains"):
        where.append("model LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(filters['model_contains'])}%")
    if filters.get("status") is not None:
        where.append("status_code = ?")
        params.append(int(filters["status"]))
    if filters.get("status_group"):
        group = str(filters["status_group"]).lower()
        if group not in ("2xx", "4xx", "5xx"):
            raise ValueError("status_group must be 2xx, 4xx or 5xx")
        start = int(group[0]) * 100
        where.append("status_code >= ? AND status_code < ?")
        params.extend((start, start + 100))
    if force_failure:
        where.append("success = 0")
    elif filters.get("success") is not None:
        where.append("success = ?")
        params.append(1 if filters["success"] else 0)
    if filters.get("date_from"):
        where.append("created_at >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("created_at < ?")
        params.append(filters["date_to"])
    return ((" WHERE " + " AND ".join(where)) if where else ""), params


def filters_for_range(range_key: str, filters: dict | None = None) -> dict:
    assert range_key in RANGE_KEYS
    result = dict(filters or {})
    if not result.get("date_from"):
        result["date_from"] = range_since(range_key)
    return result


def filtered_summary(filters: dict) -> dict:
    clause, params = _filter_clause(filters)
    return _summary(clause.removeprefix(" WHERE ") or "1 = 1", params)


def group_stats(column: str, range_or_date: str) -> list[dict]:
    """Group request totals for a rolling range or, for compatibility, a date."""
    assert column in ("model", "provider")
    if range_or_date in RANGE_KEYS:
        where, params = "created_at >= ?", (range_since(range_or_date),)
    else:
        where, params = "substr(created_at, 1, 10) = ?", (range_or_date,)
    legacy_filters = {"date_from": params[0]} if range_or_date in RANGE_KEYS else {"calendar_date": params[0]}
    return grouped_stats(column, legacy_filters, limit=10000)["items"]


def grouped_stats(column: str, filters: dict, limit: int = 50, offset: int = 0,
                  sort_by: str = "total_tokens", order: str = "desc") -> dict:
    assert column in ("model", "provider")
    if sort_by not in GROUP_SORT_FIELDS:
        raise ValueError(f"unsupported sort field: {sort_by}")
    order = order.lower()
    if order not in ("asc", "desc"):
        raise ValueError("order must be asc or desc")
    filters = dict(filters)
    calendar_date = filters.pop("calendar_date", None)
    clause, params = _filter_clause(filters)
    if calendar_date:
        calendar = "substr(created_at, 1, 10) = ?"
        clause = f"{clause} {'AND' if clause else 'WHERE'} {calendar}"
        params.append(calendar_date)
    key_expr = f"COALESCE({column}, 'unknown')"
    from_where = f"FROM api_requests{clause}"
    select = f"""SELECT {key_expr} AS {column},
                   COUNT(*) AS requests,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                   COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS errors,
                   COALESCE(SUM((SELECT total_cost_micros FROM request_costs c WHERE c.request_row_id = api_requests.id)), 0) AS total_cost_micros,
                   COALESCE(SUM(CASE WHEN COALESCE((SELECT priced FROM request_costs c WHERE c.request_row_id = api_requests.id), 0) = 0 THEN 1 ELSE 0 END), 0) AS unpriced_requests,
                   CASE WHEN COUNT(*) = 0 THEN 0 ELSE
                     ROUND(COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) * 100.0 / COUNT(*), 2)
                   END AS error_rate
            {from_where} GROUP BY {key_expr}"""
    conn = get_connection()
    total = conn.execute(f"SELECT COUNT(*) FROM (SELECT 1 {from_where} GROUP BY {key_expr})", params).fetchone()[0]
    limit = max(1, min(int(limit), 200))
    offset = max(int(offset), 0)
    rows = conn.execute(f"{select} ORDER BY {sort_by} {order.upper()}, {column} ASC LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
    return {"items": [_row_to_dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def trend_stats(range_key: str, filters: dict | None = None, bucket_hours: int | None = None) -> list[dict]:
    assert range_key in RANGE_KEYS
    if bucket_hours not in (None, 1, 3):
        raise ValueError("bucket_hours must be 1 or 3")
    if bucket_hours == 1 or (bucket_hours is None and range_key in ("12h", "24h", "last24h")):
        bucket_expr = "substr(created_at, 1, 13)"
    elif bucket_hours == 3:
        bucket_expr = (
            "substr(created_at, 1, 11) || "
            "printf('%02d', CAST(CAST(substr(created_at, 12, 2) AS INTEGER) / 3 AS INTEGER) * 3)"
        )
    else:
        bucket_expr = "substr(created_at, 1, 10)"
    scoped = filters_for_range(range_key, filters)
    clause, params = _filter_clause(scoped)
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT {bucket_expr} AS bucket,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens
                   ,COALESCE(SUM((SELECT total_cost_micros FROM request_costs c WHERE c.request_row_id = api_requests.id)), 0) AS total_cost_micros
            FROM api_requests{clause}
            GROUP BY bucket ORDER BY bucket""",
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def error_stats(range_key: str, filters: dict | None = None) -> dict:
    """Return failure-only status-code and error-type distributions for a range."""
    scoped = filters_for_range(range_key, filters)
    clause, params = _filter_clause(scoped, force_failure=True)
    conn = get_connection()
    by_status = conn.execute(
        f"""SELECT COALESCE(status_code, 0) AS status_code, COUNT(*) AS count
           FROM api_requests{clause}
           GROUP BY status_code ORDER BY count DESC, status_code ASC""",
        params,
    ).fetchall()
    by_type = conn.execute(
        f"""SELECT COALESCE(error_type, 'unknown') AS error_type, COUNT(*) AS count
           FROM api_requests{clause}
           GROUP BY error_type ORDER BY count DESC, error_type ASC""",
        params,
    ).fetchall()
    return {
        "by_status": [_row_to_dict(row) for row in by_status],
        "by_type": [_row_to_dict(row) for row in by_type],
    }


def query_requests(filters: dict) -> dict:
    clause, params = _filter_clause(filters)
    limit = max(1, min(int(filters.get("limit", 50)), 200))
    offset = max(int(filters.get("offset", 0)), 0)
    conn = get_connection()
    total = conn.execute(f"SELECT COUNT(*) FROM api_requests{clause}", params).fetchone()[0]
    rows = conn.execute(
        f"""SELECT api_requests.*, c.total_cost_micros, c.priced
            FROM api_requests LEFT JOIN request_costs c ON c.request_row_id = api_requests.id
            {clause} ORDER BY api_requests.id DESC LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    return {"items": [_row_to_dict(r) for r in rows], "total": total}


def delete_request(request_id: int) -> bool:
    """Delete one request and its associated immutable cost snapshot."""
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM request_costs WHERE request_row_id = ?", (request_id,))
        cursor = conn.execute("DELETE FROM api_requests WHERE id = ?", (request_id,))
    return cursor.rowcount > 0


def delete_requests(filters: dict) -> int:
    """Delete request records selected by at least one explicit filter."""
    clause, params = _filter_clause(filters)
    if not clause:
        raise ValueError("at least one filter is required to delete request records")
    conn = get_connection()
    with conn:
        conn.execute(
            f"DELETE FROM request_costs WHERE request_row_id IN (SELECT id FROM api_requests{clause})",
            params,
        )
        cursor = conn.execute(f"DELETE FROM api_requests{clause}", params)
    return cursor.rowcount

def get_request(request_id: int) -> dict | None:
    row = get_connection().execute("SELECT * FROM api_requests WHERE id = ?", (request_id,)).fetchone()
    if not row:
        return None
    result = _row_to_dict(row)
    cost = get_connection().execute("SELECT * FROM request_costs WHERE request_row_id = ?", (request_id,)).fetchone()
    result["cost"] = _row_to_dict(cost) if cost else None
    return result