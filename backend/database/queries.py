from datetime import datetime, timedelta

from backend.database.database import get_connection


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


RANGE_KEYS = ("24h", "7d", "30d")


def range_since(range_key: str) -> str:
    """Return the rolling-window lower bound used by all statistics queries."""
    assert range_key in RANGE_KEYS
    delta = timedelta(hours=24) if range_key == "24h" else timedelta(days=int(range_key[:-1]))
    return (datetime.now() - delta).isoformat(timespec="seconds")


def _summary(where: str, params: tuple | list) -> dict:
    conn = get_connection()
    row = conn.execute(
        f"""SELECT COUNT(*) AS requests,
                   COALESCE(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END), 0) AS success,
                   COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS errors,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                   COALESCE(SUM(cache_write_tokens), 0) AS cache_write_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) +
                     COALESCE(SUM(cache_write_tokens), 0) AS cache_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
            FROM api_requests WHERE {where}""",
        params,
    ).fetchone()
    return _row_to_dict(row)


def today_summary(date_str: str) -> dict:
    """Legacy calendar-day summary retained for callers outside the HTTP API."""
    return _summary("substr(created_at, 1, 10) = ?", (date_str,))


def range_summary(range_key: str) -> dict:
    return _summary("created_at >= ?", (range_since(range_key),))


def group_stats(column: str, range_or_date: str) -> list[dict]:
    """Group request totals for a rolling range or, for compatibility, a date."""
    assert column in ("model", "provider")
    if range_or_date in RANGE_KEYS:
        where, params = "created_at >= ?", (range_since(range_or_date),)
    else:
        where, params = "substr(created_at, 1, 10) = ?", (range_or_date,)
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT COALESCE({column}, 'unknown') AS {column},
                   COUNT(*) AS requests,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                   COALESCE(SUM(cache_write_tokens), 0) AS cache_write_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) +
                     COALESCE(SUM(cache_write_tokens), 0) AS cache_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM api_requests WHERE {where}
            GROUP BY {column} ORDER BY total_tokens DESC""",
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def trend_stats(range_key: str) -> list[dict]:
    assert range_key in RANGE_KEYS
    if range_key == "24h":
        bucket_expr = "substr(created_at, 1, 13)"
    else:
        bucket_expr = "substr(created_at, 1, 10)"
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT {bucket_expr} AS bucket, COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM api_requests WHERE created_at >= ?
            GROUP BY bucket ORDER BY bucket""",
        (range_since(range_key),),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def error_stats(range_key: str) -> dict:
    """Return failure-only status-code and error-type distributions for a range."""
    since = range_since(range_key)
    conn = get_connection()
    by_status = conn.execute(
        """SELECT COALESCE(status_code, 0) AS status_code, COUNT(*) AS count
           FROM api_requests WHERE created_at >= ? AND success = 0
           GROUP BY status_code ORDER BY count DESC, status_code ASC""",
        (since,),
    ).fetchall()
    by_type = conn.execute(
        """SELECT COALESCE(error_type, 'unknown') AS error_type, COUNT(*) AS count
           FROM api_requests WHERE created_at >= ? AND success = 0
           GROUP BY error_type ORDER BY count DESC, error_type ASC""",
        (since,),
    ).fetchall()
    return {
        "by_status": [_row_to_dict(row) for row in by_status],
        "by_type": [_row_to_dict(row) for row in by_type],
    }


def query_requests(filters: dict) -> dict:
    where, params = [], []
    if filters.get("provider"):
        where.append("provider = ?")
        params.append(filters["provider"])
    if filters.get("model"):
        where.append("model = ?")
        params.append(filters["model"])
    if filters.get("status") is not None:
        where.append("status_code = ?")
        params.append(int(filters["status"]))
    if filters.get("success") is not None:
        where.append("success = ?")
        params.append(1 if filters["success"] else 0)
    if filters.get("date_from"):
        where.append("created_at >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("created_at < ?")
        params.append(filters["date_to"])
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(int(filters.get("limit", 50)), 200))
    offset = max(int(filters.get("offset", 0)), 0)
    conn = get_connection()
    total = conn.execute(f"SELECT COUNT(*) FROM api_requests{clause}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM api_requests{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {"items": [_row_to_dict(r) for r in rows], "total": total}
