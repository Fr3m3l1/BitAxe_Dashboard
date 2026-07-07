"""
Enhanced Dash application with modern, responsive UI and improved functionality.
"""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback_context, no_update
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta, timezone
import logging

from ..models import MinerData, Settings, AlertLog

logger = logging.getLogger(__name__)

# Custom CSS for enhanced styling
CUSTOM_CSS = """
.dash-container {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 0;
}

.main-header {
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    position: sticky;
    top: 0;
    z-index: 1000;
}

.stat-card {
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 15px;
    transition: all 0.3s ease;
}

.stat-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
}

.stat-value {
    font-size: 2.5rem;
    font-weight: 700;
    color: #fff;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.stat-label {
    font-size: 0.9rem;
    color: rgba(255, 255, 255, 0.8);
    text-transform: uppercase;
    letter-spacing: 1px;
}

.alert-badge {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}

.chart-container {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 15px;
    padding: 20px;
    margin-bottom: 20px;
}
"""

def init_dash_app(flask_app):
    """Initialize the enhanced Dash application."""
    
    dash_app = dash.Dash(
        __name__,
        server=flask_app,
        url_base_pathname='/dashboard/',
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            dbc.icons.FONT_AWESOME,
            'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
        ],
        suppress_callback_exceptions=True,
        meta_tags=[
            {"name": "viewport", "content": "width=device-width, initial-scale=1"}
        ]
    )
    
    # Layout
    dash_app.layout = dbc.Container([
        # Custom CSS
        html.Style(CUSTOM_CSS),
        
        # Header
        create_header(),
        
        # Main content
        dbc.Row([
            # Left sidebar with controls
            dbc.Col([
                create_controls_panel(),
                create_alerts_panel()
            ], width=12, lg=3, className="mb-4"),
            
            # Main dashboard area
            dbc.Col([
                create_stats_cards(),
                create_charts_area(),
                create_detailed_info()
            ], width=12, lg=9)
        ], className="mt-4"),
        
        # Update intervals
        dcc.Interval(id='main-interval', interval=30*1000, n_intervals=0),
        dcc.Interval(id='fast-interval', interval=5*1000, n_intervals=0),
        
        # Data stores
        dcc.Store(id='data-store'),
        dcc.Store(id='settings-store'),
        dcc.Store(id='alerts-store')
        
    ], fluid=True, className="dash-container")
    
    # Register callbacks
    register_callbacks(dash_app)
    
    return dash_app

def create_header():
    """Create the main header component."""
    return dbc.Row([
        dbc.Col([
            html.Div([
                html.H1([
                    html.I(className="fas fa-microchip me-3"),
                    "BitAxe Dashboard"
                ], className="h3 mb-0 text-white"),
                html.P("Real-time mining monitoring & analytics", 
                       className="mb-0 text-white-50 small")
            ])
        ], width="auto"),
        
        dbc.Col([
            html.Div([
                html.Div(id="connection-status", className="me-3"),
                html.Div(id="last-update", className="text-white-50 small"),
                dbc.Button([
                    html.I(className="fas fa-sign-out-alt me-2"),
                    "Logout"
                ], href="/logout", color="outline-light", size="sm", className="ms-3")
            ], className="d-flex align-items-center justify-content-end")
        ], width=True)
    ], className="main-header p-3 align-items-center")

def create_controls_panel():
    """Create the controls panel."""
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-sliders-h me-2"),
            "Controls"
        ], className="d-flex align-items-center"),
        dbc.CardBody([
            # Time range selector
            html.Label("Time Range", className="form-label small fw-bold"),
            dcc.Dropdown(
                id='timeframe-dropdown',
                options=[
                    {'label': '1 Hour', 'value': 1},
                    {'label': '6 Hours', 'value': 6},
                    {'label': '12 Hours', 'value': 12},
                    {'label': '24 Hours', 'value': 24},
                    {'label': '3 Days', 'value': 72},
                    {'label': '7 Days', 'value': 168}
                ],
                value=6,
                className="mb-3"
            ),
            
            # Refresh controls
            html.Label("Auto Refresh", className="form-label small fw-bold"),
            dbc.Switch(
                id="auto-refresh-switch",
                label="Enable auto refresh",
                value=True,
                className="mb-3"
            ),
            
            # Chart type selector
            html.Label("Chart Style", className="form-label small fw-bold"),
            dbc.RadioItems(
                id="chart-style",
                options=[
                    {"label": "Lines", "value": "lines"},
                    {"label": "Lines + Markers", "value": "lines+markers"},
                    {"label": "Bars", "value": "bars"}
                ],
                value="lines",
                inline=True,
                className="mb-3"
            ),
            
            # Settings button
            dbc.Button([
                html.I(className="fas fa-cog me-2"),
                "Settings"
            ], id="open-settings", color="primary", size="sm", className="w-100")
        ])
    ], className="stat-card mb-4")

