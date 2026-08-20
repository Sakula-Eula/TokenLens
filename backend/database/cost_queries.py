from datetime import datetime, timedelta

from backend.database.database import get_connection

PERIODS = ("today", "month", "24h", "7d", "30d")


def period_start(period: str) -> str:
    if period not in PERIODS:
        raise ValueError("period must be today, month, 24h, 7d or 30d")
    now = datetime.now()
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "24h":
        start = now - timedelta(hours=24)
    else:
        start = now - timedelta(days=int(period[:-1]))
    return start.isoformat(timespec="seconds")


def _row(row) -> dict:
    return {key: row[key] for key in row.keys()}


def summary(period: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) AS requests,
           COALESCE(SUM(CASE WHEN c.priced = 1 THEN 1 ELSE 0 END), 0) AS priced_requests,
           COALESCE(SUM(CASE WHEN c.priced = 0 OR c.priced IS NULL THEN 1 ELSE 0 END), 0) AS unpriced_requests,
           COALESCE(SUM(CASE WHEN c.priced = 0 OR c.priced IS NULL THEN r.total_tokens ELSE 0 END), 0) AS unpriced_tokens,
           COALESCE(SUM(c.input_cost_micros), 0) AS input_cost_micros,
           COALESCE(SUM(c.output_cost_micros), 0) AS output_cost_micros,
           COALESCE(SUM(c.cache_read_cost_micros), 0) AS cache_read_cost_micros,
           COALESCE(SUM(c.cache_write_cost_micros), 0) AS cache_write_cost_micros,
           COALESCE(SUM(c.total_cost_micros), 0) AS total_cost_micros
           FROM api_requests r LEFT JOIN request_costs c ON c.request_row_id = r.id
           WHERE r.created_at >= ?""",
        (period_start(period),),
    ).fetchone()
    result = _row(row)
    result["period"] = period
    result["coverage_rate"] = round(result["priced_requests"] / result["requests"] * 100, 2) if result["requests"] else 100.0
    return result


def grouped(column: str, period: str, limit: int = 50) -> dict:
    if column not in ("model", "provider"):
        raise ValueError("column must be model or provider")
    key = f"COALESCE(r.{column}, 'unknown')"
    rows = get_connection().execute(
        f"""SELECT {key} AS {column}, COUNT(*) AS requests,
           COALESCE(SUM(r.total_tokens), 0) AS total_tokens,
           COALESCE(SUM(c.input_cost_micros), 0) AS input_cost_micros,
           COALESCE(SUM(c.output_cost_micros), 0) AS output_cost_micros,
           COALESCE(SUM(c.cache_read_cost_micros), 0) AS cache_read_cost_micros,
           COALESCE(SUM(c.cache_write_cost_micros), 0) AS cache_write_cost_micros,
           COALESCE(SUM(c.total_cost_micros), 0) AS total_cost_micros,
           COALESCE(SUM(CASE WHEN c.priced = 0 OR c.priced IS NULL THEN 1 ELSE 0 END), 0) AS unpriced_requests
           FROM api_requests r LEFT JOIN request_costs c ON c.request_row_id = r.id
           WHERE r.created_at >= ? GROUP BY {key}
           ORDER BY total_cost_micros DESC, total_tokens DESC LIMIT ?""",
        (period_start(period), max(1, min(int(limit), 200))),
    ).fetchall()
    return {"items": [_row(item) for item in rows], "period": period}


def trend(period: str) -> dict:
    bucket = "substr(r.created_at, 1, 13)" if period in ("today", "24h") else "substr(r.created_at, 1, 10)"
    rows = get_connection().execute(
        f"""SELECT {bucket} AS bucket,
           COALESCE(SUM(c.input_cost_micros), 0) AS input_cost_micros,
           COALESCE(SUM(c.output_cost_micros), 0) AS output_cost_micros,
           COALESCE(SUM(c.cache_read_cost_micros), 0) AS cache_read_cost_micros,
           COALESCE(SUM(c.cache_write_cost_micros), 0) AS cache_write_cost_micros,
           COALESCE(SUM(c.total_cost_micros), 0) AS total_cost_micros
           FROM api_requests r LEFT JOIN request_costs c ON c.request_row_id = r.id
           WHERE r.created_at >= ? GROUP BY bucket ORDER BY bucket""",
        (period_start(period),),
    ).fetchall()
    return {"items": [_row(item) for item in rows], "period": period}


def unpriced(period: str) -> dict:
    rows = get_connection().execute(
        """SELECT r.provider, COALESCE(r.model, 'unknown') AS model, COUNT(*) AS requests,
           COALESCE(SUM(r.total_tokens), 0) AS total_tokens
           FROM api_requests r LEFT JOIN request_costs c ON c.request_row_id = r.id
           WHERE r.created_at >= ? AND (c.priced = 0 OR c.priced IS NULL)
           GROUP BY r.provider, r.model ORDER BY total_tokens DESC""",
        (period_start(period),),
    ).fetchall()
    return {"items": [_row(item) for item in rows], "period": period}
