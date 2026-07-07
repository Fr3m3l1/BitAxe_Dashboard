"""
BitAxe Dashboard - Enhanced Mining Dashboard Application

A modern, responsive web application for monitoring BitAxe miners with
real-time data visualization, advanced alerting, and improved stability.
"""

import os
import logging
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    """Application factory pattern for creating Flask app"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///miner_data.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['LOGIN_CODE'] = os.getenv('LOGIN_CODE', '1234')
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access the dashboard.'
    login_manager.login_message_category = 'info'
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # User loader for Flask-Login
    from .models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.api import api_bp
    from .routes.dashboard import dashboard_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)
    
    # Initialize database
    with app.app_context():
        db.create_all()
        
        # Create default user if not exists
        from .models import User
        if not User.query.filter_by(username='admin').first():
            user = User(username='admin')
            user.set_password(app.config['LOGIN_CODE'])
            db.session.add(user)
            db.session.commit()
    
    # Initialize Dash app
    from .dashboard.dash_app import init_dash_app
    dash_app = init_dash_app(app)
    
    # Start background services
    from .services.scheduler import start_scheduler
    start_scheduler()
    
    return app