def create_alerts_panel():
    """Create the alerts panel."""
    return dbc.Card([
        dbc.CardHeader([
            html.I(className="fas fa-bell me-2"),
            "Recent Alerts",
            dbc.Badge("0", id="alert-count", color="danger", className="ms-auto")
        ], className="d-flex align-items-center"),
        dbc.CardBody([
            html.Div(id="alerts-list", children="No recent alerts")
        ], style={"max-height": "300px", "overflow-y": "auto"})
    ], className="stat-card")

def create_stats_cards():
    """Create the main statistics cards."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-tachometer-alt fa-2x text-primary mb-2"),
                        html.Div("0.00", id="hash-rate-value", className="stat-value"),
                        html.Div("Hash Rate (GH/s)", className="stat-label")
                    ], className="text-center")
                ])
            ], className="stat-card h-100")
        ], width=6, lg=3, className="mb-3"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-thermometer-half fa-2x text-warning mb-2"),
                        html.Div("0°C", id="temp-value", className="stat-value"),
                        html.Div("Temperature", className="stat-label")
                    ], className="text-center")
                ])
            ], className="stat-card h-100")
        ], width=6, lg=3, className="mb-3"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-bolt fa-2x text-success mb-2"),
                        html.Div("0W", id="power-value", className="stat-value"),
                        html.Div("Power", className="stat-label")
                    ], className="text-center")
                ])
            ], className="stat-card h-100")
        ], width=6, lg=3, className="mb-3"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-chart-line fa-2x text-info mb-2"),
                        html.Div("0 J/TH", id="efficiency-value", className="stat-value"),
                        html.Div("Efficiency", className="stat-label")
                    ], className="text-center")
                ])
            ], className="stat-card h-100")
        ], width=6, lg=3, className="mb-3")
    ])

def create_charts_area():
    """Create the main charts area."""
    return dbc.Row([
        dbc.Col([
            html.Div([
                html.H5([
                    html.I(className="fas fa-chart-area me-2"),
                    "Performance Metrics"
                ], className="text-white mb-3"),
                dcc.Graph(id="main-chart", style={"height": "400px"})
            ], className="chart-container")
        ], width=12, className="mb-4"),
        
        dbc.Col([
            html.Div([
                html.H5([
                    html.I(className="fas fa-thermometer-half me-2"),
                    "Temperature Monitoring"
                ], className="text-white mb-3"),
                dcc.Graph(id="temp-chart", style={"height": "300px"})
            ], className="chart-container")
        ], width=12, lg=6, className="mb-4"),
        
        dbc.Col([
            html.Div([
                html.H5([
                    html.I(className="fas fa-bolt me-2"),
                    "Power & Efficiency"
                ], className="text-white mb-3"),
                dcc.Graph(id="power-chart", style={"height": "300px"})
            ], className="chart-container")
        ], width=12, lg=6, className="mb-4")
    ])

def create_detailed_info():
    """Create detailed information panels."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-info-circle me-2"),
                    "System Information"
                ]),
                dbc.CardBody(id="system-info")
            ], className="stat-card")
        ], width=12, lg=6, className="mb-4"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-network-wired me-2"),
                    "Network Status"
                ]),
                dbc.CardBody(id="network-info")
            ], className="stat-card")
        ], width=12, lg=6, className="mb-4")
    ])

