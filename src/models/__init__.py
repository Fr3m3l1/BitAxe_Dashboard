"""
Database models for the BitAxe Dashboard application.
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class MinerData(db.Model):
    """Model for storing miner data"""
    __tablename__ = 'miner_data'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Power and electrical data
    power = db.Column(db.Float)
    voltage = db.Column(db.Float)
    current = db.Column(db.Float)
    core_voltage = db.Column(db.Float)
    core_voltage_actual = db.Column(db.Float)
    
    # Temperature data
    temp = db.Column(db.Float)
    vr_temp = db.Column(db.Float)
    
    # Performance data
    hash_rate = db.Column(db.Float)
    best_diff = db.Column(db.String(50))
    best_session_diff = db.Column(db.String(50))
    stratum_diff = db.Column(db.Float)
    shares_accepted = db.Column(db.Integer)
    shares_rejected = db.Column(db.Integer)
    
    # System data
    frequency = db.Column(db.Float)
    free_heap = db.Column(db.Float)
    uptime_seconds = db.Column(db.Integer)
    
    # Network data
    ssid = db.Column(db.String(100))
    mac_addr = db.Column(db.String(20))
    hostname = db.Column(db.String(100))
    wifi_status = db.Column(db.String(50))
    is_using_fallback_stratum = db.Column(db.Boolean, default=False)
    
    # Hardware data
    asic_count = db.Column(db.Integer)
    small_core_count = db.Column(db.Integer)
    asic_model = db.Column(db.String(50))
    
    # Stratum data
    stratum_url = db.Column(db.String(200))
    fallback_stratum_url = db.Column(db.String(200))
    stratum_port = db.Column(db.Integer)
    fallback_stratum_port = db.Column(db.Integer)
    stratum_user = db.Column(db.String(200))
    fallback_stratum_user = db.Column(db.String(200))
    
    # Firmware data
    version = db.Column(db.String(50))
    idf_version = db.Column(db.String(50))
    board_version = db.Column(db.String(50))
    running_partition = db.Column(db.String(50))
    
    # Settings
    flipscreen = db.Column(db.Boolean, default=False)
    overheat_mode = db.Column(db.Boolean, default=False)
    invertscreen = db.Column(db.Boolean, default=False)
    invertfanpolarity = db.Column(db.Boolean, default=False)
    autofanspeed = db.Column(db.Boolean, default=True)
    fanspeed = db.Column(db.Integer)
    fanrpm = db.Column(db.Integer)
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'power': self.power,
            'voltage': self.voltage,
            'current': self.current,
            'temp': self.temp,
            'vr_temp': self.vr_temp,
            'hash_rate': self.hash_rate,
            'best_diff': self.best_diff,
            'best_session_diff': self.best_session_diff,
            'stratum_diff': self.stratum_diff,
            'shares_accepted': self.shares_accepted,
            'shares_rejected': self.shares_rejected,
            'frequency': self.frequency,
            'free_heap': self.free_heap,
            'uptime_seconds': self.uptime_seconds,
            'ssid': self.ssid,
            'mac_addr': self.mac_addr,
            'hostname': self.hostname,
            'wifi_status': self.wifi_status,
            'is_using_fallback_stratum': self.is_using_fallback_stratum,
            'asic_count': self.asic_count,
            'small_core_count': self.small_core_count,
            'asic_model': self.asic_model,
            'version': self.version
        }
    
    @property
    def reject_rate(self):
        """Calculate rejection rate"""
        if not self.shares_accepted or not self.shares_rejected:
            return 0
        total = self.shares_accepted + self.shares_rejected
        return (self.shares_rejected / total) * 100 if total > 0 else 0
    
    @property
    def efficiency(self):
        """Calculate efficiency in J/TH"""
        if not self.power or not self.hash_rate:
            return 0
        hash_rate_th = self.hash_rate / 1000  # Convert to TH/s
        return self.power / hash_rate_th if hash_rate_th > 0 else 0

class Settings(db.Model):
    """Model for storing application settings"""
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    @staticmethod
    def get_setting(key, default=None):
        """Get a setting value"""
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            # Try to convert to appropriate type
            try:
                if setting.value.lower() in ['true', 'false']:
                    return setting.value.lower() == 'true'
                return float(setting.value)
            except (ValueError, AttributeError):
                return setting.value
        return default
    
    @staticmethod
    def set_setting(key, value):
        """Set a setting value"""
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
            setting.updated_at = datetime.now(timezone.utc)
        else:
            setting = Settings(key=key, value=str(value))
            db.session.add(setting)
        db.session.commit()
        return setting

class AlertLog(db.Model):
    """Model for logging alerts"""
    __tablename__ = 'alert_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    alert_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    value = db.Column(db.Float)
    threshold = db.Column(db.Float)
    severity = db.Column(db.String(20), default='warning')  # info, warning, error, critical
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
