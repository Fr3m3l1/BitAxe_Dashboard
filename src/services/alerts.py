"""
Enhanced alert service for monitoring miner conditions and sending notifications.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..models import db, MinerData, Settings, AlertLog
from .telegram import TelegramService

logger = logging.getLogger(__name__)

class AlertService:
    """Service for handling miner alerts and notifications."""
    
    def __init__(self):
        self.telegram_service = TelegramService()
        self.cooldown_minutes = Settings.get_setting('alert_cooldown_minutes', 30)
    
    def check_alerts(self, current_data: MinerData, previous_data: Optional[MinerData] = None):
        """Check all alert conditions for the current data."""
        try:
            # Temperature alerts
            self._check_temperature_alerts(current_data)
            
            # Power alerts
            self._check_power_alerts(current_data)
            
            # Performance alerts
            self._check_performance_alerts(current_data, previous_data)
            
            # Network alerts
            self._check_network_alerts(current_data, previous_data)
            
            # Achievement alerts (new bests)
            self._check_achievement_alerts(current_data, previous_data)
            
        except Exception as e:
            logger.error(f"Error checking alerts: {str(e)}")
    
    def _check_temperature_alerts(self, data: MinerData):
        """Check temperature-related alerts."""
        temp_limit = Settings.get_setting('temp_limit', 66.0)
        vr_temp_limit = Settings.get_setting('vr_temp_limit', 78.0)
        
        # Main temperature check
        if data.temp and data.temp > temp_limit:
            if not self._is_in_cooldown('high_temp'):
                self._send_alert(
                    alert_type='high_temp',
                    message=f"⚠️ High temperature detected: {data.temp:.1f}°C (limit: {temp_limit:.1f}°C)",
                    value=data.temp,
                    threshold=temp_limit,
                    severity='warning'
                )
        
        # VR temperature check
        if data.vr_temp and data.vr_temp > vr_temp_limit:
            if not self._is_in_cooldown('high_vr_temp'):
                self._send_alert(
                    alert_type='high_vr_temp',
                    message=f"⚠️ High VR temperature detected: {data.vr_temp:.1f}°C (limit: {vr_temp_limit:.1f}°C)",
                    value=data.vr_temp,
                    threshold=vr_temp_limit,
                    severity='warning'
                )
        
        # Critical temperature check
        critical_temp = temp_limit + 10
        if data.temp and data.temp > critical_temp:
            self._send_alert(
                alert_type='critical_temp',
                message=f"🚨 CRITICAL temperature detected: {data.temp:.1f}°C",
                value=data.temp,
                threshold=critical_temp,
                severity='critical'
            )
    
    def _check_power_alerts(self, data: MinerData):
        """Check power-related alerts."""
        power_limit = Settings.get_setting('power_limit', 20.0)
        
        if data.power and data.power > power_limit:
            if not self._is_in_cooldown('high_power'):
                efficiency = data.efficiency
                self._send_alert(
                    alert_type='high_power',
                    message=f"⚠️ High power consumption: {data.power:.1f}W (limit: {power_limit:.1f}W) | Efficiency: {efficiency:.1f} J/TH",
                    value=data.power,
                    threshold=power_limit,
                    severity='warning'
                )
    
    def _check_performance_alerts(self, data: MinerData, previous_data: Optional[MinerData]):
        """Check performance-related alerts."""
        reject_rate_limit = Settings.get_setting('reject_rate_limit', 0.5) * 100  # Convert to percentage
        
        # Reject rate check
        if data.reject_rate > reject_rate_limit:
            if not self._is_in_cooldown('high_reject_rate'):
                self._send_alert(
                    alert_type='high_reject_rate',
                    message=f"⚠️ High reject rate: {data.reject_rate:.2f}% (limit: {reject_rate_limit:.2f}%)",
                    value=data.reject_rate,
                    threshold=reject_rate_limit,
                    severity='warning'
                )
        
        # Hash rate drop check (if previous data available)
        if previous_data and data.hash_rate and previous_data.hash_rate:
            drop_threshold = 0.2  # 20% drop
            if data.hash_rate < previous_data.hash_rate * (1 - drop_threshold):
                if not self._is_in_cooldown('hash_rate_drop'):
                    self._send_alert(
                        alert_type='hash_rate_drop',
                        message=f"⚠️ Significant hash rate drop: {data.hash_rate:.2f} GH/s (was: {previous_data.hash_rate:.2f} GH/s)",
                        value=data.hash_rate,
                        threshold=previous_data.hash_rate * (1 - drop_threshold),
                        severity='warning'
                    )
    
    def _check_network_alerts(self, data: MinerData, previous_data: Optional[MinerData]):
        """Check network-related alerts."""
        # Fallback stratum check
        if data.is_using_fallback_stratum:
            if not previous_data or not previous_data.is_using_fallback_stratum:
                self._send_alert(
                    alert_type='fallback_stratum',
                    message="⚠️ Miner switched to fallback stratum",
                    severity='warning'
                )
        else:
            # Recovery from fallback
            if previous_data and previous_data.is_using_fallback_stratum:
                self._send_alert(
                    alert_type='stratum_recovery',
                    message="✅ Miner recovered from fallback stratum",
                    severity='info'
                )
    
    def _check_achievement_alerts(self, data: MinerData, previous_data: Optional[MinerData]):
        """Check for new achievements (best difficulty, etc.)."""
        if not previous_data:
            return
        
        # Best overall difficulty
        try:
            current_best = float(data.best_diff) if data.best_diff else 0
            previous_best = float(previous_data.best_diff) if previous_data.best_diff else 0
            
            if current_best > previous_best and current_best > 0:
                self._send_alert(
                    alert_type='new_best_diff',
                    message=f"🎉 New best OVERALL difficulty: {data.best_diff}",
                    value=current_best,
                    severity='info'
                )
        except (ValueError, TypeError):
            pass
        
        # Best session difficulty
        try:
            current_session = float(data.best_session_diff) if data.best_session_diff else 0
            previous_session = float(previous_data.best_session_diff) if previous_data.best_session_diff else 0
            
            if current_session > previous_session and current_session > 0:
                self._send_alert(
                    alert_type='new_session_best',
                    message=f"🎉 New best SESSION difficulty: {data.best_session_diff}",
                    value=current_session,
                    severity='info'
                )
        except (ValueError, TypeError):
            pass
    
    def check_offline_status(self):
        """Check if miner appears to be offline."""
        if not Settings.get_setting('offline_alert_enabled', True):
            return
        
        # Get the latest data
        latest_data = MinerData.query.order_by(MinerData.timestamp.desc()).first()
        
        if not latest_data:
            if not self._is_in_cooldown('no_data'):
                self._send_alert(
                    alert_type='no_data',
                    message="🚨 No data in database - miner may be offline",
                    severity='error'
                )
            return
        
        # Check if data is too old (30 minutes)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        if latest_data.timestamp < cutoff_time:
            if not self._is_in_cooldown('miner_offline'):
                minutes_offline = (datetime.now(timezone.utc) - latest_data.timestamp).seconds // 60
                self._send_alert(
                    alert_type='miner_offline',
                    message=f"🚨 Miner appears offline - last data received {minutes_offline} minutes ago",
                    severity='error'
                )
    
    def _send_alert(self, alert_type: str, message: str, value: float = None, 
                   threshold: float = None, severity: str = 'warning'):
        """Send an alert via all configured channels."""
        try:
            # Log alert to database
            alert_log = AlertLog(
                alert_type=alert_type,
                message=message,
                value=value,
                threshold=threshold,
                severity=severity
            )
            db.session.add(alert_log)
            db.session.commit()
            
            # Send via Telegram if enabled
            if Settings.get_setting('telegram_enabled', False):
                self.telegram_service.send_message(message)
            
            logger.info(f"Alert sent: {alert_type} - {message}")
            
        except Exception as e:
            logger.error(f"Error sending alert: {str(e)}")
    
    def _is_in_cooldown(self, alert_type: str) -> bool:
        """Check if an alert type is in cooldown period."""
        cooldown_time = datetime.now(timezone.utc) - timedelta(minutes=self.cooldown_minutes)
        
        recent_alert = AlertLog.query.filter(
            AlertLog.alert_type == alert_type,
            AlertLog.timestamp > cooldown_time
        ).first()
        
        return recent_alert is not None
