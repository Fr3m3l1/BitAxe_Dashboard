import os
import schedule
import time
import threading
from flask import Flask, session, redirect, url_for, request

from web.api import api_bp
from web.auth import auth_bp
from db.database import init_db
from web.dashboard import dashboard_bp
from web.dash_app import init_dash_app
from service.check_online import check_miner_status

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "defaultsecret")

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)
app.register_blueprint(dashboard_bp)

# Initialize the Dash app with the Flask app as server
dash_app = init_dash_app(app)

# Protect all routes under /dashboard if not logged in
@app.before_request
def restrict_dashboard():
    if request.path.startswith('/dashboard') and not session.get("logged_in"):
        return redirect(url_for("auth.login"))

# Function to run the scheduler
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    init_db()
    
    # Schedule the task
    schedule.every(30).minutes.do(check_miner_status)
    
    # Start the scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True  # Daemonize thread to stop when main exits
    scheduler_thread.start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000)