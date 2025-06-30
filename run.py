#!/usr/bin/env python3
"""
Main entry point for the Enhanced BitAxe Dashboard.

This script creates and runs the Flask application with all enhanced features:
- Modern responsive UI with glassmorphism design
- Improved authentication and session management
- Advanced alerting system with Telegram integration
- Better error handling and logging
- Scheduled background tasks for monitoring
- Enhanced API endpoints with validation

Usage:
    python run_new.py

Environment Variables:
    FLASK_SECRET_KEY: Secret key for Flask sessions (default: auto-generated)
    DATABASE_URL: Database connection URL (default: sqlite:///miner_data.db)
    LOGIN_CODE: Authentication code (default: 1234)
    TELEGRAM_TOKEN: Telegram bot token for notifications
    TELEGRAM_CHAT_ID: Telegram chat ID for notifications
    DEBUG: Enable debug mode (default: False)
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from flask import Flask
    from flask_login import LoginManager
    from flask_sqlalchemy import SQLAlchemy
    from sqlalchemy import text
    from dotenv import load_dotenv
    import dash
    import dash_bootstrap_components as dbc
    from dash import dcc, html
    import requests
    import schedule
    import pandas as pd
    print("✅ All required packages are available")
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("\nPlease install the required packages:")
    print("pip install -r requirements_new.txt")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()

# Global monitoring system functions
def send_telegram_alert_global(app_instance, message):
    """Send alert message via Telegram using app context."""
    try:
        with app_instance.app_context():
            # Get telegram settings from database
            telegram_token_result = db.session.execute(
                text("SELECT setting_value FROM settings WHERE setting_key = 'telegram_token'")
            ).fetchone()
            telegram_token = telegram_token_result[0] if telegram_token_result else None
            
            telegram_chat_result = db.session.execute(
                text("SELECT setting_value FROM settings WHERE setting_key = 'telegram_chat_id'")
            ).fetchone()
            telegram_chat_id = telegram_chat_result[0] if telegram_chat_result else None
            
            if not telegram_token or not telegram_chat_id:
                logging.getLogger(__name__).warning("Telegram credentials not configured for alerts")
                return False
            
            import requests
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            
            response = requests.post(url, json={
                'chat_id': telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }, timeout=10)
            
            if response.status_code == 200:
                logging.getLogger(__name__).info(f"Telegram alert sent successfully")
                return True
            else:
                logging.getLogger(__name__).error(f"Failed to send Telegram alert: {response.text}")
                return False
                
    except Exception as e:
        logging.getLogger(__name__).error(f"Error sending Telegram alert: {str(e)}")
        return False

def check_thresholds_global(app_instance):
    """Check latest data against configured thresholds and send alerts."""
    try:
        with app_instance.app_context():
            # Import models within app context
            logger = logging.getLogger(__name__)
            
            # Get latest data  
            latest_data = db.session.execute(
                text('SELECT * FROM miner_data ORDER BY timestamp DESC LIMIT 1')
            ).fetchone()
            
            if not latest_data:
                return
            
            # Get threshold settings
            temp_high_setting = db.session.execute(
                text("SELECT setting_value FROM settings WHERE setting_key = 'temp_high_threshold'")
            ).fetchone()
            temp_high = float(temp_high_setting[0] if temp_high_setting else 85)
            
            vrtemp_high_setting = db.session.execute(
                text("SELECT setting_value FROM settings WHERE setting_key = 'vrtemp_high_threshold'")
            ).fetchone()
            vrtemp_high = float(vrtemp_high_setting[0] if vrtemp_high_setting else 75)
            
            hashrate_low_setting = db.session.execute(
                text("SELECT setting_value FROM settings WHERE setting_key = 'hashrate_low_threshold'")
            ).fetchone()
            hashrate_low = float(hashrate_low_setting[0] if hashrate_low_setting else 400)
            
            hashrate_high_setting = db.session.execute(
                text("SELECT setting_value FROM settings WHERE setting_key = 'hashrate_high_threshold'")
            ).fetchone()
            hashrate_high = float(hashrate_high_setting[0] if hashrate_high_setting else 800)
            
            power_high_setting = db.session.execute(
                text("SELECT setting_value FROM settings WHERE setting_key = 'power_high_threshold'")
            ).fetchone()
            power_high = float(power_high_setting[0] if power_high_setting else 15)
            
            alerts = []
            current_temp = latest_data.temp if hasattr(latest_data, 'temp') else latest_data[4]  # temp column
            current_vrtemp = latest_data.vrTemp if hasattr(latest_data, 'vrTemp') else latest_data[5]  # vrTemp column
            current_hashrate = latest_data.hashRate if hasattr(latest_data, 'hashRate') else latest_data[6]  # hashRate column
            current_power = latest_data.power if hasattr(latest_data, 'power') else latest_data[1]  # power column
            current_hostname = latest_data.hostname if hasattr(latest_data, 'hostname') else latest_data[11]  # hostname column
            
            # Check temperature thresholds
            if current_temp and current_temp > temp_high:
                alerts.append(f"🌡️ **High Temperature Alert**\n"
                             f"Current: {current_temp:.1f}°C\n"
                             f"Threshold: {temp_high}°C")
            
            # Check VR temperature thresholds
            if current_vrtemp and current_vrtemp > vrtemp_high:
                alerts.append(f"🔥 **High VR Temperature Alert**\n"
                             f"Current: {current_vrtemp:.1f}°C\n"
                             f"Threshold: {vrtemp_high}°C")
            
            # Check hash rate thresholds
            if current_hashrate and current_hashrate < hashrate_low:
                alerts.append(f"📉 **Low Hash Rate Alert**\n"
                             f"Current: {current_hashrate:.1f} GH/s\n"
                             f"Threshold: {hashrate_low} GH/s")
            
            if current_hashrate and current_hashrate > hashrate_high:
                alerts.append(f"📈 **High Hash Rate Alert**\n"
                             f"Current: {current_hashrate:.1f} GH/s\n"
                             f"Threshold: {hashrate_high} GH/s")
            
            # Check power thresholds
            if current_power and current_power > power_high:
                alerts.append(f"⚡️ **High Power Alert**\n"
                             f"Current: {current_power:.1f}W\n"
                             f"Threshold: {power_high}W")
            
            # Send alerts if any thresholds are violated
            if alerts:
                hostname = current_hostname or "Unknown"
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                message = f"🚨 **BitAxe Alert - {hostname}**\n"
                message += f"Time: {timestamp}\n\n"
                message += "\n\n".join(alerts)
                
                send_telegram_alert_global(app_instance, message)
                logger.warning(f"Threshold violations detected: {len(alerts)} alerts sent")
            
    except Exception as e:
        logging.getLogger(__name__).error(f"Error checking thresholds: {str(e)}")

def start_monitoring_global(app_instance):
    """Start the background monitoring system."""
    try:
        import threading
        import time
        
        def monitoring_loop():
            while True:
                try:
                    check_thresholds_global(app_instance)
                    
                    # Get alert interval from settings (default 5 minutes)
                    with app_instance.app_context():
                        interval_setting = db.session.execute(
                            text("SELECT setting_value FROM settings WHERE setting_key = 'alert_interval'")
                        ).fetchone()
                        alert_interval = int(interval_setting[0] if interval_setting else 5)
                    
                    time.sleep(alert_interval * 60)  # Convert minutes to seconds
                    
                except Exception as e:
                    logging.getLogger(__name__).error(f"Error in monitoring loop: {str(e)}")
                    time.sleep(60)  # Wait 1 minute before retrying
        
        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitor_thread.start()
        logging.getLogger(__name__).info("Background monitoring system started")
        print("✅ Background alert monitoring system started")
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to start monitoring system: {str(e)}")
        print(f"❌ Failed to start monitoring system: {str(e)}")

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Ensure db directory exists
    db_dir = Path('db')
    db_dir.mkdir(exist_ok=True)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'bitaxe-dashboard-secret-key-2024')
    # Use database in db folder - ensure absolute path for SQLite
    db_path = db_dir / 'miner_data.db'
    db_absolute_path = db_path.resolve()
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f'sqlite:///{db_absolute_path}')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['LOGIN_CODE'] = os.getenv('LOGIN_CODE', '1234')
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access the dashboard.'
    login_manager.login_message_category = 'info'
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bitaxe_dashboard.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Simple models for the new application
    from werkzeug.security import generate_password_hash, check_password_hash
    from flask_login import UserMixin
    
    class User(UserMixin, db.Model):
        __tablename__ = 'users'
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(80), unique=True, nullable=False)
        password_hash = db.Column(db.String(120), nullable=False)
        is_active = db.Column(db.Boolean, default=True)
        created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))        
        def set_password(self, password):
            self.password_hash = generate_password_hash(password)
        
        def check_password(self, password):
            return check_password_hash(self.password_hash, password)
    
    class MinerData(db.Model):
        __tablename__ = 'miner_data'
        id = db.Column(db.Integer, primary_key=True)
        timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
        power = db.Column(db.Float)
        voltage = db.Column(db.Float)
        current = db.Column(db.Float)
        temp = db.Column(db.Float)
        vrTemp = db.Column(db.Float)
        hashRate = db.Column(db.Float)
        bestDiff = db.Column(db.String(50))
        bestSessionDiff = db.Column(db.String(50))
        sharesAccepted = db.Column(db.Integer)
        sharesRejected = db.Column(db.Integer)
        hostname = db.Column(db.String(100))
        uptimeSeconds = db.Column(db.Integer)
        
        def to_dict(self):
            return {
                'id': self.id,
                'timestamp': self.timestamp.isoformat() if self.timestamp else None,
                'power': self.power or 0,
                'temp': self.temp or 0,
                'hash_rate': self.hashRate or 0,
                'best_diff': self.bestDiff or '',
                'shares_accepted': self.sharesAccepted or 0,
                'shares_rejected': self.sharesRejected or 0,
                'hostname': self.hostname or 'Unknown'            }
    
    class Settings(db.Model):
        __tablename__ = 'settings'
        id = db.Column(db.Integer, primary_key=True)
        setting_key = db.Column(db.String(100), unique=True, nullable=False)
        setting_value = db.Column(db.Text)
        updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
        
        @staticmethod
        def get_setting(key, default=None):
            """Get a setting value by key."""
            setting = Settings.query.filter_by(setting_key=key).first()
            return setting.setting_value if setting else default
        
        @staticmethod
        def set_setting(key, value):
            """Set a setting value by key."""
            setting = Settings.query.filter_by(setting_key=key).first()
            if setting:
                setting.setting_value = str(value)
                setting.updated_at = datetime.now(timezone.utc)
            else:
                setting = Settings(setting_key=key, setting_value=str(value))
                db.session.add(setting)
            db.session.commit()
            return setting
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Routes
    from flask import render_template, request, redirect, url_for, flash, jsonify
    from flask_login import login_user, logout_user, login_required, current_user
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect('/dashboard/')
        
        if request.method == 'POST':
            password = request.form.get('password', '')
            
            if not password:
                return login_form('Please enter the password.')
            
            # Check if password matches the configured login code
            if password == app.config['LOGIN_CODE']:
                # Get or create the default admin user
                user = User.query.filter_by(username='admin').first()
                if not user:
                    user = User(username='admin')
                    user.set_password(password)
                    db.session.add(user)
                    db.session.commit()
                
                login_user(user, remember=bool(request.form.get('remember')))
                logger.info(f"User logged in successfully")
                return redirect('/dashboard/')
            else:
                logger.warning(f"Failed login attempt with incorrect password")
                return login_form('Invalid password.')
        
        return login_form()
    
    def login_form(error_msg=None):
        """Generate a simple HTML login form."""
        error_html = f'<div style="color: red; margin-bottom: 10px;">{error_msg}</div>' if error_msg else ''
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>BitAxe Dashboard - Login</title>
            <style>
                body {{ font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       margin: 0; padding: 0; height: 100vh; display: flex; align-items: center; justify-content: center; }}
                .login-container {{ background: rgba(255,255,255,0.1); padding: 40px; border-radius: 15px; 
                                  backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); 
                                  box-shadow: 0 8px 32px rgba(0,0,0,0.3); }}
                .login-form {{ max-width: 300px; }}
                h1 {{ color: white; text-align: center; margin-bottom: 30px; }}                .form-group {{ margin-bottom: 20px; }}
                label {{ display: block; color: white; margin-bottom: 5px; }}
                input[type="password"] {{ width: 100%; padding: 10px; border: none; 
                                        border-radius: 5px; background: rgba(255,255,255,0.2); 
                                        color: white; }}
                input[type="password"]::placeholder {{ color: rgba(255,255,255,0.7); }}
                input[type="submit"] {{ width: 100%; padding: 12px; background: #007bff; color: white; 
                                      border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }}
                input[type="submit"]:hover {{ background: #0056b3; }}
                .checkbox-group {{ display: flex; align-items: center; color: white; }}
                .checkbox-group input {{ margin-right: 8px; }}
            </style>
        </head>
        <body>
            <div class="login-container">
                <div class="login-form">
                    <h1>🚀 BitAxe Dashboard</h1>
                    {error_html}                    <form method="post">
                        <div class="form-group">
                            <label for="password">Access Code:</label>
                            <input type="password" id="password" name="password" required placeholder="Enter access code">
                        </div>
                        <div class="form-group">
                            <label class="checkbox-group">
                                <input type="checkbox" name="remember"> Remember me
                            </label>
                        </div>
                        <div class="form-group">
                            <input type="submit" value="Login">
                        </div>
                    </form>
                </div>
            </div>
        </body>
        </html>
        """    
    @app.route('/logout')
    def logout():
        """Logout user and redirect to login page."""
        if current_user.is_authenticated:
            username = current_user.username
            logout_user()
            logger.info(f"User {username} logged out successfully")
        return redirect(url_for('login'))
    
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect('/dashboard/')
        return redirect(url_for('login'))
    
    # API routes
    @app.route('/api/data', methods=['POST'])
    def receive_data():
        """Enhanced API endpoint for receiving miner data."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data received'}), 400
            
            # Create new data record
            miner_data = MinerData(
                power=data.get('power'),
                voltage=data.get('voltage'),
                current=data.get('current'),
                temp=data.get('temp'),
                vrTemp=data.get('vrTemp'),
                hashRate=data.get('hashRate'),
                bestDiff=str(data.get('bestDiff', '')),
                bestSessionDiff=str(data.get('bestSessionDiff', '')),
                sharesAccepted=data.get('sharesAccepted'),
                sharesRejected=data.get('sharesRejected'),
                hostname=data.get('hostname'),
                uptimeSeconds=data.get('uptimeSeconds')
            )
            
            db.session.add(miner_data)
            db.session.commit()
            
            logger.info(f"Received and saved miner data from {miner_data.hostname or 'Unknown'}")
            return jsonify({'message': 'Data saved successfully', 'id': miner_data.id}), 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving miner data: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/data/latest')
    @login_required
    def get_latest_data():
        """Get the latest miner data."""
        try:
            data = MinerData.query.order_by(MinerData.timestamp.desc()).first()
            if not data:
                return jsonify({'error': 'No data available'}), 404
            return jsonify(data.to_dict()), 200
        except Exception as e:
            logger.error(f"Error fetching latest data: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500
    
    # Create Dash app
    dash_app = dash.Dash(
        __name__,
        server=app,
        url_base_pathname='/dashboard/',
        external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]    )
    
    # Custom CSS for dropdown styling with elegant overflow handling
    dash_app.index_string = '''
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>{%title%}</title>
            {%favicon%}
            {%css%}
            <style>
                /* Custom styles for Dash dropdowns */
                .Select-control {
                    background-color: white !important;
                    color: black !important;
                    border: 1px solid #ccc !important;
                    border-radius: 4px !important;
                }
                .Select-control .Select-value {
                    color: black !important;
                }
                .Select-control .Select-placeholder {
                    color: #666 !important;
                }
                .Select-menu {
                    background-color: white !important;
                    z-index: 999999 !important;
                    border: 1px solid #ccc !important;
                    border-radius: 4px !important;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
                }
                .Select-option {
                    background-color: white !important;
                    color: black !important;
                    padding: 8px 12px !important;
                }
                .Select-option:hover {
                    background-color: #f8f9fa !important;
                    color: black !important;
                }
                .Select-option.is-selected {
                    background-color: #007bff !important;
                    color: white !important;
                }
                
                /* For newer React Select versions */
                div[class*="control"] {
                    background-color: white !important;
                    border: 1px solid #ccc !important;
                    border-radius: 4px !important;
                }
                div[class*="singleValue"] {
                    color: black !important;
                }
                div[class*="placeholder"] {
                    color: #666 !important;
                }
                div[class*="menu"] {
                    background-color: white !important;
                    z-index: 999999 !important;
                    border: 1px solid #ccc !important;
                    border-radius: 4px !important;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
                }
                div[class*="option"] {
                    background-color: white !important;
                    color: black !important;
                    padding: 8px 12px !important;
                }
                div[class*="option"]:hover {
                    background-color: #f8f9fa !important;
                    color: black !important;
                }
                
                /* Analysis tab card styling with proper overflow handling */
                .analysis-card {
                    overflow: visible !important;
                    z-index: 100 !important;
                    position: relative !important;
                }
                
                /* Analysis dropdown containers */
                .analysis-dropdown {
                    z-index: 1000 !important;
                    position: relative !important;
                }
                
                /* Force dropdown menus to appear above everything */
                .Select-menu-outer,
                .Select-menu {
                    z-index: 999999 !important;
                    position: absolute !important;
                }
                
                /* Ensure cards don't clip dropdown menus */
                .card {
                    overflow: visible !important;
                }
                .card-body {
                    overflow: visible !important;
                }
                
                /* For Dash components specifically */
                ._dash-dropdown .Select-control {
                    background-color: white !important;
                    color: black !important;
                    border-radius: 4px !important;
                }
                ._dash-dropdown .Select-value {
                    color: black !important;
                }
                ._dash-dropdown .Select-input input {
                    color: black !important;
                }
                ._dash-dropdown .Select-menu {
                    z-index: 999999 !important;
                }
                
                /* Portal-style positioning for dropdown menus */
                .dash-dropdown .Select-menu,
                .dash-dropdown .Select-menu-outer {
                    z-index: 999999 !important;
                    position: fixed !important;
                }
                
                /* Modern styling for analysis cards */
                .analysis-dropdown .Select-control {
                    border-radius: 8px !important;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
                }
                .analysis-dropdown .Select-menu {
                    border-radius: 8px !important;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
                }
            </style>
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
        </body>
    </html>
    '''
    
    dash_app.layout = dbc.Container([
        # Navigation tabs
        dbc.Tabs([
            dbc.Tab(label="📊 Main Dashboard", tab_id="main-dashboard"),
            dbc.Tab(label="📈 Analysis", tab_id="analysis-dashboard"),
            dbc.Tab(label="⚙️ Settings", tab_id="settings-dashboard")
        ], id="tabs", active_tab="main-dashboard", className="mb-3"),
        
        # Content area
        html.Div(id="tab-content"),
        
        # Common elements
        html.Div([
            dbc.Button("Logout", href="/logout", color="outline-light", className="me-2"),
        ], className="text-center mt-4"),
        
        dcc.Interval(id='interval-component', interval=30*1000, n_intervals=0)
    ], fluid=True, style={
        'background': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'min-height': '100vh',
        'padding': '20px'
    })
    
    @dash_app.callback(
        dash.dependencies.Output('stats-content', 'children'),
        [dash.dependencies.Input('interval-component', 'n_intervals')]
    )
    def update_stats(n):
        try:
            latest = MinerData.query.order_by(MinerData.timestamp.desc()).first()
            if latest:
                return dbc.Row([
                    dbc.Col([
                        html.H4(f"{latest.hashRate or 0:.2f} GH/s", className="text-primary"),
                        html.P("Hash Rate", className="text-muted")
                    ], width=3),
                    dbc.Col([
                        html.H4(f"{latest.temp or 0:.1f}°C", className="text-warning"),
                        html.P("Temperature", className="text-muted")
                    ], width=3),
                    dbc.Col([
                        html.H4(f"{latest.power or 0:.1f}W", className="text-success"),
                        html.P("Power", className="text-muted")
                    ], width=3),                    dbc.Col([
                        html.H4(latest.hostname or "Unknown", className="text-info"),
                        html.P("Hostname", className="text-muted")
                    ], width=3)
                ])
            else:
                return html.P("No data available", className="text-muted text-center")
        except Exception as e:            return html.P(f"Error loading data: {str(e)}", className="text-danger text-center")
    
    # Hash Rate Chart Callback
    @dash_app.callback(
        dash.dependencies.Output('hashrate-chart', 'figure'),
        [dash.dependencies.Input('interval-component', 'n_intervals')]
    )
    def update_hashrate_chart(n):
        import plotly.graph_objects as go
        
        try:
            # Get last 24 hours of data
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            data = MinerData.query.filter(MinerData.timestamp >= cutoff).order_by(MinerData.timestamp).all()
            
            if data:
                timestamps = [d.timestamp for d in data]
                hash_rates = [d.hashRate or 0 for d in data]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=hash_rates,
                    mode='lines+markers',
                    name='Hash Rate',
                    line=dict(color='#00d4ff', width=3),
                    marker=dict(size=4, color='#00d4ff'),                    fill='tonexty',
                    fillcolor='rgba(0, 212, 255, 0.1)'
                ))
                
                fig.update_layout(
                    title=dict(
                        text="Hash Rate Performance", 
                        font=dict(color='black', size=16),
                        x=0.5
                    ),
                    xaxis=dict(
                        title="Time",
                        gridcolor='rgba(0,0,0,0.1)',
                        color='black',
                        showgrid=True
                    ),
                    yaxis=dict(
                        title="Hash Rate (GH/s)",
                        gridcolor='rgba(0,0,0,0.1)',
                        color='black',
                        showgrid=True
                    ),
                    template="plotly_white",
                    height=400,
                    paper_bgcolor='white',
                    plot_bgcolor='white',
                    margin=dict(l=60, r=60, t=60, b=60)
                )
                
                return fig
            else:
                # Empty chart
                fig = go.Figure()
                fig.add_annotation(
                    text="No hash rate data available",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(color="black", size=16)
                )
                fig.update_layout(
                    template="plotly_white", 
                    height=400,
                    paper_bgcolor='white',
                    plot_bgcolor='white',
                    xaxis=dict(showgrid=False, showticklabels=False),
                    yaxis=dict(showgrid=False, showticklabels=False)
                )
                return fig
                
        except Exception as e:
            logger.error(f"Error updating hash rate chart: {str(e)}")
            # Error chart
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error loading hash rate chart",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(color="black", size=16)
            )
            fig.update_layout(
                template="plotly_white", 
                height=400,
                paper_bgcolor='white',
                plot_bgcolor='white',
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=False, showticklabels=False)
            )
            return fig
    
    # Temperature Chart Callback
    @dash_app.callback(
        dash.dependencies.Output('temperature-chart', 'figure'),
        [dash.dependencies.Input('interval-component', 'n_intervals')]
    )
    def update_temperature_chart(n):
        import plotly.graph_objects as go
        
        try:
            # Get last 24 hours of data
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            data = MinerData.query.filter(MinerData.timestamp >= cutoff).order_by(MinerData.timestamp).all()
            
            if data:
                timestamps = [d.timestamp for d in data]
                temps = [d.temp or 0 for d in data]
                vr_temps = [d.vrTemp or 0 for d in data]
                
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=temps,
                    mode='lines+markers',
                    name='Temperature',
                    line=dict(color='#00ff88', width=3),
                    marker=dict(size=4, color='#00ff88')
                ))
                
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=vr_temps,
                    mode='lines+markers',
                    name='VR Temperature',
                    line=dict(color='#ff6b6b', width=3),
                    marker=dict(size=4, color='#ff6b6b')
                ))
                
                fig.update_layout(                    title=dict(
                        text="Temperature Monitoring", 
                        font=dict(color='black', size=16),
                        x=0.5
                    ),
                    xaxis=dict(
                        title="Time",
                        gridcolor='rgba(0,0,0,0.1)',
                        color='black',
                        showgrid=True
                    ),
                    yaxis=dict(
                        title="Temperature (°C)",
                        gridcolor='rgba(0,0,0,0.1)',
                        color='black',
                        showgrid=True
                    ),
                    template="plotly_white",
                    height=400,
                    paper_bgcolor='white',
                    plot_bgcolor='white',
                    margin=dict(l=60, r=60, t=60, b=60),
                    legend=dict(
                        font=dict(color='black'),
                        bgcolor='rgba(255,255,255,0.8)',
                        bordercolor='rgba(0,0,0,0.2)',
                        borderwidth=1
                    )
                )
                
                return fig
            else:
                # Empty chart
                fig = go.Figure()
                fig.add_annotation(
                    text="No temperature data available",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(color="black", size=16)
                )
                fig.update_layout(
                    template="plotly_white", 
                    height=400,
                    paper_bgcolor='white',
                    plot_bgcolor='white',
                    xaxis=dict(showgrid=False, showticklabels=False),
                    yaxis=dict(showgrid=False, showticklabels=False)
                )
                return fig
                
        except Exception as e:
            logger.error(f"Error updating temperature chart: {str(e)}")
            # Error chart
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error loading temperature chart",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(color="black", size=16)
            )
            fig.update_layout(
                template="plotly_white", 
                height=400,
                paper_bgcolor='white',
                plot_bgcolor='white',
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=False, showticklabels=False)
            )
            return fig
    
    @dash_app.callback(
        dash.dependencies.Output('test-data-result', 'children'),
        [dash.dependencies.Input('test-data-btn', 'n_clicks')]
    )
    def handle_test_data_generation(n_clicks):
        if n_clicks:
            try:
                # Check if data already exists
                existing_data = MinerData.query.count()
                if existing_data > 100:
                    return dbc.Alert(f'Already have {existing_data} data points. Skipping test data generation.', 
                                   color="info", dismissable=True)
                
                generate_test_data()
                return dbc.Alert('Test data generated successfully!', color="success", dismissable=True)
            except Exception as e:
                return dbc.Alert(f'Error generating test data: {str(e)}', color="danger", dismissable=True)
        return ""
    
    # Test data generation function
    def generate_test_data():
        """Generate some test data for demonstration purposes."""
        import random
        
        # Create 24 hours of test data (one point every 5 minutes)
        for i in range(288):  # 24 * 60 / 5 = 288 points
            timestamp = datetime.now(timezone.utc) - timedelta(minutes=i*5)
              # Generate realistic test data
            base_hash_rate = 485.0
            hash_rate = base_hash_rate + random.uniform(-50, 50)
            
            base_temp = 45.0
            temp = base_temp + random.uniform(-5, 15)
            
            base_power = 15.5
            power = base_power + random.uniform(-2, 3)
            
            test_data = MinerData(
                timestamp=timestamp,
                power=power,
                voltage=12.0 + random.uniform(-0.5, 0.5),
                current=power / 12.0,
                temp=temp,
                vrTemp=temp + random.uniform(5, 15),
                hashRate=hash_rate,
                bestDiff=str(random.randint(1000, 50000)),
                bestSessionDiff=str(random.randint(100, 5000)),
                sharesAccepted=random.randint(1000, 2000),
                sharesRejected=random.randint(0, 10),
                hostname="bitaxe-test-001",
                uptimeSeconds=86400 + i * 300
            )
            
            db.session.add(test_data)
        
        db.session.commit()
        logger.info("Generated test data for 24 hours")    # Initialize database and create admin user
    with app.app_context():
        db.create_all()
        logger.info("Database tables created")
        
        # Check if settings table exists and create default settings
        try:
            # Try to query the settings table to see if it exists
            Settings.query.first()
            logger.info("Settings table exists")
        except Exception as e:
            logger.error(f"Settings table issue: {str(e)}")
            # Force recreate the settings table
            try:
                db.drop_all()
                db.create_all()
                logger.info("Database recreated with all tables")
            except Exception as recreate_error:
                logger.error(f"Error recreating database: {str(recreate_error)}")
        
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin')
            admin.set_password(app.config['LOGIN_CODE'])
            db.session.add(admin)
            db.session.commit()
            logger.info("Created admin user with default password")
        
        # Create default settings if they don't exist
        default_settings = {
            'temp_high_threshold': '85',
            'vrtemp_high_threshold': '75',
            'hashrate_low_threshold': '400',
            'hashrate_high_threshold': '800',
            'power_high_threshold': '15',
            'alert_interval': '5',
            'telegram_token': '',
            'telegram_chat_id': ''
        }
        
        for key, value in default_settings.items():
            if not Settings.query.filter_by(setting_key=key).first():
                setting = Settings(setting_key=key, setting_value=value)
                db.session.add(setting)
        
        try:
            db.session.commit()
            logger.info("Default settings created")
        except Exception as e:
            logger.error(f"Error creating default settings: {str(e)}")
            db.session.rollback()
    
    # Dashboard authentication middleware
    @app.before_request
    def check_dashboard_auth():
        """Check authentication for dashboard routes."""
        if request.path.startswith('/dashboard/'):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
    
    # Tab content callback
    @dash_app.callback(
        dash.dependencies.Output('tab-content', 'children'),
        [dash.dependencies.Input('tabs', 'active_tab')]
    )
    def render_tab_content(active_tab):
        if active_tab == "main-dashboard":
            return html.Div([
                html.H1("🚀 BitAxe Dashboard", className="text-center text-white mb-4"),
                html.P("Welcome to the BitAxe monitoring system!", 
                       className="text-center text-white-50 mb-4"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("📊 Latest Statistics"),
                            dbc.CardBody([
                                html.Div(id="stats-content", children="Loading...")
                            ])
                        ], className="mb-3")
                    ], width=12)
                ]),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("📈 Hash Rate Over Time"),
                            dbc.CardBody([
                                dcc.Graph(id="hashrate-chart", style={'height': '400px'})
                            ])
                        ], className="mb-3")
                    ], width=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("🌡️ Temperature Over Time"),
                            dbc.CardBody([
                                dcc.Graph(id="temperature-chart", style={'height': '400px'})
                            ])
                        ], className="mb-3")
                    ], width=6)                ])
            ])
        
        elif active_tab == "analysis-dashboard":
            return html.Div([
                html.H1("📈 Flexible Analysis", className="text-center text-white mb-4"),
                html.P("Compare up to 2 variables over time", 
                       className="text-center text-white-50 mb-4"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("📈 Custom Variable Analysis"),
                            dbc.CardBody([
                                dcc.Graph(id="analysis-chart", style={'height': '500px'})
                            ])
                        ])
                    ], width=12, className="mb-3")]),

                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("📊 Variable Selection"),
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        html.Label("Select First Variable:", className="mb-2"),
                                        dcc.Dropdown(
                                            id="analysis-var1",
                                            options=[
                                                {'label': 'Hash Rate (GH/s)', 'value': 'hashRate'},
                                                {'label': 'Temperature (°C)', 'value': 'temp'},
                                                {'label': 'VR Temperature (°C)', 'value': 'vrTemp'},
                                                {'label': 'Power (W)', 'value': 'power'},
                                                {'label': 'Voltage (V)', 'value': 'voltage'},
                                                {'label': 'Current (A)', 'value': 'current'},
                                                {'label': 'Shares Accepted', 'value': 'sharesAccepted'},
                                                {'label': 'Shares Rejected', 'value': 'sharesRejected'}
                                            ],
                                            value='hashRate',
                                            placeholder="Select first variable...",
                                            className="analysis-dropdown",
                                            style={
                                                'color': 'black',
                                                'backgroundColor': 'white',
                                                'border': '1px solid #ccc'
                                            }
                                        )
                                    ], width=6),
                                    dbc.Col([
                                        html.Label("Select Second Variable:", className="mb-2"),
                                        dcc.Dropdown(
                                            id="analysis-var2",
                                            options=[
                                                {'label': 'None', 'value': 'none'},
                                                {'label': 'Hash Rate (GH/s)', 'value': 'hashRate'},
                                                {'label': 'Temperature (°C)', 'value': 'temp'},
                                                {'label': 'VR Temperature (°C)', 'value': 'vrTemp'},
                                                {'label': 'Power (W)', 'value': 'power'},
                                                {'label': 'Voltage (V)', 'value': 'voltage'},
                                                {'label': 'Current (A)', 'value': 'current'},
                                                {'label': 'Shares Accepted', 'value': 'sharesAccepted'},
                                                {'label': 'Shares Rejected', 'value': 'sharesRejected'}
                                            ],
                                            value='temp',
                                            placeholder="Select second variable...",
                                            className="analysis-dropdown",
                                            style={
                                                'color': 'black',
                                                'backgroundColor': 'white',
                                                'border': '1px solid #ccc'
                                            }
                                        )
                                    ], width=6)
                                ]),
                                dbc.Row([
                                    dbc.Col([
                                        html.Label("Time Range:", className="mb-2 mt-3"),
                                        dcc.Dropdown(
                                            id="analysis-timerange",
                                            options=[
                                                {'label': 'Last 1 Hour', 'value': 1},
                                                {'label': 'Last 6 Hours', 'value': 6},
                                                {'label': 'Last 12 Hours', 'value': 12},
                                                {'label': 'Last 24 Hours', 'value': 24},
                                                {'label': 'Last 3 Days', 'value': 72},
                                                {'label': 'Last Week', 'value': 168}
                                            ],
                                            value=24,
                                            className="analysis-dropdown",
                                            style={
                                                'color': 'black',
                                                'backgroundColor': 'white',
                                                'border': '1px solid #ccc'
                                            }
                                        )
                                    ], width=6)
                                ])
                            ])
                        ], className="mb-3")
                    ], width=12)
                ])
            ])
        
        elif active_tab == "settings-dashboard":
            return html.Div([
                html.H1("⚙️ Settings", className="text-center text-white mb-4"),
                html.P("Configure alarm settings and notifications", 
                       className="text-center text-white-50 mb-4"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("🔔 Alarm Configuration"),
                            dbc.CardBody([
                                dbc.Form([                                    # Temperature Alarms
                                    dbc.Row([                                        dbc.Col([
                                            html.H5("Temperature Alarms", className="text-primary mb-3"),
                                            dbc.Label("High Temperature Alert (°C):", className="mb-2"),
                                            dbc.Input(
                                                id="temp-high-threshold", 
                                                type="number", 
                                                placeholder="e.g., 85",
                                                value=85,
                                                min=40, 
                                                max=120,
                                                className="mb-3"
                                            ),
                                            dbc.Label("High VR Temperature Alert (°C):", className="mb-2"),
                                            dbc.Input(
                                                id="vrtemp-high-threshold", 
                                                type="number", 
                                                placeholder="e.g., 75",
                                                value=75,
                                                min=40, 
                                                max=120,
                                                className="mb-3"
                                            )
                                        ], width=6),
                                        
                                        dbc.Col([
                                            html.H5("Hash Rate Alarms", className="text-success mb-3"),
                                            dbc.Label("Low Hash Rate Alert (GH/s):", className="mb-2"),
                                            dbc.Input(
                                                id="hashrate-low-threshold", 
                                                type="number", 
                                                placeholder="e.g., 400",
                                                value=400,
                                                min=0, 
                                                max=2000,
                                                step=10,
                                                className="mb-3"
                                            ),
                                            dbc.Label("High Hash Rate Alert (GH/s):", className="mb-2"),
                                            dbc.Input(
                                                id="hashrate-high-threshold", 
                                                type="number", 
                                                placeholder="e.g., 800",
                                                value=800,
                                                min=100, 
                                                max=3000,
                                                step=10,
                                                className="mb-3"
                                            )
                                        ], width=6)
                                    ]),                                    
                                    # Power Alarms
                                    dbc.Row([
                                        dbc.Col([
                                            html.H5("Power Alarms", className="text-warning mb-3"),
                                            dbc.Label("High Power Alert (W):", className="mb-2"),
                                            dbc.Input(
                                                id="power-high-threshold", 
                                                type="number", 
                                                placeholder="e.g., 15",
                                                value=15,
                                                min=5, 
                                                max=50,
                                                step=0.1,
                                                className="mb-3"
                                            )
                                        ], width=6),
                                        
                                        dbc.Col([
                                            html.H5("General Settings", className="text-info mb-3"),                                            dbc.Label("Alert Check Interval (minutes):", className="mb-2"),
                                            dbc.Input(
                                                id="alert-interval", 
                                                type="number", 
                                                placeholder="e.g., 5",
                                                value=5,
                                                min=1, 
                                                max=60,
                                                className="mb-3"
                                            )
                                        ], width=6)
                                    ]),
                                    
                                    # Telegram Settings
                                    html.H5("Telegram Configuration", className="text-primary mb-3"),
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Label("Telegram Bot Token:", className="mb-2"),
                                            dbc.Input(
                                                id="telegram-token", 
                                                type="password", 
                                                placeholder="Enter your bot token",
                                                className="mb-3"
                                            )
                                        ], width=6),
                                        dbc.Col([
                                            dbc.Label("Telegram Chat ID:", className="mb-2"),
                                            dbc.Input(
                                                id="telegram-chat-id", 
                                                type="text", 
                                                placeholder="Enter chat ID",
                                                className="mb-3"
                                            )
                                        ], width=6)
                                    ]),
                                    
                                    # Save and Test buttons
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Button(
                                                "💾 Save Settings", 
                                                id="save-settings-btn", 
                                                color="success", 
                                                size="lg",
                                                className="me-3"
                                            ),
                                            dbc.Button(
                                                "🧪 Test Telegram", 
                                                id="test-telegram-btn", 
                                                color="info", 
                                                size="lg"
                                            ),
                                            html.Div(id="settings-feedback", className="mt-3")
                                        ], width=12, className="text-center")
                                    ])
                                ])
                            ])
                        ], className="mb-3")
                    ], width=12)
                ])
            ])
        
        return html.Div("Error loading content")
    
    # Analysis Chart Callback
    @dash_app.callback(
        dash.dependencies.Output('analysis-chart', 'figure'),
        [
            dash.dependencies.Input('analysis-var1', 'value'),
            dash.dependencies.Input('analysis-var2', 'value'),
            dash.dependencies.Input('analysis-timerange', 'value'),
            dash.dependencies.Input('interval-component', 'n_intervals')
        ]
    )
    def update_analysis_chart(var1, var2, timerange_hours, n):
        import plotly.graph_objects as go
        
        try:
            # Get data for the specified time range
            cutoff = datetime.now(timezone.utc) - timedelta(hours=timerange_hours)
            data = MinerData.query.filter(MinerData.timestamp >= cutoff).order_by(MinerData.timestamp).all()
            
            if not data:
                fig = go.Figure()
                fig.add_annotation(
                    text="No data available for selected time range",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(color="black", size=16)
                )
                fig.update_layout(
                    template="plotly_white", 
                    height=500,
                    paper_bgcolor='white',
                    plot_bgcolor='white',
                    xaxis=dict(showgrid=False, showticklabels=False),
                    yaxis=dict(showgrid=False, showticklabels=False)
                )
                return fig
            
            timestamps = [d.timestamp for d in data]
            
            # Variable mapping and labels
            var_mapping = {
                'hashRate': ('Hash Rate', 'GH/s', lambda d: d.hashRate or 0, '#00d4ff'),
                'temp': ('Temperature', '°C', lambda d: d.temp or 0, '#00ff88'),
                'vrTemp': ('VR Temperature', '°C', lambda d: d.vrTemp or 0, '#ff6b6b'),
                'power': ('Power', 'W', lambda d: d.power or 0, '#ffeb3b'),
                'voltage': ('Voltage', 'V', lambda d: d.voltage or 0, '#ff9800'),
                'current': ('Current', 'A', lambda d: d.current or 0, '#9c27b0'),
                'sharesAccepted': ('Shares Accepted', 'count', lambda d: d.sharesAccepted or 0, '#4caf50'),
                'sharesRejected': ('Shares Rejected', 'count', lambda d: d.sharesRejected or 0, '#f44336')
            }
            
            fig = go.Figure()
            
            # Add first variable
            if var1 and var1 in var_mapping:
                var1_info = var_mapping[var1]
                var1_values = [var1_info[2](d) for d in data]
                
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=var1_values,
                    mode='lines+markers',
                    name=f'{var1_info[0]} ({var1_info[1]})',
                    line=dict(color=var1_info[3], width=3),
                    marker=dict(size=4, color=var1_info[3]),
                    yaxis='y'
                ))
            
            # Add second variable if selected and different from first
            if var2 and var2 != 'none' and var2 != var1 and var2 in var_mapping:
                var2_info = var_mapping[var2]
                var2_values = [var2_info[2](d) for d in data]
                
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=var2_values,
                    mode='lines+markers',
                    name=f'{var2_info[0]} ({var2_info[1]})',
                    line=dict(color=var2_info[3], width=3),
                    marker=dict(size=4, color=var2_info[3]),
                    yaxis='y2'
                ))
                  # Dual y-axis layout
                fig.update_layout(
                    yaxis=dict(
                        title=f"{var_mapping[var1][0]} ({var_mapping[var1][1]})",
                        side='left',
                        gridcolor='rgba(0,0,0,0.1)',
                        color='black',
                        showgrid=True
                    ),
                    yaxis2=dict(
                        title=f"{var_mapping[var2][0]} ({var_mapping[var2][1]})",
                        side='right',
                        overlaying='y',
                        gridcolor='rgba(0,0,0,0.05)',
                        color='black',
                        showgrid=True
                    )
                )
            else:
                # Single y-axis layout
                if var1 and var1 in var_mapping:
                    fig.update_layout(
                        yaxis=dict(
                            title=f"{var_mapping[var1][0]} ({var_mapping[var1][1]})",
                            gridcolor='rgba(0,0,0,0.1)',
                            color='black',
                            showgrid=True
                        )
                    )
              # Common layout settings
            fig.update_layout(
                title=dict(
                    text=f"Custom Analysis - {timerange_hours}h timerange", 
                    font=dict(color='black', size=18),
                    x=0.5
                ),
                xaxis=dict(
                    title="Time",
                    gridcolor='rgba(0,0,0,0.1)',
                    color='black',
                    showgrid=True
                ),
                template="plotly_white",
                height=500,
                paper_bgcolor='white',
                plot_bgcolor='white',
                margin=dict(l=80, r=80, t=80, b=60),
                legend=dict(
                    font=dict(color='black'),
                    bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='rgba(0,0,0,0.2)',
                    borderwidth=1,
                    x=0.02,
                    y=0.98
                )
            )
            
            return fig
                
        except Exception as e:
            logger.error(f"Error updating analysis chart: {str(e)}")
            # Error chart
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error loading analysis chart: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(color="black", size=16)
            )
            fig.update_layout(
                template="plotly_white", 
                height=500,
                paper_bgcolor='white',
                plot_bgcolor='white',
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=False, showticklabels=False)
            )
            return fig
    
    # Settings Callbacks
    @dash_app.callback(
        dash.dependencies.Output('settings-feedback', 'children'),
        [
            dash.dependencies.Input('save-settings-btn', 'n_clicks'),
            dash.dependencies.Input('test-telegram-btn', 'n_clicks')
        ],        [
            dash.dependencies.State('temp-high-threshold', 'value'),
            dash.dependencies.State('vrtemp-high-threshold', 'value'),
            dash.dependencies.State('hashrate-low-threshold', 'value'),
            dash.dependencies.State('hashrate-high-threshold', 'value'),
            dash.dependencies.State('power-high-threshold', 'value'),
            dash.dependencies.State('alert-interval', 'value'),
            dash.dependencies.State('telegram-token', 'value'),
            dash.dependencies.State('telegram-chat-id', 'value')        ]
    )
    def handle_settings_actions(save_clicks, test_clicks, temp_high, vrtemp_high,
                               hashrate_low, hashrate_high, power_high,
                               alert_interval, telegram_token, telegram_chat_id):
        """Handle settings save and telegram test actions."""
        import dash
        from dash.exceptions import PreventUpdate
        
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'save-settings-btn' and save_clicks:
            try:                # Save settings to database
                Settings.set_setting('temp_high_threshold', temp_high or 85)
                Settings.set_setting('vrtemp_high_threshold', vrtemp_high or 75)
                Settings.set_setting('hashrate_low_threshold', hashrate_low or 400)
                Settings.set_setting('hashrate_high_threshold', hashrate_high or 800)
                Settings.set_setting('power_high_threshold', power_high or 15)
                Settings.set_setting('alert_interval', alert_interval or 5)
                Settings.set_setting('telegram_token', telegram_token or '')
                Settings.set_setting('telegram_chat_id', telegram_chat_id or '')
                
                logger.info("Settings saved successfully to database")
                
                return dbc.Alert(
                    "✅ Settings saved successfully!", 
                    color="success", 
                    dismissable=True,
                    duration=5000
                )
                
            except Exception as e:
                logger.error(f"Error saving settings: {str(e)}")
                return dbc.Alert(
                    f"❌ Error saving settings: {str(e)}", 
                    color="danger", 
                    dismissable=True,
                    duration=5000
                )
        
        elif button_id == 'test-telegram-btn' and test_clicks:
            try:
                if not telegram_token or not telegram_chat_id:
                    return dbc.Alert(
                        "⚠️ Please enter both Telegram token and chat ID", 
                        color="warning", 
                        dismissable=True,
                        duration=5000
                    )
                
                # Test telegram notification
                import requests
                message = "🧪 Test message from BitAxe Dashboard\nIf you receive this, notifications are working!"
                url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                
                response = requests.post(url, json={
                    'chat_id': telegram_chat_id,
                    'text': message,
                    'parse_mode': 'Markdown'
                }, timeout=10)
                
                if response.status_code == 200:
                    return dbc.Alert(
                        "✅ Telegram test message sent successfully!", 
                        color="success", 
                        dismissable=True,
                        duration=5000
                    )
                else:
                    return dbc.Alert(
                        f"❌ Telegram test failed: {response.text}", 
                        color="danger", 
                        dismissable=True,
                        duration=5000
                    )
                    
            except Exception as e:
                logger.error(f"Error testing Telegram: {str(e)}")
                return dbc.Alert(
                    f"❌ Telegram test error: {str(e)}", 
                    color="danger", 
                    dismissable=True,                    duration=5000
                )
        
        raise PreventUpdate

    # Load settings callback
    @dash_app.callback(        [
            dash.dependencies.Output('temp-high-threshold', 'value'),
            dash.dependencies.Output('vrtemp-high-threshold', 'value'),
            dash.dependencies.Output('hashrate-low-threshold', 'value'),
            dash.dependencies.Output('hashrate-high-threshold', 'value'),
            dash.dependencies.Output('power-high-threshold', 'value'),
            dash.dependencies.Output('alert-interval', 'value'),
            dash.dependencies.Output('telegram-token', 'value'),
            dash.dependencies.Output('telegram-chat-id', 'value')
        ],
        [dash.dependencies.Input('tabs', 'active_tab')]
    )
    def load_settings(active_tab):
        """Load settings from database when Settings tab is opened."""
        if active_tab == "settings-dashboard":
            try:
                temp_high = float(Settings.get_setting('temp_high_threshold', 85))
                vrtemp_high = float(Settings.get_setting('vrtemp_high_threshold', 75))
                hashrate_low = float(Settings.get_setting('hashrate_low_threshold', 400))
                hashrate_high = float(Settings.get_setting('hashrate_high_threshold', 800))
                power_high = float(Settings.get_setting('power_high_threshold', 15))
                alert_interval = int(Settings.get_setting('alert_interval', 5))
                telegram_token = Settings.get_setting('telegram_token', '')
                telegram_chat_id = Settings.get_setting('telegram_chat_id', '')
                
                return temp_high, vrtemp_high, hashrate_low, hashrate_high, power_high, alert_interval, telegram_token, telegram_chat_id
            except Exception as e:
                logger.error(f"Error loading settings: {str(e)}")
                # Return default values if loading fails
                return 85, 75, 400, 800, 15, 5, '', ''
        
        # Return default values for other tabs to prevent callback errors
        return 85, 75, 400, 800, 15, 5, '', ''

    # Add custom CSS for better tab visibility
    dash_app.index_string = '''
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>{%title%}</title>
            {%favicon%}
            {%css%}
            <style>
                /* Custom tab styling for better visibility */
                .nav-tabs {
                    background: rgba(255,255,255,0.15) !important;
                    border-radius: 10px !important;
                    padding: 5px !important;
                    backdrop-filter: blur(10px) !important;
                    border: 1px solid rgba(255,255,255,0.2) !important;
                }
                .nav-tabs .nav-item .nav-link {
                    color: white !important;
                    background: rgba(255,255,255,0.1) !important;
                    border: 1px solid rgba(255,255,255,0.2) !important;
                    border-radius: 8px !important;
                    margin: 2px !important;
                    font-weight: 500 !important;
                    transition: all 0.3s ease !important;
                }
                .nav-tabs .nav-item .nav-link:hover {
                    background: rgba(255,255,255,0.2) !important;
                    color: white !important;
                    transform: translateY(-1px) !important;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
                }
                .nav-tabs .nav-item .nav-link.active {
                    background: rgba(255,255,255,0.3) !important;
                    color: white !important;
                    border: 1px solid rgba(255,255,255,0.4) !important;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
                }
                /* Card styling improvements */
                .card {
                    background: rgba(255,255,255,0.95) !important;
                    backdrop-filter: blur(10px) !important;
                    border: 1px solid rgba(255,255,255,0.2) !important;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1) !important;
                }
                .card-header {
                    background: rgba(255,255,255,0.8) !important;
                    border-bottom: 1px solid rgba(0,0,0,0.1) !important;
                    font-weight: 600 !important;
                }
            </style>
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
        </body>
    </html>
    '''
    
    # Alert monitoring system
    def send_telegram_alert(message, telegram_token=None, telegram_chat_id=None):
        """Send alert message via Telegram."""
        try:
            if not telegram_token:
                telegram_token = Settings.get_setting('telegram_token')
            if not telegram_chat_id:
                telegram_chat_id = Settings.get_setting('telegram_chat_id')
            
            if not telegram_token or not telegram_chat_id:
                logger.warning("Telegram credentials not configured for alerts")
                return False
            
            import requests
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            
            response = requests.post(url, json={
                'chat_id': telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Telegram alert sent successfully: {message}")
                return True
            else:
                logger.error(f"Failed to send Telegram alert: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {str(e)}")
            return False
    
    def check_thresholds():
        """Check latest data against configured thresholds and send alerts."""
        try:
            # Get latest data
            latest_data = MinerData.query.order_by(MinerData.timestamp.desc()).first()
            if not latest_data:
                return
            
            # Get threshold settings
            temp_high = float(Settings.get_setting('temp_high_threshold', 85))
            vrtemp_high = float(Settings.get_setting('vrtemp_high_threshold', 75))
            hashrate_low = float(Settings.get_setting('hashrate_low_threshold', 400))
            hashrate_high = float(Settings.get_setting('hashrate_high_threshold', 800))
            power_high = float(Settings.get_setting('power_high_threshold', 15))
            
            alerts = []
            
            # Check temperature thresholds
            if latest_data.temp and latest_data.temp > temp_high:
                alerts.append(f"🌡️ **High Temperature Alert**\n"
                             f"Current: {latest_data.temp:.1f}°C\n"
                             f"Threshold: {temp_high}°C")
            
            # Check VR temperature thresholds
            if latest_data.vrTemp and latest_data.vrTemp > vrtemp_high:
                alerts.append(f"🔥 **High VR Temperature Alert**\n"
                             f"Current: {latest_data.vrTemp:.1f}°C\n"
                             f"Threshold: {vrtemp_high}°C")
            
            # Check hash rate thresholds
            if latest_data.hashRate and latest_data.hashRate < hashrate_low:
                alerts.append(f"📉 **Low Hash Rate Alert**\n"
                             f"Current: {latest_data.hashRate:.1f} GH/s\n"
                             f"Threshold: {hashrate_low} GH/s")
            
            if latest_data.hashRate and latest_data.hashRate > hashrate_high:
                alerts.append(f"📈 **High Hash Rate Alert**\n"
                             f"Current: {latest_data.hashRate:.1f} GH/s\n"
                             f"Threshold: {hashrate_high} GH/s")
            
            # Check power thresholds
            if latest_data.power and latest_data.power > power_high:
                alerts.append(f"⚡️ **High Power Alert**\n"
                             f"Current: {latest_data.power:.1f}W\n"
                             f"Threshold: {power_high}W")
            
            # Send alerts if any thresholds are violated
            if alerts:
                hostname = latest_data.hostname or "Unknown"
                timestamp = latest_data.timestamp.strftime("%Y-%m-%d %H:%M:%S") if latest_data.timestamp else "Unknown"
                
                message = f"🚨 **BitAxe Alert - {hostname}**\n"
                message += f"Time: {timestamp}\n\n"
                message += "\n\n".join(alerts)
                
                send_telegram_alert(message)
                logger.warning(f"Threshold violations detected: {len(alerts)} alerts sent")
            
        except Exception as e:
            logger.error(f"Error checking thresholds: {str(e)}")
    
    def start_monitoring():
        """Start the background monitoring system."""
        try:
            import threading
            import time
            
            def monitoring_loop():
                while True:
                    try:
                        with app.app_context():
                            check_thresholds()
                        
                        # Get alert interval from settings (default 5 minutes)
                        alert_interval = int(Settings.get_setting('alert_interval', 5))
                        time.sleep(alert_interval * 60)  # Convert minutes to seconds
                        
                    except Exception as e:
                        logger.error(f"Error in monitoring loop: {str(e)}")
                        time.sleep(60)  # Wait 1 minute before retrying
            
            # Start monitoring in background thread
            monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
            monitor_thread.start()
            logger.info("Background monitoring system started")
        except Exception as e:
            logger.error(f"Failed to start monitoring system: {str(e)}")
    return app

    # Add monitoring methods to app instance
    app.send_telegram_alert = send_telegram_alert
    app.check_thresholds = check_thresholds  
    app.start_monitoring = start_monitoring

if __name__ == '__main__':
    print("🚀 Starting Enhanced BitAxe Dashboard...")
    print("=" * 60)
    
    # Check if all required packages are available
    missing_packages = []
    required_packages = [
        ('flask', 'Flask'),
        ('flask_login', 'Flask-Login'),
        ('flask_sqlalchemy', 'Flask-SQLAlchemy'),
        ('dash', 'Dash'),
        ('dash_bootstrap_components', 'Dash Bootstrap Components'),
        ('plotly', 'Plotly'),
        ('pandas', 'Pandas'),
        ('requests', 'Requests')    ]
    
    for package, name in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(name)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nPlease install missing packages:")
        print("pip install -r requirements_new.txt")
        sys.exit(1)
    
    print("✅ All required packages are available")
    
    # Create and run the app
    app = create_app()
    
    data_count = 0
    with app.app_context():
        try:
            # Count data points if table exists
            result = db.session.execute(text('SELECT COUNT(*) FROM miner_data'))
            data_count = result.scalar() or 0
        except Exception:
            data_count = 0    # Run the development server
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    print(f"🚀 Starting server (Debug: {debug_mode})...")
    
    # Start background monitoring system
    try:
        start_monitoring_global(app)
    except Exception as e:
        print(f"⚠️ Failed to start monitoring: {str(e)}")
    
    try:
        app.run(
            host='0.0.0.0', 
            port=5000, 
            debug=debug_mode,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)
