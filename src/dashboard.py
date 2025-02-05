from flask import Blueprint, redirect

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard_home():
    """
    Redirects to the Dash app hosted under /dashboard/.
    """
    return redirect("/dashboard/")
