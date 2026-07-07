"""Alert engine: threshold checks on ingest, offline watchdog, daily summary."""

import logging
from datetime import datetime, timedelta, timezone

from . import db as dbm
from . import telegram
from .defaults import ALERT_DEFAULTS
from .ingest import parse_diff

logger = logging.getLogger(__name__)


def get_alert_settings(db) -> dict:
    saved = dbm.get_setting(db, "alerts", {}) or {}
    return {**ALERT_DEFAULTS, **saved}


def _in_cooldown(db, miner_id, alert_type: str, minutes: float) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S")
    row = db.execute(
        "SELECT 1 FROM alerts WHERE type = ? AND ts > ? AND (miner_id IS ? OR miner_id = ?) LIMIT 1",
        (alert_type, cutoff, miner_id, miner_id),
    ).fetchone()
    return row is not None


def raise_alert(db, settings, miner_id, alert_type, message, value=None,
                threshold=None, severity="warning", cooldown=True):
    if cooldown and _in_cooldown(db, miner_id, alert_type, settings["cooldown_minutes"]):
        return False
    db.execute(
        "INSERT INTO alerts (miner_id, ts, type, severity, message, value, threshold) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (miner_id, dbm.utcnow(), alert_type, severity, message, value, threshold),
    )
    if settings["telegram_enabled"]:
        telegram.send(message)
    logger.info("Alert [%s/%s]: %s", severity, alert_type, message)
    return True


def check_sample(db, miner_id: int, row: dict, prev: dict | None):
    """Run all threshold checks for a freshly ingested sample."""
    s = get_alert_settings(db)
    name = _miner_name(db, miner_id)

    temp, vr_temp, power = row["temp"], row["vr_temp"], row["power"]

    if temp and temp > s["temp_limit"] + 5:
        raise_alert(db, s, miner_id, "critical_temp",
                    f"🚨 <b>{name}</b> CRITICAL temperature: {temp:.1f}°C (limit {s['temp_limit']:.0f}°C)",
                    temp, s["temp_limit"] + 5, "critical")
    elif temp and temp > s["temp_limit"]:
        raise_alert(db, s, miner_id, "high_temp",
                    f"🌡️ <b>{name}</b> high temperature: {temp:.1f}°C (limit {s['temp_limit']:.0f}°C)",
                    temp, s["temp_limit"])

    if vr_temp and vr_temp > s["vr_temp_limit"]:
        raise_alert(db, s, miner_id, "high_vr_temp",
                    f"🔥 <b>{name}</b> high VR temperature: {vr_temp:.1f}°C (limit {s['vr_temp_limit']:.0f}°C)",
                    vr_temp, s["vr_temp_limit"])

    if power and power > s["power_limit"]:
        raise_alert(db, s, miner_id, "high_power",
                    f"⚡ <b>{name}</b> high power draw: {power:.1f}W (limit {s['power_limit']:.0f}W)",
                    power, s["power_limit"])

    if row["overheat_mode"]:
        raise_alert(db, s, miner_id, "overheat_mode",
                    f"🚨 <b>{name}</b> entered AxeOS overheat mode — clocks reset by firmware",
                    severity="critical")

    # Hashrate drop vs. the miner's own expectation (firmware-computed).
    hr, expected = row["hash_rate"], row["expected_hash_rate"]
    if hr is not None and expected and expected > 0:
        floor = expected * (1 - s["hashrate_drop_pct"] / 100.0)
        if hr < floor:
            raise_alert(db, s, miner_id, "hashrate_drop",
                        f"📉 <b>{name}</b> hashrate {hr:.0f} GH/s is "
                        f"{100 * (1 - hr / expected):.0f}% below expected {expected:.0f} GH/s",
                        hr, floor)

    acc, rej = row["shares_accepted"] or 0, row["shares_rejected"] or 0
    if acc + rej > 100:
        reject_rate = 100.0 * rej / (acc + rej)
        if reject_rate > s["reject_rate_limit"]:
            raise_alert(db, s, miner_id, "high_reject_rate",
                        f"⚠️ <b>{name}</b> reject rate {reject_rate:.2f}% "
                        f"(limit {s['reject_rate_limit']:.2f}%)",
                        reject_rate, s["reject_rate_limit"])

    if prev is not None:
        if row["using_fallback"] and not prev["using_fallback"]:
            raise_alert(db, s, miner_id, "fallback_stratum",
                        f"⚠️ <b>{name}</b> switched to fallback stratum", cooldown=False)
        elif prev["using_fallback"] and not row["using_fallback"]:
            raise_alert(db, s, miner_id, "stratum_recovery",
                        f"✅ <b>{name}</b> back on primary stratum",
                        severity="info", cooldown=False)

        if s["achievement_alerts"]:
            cur_best = parse_diff(row["best_diff"])
            if cur_best > parse_diff(prev["best_diff"]) > 0:
                raise_alert(db, s, miner_id, "new_best_diff",
                            f"🎉 <b>{name}</b> new all-time best difficulty: {row['best_diff']}",
                            cur_best, severity="info", cooldown=False)


