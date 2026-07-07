"""All HTTP routes: collector ingest, web-UI API, auth, static pages."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from . import alerts, config, db as dbm, ingest, telegram
from .defaults import ALERT_DEFAULTS, TUNER_DEFAULTS

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------- auth helpers

def _require_session(request: Request):
    if not request.session.get("authed"):
        raise HTTPException(status_code=401, detail="Not authenticated")


def _require_api_key(x_api_key: str | None):
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _cutoff(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------- pages & auth

@router.get("/", include_in_schema=False)
def index(request: Request):
    if not request.session.get("authed"):
        return RedirectResponse("/login")
    return FileResponse(config.STATIC_DIR / "index.html")


@router.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(config.STATIC_DIR / "login.html")


@router.post("/login")
def login(request: Request, payload: dict = Body(...)):
    if payload.get("code") == config.ACCESS_CODE:
        request.session["authed"] = True
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Wrong access code")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/static/{path:path}", include_in_schema=False)
def static_files(path: str):
    file = (config.STATIC_DIR / path).resolve()
    if not file.is_file() or config.STATIC_DIR not in file.parents:
        raise HTTPException(status_code=404)
    return FileResponse(file)


# ---------------------------------------------------------------- collector API

@router.post("/api/ingest")
@router.post("/api/data")  # backwards-compatible alias for the old collector
def api_ingest(payload: dict = Body(...), x_api_key: str | None = Header(default=None)):
    _require_api_key(x_api_key)
    samples = payload.get("samples") if "samples" in payload else [{"info": payload}]
    if not samples:
        raise HTTPException(status_code=400, detail="No samples")
    stored = 0
    with dbm.get_db() as db:
        for item in samples:
            info = item.get("info") or {}
            if not info:
                continue
            prev_row = None
            mac = info.get("macAddr") or info.get("hostname")
            if mac:
                prev_row = db.execute(
                    "SELECT s.* FROM samples s JOIN miners m ON m.id = s.miner_id "
                    "WHERE m.mac = ? ORDER BY s.ts DESC LIMIT 1", (mac,)).fetchone()
            miner_id, row = ingest.store_sample(db, info, item.get("ts"))
            stored += 1
            # Alert checks only on the newest sample of a batch (buffered
            # backlog would otherwise fire stale alerts).
            if item is samples[-1]:
                alerts.check_sample(db, miner_id, row, dict(prev_row) if prev_row else None)
    return {"ok": True, "stored": stored}


@router.get("/api/collector/config")
def api_collector_config(x_api_key: str | None = Header(default=None)):
    """Tuner configuration for the collector, keyed by miner MAC ('default' fallback)."""
    _require_api_key(x_api_key)
    with dbm.get_db() as db:
        default = {**TUNER_DEFAULTS, **(dbm.get_setting(db, "tuner:default", {}) or {})}
        tuners = {"default": default}
        for m in db.execute("SELECT mac FROM miners").fetchall():
            override = dbm.get_setting(db, f"tuner:{m['mac']}")
            if override:
                tuners[m["mac"]] = {**default, **override}
    return {"tuners": tuners}


@router.post("/api/collector/events")
def api_collector_events(payload: dict = Body(...), x_api_key: str | None = Header(default=None)):
    """Tuner event reports from the collector."""
    _require_api_key(x_api_key)
    events = payload.get("events") or []
    with dbm.get_db() as db:
        for ev in events:
            mac = ev.get("mac")
            miner = db.execute("SELECT id, hostname FROM miners WHERE mac = ?", (mac,)).fetchone()
            db.execute(
                "INSERT INTO tuner_events (miner_id, ts, action, frequency, core_voltage, reason, details) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (miner["id"] if miner else None, ev.get("ts") or dbm.utcnow(),
                 ev.get("action") or "unknown", ev.get("frequency"), ev.get("core_voltage"),
                 ev.get("reason"), ev.get("details")),
            )
            if ev.get("action") in ("emergency", "overheat_hold"):
                s = alerts.get_alert_settings(db)
                name = miner["hostname"] if miner else mac
                alerts.raise_alert(db, s, miner["id"] if miner else None, f"tuner_{ev['action']}",
                                   f"🛠️ <b>{name}</b> tuner {ev['action']}: {ev.get('reason')}")
    return {"ok": True, "stored": len(events)}


# ---------------------------------------------------------------- web UI API

@router.get("/api/overview")
def api_overview(request: Request):
    _require_session(request)
    out = {"miners": []}
    now = datetime.now(timezone.utc)
    with dbm.get_db() as db:
        s = alerts.get_alert_settings(db)
        for m in db.execute("SELECT * FROM miners ORDER BY hostname").fetchall():
            latest = db.execute(
                "SELECT * FROM samples WHERE miner_id = ? ORDER BY ts DESC LIMIT 1",
                (m["id"],)).fetchone()
            last_seen = datetime.strptime(m["last_seen"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            entry = {
                "mac": m["mac"],
                "hostname": m["hostname"],
                "asic_model": m["asic_model"],
                "last_seen": m["last_seen"],
                "online": (now - last_seen).total_seconds() < s["offline_minutes"] * 60,
                "latest": {k: v for k, v in dict(latest).items() if k != "raw"} if latest else None,
            }
            out["miners"].append(entry)
        out["alerts_24h"] = db.execute(
            "SELECT COUNT(*) n FROM alerts WHERE ts > ? AND severity != 'info'",
            (_cutoff(24),)).fetchone()["n"]
    return out


@router.get("/api/history")
def api_history(request: Request, mac: str, hours: float = 6, points: int = 700):
    _require_session(request)
    with dbm.get_db() as db:
        miner = db.execute("SELECT id FROM miners WHERE mac = ?", (mac,)).fetchone()
        if not miner:
            raise HTTPException(status_code=404, detail="Unknown miner")
        bucket = max(1, int(hours * 3600 / points))
        rows = db.execute(
            """SELECT MIN(ts) ts, AVG(hash_rate) hash_rate, AVG(expected_hash_rate) expected_hash_rate,
                      AVG(temp) temp, AVG(vr_temp) vr_temp, AVG(power) power,
                      AVG(frequency) frequency, AVG(core_voltage) core_voltage,
                      AVG(core_voltage_actual) core_voltage_actual,
                      MAX(shares_accepted) shares_accepted, MAX(shares_rejected) shares_rejected,
                      AVG(fan_rpm) fan_rpm
               FROM samples WHERE miner_id = ? AND ts > ?
               GROUP BY CAST(strftime('%s', ts) / ? AS INTEGER) ORDER BY ts""",
            (miner["id"], _cutoff(hours), bucket)).fetchall()
    return {"points": [dict(r) for r in rows]}


@router.get("/api/stats")
def api_stats(request: Request, mac: str, hours: float = 24):
    _require_session(request)
    with dbm.get_db() as db:
        miner = db.execute("SELECT id FROM miners WHERE mac = ?", (mac,)).fetchone()
        if not miner:
            raise HTTPException(status_code=404, detail="Unknown miner")
        cutoff = _cutoff(hours)
        agg = db.execute(
            """SELECT COUNT(*) n,
                      AVG(hash_rate) hr_avg, MIN(hash_rate) hr_min, MAX(hash_rate) hr_max,
                      AVG(temp) t_avg, MIN(temp) t_min, MAX(temp) t_max,
                      AVG(power) p_avg, MIN(power) p_min, MAX(power) p_max
               FROM samples WHERE miner_id = ? AND ts > ?""",
            (miner["id"], cutoff)).fetchone()
        first = db.execute(
            "SELECT shares_accepted, shares_rejected FROM samples "
            "WHERE miner_id = ? AND ts > ? ORDER BY ts LIMIT 1", (miner["id"], cutoff)).fetchone()
        last = db.execute(
            "SELECT shares_accepted, shares_rejected, uptime_seconds, best_diff, best_session_diff "
            "FROM samples WHERE miner_id = ? ORDER BY ts DESC LIMIT 1", (miner["id"],)).fetchone()
    if not agg["n"]:
        return {"n": 0}
    eff = (agg["p_avg"] / (agg["hr_avg"] / 1000)) if agg["hr_avg"] else 0
    shares_acc = max(0, (last["shares_accepted"] or 0) - (first["shares_accepted"] or 0))
    shares_rej = max(0, (last["shares_rejected"] or 0) - (first["shares_rejected"] or 0))
    return {
        "n": agg["n"], "hours": hours,
        "hash_rate": {"avg": agg["hr_avg"], "min": agg["hr_min"], "max": agg["hr_max"]},
        "temp": {"avg": agg["t_avg"], "min": agg["t_min"], "max": agg["t_max"]},
        "power": {"avg": agg["p_avg"], "min": agg["p_min"], "max": agg["p_max"]},
        "efficiency_avg": eff,
        "shares": {"accepted": shares_acc, "rejected": shares_rej},
        "uptime_seconds": last["uptime_seconds"],
        "best_diff": last["best_diff"], "best_session_diff": last["best_session_diff"],
    }


@router.get("/api/alerts")
def api_alerts(request: Request, hours: float = 72, limit: int = 200):
    _require_session(request)
    with dbm.get_db() as db:
        rows = db.execute(
            """SELECT a.*, m.hostname FROM alerts a LEFT JOIN miners m ON m.id = a.miner_id
               WHERE a.ts > ? ORDER BY a.ts DESC LIMIT ?""",
            (_cutoff(hours), limit)).fetchall()
    return {"alerts": [dict(r) for r in rows]}


@router.get("/api/tuner/events")
def api_tuner_events(request: Request, mac: str | None = None, limit: int = 100):
    _require_session(request)
    with dbm.get_db() as db:
        if mac:
            rows = db.execute(
                """SELECT e.*, m.hostname FROM tuner_events e LEFT JOIN miners m ON m.id = e.miner_id
                   WHERE m.mac = ? ORDER BY e.ts DESC LIMIT ?""", (mac, limit)).fetchall()
        else:
            rows = db.execute(
                """SELECT e.*, m.hostname FROM tuner_events e LEFT JOIN miners m ON m.id = e.miner_id
                   ORDER BY e.ts DESC LIMIT ?""", (limit,)).fetchall()
    return {"events": [dict(r) for r in rows]}


@router.get("/api/settings")
def api_get_settings(request: Request):
    _require_session(request)
    with dbm.get_db() as db:
        alert_settings = {**ALERT_DEFAULTS, **(dbm.get_setting(db, "alerts", {}) or {})}
        tuner_settings = {**TUNER_DEFAULTS, **(dbm.get_setting(db, "tuner:default", {}) or {})}
    return {
        "alerts": alert_settings,
        "tuner": tuner_settings,
        "telegram_configured": telegram.enabled(),
    }


@router.put("/api/settings")
def api_put_settings(request: Request, payload: dict = Body(...)):
    _require_session(request)
    with dbm.get_db() as db:
        if "alerts" in payload:
            clean = {k: payload["alerts"][k] for k in ALERT_DEFAULTS if k in payload["alerts"]}
            dbm.set_setting(db, "alerts", clean)
        if "tuner" in payload:
            clean = {k: payload["tuner"][k] for k in TUNER_DEFAULTS if k in payload["tuner"]}
            dbm.set_setting(db, "tuner:default", clean)
    return {"ok": True}


@router.post("/api/telegram/test")
def api_telegram_test(request: Request):
    _require_session(request)
    if not telegram.enabled():
        return JSONResponse({"ok": False, "error": "TELEGRAM_TOKEN / TELEGRAM_CHAT_ID not configured"},
                            status_code=400)
    ok = telegram.send("🧪 BitAxe Dashboard — Telegram test message")
    return {"ok": ok}
