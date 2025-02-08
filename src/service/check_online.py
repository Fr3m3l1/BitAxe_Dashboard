from datetime import timezone, datetime

from db.database import get_latest_data
from send.telegram_notification import send_telegram_notification

def check_miner_status():
    "Check if the last data got sent within the last 30min"
    last_data = get_latest_data()

    if last_data:
        last_timestamp = datetime.fromisoformat(last_data['timestamp'])
        if last_timestamp.tzinfo is None:
            last_timestamp = last_timestamp.replace(tzinfo=timezone.utc)

        print(f"Last timestamp: {last_timestamp}")
        now = datetime.now(timezone.utc)
        print(f"Now: {now}")
        if (now - last_timestamp).seconds > 1800:
            send_telegram_notification("Miner is offline!")
            return False
    else:
        send_telegram_notification("No data in the database!")
        return False
    
    return True