def check_offline(db):
    """Watchdog: alert when a miner stops reporting, and on recovery."""
    s = get_alert_settings(db)
    now = datetime.now(timezone.utc)
    for m in db.execute("SELECT * FROM miners").fetchall():
        last_seen = datetime.strptime(m["last_seen"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        offline_for = (now - last_seen).total_seconds() / 60
        was_offline = dbm.get_setting(db, f"offline:{m['mac']}", False)
        if offline_for > s["offline_minutes"] and not was_offline:
            dbm.set_setting(db, f"offline:{m['mac']}", True)
            raise_alert(db, s, m["id"], "miner_offline",
                        f"🚨 <b>{m['hostname']}</b> appears offline — "
                        f"no data for {offline_for:.0f} minutes",
                        offline_for, s["offline_minutes"], "error", cooldown=False)
        elif offline_for <= s["offline_minutes"] and was_offline:
            dbm.set_setting(db, f"offline:{m['mac']}", False)
            raise_alert(db, s, m["id"], "miner_recovered",
                        f"✅ <b>{m['hostname']}</b> is reporting again",
                        severity="info", cooldown=False)


def send_daily_summary(db):
    s = get_alert_settings(db)
    if not (s["daily_summary_enabled"] and s["telegram_enabled"]):
        return
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    lines = ["📊 <b>Daily mining summary (24h)</b>"]
    for m in db.execute("SELECT * FROM miners").fetchall():
        agg = db.execute(
            "SELECT COUNT(*) n, AVG(hash_rate) hr, AVG(temp) t, AVG(power) p, "
            "MAX(uptime_seconds) up FROM samples WHERE miner_id = ? AND ts > ?",
            (m["id"], cutoff),
        ).fetchone()
        if not agg["n"]:
            lines.append(f"\n🏷️ <b>{m['hostname']}</b>: no data")
            continue
        eff = (agg["p"] / (agg["hr"] / 1000)) if agg["hr"] else 0
        best = db.execute(
            "SELECT best_diff FROM samples WHERE miner_id = ? ORDER BY ts DESC LIMIT 1",
            (m["id"],),
        ).fetchone()
        lines.append(
            f"\n🏷️ <b>{m['hostname']}</b>\n"
            f"⚡ Avg hashrate: {agg['hr']:.1f} GH/s\n"
            f"🌡️ Avg temp: {agg['t']:.1f}°C\n"
            f"🔌 Avg power: {agg['p']:.1f}W ({eff:.1f} J/TH)\n"
            f"⏱️ Uptime: {(agg['up'] or 0) / 3600:.1f} h\n"
            f"🏆 Best diff: {best['best_diff'] if best else '—'}"
        )
    telegram.send("\n".join(lines))


def _miner_name(db, miner_id) -> str:
    row = db.execute("SELECT hostname FROM miners WHERE id = ?", (miner_id,)).fetchone()
    return row["hostname"] if row else "miner"
