import sqlite3
import os
from datetime import datetime, timezone

# Create "db" folder and define database path
DB_FOLDER = "db"
os.makedirs(DB_FOLDER, exist_ok=True)
DATABASE = os.path.join(DB_FOLDER, "miner_data.db")

def init_db():
    """Initializes the SQLite database and creates the tables if they do not exist."""
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS miner_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                power REAL,
                voltage REAL,
                current REAL,
                temp REAL,
                vrTemp REAL,
                hashRate REAL,
                bestDiff TEXT,
                bestSessionDiff TEXT,
                stratumDiff REAL,
                isUsingFallbackStratum INTEGER,
                freeHeap REAL,
                coreVoltage REAL,
                coreVoltageActual REAL,
                frequency REAL,
                ssid TEXT,
                macAddr TEXT,
                hostname TEXT,
                wifiStatus TEXT,
                sharesAccepted INTEGER,
                sharesRejected INTEGER,
                uptimeSeconds INTEGER,
                asicCount INTEGER,
                smallCoreCount INTEGER,
                ASICModel TEXT,
                stratumURL TEXT,
                fallbackStratumURL TEXT,
                stratumPort INTEGER,
                fallbackStratumPort INTEGER,
                stratumUser TEXT,
                fallbackStratumUser TEXT,
                version TEXT,
                idfVersion TEXT,
                boardVersion TEXT,
                runningPartition TEXT,
                flipscreen INTEGER,
                overheat_mode INTEGER,
                invertscreen INTEGER,
                invertfanpolarity INTEGER,
                autofanspeed INTEGER,
                fanspeed INTEGER,
                fanrpm INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        
        # Create settings table if it doesn't exist
        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                temp_limit REAL DEFAULT 66.0,
                vr_temp_limit REAL DEFAULT 78.0,
                shares_reject_limit REAL DEFAULT 0.5,
                offline_alarm_enabled INTEGER DEFAULT 1,
                power_consumption_limit REAL DEFAULT 20.0
            )
        ''')
        conn.commit()
        
        # Insert default settings if none exist
        c.execute("SELECT COUNT(*) FROM settings")
        if c.fetchone()[0] == 0:
            c.execute('''
                INSERT INTO settings (temp_limit, vr_temp_limit, shares_reject_limit, offline_alarm_enabled, power_consumption_limit)
                VALUES (65.0, 75.0, 1, 1, 20)
            ''')
            conn.commit()

        # create power_consumption_limit column if it doesn't exist
        c.execute("PRAGMA table_info(settings)")
        columns = [column[1] for column in c.fetchall()]
        if 'power_consumption_limit' not in columns:
            c.execute('''
                ALTER TABLE settings ADD COLUMN power_consumption_limit REAL DEFAULT 20.0
            ''')
            conn.commit()

def get_settings():
    """Retrieves the current settings from the settings table."""
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM settings ORDER BY id DESC LIMIT 1")
        record = c.fetchone()
        if record:
            columns = [desc[0] for desc in c.description]
            return dict(zip(columns, record))
    return {
        'temp_limit': 66.0,
        'vr_temp_limit': 78.0,
        'shares_reject_limit': 0.5,
        'offline_alarm_enabled': 1,
        'power_consumption_limit': 20.0
    }

def update_settings(temp_limit, vr_temp_limit, shares_reject_limit, offline_alarm_enabled, power_consumption_limit):
    """Updates the settings in the settings table."""
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('''
            UPDATE settings
            SET temp_limit = ?,
                vr_temp_limit = ?,
                shares_reject_limit = ?,
                offline_alarm_enabled = ?,
                power_consumption_limit = ?
            WHERE id = (SELECT id FROM settings ORDER BY id DESC LIMIT 1)
        ''', (temp_limit, vr_temp_limit, shares_reject_limit, offline_alarm_enabled, power_consumption_limit))
        conn.commit()
        return True

def get_latest_data():
    """Retrieves the most recent record from the miner_data table."""
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM miner_data ORDER BY id DESC LIMIT 1")
        record = c.fetchone()
        if record:
            columns = [desc[0] for desc in c.description]
            return dict(zip(columns, record))
    return {}

def get_historical_data(minutes=None):
    """Retrieves all miner data records from the database ordered by timestamp."""
    # get now in utc
    now = datetime.now(timezone.utc) 

    if minutes:
        query = f"SELECT * FROM miner_data WHERE timestamp >= datetime('{now}', '-{minutes} minutes') ORDER BY timestamp ASC"
    else:
        query = "SELECT * FROM miner_data ORDER BY timestamp ASC"

    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute(query)
        records = c.fetchall()
        columns = [desc[0] for desc in c.description]
        return [dict(zip(columns, record)) for record in records]


def do_db_request(query, values=None):
    """Executes a database query and returns the result."""
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        if values:
            c.execute(query, values)
        else:
            c.execute(query)
        conn.commit()
        return c.fetchall()
