import pandas as pd
import os
import time
from datetime import datetime
from tradingview_screener import Query  # ✅ For live LTP fetch
import dash
from dash import Dash, dash_table, html

from datetime import datetime
import plotly.graph_objects as go

# === 🧠 Global DataFrame to track progressive MTM changes ===
df_history = pd.DataFrame(columns=['Time', 'MTM', 'Diff_MTM', 'MTM %', 'Diff_MTM %'])

# === CONFIG ===
google_csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQyY0N1hFIGML56I49kSRPWd7loDPQsa284rBn6o902zphvLQmtda5Rh76dCEm-3SjL3at9F2SVSltE/pub?gid=0&single=true&output=csv"
base_dir = r"C:\Users\freedom\Desktop\ORDER B005\backup\GETS_FILES\GETS_EXCEL"
file_name = "NetPositionAutoBackup.xls"
refresh_interval = 5  # seconds


# === 🧩 Function: Load Both Files ===
def load_data(load_google=False):
    today_folder = datetime.now().strftime("%d%b")
    folder_path = os.path.join(base_dir, today_folder)
    file_path = os.path.join(folder_path, file_name)

    # === Local file ===
    try:
        df_local = pd.read_csv(file_path, sep="\t", engine="python")
        df_local.columns = df_local.columns.str.strip().str.replace(" ", "_")
        print(f"✅ Local file loaded: {len(df_local)} rows")

        df_local.dropna(subset=["User", "Symbol"], inplace=True)
        for col in ["BuyQty", "BuyVal", "SellQty", "SellVal", "NetQty", "NetVal", "NetPrice"]:
            if col in df_local.columns:
                df_local[col] = pd.to_numeric(df_local[col], errors="coerce").fillna(0)

        df_local = (
            df_local.groupby(["User", "Symbol"], as_index=False)
            .agg({
                "Exchange": "first", "Ser_Exp": "first",
                "BuyQty": "sum", "BuyVal": "sum",
                "SellQty": "sum", "SellVal": "sum",
                "NetQty": "sum", "NetVal": "sum"
            })
        )
        df_local["NetPrice"] = df_local["NetVal"] / df_local["NetQty"].replace(0, pd.NA)
        df_local["CumStrategy"] = df_local["NetVal"].apply(
            lambda x: "Circuit" if abs(x) > 425000 else "Chart"
        )
        df_local = df_local[df_local["NetQty"] != 0].reset_index(drop=True)

    except Exception as e:
        print(f"❌ Error reading local file: {e}")
        df_local = pd.DataFrame()

    # === Google Sheet ===
    if load_google:
        try:
            df_google = pd.read_csv(google_csv_url, header=0, skiprows=range(1, 6))
            df_google.columns = df_google.columns.str.strip().str.replace(" ", "_")
            print(f"✅ Google Sheet loaded: {len(df_google)} rows")

            df_google.dropna(subset=["User", "Symbol"], inplace=True)
            for col in ["BuyQty", "BuyVal", "SellQty", "SellVal", "NetQty", "NetVal", "NetPrice", "Nse_close"]:
                if col in df_google.columns:
                    df_google[col] = pd.to_numeric(df_google[col], errors="coerce").fillna(0)

            df_google = (
                df_google.groupby(["User", "Symbol"], as_index=False)
                .agg({
                    "Date": "first", "Exchange": "first", "Ser_Exp": "first",
                    "BuyQty": "sum", "BuyVal": "sum",
                    "SellQty": "sum", "SellVal": "sum",
                    "NetQty": "sum", "NetVal": "sum",
                    "Nse_close": "first"
                })
            )
            df_google["NetPrice"] = df_google["NetVal"] / df_google["NetQty"].replace(0, pd.NA)
            df_google["CumStrategy"] = df_google["NetVal"].apply(
                lambda x: "Circuit" if abs(x) > 425000 else "Chart"
            )
            df_google = df_google[df_google["NetQty"] != 0].reset_index(drop=True)

        except Exception as e:
            print(f"❌ Error reading Google Sheet: {e}")
            df_google = pd.DataFrame()
    else:
        df_google = pd.DataFrame()

    return df_local, df_google


