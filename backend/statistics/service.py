from datetime import datetime

from backend.database import queries


def summary(range_key: str = "24h") -> dict:
    s = queries.range_summary(range_key)
    # Retained for clients of the original summary API; range is authoritative.
    s["date"] = datetime.now().strftime("%Y-%m-%d")
    s["range"] = range_key
    s["error_rate"] = round(s["errors"] / s["requests"] * 100, 2) if s["requests"] else 0.0
    return s


def models(range_key: str = "24h") -> dict:
    return {"items": queries.group_stats("model", range_key)}


def providers(range_key: str = "24h") -> dict:
    return {"items": queries.group_stats("provider", range_key)}


def trend(range_key: str) -> dict:
    return {"items": queries.trend_stats(range_key)}


def errors(range_key: str = "24h") -> dict:
    summary_data = queries.range_summary(range_key)
    distributions = queries.error_stats(range_key)
    return {
        "errors": summary_data["errors"],
        "total_requests": summary_data["requests"],
        "error_rate": round(summary_data["errors"] / summary_data["requests"] * 100, 2)
        if summary_data["requests"] else 0.0,
        **distributions,
    }
