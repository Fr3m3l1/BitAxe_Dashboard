"""
Main dashboard routes.
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard page - redirects to Dash app."""
    return redirect('/dashboard/')

@dashboard_bp.route('/overview')
@login_required
def overview():
    """Dashboard overview page."""
    return render_template('dashboard/overview.html')
