import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Input, Output
from db.database import get_latest_data, get_historical_data, do_db_request
from datetime import datetime

def init_dash_app(flask_app):
    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname='/dashboard/',
        suppress_callback_exceptions=True,
        external_stylesheets=[dbc.themes.BOOTSTRAP]
    )
    
    # Hier wird die erste Zeile in zwei Spalten aufgeteilt: Titel und Performance Overview
    dash_app.layout = dbc.Container([
        dbc.Row([
            dbc.Col(html.H1("Miner Dashboard"), width=6),
                ], className="mt-4"),
        # Zeile zur Auswahl des Zeitrahmens
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Timeframe"),
                    dbc.CardBody(
                        [dcc.Dropdown(
                            id='timeframe-dropdown',
                            options=[
                                {'label': '1 hour', 'value': 1},
                                {'label': '6 hours', 'value': 6},
                                {'label': '12 hours', 'value': 12},
                                {'label': '24 hours', 'value': 24},
                                {'label': '3 days', 'value': 3*24},
                                {'label': '7 days', 'value': 7*24}
                            ],
                            value=6
                        ),
                        html.Div(id='average-overview', children="Calculating metrics...", className="mt-2")]
                    )
                ], className="mb-4"),
                width=4,
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Performance Overview"),
                    dbc.CardBody(html.Div(id='performance-overview', children="Calculating metrics..."))
                ], className="mb-4"),
                width=8
            ),
        ]),
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Latest Data"),
                    dbc.CardBody(html.Div(id='live-update', children="Loading data..."))
                ], className="mb-4"),
                width=4
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Temperature over Time"),
                    dbc.CardBody(dcc.Graph(id='temp-graph'))
                ], className="mb-4"),
                width=8
            )
        ]),
        dbc.Row(
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Hash Rate over Time"),
                    dbc.CardBody(dcc.Graph(id='hashrate-graph'))
                ], className="mb-4"),
                width=12
            )
        ),
        dbc.Row(
            dbc.Col(
                html.Div(html.A("Logout", href="/logout", className="btn btn-secondary")),
                className="text-center mb-4"
            )
        ),
        dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0)
    ], fluid=True)

    # Callback für die Anzeige der durchschnittlichen Werte
    @dash_app.callback(
        Output('average-overview', 'children'),
        [Input('interval-component', 'n_intervals'),
            Input('timeframe-dropdown', 'value')]
    )
    def update_average_overview(n, timeframe):
        data_array = get_historical_data(timeframe * 60)
        if not data_array:
            return "No data available."
        if 'hashRate' not in data_array[0]:
            return "Required data not available."
        
        hash_rate_array = []
        for data in data_array:
            hash_rate_raw = data['hashRate']
            # Umrechnung in THashes pro Sekunde (1 GH/s = 1e9)
            hash = hash_rate_raw / 1000
            hash_rate_array.append(hash)
        
        # Berechnung des Durchschnitts der Hashrate
        H = sum(hash_rate_array) / len(hash_rate_array)
        return f"Average Hash Rate: {H:.2f} TH/s"


    @dash_app.callback(
    Output('performance-overview', 'children'),
    [Input('interval-component', 'n_intervals'),
        Input('timeframe-dropdown', 'value')]
    )
    def update_performance_overview(n, timeframe):
        data_array = get_historical_data(timeframe * 60)
        if not data_array:
            return "No data available."
        if 'bestSessionDiff' not in data_array[0] or 'hashRate' not in data_array[0]:
            return "Required data not available."
                

        best_session_diff = data_array[-1]['bestSessionDiff']
        # convert to integer (80.8M -> 80800000)
        if best_session_diff[-1] == 'M':
            best_session_diff = float(best_session_diff[:-1]) * 1000000
        elif best_session_diff[-1] == 'G':
            best_session_diff = float(best_session_diff[:-1]) * 1000000000
        elif best_session_diff[-1] == 'T':
            best_session_diff = float(best_session_diff[:-1]) * 1000000000000
        else:
            best_session_diff = -1

        # Get the first record from the database where the bestSessionDiff is equal to the bestSessionDiff of the latest record
        query = f"SELECT * FROM miner_data WHERE bestSessionDiff = '{data_array[-1]['bestSessionDiff']}' ORDER BY id ASC LIMIT 1"
        first_diff_record = do_db_request(query)
        # Get the timestamp of the first record
        time_first_record = first_diff_record[0][42]

        # calculate the time difference between the first and the latest record
        time_last_record = data_array[-1]['timestamp']
        time_last_record_datetime = datetime.strptime(time_last_record, '%Y-%m-%d %H:%M:%S')
        time_first_record_datetime = datetime.strptime(time_first_record, '%Y-%m-%d %H:%M:%S')

        time_diff = time_last_record_datetime - time_first_record_datetime
        time_diff_seconds = time_diff.total_seconds()

        hash_rate_array = []
        for data in data_array:
            hash_rate_raw = data['hashRate']
            # Umrechnung in Hashes pro Sekunde (1 GH/s = 1e9)
            hash = hash_rate_raw * 1e9
            hash_rate_array.append(hash)

        # Berechnung des Durchschnitts der Hashrate
        H = sum(hash_rate_array) / len(hash_rate_array)
        constant = 4294967296  # 2**32

        if best_session_diff <= 0:
            return "Invalid best session difficulty."
        
        # Berechnung der Chance pro Hash
        chance_per_hash = 1 / (best_session_diff * constant)
        # Berechnung der Wahrscheinlichkeit pro Sekunde
        chance_per_second = H / (best_session_diff * constant)
        # Erwartete Zeit in Sekunden, bis ein neuer Durchbruch erreicht wird
        expected_time_seconds = 1 / chance_per_second if chance_per_second > 0 else float('inf')
        
        chance_per_day = 86400 * chance_per_second
        chance_per_month = 30 * chance_per_day
        chance_per_year = 365 * chance_per_day
        # convert it to percentage
        chance_per_day_str = f"{chance_per_day:.2%}"
        chance_per_month_str = f"{chance_per_month:.2%}"
        chance_per_year_str = f"{chance_per_year:.2%}"

        def calculate_time_str(expected_time_seconds):
            if expected_time_seconds < 60:
                return f"{expected_time_seconds:.2f} Sekunden"
            elif expected_time_seconds < 3600:
                return f"{expected_time_seconds/60:.2f} Minuten"
            elif expected_time_seconds < 86400:
                return f"{expected_time_seconds/3600:.2f} Stunden"
            else:
                return f"{expected_time_seconds/86400:.2f} Tage"

        time_str_all = calculate_time_str(expected_time_seconds)
        time_str_difference = calculate_time_str(time_diff_seconds)
        
        return html.Div([
            html.P(f"Chance für neue bestSessionDiff: {chance_per_day_str} pro Tag | {chance_per_month_str} pro Monat | {chance_per_year_str} pro Jahr"),
            html.P(f"Erwartete Zeit, um bestSessionDiff zu überschreiten: {time_str_all}"),
            html.P(f"Zeit seit dem letzten Durchbruch: {time_str_difference}")
        ])


    # Callback fuer die Anzeige der aktuellen Daten in einer Tabelle
    @dash_app.callback(Output('live-update', 'children'),
                       [Input('interval-component', 'n_intervals')])
    def update_latest_data(n):
        data = get_latest_data()
        if not data:
            return html.Div("No data available.")
        
        # Berechne die Hashrate in TH/s
        hashrate = data['hashRate'] / 1000
        hashrate = round(hashrate, 2)
        data['hashRate'] = f"{hashrate} TH/s"

        # Berechne die Power in W
        power = data['power']
        power = round(power, 2)
        data['power'] = f"{power} W"

        # Berechne die Temperatur in °C
        temp = data['temp']
        temp = round(temp, 2)
        data['temp'] = f"{temp} °C"

        # Berechne die VR Temperatur in °C
        vrTemp = data['vrTemp']
        vrTemp = round(vrTemp, 2)
        data['vrTemp'] = f"{vrTemp} °C"

        # Konvertiere uptimeSeconds in Tage, Stunden und Minuten
        uptime = data['uptimeSeconds']
        days = uptime // (24 * 3600)
        uptime = uptime % (24 * 3600)
        hours = uptime // 3600
        uptime %= 3600
        minutes = uptime // 60
        data['uptime'] = f"{days} days, {hours} hours, {minutes} minutes"

        # Berechne die Rejection Rate
        if data['sharesRejected'] and data['sharesAccepted']:
            reject_rate = data['sharesRejected'] / (data['sharesRejected'] + data['sharesAccepted'])
            reject_rate = round(reject_rate, 4)
            data['rejectionRate'] = f"{reject_rate:.2%}"
        
        # Zeige nur die folgenden Felder in der Tabelle an
        fields = ['id', 'power', 'temp', 'vrTemp', 'hashRate', 'bestDiff', 'bestSessionDiff', 'sharesAccepted', 'sharesRejected', 'rejectionRate', 'uptime', 'timestamp']
        data = {key: data[key] for key in fields}

        table_header = html.Thead(
            html.Tr([html.Th("Field"), html.Th("Value")])
        )
        table_body = html.Tbody([
            html.Tr([html.Td(key), html.Td(str(value))]) for key, value in data.items()
        ])
        table = dbc.Table(
            [table_header, table_body],
            bordered=True,
            hover=True,
            responsive=True,
            striped=True,
            className="mb-0"
        )
        return table

    # Callback zum Aktualisieren des Temperatur-Diagramms
    @dash_app.callback(
        Output('temp-graph', 'figure'),
        [Input('interval-component', 'n_intervals'),
         Input('timeframe-dropdown', 'value')]
    )
    def update_temp_graph(n, timeframe):
        timeframe_minutes = timeframe * 60  # Stunden in Minuten umrechnen
        data = get_historical_data(timeframe_minutes)
        if not data:
            return {"data": []}
        timestamps = [record['timestamp'] for record in data]
        temps = [record['temp'] for record in data]
        figure = {
            "data": [{
                "x": timestamps,
                "y": temps,
                "type": "line",
                "name": "Temperature"
            }],
            "layout": {
                "title": "Temperature over Time",
                "xaxis": {"title": "Time"},
                "yaxis": {"title": "Temperature (°C)"}
            }
        }
        return figure

    # Callback zum Aktualisieren des Hash Rate Diagramms
    @dash_app.callback(
        Output('hashrate-graph', 'figure'),
        [Input('interval-component', 'n_intervals'),
         Input('timeframe-dropdown', 'value')]
    )
    def update_hashrate_graph(n, timeframe):
        timeframe_minutes = timeframe * 60  # Stunden in Minuten umrechnen
        data = get_historical_data(timeframe_minutes)
        if not data:
            return {"data": []}
        timestamps = [record['timestamp'] for record in data]
        hashrates = [record['hashRate'] for record in data]
        # Umrechnung in TH/s
        hashrates = [rate / 1000 for rate in hashrates]
        figure = {
            "data": [{
                "x": timestamps,
                "y": hashrates,
                "type": "line",
                "name": "Hash Rate"
            }],
            "layout": {
                "title": "Hash Rate over Time",
                "xaxis": {"title": "Time"},
                "yaxis": {"title": "Hash Rate (TH/s)"}
            }
        }
        return figure

    return dash_app
