"""Environment-based configuration for the BitAxe dashboard."""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "db" / "dashboard.db"))
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Session signing key. Auto-generated if unset (sessions reset on restart).
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

# Login code for the web UI.
ACCESS_CODE = os.getenv("ACCESS_CODE", "1234")

# Shared secret the collector must send in the X-API-Key header.
# If unset, ingest is open (a warning is logged at startup).
API_KEY = os.getenv("API_KEY", "")

# Telegram notifications
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Data retention
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "90"))
ALERT_RETENTION_DAYS = int(os.getenv("ALERT_RETENTION_DAYS", "30"))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))
