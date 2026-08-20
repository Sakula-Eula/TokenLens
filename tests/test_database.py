from datetime import datetime, timedelta

from backend.database import database, queries

SCHEMA_FIELDS = {
    "id", "request_id", "provider", "model", "endpoint", "stream",
    "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
    "total_tokens", "latency_ms", "status_code", "success", "error_type", "created_at",
}


def _record(**overrides):
    rec = {
        "request_id": "req_1", "provider": "provider_a", "model": "gpt-5.6-sol",
        "endpoint": "/v1/chat/completions", "stream": 0,
        "input_tokens": 100, "output_tokens": 50, "cache_read_tokens": 0,
        "cache_write_tokens": 0, "total_tokens": 150, "latency_ms": 800,
        "status_code": 200, "success": 1, "error_type": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    rec.update(overrides)
    return rec


def test_schema_fields(tmp_path):
    conn = database.init_db(tmp_path / "test.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    cols = {r[1] for r in conn.execute("PRAGMA table_info(api_requests)")}
    assert cols == SCHEMA_FIELDS


def test_insert_and_query_with_filters(tmp_path):
    database.init_db(tmp_path / "test.db")
    today = datetime.now().strftime("%Y-%m-%d")
    database.insert_request(_record())
    database.insert_request(_record(
        request_id="req_2", model="claude-sonnet", provider="provider_b",
        status_code=429, success=0, error_type="rate_limit",
        created_at=(datetime.now() - timedelta(days=3)).isoformat(timespec="seconds"),
    ))
    result = queries.query_requests({})
    assert result["total"] == 2 and len(result["items"]) == 2
    assert queries.query_requests({"model": "claude-sonnet"})["total"] == 1
    assert queries.query_requests({"status": 429})["total"] == 1
    assert queries.query_requests({"success": True})["total"] == 1
    assert queries.query_requests({"success": False})["total"] == 1
    assert queries.query_requests({"date_from": today})["total"] == 1
    assert queries.query_requests({"limit": 1, "offset": 1})["items"][0]["request_id"] == "req_1"


def test_summary_and_group_stats(tmp_path):
    database.init_db(tmp_path / "test.db")
    database.insert_request(_record(cache_read_tokens=25, cache_write_tokens=5))
    database.insert_request(_record(
        request_id="req_2", success=0, status_code=500, error_type="server_error",
        cache_read_tokens=10,
    ))
    today = datetime.now().strftime("%Y-%m-%d")
    s = queries.today_summary(today)
    assert s["requests"] == 2 and s["errors"] == 1 and s["input_tokens"] == 200
    assert s["cache_read_tokens"] == 35 and s["cache_write_tokens"] == 5
    assert s["cache_tokens"] == 40
    models = queries.group_stats("model", today)
    assert len(models) == 1 and models[0]["total_tokens"] == 300 and models[0]["cache_tokens"] == 40
    providers = queries.group_stats("provider", today)
    assert providers[0]["provider"] == "provider_a"


def test_rolling_range_summary_groups_and_error_distributions(tmp_path):
    database.init_db(tmp_path / "test.db")
    now = datetime.now()
    database.insert_request(_record(request_id="recent_ok", cache_read_tokens=3))
    database.insert_request(_record(
        request_id="recent_error", success=0, status_code=429, error_type="rate_limit",
        created_at=(now - timedelta(hours=2)).isoformat(timespec="seconds"),
    ))
    database.insert_request(_record(
        request_id="old_error", success=0, status_code=500, error_type="server_error",
        created_at=(now - timedelta(hours=25)).isoformat(timespec="seconds"),
    ))

    summary_24h = queries.range_summary("24h")
    assert summary_24h["requests"] == 2 and summary_24h["errors"] == 1
    assert queries.group_stats("provider", "24h")[0]["requests"] == 2
    assert queries.range_summary("7d")["requests"] == 3
    errors = queries.error_stats("24h")
    assert errors["by_status"] == [{"status_code": 429, "count": 1}]
    assert errors["by_type"] == [{"error_type": "rate_limit", "count": 1}]


def test_trend_buckets(tmp_path):
    database.init_db(tmp_path / "test.db")
    now = datetime.now()
    database.insert_request(_record(request_id="r1", created_at=now.isoformat(timespec="seconds")))
    database.insert_request(_record(request_id="r2", created_at=(now - timedelta(hours=1)).isoformat(timespec="seconds")))
    hours = queries.trend_stats("24h")
    assert len(hours) >= 2
    assert all("bucket" in h and "total_tokens" in h for h in hours)
    days = queries.trend_stats("7d")
    assert len(days) >= 1
