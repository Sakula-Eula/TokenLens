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
    conn.commit()
    return cur.lastrowid
