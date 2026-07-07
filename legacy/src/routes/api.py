"""
Enhanced API routes for BitAxe Dashboard with improved error handling and validation.
"""

import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError

from ..models import db, MinerData, Settings, AlertLog
from ..services.alerts import AlertService

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

@api_bp.route('/data', methods=['POST'])
def receive_miner_data():
    """
    Enhanced endpoint to receive miner data with validation and improved error handling.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        # Validate required fields
        required_fields = ['power', 'temp', 'hashRate']
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {missing_fields}'}), 400
        
        # Get the last data point for comparison
        last_data = MinerData.query.order_by(MinerData.timestamp.desc()).first()
        
        # Create new data record
        miner_data = MinerData(
            # Power and electrical data
            power=data.get('power'),
            voltage=data.get('voltage'),
            current=data.get('current'),
            core_voltage=data.get('coreVoltage'),
            core_voltage_actual=data.get('coreVoltageActual'),
            
            # Temperature data
            temp=data.get('temp'),
            vr_temp=data.get('vrTemp'),
            
            # Performance data
            hash_rate=data.get('hashRate'),
            best_diff=str(data.get('bestDiff', '')),
            best_session_diff=str(data.get('bestSessionDiff', '')),
            stratum_diff=data.get('stratumDiff'),
            shares_accepted=data.get('sharesAccepted'),
            shares_rejected=data.get('sharesRejected'),
            
            # System data
            frequency=data.get('frequency'),
            free_heap=data.get('freeHeap'),
            uptime_seconds=data.get('uptimeSeconds'),
            
            # Network data
            ssid=data.get('ssid'),
            mac_addr=data.get('macAddr'),
            hostname=data.get('hostname'),
            wifi_status=data.get('wifiStatus'),
            is_using_fallback_stratum=bool(data.get('isUsingFallbackStratum', False)),
            
            # Hardware data
            asic_count=data.get('asicCount'),
            small_core_count=data.get('smallCoreCount'),
            asic_model=data.get('ASICModel'),
            
            # Stratum data
            stratum_url=data.get('stratumURL'),
            fallback_stratum_url=data.get('fallbackStratumURL'),
            stratum_port=data.get('stratumPort'),
            fallback_stratum_port=data.get('fallbackStratumPort'),
            stratum_user=data.get('stratumUser'),
            fallback_stratum_user=data.get('fallbackStratumUser'),
            
            # Firmware data
            version=data.get('version'),
            idf_version=data.get('idfVersion'),
            board_version=data.get('boardVersion'),
            running_partition=data.get('runningPartition'),
            
            # Settings
            flipscreen=bool(data.get('flipscreen', False)),
            overheat_mode=bool(data.get('overheat_mode', False)),
            invertscreen=bool(data.get('invertscreen', False)),
            invertfanpolarity=bool(data.get('invertfanpolarity', False)),
            autofanspeed=bool(data.get('autofanspeed', True)),
            fanspeed=data.get('fanspeed'),
            fanrpm=data.get('fanrpm')
        )
        
        # Save to database
        db.session.add(miner_data)
        db.session.commit()
        
        # Check for alerts
        alert_service = AlertService()
        alert_service.check_alerts(miner_data, last_data)
        
        logger.info(f"Received and saved miner data: {miner_data.hostname or 'Unknown'}")
        return jsonify({'message': 'Data saved successfully', 'id': miner_data.id}), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error saving miner data: {str(e)}")
        return jsonify({'error': 'Database error'}), 500
    
    except Exception as e:
        logger.error(f"Error processing miner data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/data/latest', methods=['GET'])
@login_required
def get_latest_data():
    """Get the latest miner data point."""
    try:
        data = MinerData.query.order_by(MinerData.timestamp.desc()).first()
        if not data:
            return jsonify({'error': 'No data available'}), 404
        
        return jsonify(data.to_dict()), 200
    
    except Exception as e:
        logger.error(f"Error fetching latest data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/data/historical', methods=['GET'])
@login_required
def get_historical_data():
    """Get historical miner data with time range filtering."""
    try:
        # Get time range from query parameters
        hours = request.args.get('hours', default=6, type=int)
        limit = request.args.get('limit', default=1000, type=int)
        
        # Calculate time cutoff
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Query data
        query = MinerData.query.filter(MinerData.timestamp >= cutoff_time)
        query = query.order_by(MinerData.timestamp.desc()).limit(limit)
        data = query.all()
        
        # Convert to list of dictionaries
        result = [item.to_dict() for item in data]
        
        return jsonify({
            'data': result,
            'count': len(result),
            'hours': hours
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching historical data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/settings', methods=['GET'])
@login_required
def get_settings():
    """Get all application settings."""
    try:
        settings = {
            'temp_limit': Settings.get_setting('temp_limit', 66.0),
            'vr_temp_limit': Settings.get_setting('vr_temp_limit', 78.0),
            'power_limit': Settings.get_setting('power_limit', 20.0),
            'reject_rate_limit': Settings.get_setting('reject_rate_limit', 0.5),
            'offline_alert_enabled': Settings.get_setting('offline_alert_enabled', True),
            'telegram_enabled': Settings.get_setting('telegram_enabled', False),
            'alert_cooldown_minutes': Settings.get_setting('alert_cooldown_minutes', 30)
        }
        
        return jsonify(settings), 200
    
    except Exception as e:
        logger.error(f"Error fetching settings: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/settings', methods=['POST'])
@login_required
def update_settings():
    """Update application settings."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        # Update each setting
        for key, value in data.items():
            if key in ['temp_limit', 'vr_temp_limit', 'power_limit', 'reject_rate_limit', 
                      'offline_alert_enabled', 'telegram_enabled', 'alert_cooldown_minutes']:
                Settings.set_setting(key, value)
        
        logger.info(f"Settings updated: {list(data.keys())}")
        return jsonify({'message': 'Settings updated successfully'}), 200
    
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/alerts', methods=['GET'])
@login_required
def get_alerts():
    """Get recent alerts."""
    try:
        hours = request.args.get('hours', default=24, type=int)
        limit = request.args.get('limit', default=100, type=int)
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        alerts = AlertLog.query.filter(AlertLog.timestamp >= cutoff_time)\
                              .order_by(AlertLog.timestamp.desc())\
                              .limit(limit).all()
        
        result = []
        for alert in alerts:
            result.append({
                'id': alert.id,
                'timestamp': alert.timestamp.isoformat(),
                'type': alert.alert_type,
                'message': alert.message,
                'severity': alert.severity,
                'value': alert.value,
                'threshold': alert.threshold,
                'is_resolved': alert.is_resolved
            })
        
        return jsonify({
            'alerts': result,
            'count': len(result)
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching alerts: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """Get dashboard statistics."""
    try:
        hours = request.args.get('hours', default=24, type=int)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Get data for the time period
        data = MinerData.query.filter(MinerData.timestamp >= cutoff_time).all()
        
        if not data:
            return jsonify({'error': 'No data available for the specified period'}), 404
        
        # Calculate statistics
        hash_rates = [d.hash_rate for d in data if d.hash_rate]
        temps = [d.temp for d in data if d.temp]
        powers = [d.power for d in data if d.power]
        
        stats = {
            'period_hours': hours,
            'data_points': len(data),
            'hash_rate': {
                'avg': sum(hash_rates) / len(hash_rates) if hash_rates else 0,
                'min': min(hash_rates) if hash_rates else 0,
                'max': max(hash_rates) if hash_rates else 0
            },
            'temperature': {
                'avg': sum(temps) / len(temps) if temps else 0,
                'min': min(temps) if temps else 0,
                'max': max(temps) if temps else 0
            },
            'power': {
                'avg': sum(powers) / len(powers) if powers else 0,
                'min': min(powers) if powers else 0,
                'max': max(powers) if powers else 0
            },
            'uptime_hours': data[-1].uptime_seconds / 3600 if data and data[-1].uptime_seconds else 0,
            'efficiency_avg': sum(d.efficiency for d in data if d.efficiency) / len(data) if data else 0
        }
        
        return jsonify(stats), 200
    
    except Exception as e:
        logger.error(f"Error calculating stats: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