# === 🧩 Merge Local + Google ===
def merge_local_google(df_local, df_google):
    if df_google.empty:
        return df_local
    if df_local.empty:
        return df_google

    merged_df = pd.concat([df_local, df_google], ignore_index=True)
    merged_df = merged_df.sort_values(["User", "Symbol"]).reset_index(drop=True)

    merged_df = (
        merged_df.groupby(["User", "Symbol"], as_index=False)
        .agg({
            "Exchange": "first", "Ser_Exp": "first",
            "BuyQty": "sum", "BuyVal": "sum",
            "SellQty": "sum", "SellVal": "sum",
            "NetQty": "sum", "NetVal": "sum",
            "CumStrategy": "first"
        })
    )

    merged_df["NetPrice"] = merged_df["NetVal"] / merged_df["NetQty"].replace(0, pd.NA)
    merged_df = merged_df[merged_df["NetQty"] != 0].reset_index(drop=True)

    return merged_df


# === ⚡ Fetch LTP ===
def fetch_ltp(symbols_needed):
    try:
        n_rows, tv_data = (
            Query()
            .select("name", "exchange", "close")
            .set_markets("india")
            .limit(9000)
            .get_scanner_data()
        )

        tv_data = (
            tv_data.rename(columns={"name": "Symbol", "close": "LTP"})
            .round(2)
            .fillna(0)
            .drop_duplicates(subset=["Symbol"], keep="first")
        )
        return tv_data[tv_data["Symbol"].isin(symbols_needed)][["Symbol", "LTP"]]

    except Exception as e:
        print(f"⚠️ LTP fetch failed: {e}")
        return pd.DataFrame(columns=["Symbol", "LTP"])


# === 🚀 MAIN LOOP ===
# === 🚀 DASH + LIVE TABLE ===
from dash import Dash, dash_table, html, dcc
from dash.dependencies import Input, Output
import threading

app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Live MTM Dashboard"

# Store dataframe globally
df_final = pd.DataFrame()