def register_callbacks(dash_app):
    """Register all Dash callbacks."""
    
    # Main data update callback
    @dash_app.callback(
        [Output('data-store', 'data'),
         Output('connection-status', 'children'),
         Output('last-update', 'children')],
        [Input('main-interval', 'n_intervals'),
         Input('fast-interval', 'n_intervals')],
        [State('auto-refresh-switch', 'value')]
    )
    def update_data_store(main_intervals, fast_intervals, auto_refresh):
        if not auto_refresh:
            return no_update, no_update, no_update
        
        try:
            # Get latest data
            latest = MinerData.query.order_by(MinerData.timestamp.desc()).first()
            
            if latest:
                # Check if data is recent (within 5 minutes)
                time_diff = datetime.now(timezone.utc) - latest.timestamp
                is_online = time_diff.total_seconds() < 300
                
                status_icon = html.I(
                    className=f"fas fa-circle text-{'success' if is_online else 'danger'} me-2"
                )
                status_text = "Online" if is_online else "Offline"
                
                return latest.to_dict(), [status_icon, status_text], f"Last update: {latest.timestamp.strftime('%H:%M:%S')}"
            else:
                return {}, [html.I(className="fas fa-circle text-danger me-2"), "No Data"], "No data available"
                
        except Exception as e:
            logger.error(f"Error updating data store: {str(e)}")
            return {}, [html.I(className="fas fa-circle text-danger me-2"), "Error"], "Update failed"
    
    # Stats cards update
    @dash_app.callback(
        [Output('hash-rate-value', 'children'),
         Output('temp-value', 'children'),
         Output('power-value', 'children'),
         Output('efficiency-value', 'children')],
        [Input('data-store', 'data')]
    )
    def update_stats_cards(data):
        if not data:
            return "0.00", "0°C", "0W", "0 J/TH"
        
        hash_rate = f"{data.get('hash_rate', 0):.2f}"
        temp = f"{data.get('temp', 0):.1f}°C"
        power = f"{data.get('power', 0):.1f}W"
        
        # Calculate efficiency
        efficiency = 0
        if data.get('power') and data.get('hash_rate'):
            efficiency = data['power'] / (data['hash_rate'] / 1000)
        
        efficiency_str = f"{efficiency:.1f} J/TH"
        
        return hash_rate, temp, power, efficiency_str
    
    # Main chart update
    @dash_app.callback(
        Output('main-chart', 'figure'),
        [Input('data-store', 'data'),
         Input('timeframe-dropdown', 'value'),
         Input('chart-style', 'value')]
    )
    def update_main_chart(current_data, timeframe, chart_style):
        try:
            # Get historical data
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=timeframe)
            data = MinerData.query.filter(MinerData.timestamp >= cutoff_time).order_by(MinerData.timestamp).all()
            
            if not data:
                return create_empty_chart("No data available")
            
            # Convert to DataFrame
            df = pd.DataFrame([d.to_dict() for d in data])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Create subplot
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=['Hash Rate (GH/s)', 'Shares (Accepted/Rejected)'],
                vertical_spacing=0.1
            )
            
            # Hash rate trace
            mode = chart_style if chart_style != 'bars' else 'lines+markers'
            fig.add_trace(
                go.Scatter(
                    x=df['timestamp'],
                    y=df['hash_rate'],
                    mode=mode,
                    name='Hash Rate',
                    line=dict(color='#00d4ff', width=3),
                    marker=dict(size=6)
                ),
                row=1, col=1
            )
            
            # Shares traces
            fig.add_trace(
                go.Bar(
                    x=df['timestamp'],
                    y=df['shares_accepted'],
                    name='Accepted',
                    marker_color='#28a745'
                ),
                row=2, col=1
            )
            
            fig.add_trace(
                go.Bar(
                    x=df['timestamp'],
                    y=df['shares_rejected'],
                    name='Rejected',
                    marker_color='#dc3545'
                ),
                row=2, col=1
            )
            
            # Update layout
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                showlegend=True,
                height=400,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error updating main chart: {str(e)}")
            return create_empty_chart("Error loading chart")
    
    # System info update
    @dash_app.callback(
        Output('system-info', 'children'),
        [Input('data-store', 'data')]
    )
    def update_system_info(data):
        if not data:
            return "No system information available"
        
        return dbc.ListGroup([
            dbc.ListGroupItem([
                html.Strong("Hostname: "),
                data.get('hostname', 'Unknown')
            ]),
            dbc.ListGroupItem([
                html.Strong("ASIC Model: "),
                data.get('asic_model', 'Unknown')
            ]),
            dbc.ListGroupItem([
                html.Strong("Frequency: "),
                f"{data.get('frequency', 0):.0f} MHz"
            ]),
            dbc.ListGroupItem([
                html.Strong("Uptime: "),
                f"{(data.get('uptime_seconds', 0) / 3600):.1f} hours"
            ]),
            dbc.ListGroupItem([
                html.Strong("Version: "),
                data.get('version', 'Unknown')
            ])
        ], flush=True)

def create_empty_chart(message):
    """Create an empty chart with a message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16, color="white")
    )
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, showticklabels=False)
    )
    return fig
