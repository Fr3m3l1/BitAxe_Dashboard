import os
import requests

def send_telegram_notification(message):
    """
    Sends a Telegram notification if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID are set.
    """
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram notification skipped: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")