# === 🔁 Function to refresh df_final every few seconds ===
def update_data_loop():
    global df_final
    _, df_google = load_data(load_google=True)

    while True:
        try:
            df_local, _ = load_data(load_google=False)
            df_merged = merge_local_google(df_local, df_google)

            # --- Fetch LTP
            symbols = df_merged["Symbol"].dropna().unique().tolist()
            if symbols:
                df_ltp = fetch_ltp(symbols)
                df_merged = df_merged.merge(df_ltp, on="Symbol", how="left")
            else:
                df_merged["LTP"] = 0

            # --- Merge with Google Close
            df_merged = df_merged.merge(
                df_google[["Symbol", "Nse_close", "NetQty", "NetVal"]],
                on="Symbol",
                how="left",
                suffixes=("", "_google")
            )

            df_merged["Close"] = df_merged["Nse_close"].fillna(0)

            # --- MTM calculations
            df_merged["MTM"] = (df_merged["LTP"] - df_merged["NetPrice"]) * df_merged["NetQty"]
            df_merged["MTM %"] = (df_merged["MTM"] / df_merged["NetVal"].replace(0, pd.NA)) * 100
            df_merged["Diff_MTM"] = (df_merged["LTP"] - df_merged["Close"]) * df_merged["NetQty_google"].fillna(0)
            df_merged["Diff_MTM %"] = (df_merged["Diff_MTM"] / df_merged["NetVal_google"].replace(0, pd.NA)) * 100

            final_cols = [
                "Exchange", "User", "CumStrategy", "Symbol", "Ser_Exp",
                "NetQty", "NetVal", "NetPrice",
                "Close", "LTP", "MTM", "MTM %", "Diff_MTM", "Diff_MTM %"
            ]
            df_final_temp = df_merged.reindex(columns=final_cols)

            # Round
            numeric_cols = df_final_temp.select_dtypes(include='number').columns
            df_final_temp[numeric_cols] = df_final_temp[numeric_cols].round(2)

            # Totals
            sum_netqty = df_final_temp['NetQty'].sum()
            sum_netval = df_final_temp['NetVal'].sum()
            sum_mtm = df_final_temp['MTM'].sum()
            sum_diff_mtm = df_final_temp['Diff_MTM'].sum()
            mtm_percent = (sum_mtm / sum_netval) * 100 if sum_netval != 0 else 0
            diff_mtm_percent = (sum_diff_mtm / sum_netval) * 100 if sum_netval != 0 else 0

            total_row = {
                "Exchange": "",
                "User": "TOTAL",
                "CumStrategy": "",
                "Symbol": "",
                "Ser_Exp": "",
                "NetQty": sum_netqty,
                "NetVal": sum_netval,
                "NetPrice": "",
                "Close": "",
                "LTP": "",
                "MTM": sum_mtm,
                "MTM %": mtm_percent,
                "Diff_MTM": sum_diff_mtm,
                "Diff_MTM %": diff_mtm_percent
            }
            df_final_temp = pd.concat([df_final_temp, pd.DataFrame([total_row])], ignore_index=True)

            # ✅ Force convert + round these columns
            for col in ["NetPrice", "MTM", "MTM %"]:
                if col in df_final_temp.columns:
                    df_final_temp[col] = pd.to_numeric(df_final_temp[col], errors='coerce').round(2)

            df_final = df_final_temp  # update global
            # After appending total_row and rounding etc.
            df_final = df_final_temp  # update global (contains TOTAL row for display)

            # === 🕒 Record progressive MTM data for charts (USE precomputed sums to avoid double-count)
            global df_history

            now = datetime.now()
            market_open = now.replace(hour=9, minute=15, second=30, microsecond=0)
            market_close = now.replace(hour=15, minute=29, second=30, microsecond=0)

            # use the sums we computed earlier (sum_netval, sum_mtm, sum_diff_mtm)
            if market_open <= now <= market_close:
                total_netval = sum_netval
                total_mtm = sum_mtm
                total_diff_mtm = sum_diff_mtm

                mtm_pct = (total_mtm / total_netval * 100) if total_netval != 0 else 0
                diff_mtm_pct = (total_diff_mtm / total_netval * 100) if total_netval != 0 else 0

                new_row = pd.DataFrame([{
                    'Time': now.strftime("%H:%M:%S"),
                    'MTM': round(total_mtm, 2),
                    'Diff_MTM': round(total_diff_mtm, 2),
                    'MTM %': round(mtm_pct, 2),
                    'Diff_MTM %': round(diff_mtm_pct, 2)
                }])
                df_history = pd.concat([df_history, new_row], ignore_index=True)

            time.sleep(refresh_interval)

        except Exception as e:
            print(f"⚠️ Loop error: {e}")
            time.sleep(refresh_interval)

# === 🧩 DASH LAYOUT ===
from dash.dash_table.Format import Format, Scheme

# --- Reuse the same app object ---
app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Live MTM Dashboard"



from dash.dash_table.Format import Format, Scheme
from dash import dash_table

