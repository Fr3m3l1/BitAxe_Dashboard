"""Default settings for alerts and the auto-tuner.

Stored in the settings table as JSON and editable from the web UI.
Tuner settings live under key "tuner:default" with optional per-miner
overrides under "tuner:<mac>".
"""

ALERT_DEFAULTS = {
    "temp_limit": 65.0,          # deg C, ASIC temperature warning
    "vr_temp_limit": 80.0,       # deg C, voltage-regulator temperature warning
    "power_limit": 25.0,         # W
    "hashrate_drop_pct": 20.0,   # % below expected/rolling average
    "reject_rate_limit": 2.0,    # % of shares
    "offline_minutes": 10,       # no data for this long -> offline alert
    "cooldown_minutes": 30,      # min time between repeats of the same alert
    "telegram_enabled": True,
    "achievement_alerts": True,  # notify on new best difficulty
    "daily_summary_enabled": True,
    "daily_summary_hour": 8,     # UTC hour
}

TUNER_DEFAULTS = {
    "enabled": False,
    "mode": "efficiency",        # "efficiency" (J/TH) or "hashrate" (GH/s)
    "target_temp": 60.0,         # tuner keeps the ASIC at or below this
    "max_temp": 65.0,            # hard ceiling -> immediate downclock
    "max_vr_temp": 80.0,
    "max_power": 25.0,           # W
    "freq_min": 400,             # MHz
    "freq_max": 600,
    "freq_step": 25,
    "volt_min": 1000,            # mV core voltage
    "volt_max": 1200,
    "volt_step": 25,
    "settle_seconds": 180,       # wait after a change before measuring
    "dwell_seconds": 600,        # measurement window per operating point
    "allow_restart": True,       # restart the miner if a setting doesn't apply live
}
