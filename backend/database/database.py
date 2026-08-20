import sqlite3
from pathlib import Path

_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT,
    provider TEXT NOT NULL,
    model TEXT,
    endpoint TEXT,
    stream BOOLEAN DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER,
    status_code INTEGER,
    success BOOLEAN,
    error_type TEXT,
    created_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_created_at ON api_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_model ON api_requests(model);
CREATE INDEX IF NOT EXISTS idx_provider ON api_requests(provider);
CREATE TABLE IF NOT EXISTS pricing_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    provider TEXT,
    model_pattern TEXT NOT NULL,
    match_type TEXT NOT NULL CHECK(match_type IN ('exact', 'glob')),
    input_price_micros INTEGER NOT NULL DEFAULT 0,
    output_price_micros INTEGER NOT NULL DEFAULT 0,
    cache_read_price_micros INTEGER NOT NULL DEFAULT 0,
    cache_write_price_micros INTEGER NOT NULL DEFAULT 0,
    input_includes_cache BOOLEAN NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    built_in BOOLEAN NOT NULL DEFAULT 0,
    source_note TEXT,
    updated_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS request_costs (
    request_row_id INTEGER PRIMARY KEY,
    pricing_rule_id INTEGER,
    rule_name TEXT,
    provider_scope TEXT,
    model_pattern TEXT,
    match_type TEXT,
    priced BOOLEAN NOT NULL DEFAULT 0,
    input_includes_cache BOOLEAN NOT NULL DEFAULT 0,
    billable_input_tokens INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    input_price_micros INTEGER NOT NULL DEFAULT 0,
    output_price_micros INTEGER NOT NULL DEFAULT 0,
    cache_read_price_micros INTEGER NOT NULL DEFAULT 0,
    cache_write_price_micros INTEGER NOT NULL DEFAULT 0,
    input_cost_micros INTEGER NOT NULL DEFAULT 0,
    output_cost_micros INTEGER NOT NULL DEFAULT 0,
    cache_read_cost_micros INTEGER NOT NULL DEFAULT 0,
    cache_write_cost_micros INTEGER NOT NULL DEFAULT 0,
    total_cost_micros INTEGER NOT NULL DEFAULT 0,
    calculated_at DATETIME NOT NULL,
    FOREIGN KEY(request_row_id) REFERENCES api_requests(id),
    FOREIGN KEY(pricing_rule_id) REFERENCES pricing_rules(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_request_costs_priced ON request_costs(priced);
CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

FIELDS = (
    "request_id", "provider", "model", "endpoint", "stream",
    "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
    "total_tokens", "latency_ms", "status_code", "success", "error_type", "created_at",
)


def init_db(db_path: Path) -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        _conn.close()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.executescript(SCHEMA)
    from backend.pricing.service import initialize_pricing
    initialize_pricing(_conn)
    _conn.commit()
    return _conn


def get_connection() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("database not initialized")
    return _conn


def insert_request(record: dict) -> int:
    conn = get_connection()
    placeholders = ", ".join("?" for _ in FIELDS)
    sql = f"INSERT INTO api_requests ({', '.join(FIELDS)}) VALUES ({placeholders})"
    cur = conn.execute(sql, [record.get(f, 0 if f != "created_at" else "") for f in FIELDS])
    try:
        from backend.pricing.service import snapshot_request_cost
        snapshot_request_cost(conn, cur.lastrowid, record)
    except Exception:
        # Usage records are more important than estimates. Missing cost rows are
        # repaired by initialize_pricing() on the next start.
        pass
    conn.commit()
    return cur.lastrowid