def build_table(df):
    """White text for all, green/red for MTM columns."""

    # === Define columns ===
    mtm_cols = ["MTM", "Diff_MTM", "MTM %", "Diff_MTM %"]

    # === Define columns with numeric format ===
    columns = []
    for col in df.columns:
        if df[col].dtype.kind in "fi":
            columns.append({
                "name": col,
                "id": col,
                "type": "numeric",
                "format": Format(precision=2, scheme=Scheme.fixed)
            })
        else:
            columns.append({"name": col, "id": col})

    # === Conditional color rules ===
    style_data_conditional = []

    # Default white text for all cells
    style_data_conditional.append({
        "if": {"column_id": df.columns.tolist()},
        "color": "white"
    })

    # Green/red logic for MTM columns only
    for col in mtm_cols:
        if col in df.columns:
            style_data_conditional.extend([
                {
                    "if": {"filter_query": f"{{{col}}} > 0", "column_id": col},
                    "color": "limegreen",
                    "fontWeight": "bold"
                },
                {
                    "if": {"filter_query": f"{{{col}}} < 0", "column_id": col},
                    "color": "red",
                    "fontWeight": "bold"
                }
            ])

    # === Build DataTable ===
    return dash_table.DataTable(
        data=df.round(2).to_dict("records"),
        columns=columns,
        style_table={"overflowX": "auto", "border": "1px solid #444"},
        style_cell={
            "backgroundColor": "#111",
            "color": "white",  # ✅ default font
            "textAlign": "center",
            "fontFamily": "Segoe UI",
            "fontSize": "14px",
            "padding": "6px"
        },
        style_header={
            "backgroundColor": "#1E1E1E",
            "color": "white",
            "fontWeight": "bold",
            "border": "1px solid #333"
        },
        style_data_conditional=style_data_conditional,
        page_size=25
    )

# === DASH LAYOUT ===
app.layout = html.Div([
    html.H2("📊 Live MTM Dashboard", style={'textAlign': 'center', 'color': '#00BFFF'}),

    # 🔹 Store last selected strategy (memory-based)
    dcc.Store(id='stored-strategy', storage_type='memory'),

    dcc.Tabs(
        id="tabs-example",
        value='tab-dashboard',
        children=[
            dcc.Tab(label='📈 Dashboard', value='tab-dashboard', style={'backgroundColor': '#111', 'color': 'white'},
                    selected_style={'backgroundColor': '#00BFFF', 'color': 'black', 'fontWeight': 'bold'}),
            dcc.Tab(label='👤 User Summary', value='tab-user', style={'backgroundColor': '#111', 'color': 'white'},
                    selected_style={'backgroundColor': '#00BFFF', 'color': 'black', 'fontWeight': 'bold'}),
            dcc.Tab(label='📊 Strategy Stats', value='tab-strategy', style={'backgroundColor': '#111', 'color': 'white'},
                    selected_style={'backgroundColor': '#00BFFF', 'color': 'black', 'fontWeight': 'bold'}),
        ],
        style={'marginBottom': '10px'}
    ),

    html.Div(id='tabs-content'),
    dcc.Interval(id='interval-component', interval=5 * 1000, n_intervals=0)
], style={'backgroundColor': '#000', 'padding': '10px'})

# === 💾 Store last selected strategy in memory ===
@app.callback(
    Output('stored-strategy', 'data'),
    Input('strategy-dropdown', 'value'),
    prevent_initial_call=True
)
def store_selected_strategy(selected_value):
    return selected_value


