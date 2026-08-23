from datetime import datetime

from backend.database import database
from backend.pricing import service


def _record(model="gpt-5.6-sol", **overrides):
    record = {
        "request_id": "req_cost", "provider": "openai", "model": model,
        "endpoint": "/v1/chat/completions", "stream": 0,
        "input_tokens": 1000, "output_tokens": 500, "cache_read_tokens": 200,
        "cache_write_tokens": 0, "total_tokens": 1500, "latency_ms": 100,
        "status_code": 200, "success": 1, "error_type": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    record.update(overrides)
    return record


def test_snapshot_uses_integer_micros_and_avoids_cached_input_double_count(tmp_path):
    conn = database.init_db(tmp_path / "cost.db")
    request_id = database.insert_request(_record())
    cost = conn.execute("SELECT * FROM request_costs WHERE request_row_id = ?", (request_id,)).fetchone()
    assert cost["priced"] == 1 and cost["billable_input_tokens"] == 800
    assert cost["input_cost_micros"] == 28_800
    assert cost["output_cost_micros"] == 108_000
    assert cost["cache_read_cost_micros"] == 720
    assert cost["total_cost_micros"] == 137_520


def test_price_change_only_affects_future_requests(tmp_path):
    conn = database.init_db(tmp_path / "cost.db")
    first = database.insert_request(_record(request_id="first", cache_read_tokens=0))
    rule = next(item for item in service.list_rules(conn) if item["name"] == "OpenAI GPT-5.6 Sol")
    payload = service.public_rule(rule)
    payload.update({"input_price_cny": "100", "output_price_cny": "200",
                    "cache_read_price_cny": "10", "cache_write_price_cny": "0"})
    service.update_rule(conn, rule["id"], payload)
    second = database.insert_request(_record(request_id="second", cache_read_tokens=0))
    first_cost = conn.execute("SELECT total_cost_micros FROM request_costs WHERE request_row_id=?", (first,)).fetchone()[0]
    second_cost = conn.execute("SELECT total_cost_micros FROM request_costs WHERE request_row_id=?", (second,)).fetchone()[0]
    assert first_cost == 144_000 and second_cost == 200_000


def test_unpriced_and_missing_ledger_are_backfilled(tmp_path):
    conn = database.init_db(tmp_path / "cost.db")
    request_id = database.insert_request(_record(model="private-model"))
    cost = conn.execute("SELECT priced, total_cost_micros FROM request_costs WHERE request_row_id=?", (request_id,)).fetchone()
    assert tuple(cost) == (0, 0)
    conn.execute("DELETE FROM request_costs WHERE request_row_id=?", (request_id,))
    service.initialize_pricing(conn)
    assert conn.execute("SELECT COUNT(*) FROM request_costs WHERE request_row_id=?", (request_id,)).fetchone()[0] == 1


def test_defaults_seed_only_once(tmp_path):
    conn = database.init_db(tmp_path / "cost.db")
    original = conn.execute("SELECT COUNT(*) FROM pricing_rules").fetchone()[0]
    conn.execute("DELETE FROM pricing_rules")
    conn.commit()
    service.initialize_pricing(conn)
    assert original > 0 and conn.execute("SELECT COUNT(*) FROM pricing_rules").fetchone()[0] == 0
