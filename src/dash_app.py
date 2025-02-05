import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Input, Output
from database import get_latest_data, get_historical_data

def init_dash_app(flask_app):
    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname='/dashboard/',
        suppress_callback_exceptions=True,
        external_stylesheets=[dbc.themes.BOOTSTRAP]
    )
    
    dash_app.layout = dbc.Container([
        dbc.Row(
            dbc.Col(html.H1("Miner Dashboard"), width=12),
            className="mt-4"
        ),
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

    # Callback for displaying the latest received data in a table
    @dash_app.callback(Output('live-update', 'children'),
                       [Input('interval-component', 'n_intervals')])
    def update_latest_data(n):
        data = get_latest_data()
        if not data:
            return html.Div("No data available.")
        
        # only show the following fields in the table
        fields = ['id', 'power', 'temp','vrTemp', 'hashRate', 'bestDiff', 'bestSessionDiff', 'sharesAccepted', 'sharesRejected', 'uptimeSeconds', 'timestamp']
        data = {key: value for key, value in data.items() if key in fields}

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

    return dash_app
