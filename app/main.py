"""BitAxe Dashboard — FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from . import alerts, config, db as dbm, network
from .routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def _watchdog_loop():
    """Offline detection every minute."""
    while True:
        try:
            with dbm.get_db() as db:
                alerts.check_offline(db)
        except Exception:
            logger.exception("offline watchdog failed")
        await asyncio.sleep(60)


async def _housekeeping_loop():
    """Retention cleanup + daily summary at the configured hour (checked every 10 min)."""
    last_summary_day = None
    while True:
        try:
            with dbm.get_db() as db:
                cutoff = (datetime.now(timezone.utc)
                          - timedelta(days=config.RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
                db.execute("DELETE FROM samples WHERE ts < ?", (cutoff,))
                acutoff = (datetime.now(timezone.utc)
                           - timedelta(days=config.ALERT_RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
                db.execute("DELETE FROM alerts WHERE ts < ?", (acutoff,))
                db.execute("DELETE FROM tuner_events WHERE ts < ?", (acutoff,))

                s = alerts.get_alert_settings(db)
                now = datetime.now(timezone.utc)
                if now.hour == int(s["daily_summary_hour"]) and last_summary_day != now.date():
                    last_summary_day = now.date()
                    await asyncio.to_thread(alerts.send_daily_summary, db)
        except Exception:
            logger.exception("housekeeping failed")
        await asyncio.sleep(600)


async def _network_refresh_loop():
    """Keep the Bitcoin network-status cache warm so /api/nerd never blocks."""
    while True:
        try:
            await asyncio.to_thread(network.get_network_status)
        except Exception:
            logger.exception("network status refresh failed")
        await asyncio.sleep(600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    dbm.init_db()
    if not config.API_KEY:
        logger.warning("API_KEY is not set — the ingest endpoint accepts unauthenticated data!")
    tasks = [asyncio.create_task(_watchdog_loop()), asyncio.create_task(_housekeeping_loop()),
             asyncio.create_task(_network_refresh_loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="BitAxe Dashboard", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=30 * 24 * 3600)
app.include_router(router)
