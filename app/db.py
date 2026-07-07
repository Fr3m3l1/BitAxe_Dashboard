"""SQLite storage layer (stdlib sqlite3, WAL mode, one connection per call)."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS miners (
    id          INTEGER PRIMARY KEY,
    mac         TEXT UNIQUE,
    hostname    TEXT,
    asic_model  TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS samples (
    id                  INTEGER PRIMARY KEY,
    miner_id            INTEGER NOT NULL REFERENCES miners(id),
    ts                  TEXT NOT NULL,
    hash_rate           REAL,
    expected_hash_rate  REAL,
    temp                REAL,
    vr_temp             REAL,
    power               REAL,
    voltage             REAL,
    current             REAL,
    core_voltage        REAL,
    core_voltage_actual REAL,
    frequency           REAL,
    fan_rpm             INTEGER,
    fan_speed           INTEGER,
    auto_fan            INTEGER,
    shares_accepted     INTEGER,
    shares_rejected     INTEGER,
    best_diff           TEXT,
    best_session_diff   TEXT,
    stratum_url         TEXT,
    stratum_user        TEXT,
    using_fallback      INTEGER,
    wifi_rssi           INTEGER,
    free_heap           INTEGER,
    uptime_seconds      INTEGER,
    version             TEXT,
    overheat_mode       INTEGER,
    raw                 TEXT
);
CREATE INDEX IF NOT EXISTS idx_samples_miner_ts ON samples(miner_id, ts);

CREATE TABLE IF NOT EXISTS alerts (
    id        INTEGER PRIMARY KEY,
    miner_id  INTEGER REFERENCES miners(id),
    ts        TEXT NOT NULL,
    type      TEXT NOT NULL,
    severity  TEXT NOT NULL DEFAULT 'warning',
    message   TEXT NOT NULL,
    value     REAL,
    threshold REAL
);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tuner_events (
    id           INTEGER PRIMARY KEY,
    miner_id     INTEGER REFERENCES miners(id),
    ts           TEXT NOT NULL,
    action       TEXT NOT NULL,
    frequency    REAL,
    core_voltage REAL,
    reason       TEXT,
    details      TEXT
);
CREATE INDEX IF NOT EXISTS idx_tuner_events_ts ON tuner_events(miner_id, ts);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


@contextmanager
def get_db():
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(SCHEMA)


def upsert_miner(db, mac: str, hostname: str, asic_model: str) -> int:
    now = utcnow()
    row = db.execute("SELECT id FROM miners WHERE mac = ?", (mac,)).fetchone()
    if row:
        db.execute(
            "UPDATE miners SET hostname = ?, asic_model = ?, last_seen = ? WHERE id = ?",
            (hostname, asic_model, now, row["id"]),
        )
        return row["id"]
    cur = db.execute(
        "INSERT INTO miners (mac, hostname, asic_model, first_seen, last_seen) VALUES (?, ?, ?, ?, ?)",
        (mac, hostname, asic_model, now, now),
    )
    return cur.lastrowid


# --- settings (JSON values keyed by name) ---

def get_setting(db, key: str, default=None):
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    return json.loads(row["value"])


def set_setting(db, key: str, value):
    db.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (key, json.dumps(value), utcnow()),
    )
