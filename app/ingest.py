"""Normalization and storage of raw AxeOS /api/system/info payloads."""

import json
import re

from . import db as dbm

# Suffix multipliers for difficulty strings like "745.15G".
_DIFF_SUFFIX = {"k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15, "E": 1e18}


def parse_diff(value) -> float:
    """Parse an AxeOS difficulty string ("745.15G") into a float."""
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    m = re.fullmatch(r"([\d.]+)\s*([kMGTPE]?)", s)
    if not m:
        return 0.0
    try:
        num = float(m.group(1))
    except ValueError:
        return 0.0
    return num * _DIFF_SUFFIX.get(m.group(2), 1.0)


def _f(info, *keys):
    """First non-None value among keys, as float (or None)."""
    for k in keys:
        v = info.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None


def _i(info, *keys):
    v = _f(info, *keys)
    return int(v) if v is not None else None


def store_sample(db, info: dict, ts: str | None = None) -> tuple[int, dict]:
    """Normalize one AxeOS info payload and insert it. Returns (miner_id, normalized)."""
    ts = ts or dbm.utcnow()
    mac = info.get("macAddr") or info.get("hostname") or "unknown"
    hostname = info.get("hostname") or mac
    asic_model = info.get("ASICModel") or ""

    miner_id = dbm.upsert_miner(db, mac, hostname, asic_model)

    row = {
        "miner_id": miner_id,
        "ts": ts,
        "hash_rate": _f(info, "hashRate"),
        "expected_hash_rate": _f(info, "expectedHashrate"),
        "temp": _f(info, "temp"),
        "vr_temp": _f(info, "vrTemp"),
        "power": _f(info, "power"),
        "voltage": _f(info, "voltage"),
        "current": _f(info, "current"),
        "core_voltage": _f(info, "coreVoltage"),
        "core_voltage_actual": _f(info, "coreVoltageActual"),
        "frequency": _f(info, "frequency"),
        "fan_rpm": _i(info, "fanrpm"),
        "fan_speed": _i(info, "fanspeed"),
        "auto_fan": _i(info, "autofanspeed"),
        "shares_accepted": _i(info, "sharesAccepted"),
        "shares_rejected": _i(info, "sharesRejected"),
        "best_diff": str(info.get("bestDiff") or ""),
        "best_session_diff": str(info.get("bestSessionDiff") or ""),
        "stratum_url": info.get("stratumURL"),
        "stratum_user": info.get("stratumUser"),
        "using_fallback": 1 if info.get("isUsingFallbackStratum") else 0,
        "wifi_rssi": _i(info, "wifiRSSI"),
        "free_heap": _i(info, "freeHeap"),
        "uptime_seconds": _i(info, "uptimeSeconds"),
        "version": info.get("version") or info.get("axeOSVersion"),
        "overheat_mode": 1 if info.get("overheat_mode") else 0,
        "raw": json.dumps(info),
    }
    cols = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    db.execute(f"INSERT INTO samples ({cols}) VALUES ({placeholders})", list(row.values()))
    return miner_id, row
