# BitAxe Dashboard

Web dashboard for monitoring one or more [Bitaxe](https://bitaxe.org) miners.
Receives telemetry pushed by the [BitAxe_DataCollector](../BitAxe_DataCollector)
running in your local network, stores it in SQLite, renders live charts, sends
Telegram alerts and manages the configuration of the collector-side **auto-tuner**.

Built with FastAPI + vanilla JS/Chart.js (no build step). The previous
Flask/Dash implementation is preserved under [`legacy/`](legacy/).

## Features

- **Live overview** — hashrate (with firmware-expected reference), ASIC/VR
  temperature, power, efficiency (J/TH), frequency, core voltage, fan, shares,
  best difficulty, uptime, pool status. Multi-miner support (one chip per miner).
- **History charts** — 1h to 7d, server-side downsampled: hashrate,
  temperatures with limit line, power, efficiency, frequency and core voltage
  (so you can see every tuner step).
- **Alerts** — temperature, VR temperature, power, hashrate drop vs expected,
  reject rate, offline/recovery watchdog, fallback-stratum switch, AxeOS
  overheat mode, new best difficulty. Cooldowns, severity levels, alert log,
  optional Telegram delivery and a daily Telegram summary.
- **Auto-tuner control** — enable/disable and configure the tuner that runs on
  the collector (mode, temperature targets, frequency/voltage ranges); every
  tuner action is reported back and listed with its reason.
- **Stats** — per-range aggregates (avg/min/max hashrate, temps, power,
  efficiency, share counts).

## Architecture

```
Bitaxe (AxeOS) ◄──── local network ────► DataCollector ──── push (HTTPS) ────► Dashboard
   /api/system/info (poll)                  buffers offline                  FastAPI + SQLite
   PATCH /api/system (tuning)               runs the auto-tuner              charts, alerts, config
```

The collector pushes samples to `POST /api/ingest` (authenticated via
`X-API-Key`), fetches tuner configuration from `GET /api/collector/config`,
and reports tuner actions to `POST /api/collector/events`.

## Running

```bash
cp .env.example .env   # set ACCESS_CODE, API_KEY, optionally Telegram
pip install -r requirements.txt
python run.py          # http://localhost:5000
```

Or with Docker (see `docker.sh` for the image build):

```bash
docker run -d --name bitaxe-dashboard --restart unless-stopped \
  --env-file .env -p 5000:5000 -v bitaxe-dashboard-data:/data \
  fr3m3l/miner-app:latest
```

## Configuration (environment)

| Variable | Default | Purpose |
|---|---|---|
| `ACCESS_CODE` | `1234` | Web UI login code |
| `API_KEY` | *(empty = open!)* | Shared secret for the collector |
| `SECRET_KEY` | random | Session signing key |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` | — | Telegram notifications |
| `DB_PATH` | `db/dashboard.db` | SQLite location (`/data/dashboard.db` in Docker) |
| `RETENTION_DAYS` | `90` | Sample retention |
| `ALERT_RETENTION_DAYS` | `30` | Alert/tuner-event retention |
| `HOST` / `PORT` | `0.0.0.0` / `5000` | Bind address |

Alert thresholds and tuner parameters are configured in the web UI
(stored in the database), not via environment variables.

## API summary

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/ingest` (alias `/api/data`) | API key | Sample ingest (single or `{"samples": [...]}`) |
| `GET /api/collector/config` | API key | Tuner config for the collector |
| `POST /api/collector/events` | API key | Tuner event reports |
| `GET /api/overview,/history,/stats,/alerts,/tuner/events` | session | UI data |
| `GET/PUT /api/settings` | session | Alert + tuner settings |
| `POST /api/telegram/test` | session | Test notification |
