"""
Enhanced scheduler service for background tasks.
"""

import schedule
import time
import threading
import logging
from datetime import datetime, timezone, timedelta

from ..services.alerts import AlertService
from ..models import MinerData, db

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for managing scheduled background tasks."""
    
    def __init__(self):
        self.alert_service = AlertService()
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        # Schedule tasks
        schedule.every(5).minutes.do(self._check_miner_status)
        schedule.every(1).hours.do(self._cleanup_old_data)
        schedule.every(1).hours.do(self._cleanup_old_alerts)
        schedule.every(24).hours.do(self._send_daily_summary)
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        
        logger.info("Scheduler started successfully")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop."""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in scheduler: {str(e)}")
                time.sleep(5)  # Wait before retrying
    
    def _check_miner_status(self):
        """Check if miner is online and responding."""
        try:
            logger.debug("Checking miner status...")
            self.alert_service.check_offline_status()
        except Exception as e:
            logger.error(f"Error checking miner status: {str(e)}")
    
    def _cleanup_old_data(self):
        """Clean up old miner data to prevent database bloat."""
        try:
            # Keep data for 30 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            deleted_count = MinerData.query.filter(
                MinerData.timestamp < cutoff_date
            ).delete()
            
            db.session.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old data records")
                
        except Exception as e:
            logger.error(f"Error cleaning up old data: {str(e)}")
            db.session.rollback()
    
    def _cleanup_old_alerts(self):
        """Clean up old alert logs."""
        try:
            from ..models import AlertLog
            
            # Keep alerts for 7 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
            
            deleted_count = AlertLog.query.filter(
                AlertLog.timestamp < cutoff_date
            ).delete()
            
            db.session.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old alert logs")
                
        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {str(e)}")
            db.session.rollback()
    
    def _send_daily_summary(self):
        """Send daily mining summary."""
        try:
            # Get data from the last 24 hours
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            data = MinerData.query.filter(MinerData.timestamp >= cutoff_time).all()
            
            if not data:
                logger.warning("No data available for daily summary")
                return
            
            # Calculate averages
            avg_hash_rate = sum(d.hash_rate for d in data if d.hash_rate) / len(data)
            avg_temp = sum(d.temp for d in data if d.temp) / len(data)
            avg_power = sum(d.power for d in data if d.power) / len(data)
            avg_efficiency = avg_power / (avg_hash_rate / 1000) if avg_hash_rate > 0 else 0
            
            # Get latest data for current status
            latest = data[-1] if data else None
            
            if latest:
                hostname = latest.hostname or "Unknown"
                uptime_hours = latest.uptime_seconds / 3600 if latest.uptime_seconds else 0
                
                message = f"""
📊 <b>Daily Mining Summary</b>

🏷️ <b>Miner:</b> {hostname}
📈 <b>24h Avg Hash Rate:</b> {avg_hash_rate:.2f} GH/s
🌡️ <b>24h Avg Temperature:</b> {avg_temp:.1f}°C
🔌 <b>24h Avg Power:</b> {avg_power:.1f}W
📊 <b>24h Avg Efficiency:</b> {avg_efficiency:.1f} J/TH
⏱️ <b>Current Uptime:</b> {uptime_hours:.1f} hours
📉 <b>Data Points:</b> {len(data)}
                """.strip()
                
                self.alert_service.telegram_service.send_message(message)
                logger.info("Daily summary sent")
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {str(e)}")

# Global scheduler instance
_scheduler = None

def start_scheduler():
    """Start the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService()
    _scheduler.start()

def stop_scheduler():
    """Stop the global scheduler instance."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None
