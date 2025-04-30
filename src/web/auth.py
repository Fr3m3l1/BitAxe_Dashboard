import os
from flask import Blueprint, render_template_string, request, redirect, url_for, session, flash
from send.telegram_notification import send_telegram_notification

auth_bp = Blueprint('auth', __name__)

login_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 50px; }
      .container { max-width: 400px; margin: auto; }
      input[type="text"] { width: 100%; padding: 12px; margin: 8px 0; }
      input[type="submit"] { width: 100%; padding: 12px; background-color: #4CAF50; color: white; border: none; }
      .message { color: red; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Login</h2>
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="message">
              {% for message in messages %}
                <p>{{ message }}</p>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}
        <form method="POST">
            <label for="code">Enter your login code:</label>
            <input type="text" id="code" name="code" required>
            <input type="submit" value="Login">
        </form>
    </div>
</body>
</html>
"""

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Displays a login page where the user must enter a code.
    The expected code is set via the LOGIN_CODE environment variable (default: "1234").
    """
    expected_code = os.environ.get("LOGIN_CODE", "1234")
    if request.method == "POST":
        code = request.form.get("code")
        if code == expected_code:
            session["logged_in"] = True
            return redirect(url_for("dashboard.dashboard_home"))
        else:
            flash("Incorrect login code.")
    return render_template_string(login_template)

@auth_bp.route('/logout')
def logout():
    """Logs out the user and redirects to the login page."""
    session.pop("logged_in", None)
    return redirect(url_for("auth.login"))


# if path is "/" then redirect to "/login"
@auth_bp.route('/')
def redirect_to_login():
    return redirect(url_for("auth.login"))

@auth_bp.route('/check_tg_token')
def check_tg_token():
    """
    Checks if the Telegram token and chat ID are set in the environment variables.
    If not, it returns a message indicating that the notification is skipped.
    """
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return "Telegram notification skipped: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set."
    
    send_telegram_notification("Telegram notification test: Token and Chat ID are set.")