# === 🔁 CALLBACK TO UPDATE CONTENT BASED ON ACTIVE TAB ===
@app.callback(
    Output('tabs-content', 'children'),
    Input('tabs-example', 'value'),
    Input('interval-component', 'n_intervals')
)
def render_tab_content(tab_name, _):
    global df_final, df_history

    if df_final.empty:
        return html.Div("Loading data...", style={'color': 'white', 'textAlign': 'center'})

    df_display = df_final.copy()

    # === 🏠 DASHBOARD TAB ===
    if tab_name == 'tab-dashboard':
        # 🧮 Exclude TOTAL row to prevent double-counting
        df_display_no_total = df_display[df_display['User'] != 'TOTAL']

        sum_netval = df_display_no_total['NetVal'].sum()
        sum_mtm = df_display_no_total['MTM'].sum()
        sum_diff_mtm = df_display_no_total['Diff_MTM'].sum()

        mtm_percent = (sum_mtm / sum_netval * 100) if sum_netval != 0 else 0
        diff_mtm_percent = (sum_diff_mtm / sum_netval * 100) if sum_netval != 0 else 0

        # --- Summary cards
        card_style = {
            'backgroundColor': '#1E1E1E',
            'color': 'white',
            'padding': '10px 15px',
            'borderRadius': '10px',
            'textAlign': 'center',
            'flex': '1',
            'fontSize': '14px',
            'fontWeight': 'bold',
            'boxShadow': '0 0 5px #00BFFF'
        }

        summary_cards = html.Div([
            html.Div([html.Div("Holding Value"), html.Div(f"{sum_netval:,.2f}")], style=card_style),
            html.Div([html.Div("MTM"), html.Div(f"{sum_mtm:,.2f}")], style=card_style),
            html.Div([html.Div("MTM %"), html.Div(f"{mtm_percent:.2f}%")], style=card_style),
            html.Div([html.Div("Diff MTM"), html.Div(f"{sum_diff_mtm:,.2f}")], style=card_style),
            html.Div([html.Div("Diff MTM %"), html.Div(f"{diff_mtm_percent:.2f}%")], style=card_style),
        ], style={'display': 'flex', 'justifyContent': 'space-between', 'gap': '8px'})

        # --- Progressive Charts
        if not df_history.empty:
            # Chart 1: MTM vs Diff MTM
            fig_progress_mtm = go.Figure()
            fig_progress_mtm.add_trace(go.Scatter(
                x=df_history['Time'], y=df_history['MTM'],
                mode='lines+markers', name='MTM', line=dict(color='blue', width=2, shape='spline', smoothing=1.3)
            ))
            fig_progress_mtm.add_trace(go.Scatter(
                x=df_history['Time'], y=df_history['Diff_MTM'],
                mode='lines+markers', name='Diff MTM', line=dict(color='skyblue', width=2, shape='spline', smoothing=1.3)
            ))
            fig_progress_mtm.update_layout(
                title="📈 Progressive MTM vs Diff MTM",
                paper_bgcolor="#000",
                plot_bgcolor="#000",
                font_color="white",
                title_font_color="#00BFFF",
                margin=dict(l=40, r=40, t=50, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified",
                xaxis=dict(showgrid=False, showline=False, showticklabels=False),  # ⬅️ hides time
                yaxis=dict(showgrid=False, showline=True, linecolor='white', showticklabels=True)
            )

            # Chart 2: MTM % vs Diff MTM %
            fig_progress_pct = go.Figure()
            fig_progress_pct.add_trace(go.Scatter(
                x=df_history['Time'], y=df_history['MTM %'],
                mode='lines+markers', name='MTM %', line=dict(color='blue', width=2, shape='spline', smoothing=1.3)
            ))
            fig_progress_pct.add_trace(go.Scatter(
                x=df_history['Time'], y=df_history['Diff_MTM %'],
                mode='lines+markers', name='Diff MTM %', line=dict(color='skyblue', width=2, shape='spline', smoothing=1.3)
            ))
            fig_progress_pct.update_layout(
                title="📉 Progressive MTM % vs Diff MTM %",
                paper_bgcolor="#000",
                plot_bgcolor="#000",
                font_color="white",
                title_font_color="#00BFFF",
                margin=dict(l=40, r=40, t=50, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified",
                xaxis=dict(showgrid=False, showline=False, showticklabels=False),  # ⬅️ hides time
                yaxis=dict(showgrid=False, showline=True, linecolor='white', showticklabels=True)
            )


            charts = html.Div([
                dcc.Graph(figure=fig_progress_mtm, style={'height': '300px'}),
                dcc.Graph(figure=fig_progress_pct, style={'height': '300px'})
            ])
        else:
            charts = html.Div(
                "⏳ Waiting for market time (9:15:30–15:29:30)...",
                style={'color': '#AAA', 'textAlign': 'center', 'margin': '20px'}
            )

        # --- Last Updated Timestamp
        last_update = datetime.now().strftime("%H:%M:%S")
        last_update_div = html.Div(f"🕒 Last Updated: {last_update}",
                                   style={'color': '#00BFFF', 'textAlign': 'right', 'marginTop': '5px'})

        return html.Div([
            summary_cards,
            last_update_div,
            build_table(df_display),  # 🧾 Table first
            charts  # 📊 Charts below
        ])

    # === 👤 USER TAB ===
    elif tab_name == 'tab-user':
        if df_final.empty:
            return html.Div("No data available yet.", style={'color': 'white', 'textAlign': 'center'})

        # === Create User Dropdown ===
        user_list = sorted(df_final['User'].dropna().unique())

        user_dropdown = dcc.Dropdown(
            id='user-dropdown',
            options=[{'label': u, 'value': u} for u in user_list],
            value=user_list[0] if user_list else None,
            clearable=False,
            style={
                'backgroundColor': '#111',
                'color': 'white',  # ✅ White font inside dropdown
                'width': '300px',
                'margin': '10px auto'
            }
        )

        return html.Div([
            html.H4("👤 User Summary", style={'color': '#00BFFF', 'textAlign': 'center'}),
            html.Div(user_dropdown, style={'textAlign': 'center'}),
            html.Div(id='user-content')
        ])

    # === 📊 STRATEGY TAB ===
    elif tab_name == 'tab-strategy':
        if df_final.empty:
            return html.Div("No data available yet.", style={'color': 'white', 'textAlign': 'center'})

        strat_list = sorted(df_final['CumStrategy'].dropna().unique())

        strat_dropdown = dcc.Dropdown(
            id='strategy-dropdown',
            options=[{'label': s, 'value': s} for s in strat_list],
            value=None,  # 👈 initially blank — we’ll set it from memory
            clearable=False,
            style={
                'backgroundColor': '#111',
                'color': 'white',
                'width': '300px',
                'margin': '10px auto'
            }
        )

        return html.Div([
            html.H4("📊 Strategy Wise View", style={'color': '#00BFFF', 'textAlign': 'center'}),
            html.Div(strat_dropdown, style={'textAlign': 'center'}),
            html.Div(id='strategy-content')
        ])


# === 2️⃣ CHILD CALLBACK: Updates user data & chart ===
@app.callback(
    Output('user-content', 'children'),
    Input('user-dropdown', 'value'),
    Input('interval-component', 'n_intervals')
)
def update_user_tab(selected_user, _):
    global df_final

    if df_final.empty or selected_user is None:
        return html.Div("No data to display.", style={'color': 'white', 'textAlign': 'center'})

    # Filter by user and clean
    df_user = df_final[df_final['User'] == selected_user].copy()
    df_user.columns = df_user.columns.str.strip()
    df_user = df_user.sort_values(by='MTM', ascending=False).reset_index(drop=True)

    # Color logic
    style_data_conditional = [
        {'if': {'filter_query': f'{{{col}}} > 0', 'column_id': col}, 'color': 'limegreen'}
        for col in ['MTM', 'Diff_MTM', 'MTM %', 'Diff_MTM %']
    ] + [
        {'if': {'filter_query': f'{{{col}}} < 0', 'column_id': col}, 'color': 'red'}
        for col in ['MTM', 'Diff_MTM', 'MTM %', 'Diff_MTM %']
    ] + [
        {'if': {'column_id': col}, 'color': 'white'}
        for col in ['Exchange', 'User', 'CumStrategy', 'Symbol', 'Ser_Exp', 'NetQty', 'NetVal', 'NetPrice', 'Close', 'LTP']
    ]

    # Build table
    table = dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in df_user.columns],
        data=df_user.round(2).to_dict('records'),
        style_table={'overflowX': 'auto', 'border': '1px solid #444'},
        style_header={'backgroundColor': '#1E1E1E', 'color': 'white', 'fontWeight': 'bold'},
        style_data={'backgroundColor': '#111', 'textAlign': 'center'},
        style_data_conditional=style_data_conditional,
        page_size=20
    )

    # Build chart
    fig_user = go.Figure()
    fig_user.add_trace(go.Scatter(
        x=df_user['Symbol'], y=df_user['MTM'],
        mode='lines+markers', name='MTM',
        line=dict(color='blue', shape='spline', smoothing=1.3)
    ))
    fig_user.add_trace(go.Scatter(
        x=df_user['Symbol'], y=df_user['Diff_MTM'],
        mode='lines+markers', name='Diff MTM',
        line=dict(color='skyblue', shape='spline', smoothing=1.3)
    ))
    fig_user.update_layout(
        title=f"📊 MTM vs Diff MTM for {selected_user}",
        paper_bgcolor='#000',
        plot_bgcolor='#000',
        font_color='white',
        title_font_color='#00BFFF',
        hovermode="x unified",
        xaxis=dict(showgrid=False, tickangle=-45),
        yaxis=dict(showgrid=False),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=40, r=40, t=50, b=60)
    )

    return html.Div([
        html.Div(table, style={'marginBottom': '20px'}),
        dcc.Graph(figure=fig_user, style={'height': '400px'})
    ])

