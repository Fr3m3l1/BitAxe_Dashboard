import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Input, Output, State
from db.database import get_latest_data, get_historical_data, do_db_request
from datetime import datetime, timedelta

# Globale Variable zur Speicherung der letzten Daten-ID
LAST_DATA_SAVE = None

def init_dash_app(flask_app):
    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname='/dashboard/',
        suppress_callback_exceptions=True,
        external_stylesheets=[dbc.themes.BOOTSTRAP]
    )
    
    dash_app.layout = dbc.Container([
        dbc.Row([
            dbc.Col(html.H1("Miner Dashboard"), width=6),
            dbc.Col(
                html.Div([
                    html.Div(id='refresh-countdown'),
                    html.Div(id='data-countdown')
                ], className="text-right")
            ),
        ], className="mt-4"),
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader("Timeframe"),
                    dbc.CardBody([
                        dcc.Dropdown(
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
                        html.Div(id='average-overview', children="Calculating metrics...", className="mt-2")
                    ])
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
        dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0),
        dcc.Interval(id='countdown-interval', interval=1*1000, n_intervals=0),
        dcc.Store(id='last-refresh-time'),
        dcc.Store(id='last-data-recieved-time')
    ], fluid=True)

    # Callback zur Speicherung der letzten Refresh-Zeit
    @dash_app.callback(
        Output('last-refresh-time', 'data'),
        [Input('interval-component', 'n_intervals')],
    )
    def update_last_refresh_time(n):
        return datetime.now().timestamp()
    
    # Callback zur Speicherung der letzten empfangenen Datenzeit
    @dash_app.callback(
        Output('last-data-recieved-time', 'data'),
        [Input('interval-component', 'n_intervals')],
        [State('last-data-recieved-time', 'data')]
    )
    def update_last_data_recieved_time(n, stored_time):
        global LAST_DATA_SAVE
        current_time = datetime.now()
        last_data = get_latest_data()
        last_data_id = last_data.get('id', None)
        
        if last_data_id is None:
            return stored_time if stored_time is not None else current_time.timestamp()
        
        if LAST_DATA_SAVE is None or last_data_id != LAST_DATA_SAVE:
            LAST_DATA_SAVE = last_data_id
            return current_time.timestamp()
        
        return stored_time if stored_time is not None else current_time.timestamp()

    # Callback zum Aktualisieren der Countdowns
    @dash_app.callback(
        [Output('refresh-countdown', 'children'),
         Output('data-countdown', 'children')],
        [Input('countdown-interval', 'n_intervals'),
         Input('last-refresh-time', 'data'),
         Input('last-data-recieved-time', 'data')]
    )
    def update_countdowns(n, last_refresh_time, last_data_recieved_time):
        current_time = datetime.now()
            
        # Page refresh countdown
        page_countdown = "Next page refresh in: --:--"
        if last_refresh_time is None:
            last_refresh_time = current_time.timestamp()

        last_refresh = datetime.fromtimestamp(last_refresh_time)
        elapsed = (current_time - last_refresh).total_seconds()
        remaining_page = max(60 - elapsed, 0)
        minutes = int(remaining_page // 60)
        seconds = int(remaining_page % 60)
        page_countdown = f"Next page refresh in: {minutes:02}:{seconds:02}"
    
        # Data refresh countdown: Falls kein Zeitstempel vorliegt, verwende current_time
        if last_data_recieved_time is None:
            last_data_dt = current_time
        else:
            last_data_dt = datetime.fromtimestamp(last_data_recieved_time)
        
        # Calculate next expected data time based on 5-minute intervals
        interval_seconds = 5 * 60
        delta = current_time - last_data_dt
        intervals_passed = int(delta.total_seconds() // interval_seconds)
        next_data_time = last_data_dt + timedelta(seconds=interval_seconds * (intervals_passed + 1))
        remaining_data = (next_data_time - current_time).total_seconds()
        
        data_minutes = int(remaining_data // 60)
        data_seconds = int(remaining_data % 60)
        data_countdown = f"Next expected data in: {data_minutes:02}:{data_seconds:02}"
        
        return page_countdown, data_countdown

    # Callback zur Anzeige der durchschnittlichen Werte
    @dash_app.callback(
        Output('average-overview', 'children'),
        [Input('interval-component', 'n_intervals'),
         Input('timeframe-dropdown', 'value')]
    )
    def update_average_overview(n, timeframe):
        if timeframe is None:
            timeframe = 60
        data_array = get_historical_data(timeframe * 60)
        if not data_array:
            return "No data available."
        if 'hashRate' not in data_array[0]:
            return "Required data not available."
        
        hash_rate_array = []
        for data in data_array:
            hash_rate_raw = data['hashRate']
            # Umrechnung in THashes pro Sekunde (1 GH/s = 1e9)
            hash_value = hash_rate_raw / 1000
            hash_rate_array.append(hash_value)
        
        H = sum(hash_rate_array) / len(hash_rate_array)
        return f"Average Hash Rate: {H:.2f} TH/s"

    # Callback zur Anzeige der Performance-Übersicht
    @dash_app.callback(
        Output('performance-overview', 'children'),
        [Input('interval-component', 'n_intervals'),
         Input('timeframe-dropdown', 'value')]
    )
    def update_performance_overview(n, timeframe):
        if timeframe is None:
            timeframe = 60
        data_array = get_historical_data(timeframe * 60)
        if not data_array:
            return "No data available."
        if 'bestSessionDiff' not in data_array[0] or 'hashRate' not in data_array[0]:
            return "Required data not available."
        
        best_session_diff = data_array[-1]['bestSessionDiff']
        # Umrechnung in Integer (z. B. "80.8M" -> 80800000)
        if best_session_diff[-1] == 'M':
            best_session_diff = float(best_session_diff[:-1]) * 1000000
        elif best_session_diff[-1] == 'G':
            best_session_diff = float(best_session_diff[:-1]) * 1000000000
        elif best_session_diff[-1] == 'T':
            best_session_diff = float(best_session_diff[:-1]) * 1000000000000
        else:
            best_session_diff = -1

        query = f"SELECT * FROM miner_data WHERE bestSessionDiff = '{data_array[-1]['bestSessionDiff']}' ORDER BY id ASC LIMIT 1"
        first_diff_record = do_db_request(query)
        # Pruefe, ob ein entsprechender Datensatz gefunden wurde
        if not first_diff_record:
            return "No record found for bestSessionDiff."
        time_first_record = first_diff_record[0][42]

        time_last_record = data_array[-1]['timestamp']
        time_last_record_datetime = datetime.strptime(time_last_record, '%Y-%m-%d %H:%M:%S')
        time_first_record_datetime = datetime.strptime(time_first_record, '%Y-%m-%d %H:%M:%S')
        time_diff = time_last_record_datetime - time_first_record_datetime
        time_diff_seconds = time_diff.total_seconds()

        hash_rate_array = []
        for data in data_array:
            hash_rate_raw = data['hashRate']
            # Umrechnung in Hashes pro Sekunde (1 GH/s = 1e9)
            hash_value = hash_rate_raw * 1e9
            hash_rate_array.append(hash_value)

        H = sum(hash_rate_array) / len(hash_rate_array)
        constant = 4294967296  # 2**32

        if best_session_diff <= 0:
            return "Invalid best session difficulty."
        
        chance_per_hash = 1 / (best_session_diff * constant)
        chance_per_second = H / (best_session_diff * constant)
        expected_time_seconds = 1 / chance_per_second if chance_per_second > 0 else float('inf')
        
        chance_per_day = 86400 * chance_per_second
        chance_per_month = 30 * chance_per_day
        chance_per_year = 365 * chance_per_day
        
        if chance_per_day > 0.99999:
            chance_per_day = 0.9999
        if chance_per_month > 1:
            chance_per_month = 0.9999
        if chance_per_year > 1:
            chance_per_year = 0.9999

        chance_per_day_str = f"{chance_per_day:.2%}"
        chance_per_month_str = f"{chance_per_month:.2%}"
        chance_per_year_str = f"{chance_per_year:.2%}"

        def calculate_time_str(seconds):
            if seconds < 60:
                return f"{seconds:.2f} Sekunden"
            elif seconds < 3600:
                return f"{seconds/60:.2f} Minuten"
            elif seconds < 86400:
                return f"{seconds/3600:.2f} Stunden"
            elif seconds < 2592000:
                return f"{seconds/86400:.2f} Tage"
            elif seconds < 31536000:
                return f"{seconds/2592000:.2f} Monate"
            else:
                return f"{seconds/31536000:.2f} Jahre"
            

        time_str_all = calculate_time_str(expected_time_seconds)
        time_str_past = calculate_time_str(time_diff_seconds)
        if time_diff_seconds < expected_time_seconds:
            time_str_difference = calculate_time_str(expected_time_seconds - time_diff_seconds)
            future = "in"
        else:
            time_str_difference = calculate_time_str(time_diff_seconds - expected_time_seconds)
            future = "vor"
        
        return html.Div([
            html.P(f"Chance für neue bestSessionDiff: {chance_per_day_str} pro Tag | {chance_per_month_str} pro Monat | {chance_per_year_str} pro Jahr"),
            html.P(f"Erwartete Zeit, um bestSessionDiff zu überschreiten: {time_str_all} ({future}: {time_str_difference})"),
            html.P(f"Zeit seit dem letzten Durchbruch: {time_str_past}")
        ])

    # Callback zur Anzeige der aktuellen Daten in einer Tabelle
    @dash_app.callback(
        Output('live-update', 'children'),
        [Input('interval-component', 'n_intervals')]
    )
    def update_latest_data(n):
        data = get_latest_data()
        if not data:
            return html.Div("No data available.")
        
        # Berechnung und Formatierung der Werte
        hashrate = data['hashRate'] / 1000
        hashrate = round(hashrate, 2)
        data['hashRate'] = f"{hashrate} TH/s"

        power = data['power']
        power = round(power, 2)
        data['power'] = f"{power} W"

        temp = data['temp']
        temp = round(temp, 2)
        data['temp'] = f"{temp} °C"

        vrTemp = data['vrTemp']
        vrTemp = round(vrTemp, 2)
        data['vrTemp'] = f"{vrTemp} °C"

        uptime = data['uptimeSeconds']
        days = uptime // (24 * 3600)
        uptime = uptime % (24 * 3600)
        hours = uptime // 3600
        uptime %= 3600
        minutes = uptime // 60
        data['uptime'] = f"{days} days, {hours} hours, {minutes} minutes"

        if data['sharesRejected'] and data['sharesAccepted']:
            reject_rate = data['sharesRejected'] / (data['sharesRejected'] + data['sharesAccepted'])
            reject_rate = round(reject_rate, 4)
            data['rejectionRate'] = f"{reject_rate:.2%}"
        
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
        if timeframe is None:
            timeframe = 60
        data = get_historical_data(timeframe * 60)
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
        if timeframe is None:
            timeframe = 60
        data = get_historical_data(timeframe * 60)
        if not data:
            return {"data": []}
        timestamps = [record['timestamp'] for record in data]
        hashrates = [record['hashRate'] for record in data]
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
