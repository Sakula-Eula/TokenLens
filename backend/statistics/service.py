from datetime import datetime

from backend.database import queries


def summary(range_key: str = "24h") -> dict:
    s = queries.range_summary(range_key)
    # Retained for clients of the original summary API; range is authoritative.
    s["date"] = datetime.now().strftime("%Y-%m-%d")
    s["range"] = range_key
    s["error_rate"] = round(s["errors"] / s["requests"] * 100, 2) if s["requests"] else 0.0
    return s


def models(range_key: str = "24h", filters: dict | None = None, **paging) -> dict:
    return queries.grouped_stats("model", queries.filters_for_range(range_key, filters), **paging)


def providers(range_key: str = "24h", filters: dict | None = None, **paging) -> dict:
    return queries.grouped_stats("provider", queries.filters_for_range(range_key, filters), **paging)


def trend(range_key: str, filters: dict | None = None, bucket_hours: int | None = None) -> dict:
    return {"items": queries.trend_stats(range_key, filters, bucket_hours=bucket_hours)}


def errors(range_key: str = "24h", filters: dict | None = None) -> dict:
    scoped = queries.filters_for_range(range_key, filters)
    summary_data = queries.filtered_summary(scoped)
    distributions = queries.error_stats(range_key, filters)
    errors_count = sum(item["count"] for item in distributions["by_status"])
    return {
        "errors": errors_count,
        "total_requests": summary_data["requests"],
        "error_rate": round(errors_count / summary_data["requests"] * 100, 2)
        if summary_data["requests"] else 0.0,
        **distributions,
    }
