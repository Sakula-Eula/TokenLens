from datetime import datetime, timedelta

from backend.database.database import get_connection


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


def today_summary(date_str: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) AS requests,
                  COALESCE(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END), 0) AS success,
                  COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS errors,
                  COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens,
                  COALESCE(SUM(total_tokens), 0) AS total_tokens,
                  COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
           FROM api_requests WHERE substr(created_at, 1, 10) = ?""",
        (date_str,),
    ).fetchone()
    return _row_to_dict(row)


def group_stats(column: str, date_str: str) -> list[dict]:
    assert column in ("model", "provider")
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT COALESCE({column}, 'unknown') AS {column},
                   COUNT(*) AS requests,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM api_requests WHERE substr(created_at, 1, 10) = ?
            GROUP BY {column} ORDER BY total_tokens DESC""",
        (date_str,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def trend_stats(range_key: str) -> list[dict]:
    assert range_key in ("24h", "7d", "30d")
    if range_key == "24h":
        since = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
        bucket_expr = "substr(created_at, 1, 13)"
    else:
        days = 7 if range_key == "7d" else 30
        since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        bucket_expr = "substr(created_at, 1, 10)"
    conn = get_connection()
    rows = conn.execute(
        f"""SELECT {bucket_expr} AS bucket, COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM api_requests WHERE created_at >= ?
            GROUP BY bucket ORDER BY bucket""",
        (since,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


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
