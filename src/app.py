import os
import sqlite3
import requests
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, flash

# Initialize Flask
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "defaultsecret")

# Create "db" folder and set the database path
DB_FOLDER = "db"
os.makedirs(DB_FOLDER, exist_ok=True)
DATABASE = os.path.join(DB_FOLDER, "miner_data.db")

def init_db():
    """Initialisiert die SQLite-Datenbank und erstellt die Tabelle, falls noch nicht vorhanden."""
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS miner_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                power REAL,
                voltage REAL,
                current REAL,
                temp REAL,
                vrTemp REAL,
                hashRate REAL,
                bestDiff TEXT,
                bestSessionDiff TEXT,
                stratumDiff REAL,
                isUsingFallbackStratum INTEGER,
                freeHeap REAL,
                coreVoltage REAL,
                coreVoltageActual REAL,
                frequency REAL,
                ssid TEXT,
                macAddr TEXT,
                hostname TEXT,
                wifiStatus TEXT,
                sharesAccepted INTEGER,
                sharesRejected INTEGER,
                uptimeSeconds INTEGER,
                asicCount INTEGER,
                smallCoreCount INTEGER,
                ASICModel TEXT,
                stratumURL TEXT,
                fallbackStratumURL TEXT,
                stratumPort INTEGER,
                fallbackStratumPort INTEGER,
                stratumUser TEXT,
                fallbackStratumUser TEXT,
                version TEXT,
                idfVersion TEXT,
                boardVersion TEXT,
                runningPartition TEXT,
                flipscreen INTEGER,
                overheat_mode INTEGER,
                invertscreen INTEGER,
                invertfanpolarity INTEGER,
                autofanspeed INTEGER,
                fanspeed INTEGER,
                fanrpm INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def send_telegram_notification(message):
    """
    Sendet eine Telegram-Benachrichtigung, wenn die Umgebungsvariablen TELEGRAM_TOKEN und TELEGRAM_CHAT_ID gesetzt sind.
    """
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram notification skipped: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
         "chat_id": chat_id,
         "text": message
    }
    try:
         response = requests.post(url, json=payload)
         response.raise_for_status()
    except Exception as e:
         print(f"Error sending Telegram notification: {e}")

@app.route('/api/input', methods=['POST'])
def receive_data():
    """
    Empfaengt Miner-Daten per POST-Request und speichert sie in der SQLite-Datenbank.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400

    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO miner_data (
                power,
                voltage,
                current,
                temp,
                vrTemp,
                hashRate,
                bestDiff,
                bestSessionDiff,
                stratumDiff,
                isUsingFallbackStratum,
                freeHeap,
                coreVoltage,
                coreVoltageActual,
                frequency,
                ssid,
                macAddr,
                hostname,
                wifiStatus,
                sharesAccepted,
                sharesRejected,
                uptimeSeconds,
                asicCount,
                smallCoreCount,
                ASICModel,
                stratumURL,
                fallbackStratumURL,
                stratumPort,
                fallbackStratumPort,
                stratumUser,
                fallbackStratumUser,
                version,
                idfVersion,
                boardVersion,
                runningPartition,
                flipscreen,
                overheat_mode,
                invertscreen,
                invertfanpolarity,
                autofanspeed,
                fanspeed,
                fanrpm
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data.get('power'),
            data.get('voltage'),
            data.get('current'),
            data.get('temp'),
            data.get('vrTemp'),
            data.get('hashRate'),
            data.get('bestDiff'),
            data.get('bestSessionDiff'),
            data.get('stratumDiff'),
            data.get('isUsingFallbackStratum'),
            data.get('freeHeap'),
            data.get('coreVoltage'),
            data.get('coreVoltageActual'),
            data.get('frequency'),
            data.get('ssid'),
            data.get('macAddr'),
            data.get('hostname'),
            data.get('wifiStatus'),
            data.get('sharesAccepted'),
            data.get('sharesRejected'),
            data.get('uptimeSeconds'),
            data.get('asicCount'),
            data.get('smallCoreCount'),
            data.get('ASICModel'),
            data.get('stratumURL'),
            data.get('fallbackStratumURL'),
            data.get('stratumPort'),
            data.get('fallbackStratumPort'),
            data.get('stratumUser'),
            data.get('fallbackStratumUser'),
            data.get('version'),
            data.get('idfVersion'),
            data.get('boardVersion'),
            data.get('runningPartition'),
            data.get('flipscreen'),
            data.get('overheat_mode'),
            data.get('invertscreen'),
            data.get('invertfanpolarity'),
            data.get('autofanspeed'),
            data.get('fanspeed'),
            data.get('fanrpm')
        ))
        conn.commit()

    # Sende Telegram-Benachrichtigung
    send_telegram_notification("Neue Miner-Daten empfangen und gespeichert.")

    return jsonify({'message': 'Data saved successfully'}), 200

# --------------------------
# Login- und Logout-Seiten
# --------------------------
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Zeigt eine grafische Login-Seite, auf der der Nutzer einen Code eingeben muss.
    Der erwartete Code wird ueber die Umgebungsvariable LOGIN_CODE (Standard: "1234") gesetzt.
    """
    expected_code = os.environ.get("LOGIN_CODE", "1234")
    if request.method == 'POST':
        code = request.form.get("code")
        if code == expected_code:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            flash("Incorrect login code.")
    return render_template_string(login_template)

