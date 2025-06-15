"""
Enhanced Telegram notification service.
"""

import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TelegramService:
    """Service for sending Telegram notifications."""
    
    def __init__(self):
        self.token = os.getenv('TELEGRAM_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.token and self.chat_id)
        
        if not self.enabled:
            logger.info("Telegram service disabled - TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set")
    
    def send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send a message via Telegram.
        
        Args:
            message: The message to send
            parse_mode: Parse mode for formatting (HTML, Markdown, or None)
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled, would have sent: {message}")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Telegram message sent successfully")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to send Telegram message: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {str(e)}")
            return False
    
    def send_status_update(self, hostname: str, hash_rate: float, temp: float, 
                          power: float, uptime_hours: float) -> bool:
        """Send a formatted status update."""
        message = f"""
🖥️ <b>Miner Status Update</b>

🏷️ <b>Hostname:</b> {hostname}
⚡ <b>Hash Rate:</b> {hash_rate:.2f} GH/s
🌡️ <b>Temperature:</b> {temp:.1f}°C
🔌 <b>Power:</b> {power:.1f}W
⏱️ <b>Uptime:</b> {uptime_hours:.1f} hours
📊 <b>Efficiency:</b> {power / (hash_rate / 1000):.1f} J/TH
        """.strip()
        
        return self.send_message(message)
    
    def test_connection(self) -> bool:
        """Test the Telegram connection."""
        return self.send_message("🧪 Telegram connection test - BitAxe Dashboard is online!")
