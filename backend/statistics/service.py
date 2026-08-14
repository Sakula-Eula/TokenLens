from datetime import datetime

from backend.database import queries


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def summary() -> dict:
    s = queries.today_summary(today())
    s["date"] = today()
    s["error_rate"] = round(s["errors"] / s["requests"] * 100, 2) if s["requests"] else 0.0
    return s


def models() -> dict:
    return {"items": queries.group_stats("model", today())}


def providers() -> dict:
    return {"items": queries.group_stats("provider", today())}


def trend(range_key: str) -> dict:
    return {"items": queries.trend_stats(range_key)}
