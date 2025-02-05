import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from database import get_latest_data, get_historical_data

def init_dash_app(flask_app):
    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname='/dashboard/',
        suppress_callback_exceptions=True
    )
    
    dash_app.layout = html.Div([
        html.H1("Miner Dashboard"),
        dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0),
        # Latest data table
        html.Div(id='live-update'),
        html.Br(),
        # Graphs showing stats over time
        dcc.Graph(id='temp-graph'),
        dcc.Graph(id='hashrate-graph'),
        dcc.Graph(id='fanrpm-graph'),
        html.Br(),
        html.A("Logout", href="/logout")
    ])

    # Callback for displaying the latest received data in a table
    @dash_app.callback(Output('live-update', 'children'),
                       [Input('interval-component', 'n_intervals')])
    def update_latest_data(n):
        data = get_latest_data()
        if not data:
            return html.Div("No data available.")
        # Create an HTML table of the latest data
        header = [html.Tr([html.Th("Field"), html.Th("Value")])]
        rows = [html.Tr([html.Td(key), html.Td(str(value))]) for key, value in data.items()]
        table = html.Table(header + rows, style={
            'width': '100%',
            'border': '1px solid #ddd',
            'border-collapse': 'collapse'
        })
        return table

    # Callback for updating the temperature graph
    @dash_app.callback(
        Output('temp-graph', 'figure'),
        [Input('interval-component', 'n_intervals')]
    )
    def update_temp_graph(n):
        data = get_historical_data()
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

    # Callback for updating the hash rate graph
    @dash_app.callback(
        Output('hashrate-graph', 'figure'),
        [Input('interval-component', 'n_intervals')]
    )
    def update_hashrate_graph(n):
        data = get_historical_data()
        if not data:
            return {"data": []}
        timestamps = [record['timestamp'] for record in data]
        hashrates = [record['hashRate'] for record in data]
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
                "yaxis": {"title": "Hash Rate"}
            }
        }
        return figure

    # Callback for updating the fan RPM graph
    @dash_app.callback(
        Output('fanrpm-graph', 'figure'),
        [Input('interval-component', 'n_intervals')]
    )
    def update_fanrpm_graph(n):
        data = get_historical_data()
        if not data:
            return {"data": []}
        timestamps = [record['timestamp'] for record in data]
        fanrpms = [record['fanrpm'] for record in data]
        figure = {
            "data": [{
                "x": timestamps,
                "y": fanrpms,
                "type": "line",
                "name": "Fan RPM"
            }],
            "layout": {
                "title": "Fan RPM over Time",
                "xaxis": {"title": "Time"},
                "yaxis": {"title": "Fan RPM"}
            }
        }
        return figure

    return dash_app