# === 📈 CHILD CALLBACK: Strategy Wise Chart (with Bar/Line toggle) ===
@app.callback(
    Output('strategy-content', 'children'),
    Input('strategy-dropdown', 'value'),
    Input('interval-component', 'n_intervals'),
    prevent_initial_call=False
)
def update_strategy_tab(selected_strategy, _):
    global df_final

    # ✅ Keep same dropdown selection even after data refresh
    ctx = dash.callback_context
    if not ctx.triggered:
        trigger = 'initial'
    else:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]

    # If data refreshed but selection exists, don't reset
    if selected_strategy is None and not df_final.empty:
        selected_strategy = df_final['CumStrategy'].dropna().unique()[0]

    if df_final.empty or selected_strategy is None:
        return html.Div("No data to display.", style={'color': 'white', 'textAlign': 'center'})

    # === Filter Data for selected strategy
    df_strat = df_final[df_final['CumStrategy'] == selected_strategy].copy()
    df_strat.columns = df_strat.columns.str.strip()
    df_strat = df_strat.sort_values(by='MTM', ascending=False).reset_index(drop=True)

    # === Always Line Chart
    fig_strat = go.Figure()
    fig_strat.add_trace(go.Scatter(
        x=df_strat['Symbol'], y=df_strat['MTM'],
        mode='lines+markers', name='MTM',
        line=dict(color='blue', shape='spline', smoothing=1.3)
    ))
    fig_strat.add_trace(go.Scatter(
        x=df_strat['Symbol'], y=df_strat['Diff_MTM'],
        mode='lines+markers', name='Diff MTM',
        line=dict(color='skyblue', shape='spline', smoothing=1.3)
    ))

    fig_strat.update_layout(
        title=f"📈 MTM vs Diff MTM — {selected_strategy} Strategy (Line View)",
        paper_bgcolor='#000',
        plot_bgcolor='#000',
        font_color='white',
        title_font_color='#00BFFF',
        hovermode="x unified",
        xaxis=dict(showgrid=False, tickangle=-45),
        yaxis=dict(showgrid=False),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=40, r=40, t=50, b=60)
    )

    return html.Div([
        dcc.Graph(figure=fig_strat, style={'height': '500px'})
    ])

# === 🧠 START THREAD + SERVER ===
if __name__ == '__main__':
    import webbrowser
    import threading

    # ✅ Auto-open the dashboard link in Chrome or your default browser
    chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
    webbrowser.get(chrome_path).open("http://127.0.0.1:8050")

    # ✅ Start background data update thread
    data_thread = threading.Thread(target=update_data_loop, daemon=True)
    data_thread.start()

    # ✅ Start the Dash server
    app.run(debug=True, port=8050)


# -------------------------------------===== DASHBOARD PLOTLY CODE ====-------------------------------------------------