@app.route('/logout')
def logout():
    """Meldet den Nutzer ab und leitet zur Login-Seite weiter."""
    session.pop("logged_in", None)
    return redirect(url_for("login"))

# -------------------------------------------------------------------
# Schuetzen Sie alle Routen unter /dashboard, wenn der Nutzer nicht eingeloggt ist.
# -------------------------------------------------------------------
@app.before_request
def restrict_dashboard():
    if request.path.startswith('/dashboard'):
        if not session.get("logged_in"):
            return redirect(url_for("login"))

# --------------------------
# Integration von Dash als Dashboard
# --------------------------
import dash
from dash import dcc, html
from dash.dependencies import Input, Output

# Erstelle die Dash-App und binde sie in die Flask-App ein
dash_app = dash.Dash(
    __name__,
    server=app,
    url_base_pathname='/dashboard/',
    suppress_callback_exceptions=True
)

def get_latest_data():
    """Liest den zuletzt gespeicherten Datensatz aus der Datenbank."""
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM miner_data ORDER BY id DESC LIMIT 1")
        record = c.fetchone()
        if record:
            columns = [desc[0] for desc in c.description]
            return dict(zip(columns, record))
    return {}

# Definiere das Layout der Dash-App
dash_app.layout = html.Div([
    html.H1("Miner Dashboard"),
    dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0),
    html.Div(id='live-update'),
    html.Br(),
    html.A("Logout", href="/logout")
])

# Callback zum periodischen Aktualisieren der angezeigten Daten
@dash_app.callback(Output('live-update', 'children'),
                   [Input('interval-component', 'n_intervals')])
def update_data(n):
    data = get_latest_data()
    if not data:
        return html.Div("No data available.")
    # Erstelle eine HTML-Tabelle zur Darstellung der Daten
    header = [html.Tr([html.Th("Feld"), html.Th("Wert")])]
    rows = [html.Tr([html.Td(key), html.Td(str(value))]) for key, value in data.items()]
    table = html.Table(header + rows, style={'width': '100%', 'border': '1px solid #ddd', 'border-collapse': 'collapse'})
    return table

# Leite /dashboard auf die Dash-App weiter
@app.route('/dashboard')
def dashboard():
    return redirect("/dashboard/")

# --------------------------
# Main: Initialisiere die DB und starte den Server
# --------------------------
if __name__ == '__main__':
    init_db()
    # Flask (und Dash) laufen auf Port 5000; passe dies nach Bedarf an.
    app.run(host='0.0.0.0', port=5000)
