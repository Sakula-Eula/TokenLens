from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import sqlite3

from backend.pricing.defaults import DEFAULT_PRICE_RULES, PRICE_SOURCE_NOTE
from backend.pricing.matcher import choose_rule

MICROS_PER_CNY = 1_000_000
TOKENS_PER_MILLION = 1_000_000
SEED_VERSION = "pricing_seed_v1"


def cny_to_micros(value) -> int:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("price must be a valid number") from exc
    if amount < 0:
        raise ValueError("price must not be negative")
    return int((amount * MICROS_PER_CNY).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def micros_to_cny(value: int | None) -> str:
    return format(Decimal(int(value or 0)) / MICROS_PER_CNY, "f")


def _token_cost(tokens: int, price_micros_per_million: int) -> int:
    product = max(0, int(tokens or 0)) * max(0, int(price_micros_per_million or 0))
    return (product + TOKENS_PER_MILLION // 2) // TOKENS_PER_MILLION


def list_rules(conn: sqlite3.Connection, *, enabled_only: bool = False) -> list[dict]:
    where = " WHERE enabled = 1" if enabled_only else ""
    rows = conn.execute(f"SELECT * FROM pricing_rules{where} ORDER BY priority DESC, id ASC").fetchall()
    return [{key: row[key] for key in row.keys()} for row in rows]


def snapshot_request_cost(conn: sqlite3.Connection, request_row_id: int, record: dict) -> None:
    rule = choose_rule(list_rules(conn, enabled_only=True), str(record.get("provider") or ""), record.get("model"))
    input_tokens = max(0, int(record.get("input_tokens") or 0))
    output_tokens = max(0, int(record.get("output_tokens") or 0))
    cache_read_tokens = max(0, int(record.get("cache_read_tokens") or 0))
    if rule:
        billable_input = input_tokens
        if rule["input_includes_cache"]:
            billable_input = max(0, input_tokens - cache_read_tokens)
        input_cost = _token_cost(billable_input, rule["input_price_micros"])
        output_cost = _token_cost(output_tokens, rule["output_price_micros"])
        cache_read_cost = _token_cost(cache_read_tokens, rule["cache_read_price_micros"])
        values = (
            request_row_id, rule["id"], rule["name"], rule["provider"], rule["model_pattern"],
            rule["match_type"], 1, rule["input_includes_cache"], billable_input,
            input_tokens, output_tokens, cache_read_tokens,
            rule["input_price_micros"], rule["output_price_micros"],
            rule["cache_read_price_micros"],
            input_cost, output_cost, cache_read_cost,
            input_cost + output_cost + cache_read_cost,
            datetime.now().isoformat(timespec="seconds"),
        )
    else:
        values = (
            request_row_id, None, None, None, None, None, 0, 0, input_tokens,
            input_tokens, output_tokens, cache_read_tokens,
            0, 0, 0, 0, 0, 0, 0, datetime.now().isoformat(timespec="seconds"),
        )
    conn.execute(
        """INSERT OR IGNORE INTO request_costs (
             request_row_id, pricing_rule_id, rule_name, provider_scope, model_pattern,
             match_type, priced, input_includes_cache, billable_input_tokens,
             input_tokens, output_tokens, cache_read_tokens,
             input_price_micros, output_price_micros, cache_read_price_micros,
             input_cost_micros, output_cost_micros, cache_read_cost_micros, total_cost_micros, calculated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        values,
    )


def _seed_defaults(conn: sqlite3.Connection) -> None:
    seeded = conn.execute("SELECT value FROM app_metadata WHERE key = ?", (SEED_VERSION,)).fetchone()
    if seeded:
        return
    now = datetime.now().isoformat(timespec="seconds")
    for priority, item in enumerate(reversed(DEFAULT_PRICE_RULES), start=100):
        name, provider, pattern, match_type, input_p, output_p, read_p, includes = item
        conn.execute(
            """INSERT INTO pricing_rules
               (name, provider, model_pattern, match_type, input_price_micros,
                output_price_micros, cache_read_price_micros,
                input_includes_cache, priority, enabled, built_in, source_note, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            (name, provider, pattern, match_type, cny_to_micros(input_p), cny_to_micros(output_p),
             cny_to_micros(read_p), int(includes), priority,
             PRICE_SOURCE_NOTE, now),
        )
    conn.execute("INSERT INTO app_metadata(key, value) VALUES (?, ?)", (SEED_VERSION, now))


def initialize_pricing(conn: sqlite3.Connection) -> None:
    _seed_defaults(conn)
    rows = conn.execute(
        """SELECT r.* FROM api_requests r LEFT JOIN request_costs c ON c.request_row_id = r.id
           WHERE c.request_row_id IS NULL ORDER BY r.id"""
    ).fetchall()
    for row in rows:
        snapshot_request_cost(conn, row["id"], {key: row[key] for key in row.keys()})


def public_rule(rule: dict) -> dict:
    result = dict(rule)
    for key in ("input_price", "output_price", "cache_read_price"):
        result[f"{key}_cny"] = micros_to_cny(result.pop(f"{key}_micros"))
    return result


def _validate_rule(data: dict) -> dict:
    name = str(data.get("name") or "").strip()
    pattern = str(data.get("model_pattern") or "").strip()
    match_type = str(data.get("match_type") or "")
    if not name or not pattern:
        raise ValueError("name and model_pattern are required")
    if match_type not in ("exact", "glob"):
        raise ValueError("match_type must be exact or glob")
    if match_type == "exact" and any(char in pattern for char in "*?["):
        raise ValueError("exact model pattern must not contain wildcard characters")
    return {
        "name": name, "provider": str(data.get("provider") or "").strip() or None,
        "model_pattern": pattern, "match_type": match_type,
        "input_price_micros": cny_to_micros(data.get("input_price_cny", 0)),
        "output_price_micros": cny_to_micros(data.get("output_price_cny", 0)),
        "cache_read_price_micros": cny_to_micros(data.get("cache_read_price_cny", 0)),
        "input_includes_cache": int(bool(data.get("input_includes_cache"))),
        "priority": int(data.get("priority") or 0), "enabled": int(bool(data.get("enabled", True))),
        "source_note": str(data.get("source_note") or "").strip() or None,
    }


def _ensure_unique(conn: sqlite3.Connection, rule: dict, exclude_id: int | None = None) -> None:
    row = conn.execute(
        """SELECT id FROM pricing_rules WHERE COALESCE(provider, '') = COALESCE(?, '')
           AND model_pattern = ? AND match_type = ? AND (? IS NULL OR id != ?)""",
        (rule["provider"], rule["model_pattern"], rule["match_type"], exclude_id, exclude_id),
    ).fetchone()
    if row:
        raise ValueError("a pricing rule with the same provider, pattern and match type already exists")


def create_rule(conn: sqlite3.Connection, data: dict) -> dict:
    rule = _validate_rule(data)
    _ensure_unique(conn, rule)
    now = datetime.now().isoformat(timespec="seconds")
    cursor = conn.execute(
        """INSERT INTO pricing_rules
           (name, provider, model_pattern, match_type, input_price_micros, output_price_micros,
            cache_read_price_micros, input_includes_cache,
            priority, enabled, built_in, source_note, updated_at)
           VALUES (:name, :provider, :model_pattern, :match_type, :input_price_micros,
            :output_price_micros, :cache_read_price_micros,
            :input_includes_cache, :priority, :enabled, 0, :source_note, :updated_at)""",
        {**rule, "updated_at": now},
    )
    conn.commit()
    row = conn.execute("SELECT * FROM pricing_rules WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return public_rule({key: row[key] for key in row.keys()})


def update_rule(conn: sqlite3.Connection, rule_id: int, data: dict) -> dict | None:
    existing = conn.execute("SELECT * FROM pricing_rules WHERE id = ?", (rule_id,)).fetchone()
    if not existing:
        return None
    rule = _validate_rule(data)
    _ensure_unique(conn, rule, rule_id)
    conn.execute(
        """UPDATE pricing_rules SET name=:name, provider=:provider, model_pattern=:model_pattern,
           match_type=:match_type, input_price_micros=:input_price_micros,
           output_price_micros=:output_price_micros, cache_read_price_micros=:cache_read_price_micros,
           input_includes_cache=:input_includes_cache, priority=:priority, enabled=:enabled,
           source_note=:source_note, updated_at=:updated_at WHERE id=:id""",
        {**rule, "updated_at": datetime.now().isoformat(timespec="seconds"), "id": rule_id},
    )
    conn.commit()
    row = conn.execute("SELECT * FROM pricing_rules WHERE id = ?", (rule_id,)).fetchone()
    return public_rule({key: row[key] for key in row.keys()})


def delete_rule(conn: sqlite3.Connection, rule_id: int) -> bool:
    cursor = conn.execute("DELETE FROM pricing_rules WHERE id = ?", (rule_id,))
    conn.commit()
    return cursor.rowcount > 0


def preview_rule(conn: sqlite3.Connection, data: dict) -> list[dict]:
    rule = {**_validate_rule(data), "id": 0}
    from backend.pricing.matcher import rule_matches
    rows = conn.execute(
        """SELECT provider, COALESCE(model, 'unknown') AS model, COUNT(*) AS requests,
           COALESCE(SUM(total_tokens), 0) AS total_tokens FROM api_requests
           GROUP BY provider, model ORDER BY total_tokens DESC"""
    ).fetchall()
    return [
        {"provider": row["provider"], "model": row["model"], "requests": row["requests"],
         "total_tokens": row["total_tokens"]}
        for row in rows if rule_matches(rule, row["provider"], row["model"])
    ][:50]
