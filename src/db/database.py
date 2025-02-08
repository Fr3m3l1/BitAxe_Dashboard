import sqlite3
import os
from datetime import datetime, timezone

# Create "db" folder and define database path
DB_FOLDER = "db"
os.makedirs(DB_FOLDER, exist_ok=True)
DATABASE = os.path.join(DB_FOLDER, "miner_data.db")

def init_db():
    """Initializes the SQLite database and creates the table if it does not exist."""
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
