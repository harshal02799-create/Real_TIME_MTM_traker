# import pandas as pd
# import os
# import time
# from datetime import datetime
# from tradingview_screener import Query  # ✅ For live LTP fetch
# import dash
# from dash import Dash, dash_table, html
#
# from datetime import datetime
# import plotly.graph_objects as go
#
# # === 🧠 Global DataFrame to track progressive MTM changes ===
# df_history = pd.DataFrame(columns=['Time', 'MTM', 'Diff_MTM', 'MTM %', 'Diff_MTM %'])
#
# # === CONFIG ===
# google_csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQyY0N1hFIGML56I49kSRPWd7loDPQsa284rBn6o902zphvLQmtda5Rh76dCEm-3SjL3at9F2SVSltE/pub?gid=0&single=true&output=csv"
# base_dir = r"C:\Users\freedom\Desktop\ORDER B005\backup\GETS_FILES\GETS_EXCEL"
# file_name = "NetPositionAutoBackup.xls"
# refresh_interval = 5  # seconds
#
#
# # === 🧩 Function: Load Both Files ===
# def load_data(load_google=False):
#     today_folder = datetime.now().strftime("%d%b")
#     folder_path = os.path.join(base_dir, today_folder)
#     file_path = os.path.join(folder_path, file_name)
#
#     # === Local file ===
#     try:
#         df_local = pd.read_csv(file_path, sep="\t", engine="python")
#         df_local.columns = df_local.columns.str.strip().str.replace(" ", "_")
#         print(f"✅ Local file loaded: {len(df_local)} rows")
#
#         df_local.dropna(subset=["User", "Symbol"], inplace=True)
#         for col in ["BuyQty", "BuyVal", "SellQty", "SellVal", "NetQty", "NetVal", "NetPrice"]:
#             if col in df_local.columns:
#                 df_local[col] = pd.to_numeric(df_local[col], errors="coerce").fillna(0)
#
#         df_local = (
#             df_local.groupby(["User", "Symbol"], as_index=False)
#             .agg({
#                 "Exchange": "first", "Ser_Exp": "first",
#                 "BuyQty": "sum", "BuyVal": "sum",
#                 "SellQty": "sum", "SellVal": "sum",
#                 "NetQty": "sum", "NetVal": "sum"
#             })
#         )
#         df_local["NetPrice"] = df_local["NetVal"] / df_local["NetQty"].replace(0, pd.NA)
#         df_local["CumStrategy"] = df_local["NetVal"].apply(
#             lambda x: "Circuit" if abs(x) > 425000 else "Chart"
#         )
#         df_local = df_local[df_local["NetQty"] != 0].reset_index(drop=True)
#
#     except Exception as e:
#         print(f"❌ Error reading local file: {e}")
#         df_local = pd.DataFrame()
#
#     # === Google Sheet ===
#     if load_google:
#         try:
#             df_google = pd.read_csv(google_csv_url, header=0, skiprows=range(1, 6))
#             df_google.columns = df_google.columns.str.strip().str.replace(" ", "_")
#             print(f"✅ Google Sheet loaded: {len(df_google)} rows")
#
#             df_google.dropna(subset=["User", "Symbol"], inplace=True)
#             for col in ["BuyQty", "BuyVal", "SellQty", "SellVal", "NetQty", "NetVal", "NetPrice", "Nse_close"]:
#                 if col in df_google.columns:
#                     df_google[col] = pd.to_numeric(df_google[col], errors="coerce").fillna(0)
#
#             df_google = (
#                 df_google.groupby(["User", "Symbol"], as_index=False)
#                 .agg({
#                     "Date": "first", "Exchange": "first", "Ser_Exp": "first",
#                     "BuyQty": "sum", "BuyVal": "sum",
#                     "SellQty": "sum", "SellVal": "sum",
#                     "NetQty": "sum", "NetVal": "sum",
#                     "Nse_close": "first"
#                 })
#             )
#             df_google["NetPrice"] = df_google["NetVal"] / df_google["NetQty"].replace(0, pd.NA)
#             df_google["CumStrategy"] = df_google["NetVal"].apply(
#                 lambda x: "Circuit" if abs(x) > 425000 else "Chart"
#             )
#             df_google = df_google[df_google["NetQty"] != 0].reset_index(drop=True)
#
#         except Exception as e:
#             print(f"❌ Error reading Google Sheet: {e}")
#             df_google = pd.DataFrame()
#     else:
#         df_google = pd.DataFrame()
#
#     return df_local, df_google
#
#
# # === 🧩 Merge Local + Google ===
# def merge_local_google(df_local, df_google):
#     if df_google.empty:
#         return df_local
#     if df_local.empty:
#         return df_google
#
#     merged_df = pd.concat([df_local, df_google], ignore_index=True)
#     merged_df = merged_df.sort_values(["User", "Symbol"]).reset_index(drop=True)
#
#     merged_df = (
#         merged_df.groupby(["User", "Symbol"], as_index=False)
#         .agg({
#             "Exchange": "first", "Ser_Exp": "first",
#             "BuyQty": "sum", "BuyVal": "sum",
#             "SellQty": "sum", "SellVal": "sum",
#             "NetQty": "sum", "NetVal": "sum",
#             "CumStrategy": "first"
#         })
#     )
#
#     merged_df["NetPrice"] = merged_df["NetVal"] / merged_df["NetQty"].replace(0, pd.NA)
#     merged_df = merged_df[merged_df["NetQty"] != 0].reset_index(drop=True)
#
#     return merged_df
#
#
# # === ⚡ Fetch LTP ===
# def fetch_ltp(symbols_needed):
#     try:
#         n_rows, tv_data = (
#             Query()
#             .select("name", "exchange", "close")
#             .set_markets("india")
#             .limit(9000)
#             .get_scanner_data()
#         )
#
#         tv_data = (
#             tv_data.rename(columns={"name": "Symbol", "close": "LTP"})
#             .round(2)
#             .fillna(0)
#             .drop_duplicates(subset=["Symbol"], keep="first")
#         )
#         return tv_data[tv_data["Symbol"].isin(symbols_needed)][["Symbol", "LTP"]]
#
#     except Exception as e:
#         print(f"⚠️ LTP fetch failed: {e}")
#         return pd.DataFrame(columns=["Symbol", "LTP"])
#
#
# # === 🚀 MAIN LOOP ===
# # === 🚀 DASH + LIVE TABLE ===
# from dash import Dash, dash_table, html, dcc
# from dash.dependencies import Input, Output
# import threading
#
# app = Dash(__name__, suppress_callback_exceptions=True)
# app.title = "Live MTM Dashboard"
#
# # Store dataframe globally
# df_final = pd.DataFrame()
#
# # === 🔁 Function to refresh df_final every few seconds ===
# def update_data_loop():
#     global df_final
#     _, df_google = load_data(load_google=True)
#
#     while True:
#         try:
#             df_local, _ = load_data(load_google=False)
#             df_merged = merge_local_google(df_local, df_google)
#
#             # --- Fetch LTP
#             symbols = df_merged["Symbol"].dropna().unique().tolist()
#             if symbols:
#                 df_ltp = fetch_ltp(symbols)
#                 df_merged = df_merged.merge(df_ltp, on="Symbol", how="left")
#             else:
#                 df_merged["LTP"] = 0
#
#             # --- Merge with Google Close
#             df_merged = df_merged.merge(
#                 df_google[["Symbol", "Nse_close", "NetQty", "NetVal"]],
#                 on="Symbol",
#                 how="left",
#                 suffixes=("", "_google")
#             )
#
#             df_merged["Close"] = df_merged["Nse_close"].fillna(0)
#
#             # --- MTM calculations
#             df_merged["MTM"] = (df_merged["LTP"] - df_merged["NetPrice"]) * df_merged["NetQty"]
#             df_merged["MTM %"] = (df_merged["MTM"] / df_merged["NetVal"].replace(0, pd.NA)) * 100
#             df_merged["Diff_MTM"] = (df_merged["LTP"] - df_merged["Close"]) * df_merged["NetQty_google"].fillna(0)
#             df_merged["Diff_MTM %"] = (df_merged["Diff_MTM"] / df_merged["NetVal_google"].replace(0, pd.NA)) * 100
#
#             final_cols = [
#                 "Exchange", "User", "CumStrategy", "Symbol", "Ser_Exp",
#                 "NetQty", "NetVal", "NetPrice",
#                 "Close", "LTP", "MTM", "MTM %", "Diff_MTM", "Diff_MTM %"
#             ]
#             df_final_temp = df_merged.reindex(columns=final_cols)
#
#             # Round
#             numeric_cols = df_final_temp.select_dtypes(include='number').columns
#             df_final_temp[numeric_cols] = df_final_temp[numeric_cols].round(2)
#
#             # Totals
#             sum_netqty = df_final_temp['NetQty'].sum()
#             sum_netval = df_final_temp['NetVal'].sum()
#             sum_mtm = df_final_temp['MTM'].sum()
#             sum_diff_mtm = df_final_temp['Diff_MTM'].sum()
#             mtm_percent = (sum_mtm / sum_netval) * 100 if sum_netval != 0 else 0
#             diff_mtm_percent = (sum_diff_mtm / sum_netval) * 100 if sum_netval != 0 else 0
#
#             total_row = {
#                 "Exchange": "",
#                 "User": "TOTAL",
#                 "CumStrategy": "",
#                 "Symbol": "",
#                 "Ser_Exp": "",
#                 "NetQty": sum_netqty,
#                 "NetVal": sum_netval,
#                 "NetPrice": "",
#                 "Close": "",
#                 "LTP": "",
#                 "MTM": sum_mtm,
#                 "MTM %": mtm_percent,
#                 "Diff_MTM": sum_diff_mtm,
#                 "Diff_MTM %": diff_mtm_percent
#             }
#             df_final_temp = pd.concat([df_final_temp, pd.DataFrame([total_row])], ignore_index=True)
#
#             # ✅ Force convert + round these columns
#             for col in ["NetPrice", "MTM", "MTM %"]:
#                 if col in df_final_temp.columns:
#                     df_final_temp[col] = pd.to_numeric(df_final_temp[col], errors='coerce').round(2)
#
#             df_final = df_final_temp  # update global
#             # After appending total_row and rounding etc.
#             df_final = df_final_temp  # update global (contains TOTAL row for display)
#
#             # === 🕒 Record progressive MTM data for charts (USE precomputed sums to avoid double-count)
#             global df_history
#
#             now = datetime.now()
#             market_open = now.replace(hour=9, minute=15, second=30, microsecond=0)
#             market_close = now.replace(hour=15, minute=29, second=30, microsecond=0)
#
#             # use the sums we computed earlier (sum_netval, sum_mtm, sum_diff_mtm)
#             if market_open <= now <= market_close:
#                 total_netval = sum_netval
#                 total_mtm = sum_mtm
#                 total_diff_mtm = sum_diff_mtm
#
#                 mtm_pct = (total_mtm / total_netval * 100) if total_netval != 0 else 0
#                 diff_mtm_pct = (total_diff_mtm / total_netval * 100) if total_netval != 0 else 0
#
#                 new_row = pd.DataFrame([{
#                     'Time': now.strftime("%H:%M:%S"),
#                     'MTM': round(total_mtm, 2),
#                     'Diff_MTM': round(total_diff_mtm, 2),
#                     'MTM %': round(mtm_pct, 2),
#                     'Diff_MTM %': round(diff_mtm_pct, 2)
#                 }])
#                 df_history = pd.concat([df_history, new_row], ignore_index=True)
#
#             time.sleep(refresh_interval)
#
#         except Exception as e:
#             print(f"⚠️ Loop error: {e}")
#             time.sleep(refresh_interval)
#
# # === 🧩 DASH LAYOUT ===
# from dash.dash_table.Format import Format, Scheme
#
# # --- Reuse the same app object ---
# app = Dash(__name__, suppress_callback_exceptions=True)
# app.title = "Live MTM Dashboard"
#
#
#
# from dash.dash_table.Format import Format, Scheme
# from dash import dash_table
#
# def build_table(df):
#     """White text for all, green/red for MTM columns."""
#
#     # === Define columns ===
#     mtm_cols = ["MTM", "Diff_MTM", "MTM %", "Diff_MTM %"]
#
#     # === Define columns with numeric format ===
#     columns = []
#     for col in df.columns:
#         if df[col].dtype.kind in "fi":
#             columns.append({
#                 "name": col,
#                 "id": col,
#                 "type": "numeric",
#                 "format": Format(precision=2, scheme=Scheme.fixed)
#             })
#         else:
#             columns.append({"name": col, "id": col})
#
#     # === Conditional color rules ===
#     style_data_conditional = []
#
#     # Default white text for all cells
#     style_data_conditional.append({
#         "if": {"column_id": df.columns.tolist()},
#         "color": "white"
#     })
#
#     # Green/red logic for MTM columns only
#     for col in mtm_cols:
#         if col in df.columns:
#             style_data_conditional.extend([
#                 {
#                     "if": {"filter_query": f"{{{col}}} > 0", "column_id": col},
#                     "color": "limegreen",
#                     "fontWeight": "bold"
#                 },
#                 {
#                     "if": {"filter_query": f"{{{col}}} < 0", "column_id": col},
#                     "color": "red",
#                     "fontWeight": "bold"
#                 }
#             ])
#
#     # === Build DataTable ===
#     return dash_table.DataTable(
#         data=df.round(2).to_dict("records"),
#         columns=columns,
#         style_table={"overflowX": "auto", "border": "1px solid #444"},
#         style_cell={
#             "backgroundColor": "#111",
#             "color": "white",  # ✅ default font
#             "textAlign": "center",
#             "fontFamily": "Segoe UI",
#             "fontSize": "14px",
#             "padding": "6px"
#         },
#         style_header={
#             "backgroundColor": "#1E1E1E",
#             "color": "white",
#             "fontWeight": "bold",
#             "border": "1px solid #333"
#         },
#         style_data_conditional=style_data_conditional,
#         page_size=25
#     )
#
# # === DASH LAYOUT ===
# app.layout = html.Div([
#     html.H2("📊 Live MTM Dashboard", style={'textAlign': 'center', 'color': '#00BFFF'}),
#
#     # 🔹 Store last selected strategy (memory-based)
#     dcc.Store(id='stored-strategy', storage_type='memory'),
#
#     dcc.Tabs(
#         id="tabs-example",
#         value='tab-dashboard',
#         children=[
#             dcc.Tab(label='📈 Dashboard', value='tab-dashboard', style={'backgroundColor': '#111', 'color': 'white'},
#                     selected_style={'backgroundColor': '#00BFFF', 'color': 'black', 'fontWeight': 'bold'}),
#             dcc.Tab(label='👤 User Summary', value='tab-user', style={'backgroundColor': '#111', 'color': 'white'},
#                     selected_style={'backgroundColor': '#00BFFF', 'color': 'black', 'fontWeight': 'bold'}),
#             dcc.Tab(label='📊 Strategy Stats', value='tab-strategy', style={'backgroundColor': '#111', 'color': 'white'},
#                     selected_style={'backgroundColor': '#00BFFF', 'color': 'black', 'fontWeight': 'bold'}),
#         ],
#         style={'marginBottom': '10px'}
#     ),
#
#     html.Div(id='tabs-content'),
#     dcc.Interval(id='interval-component', interval=5 * 1000, n_intervals=0)
# ], style={'backgroundColor': '#000', 'padding': '10px'})
#
# # === 💾 Store last selected strategy in memory ===
# @app.callback(
#     Output('stored-strategy', 'data'),
#     Input('strategy-dropdown', 'value'),
#     prevent_initial_call=True
# )
# def store_selected_strategy(selected_value):
#     return selected_value
#
#
# # === 🔁 CALLBACK TO UPDATE CONTENT BASED ON ACTIVE TAB ===
# @app.callback(
#     Output('tabs-content', 'children'),
#     Input('tabs-example', 'value'),
#     Input('interval-component', 'n_intervals')
# )
# def render_tab_content(tab_name, _):
#     global df_final, df_history
#
#     if df_final.empty:
#         return html.Div("Loading data...", style={'color': 'white', 'textAlign': 'center'})
#
#     df_display = df_final.copy()
#
#     # === 🏠 DASHBOARD TAB ===
#     if tab_name == 'tab-dashboard':
#         # 🧮 Exclude TOTAL row to prevent double-counting
#         df_display_no_total = df_display[df_display['User'] != 'TOTAL']
#
#         sum_netval = df_display_no_total['NetVal'].sum()
#         sum_mtm = df_display_no_total['MTM'].sum()
#         sum_diff_mtm = df_display_no_total['Diff_MTM'].sum()
#
#         mtm_percent = (sum_mtm / sum_netval * 100) if sum_netval != 0 else 0
#         diff_mtm_percent = (sum_diff_mtm / sum_netval * 100) if sum_netval != 0 else 0
#
#         # --- Summary cards
#         card_style = {
#             'backgroundColor': '#1E1E1E',
#             'color': 'white',
#             'padding': '10px 15px',
#             'borderRadius': '10px',
#             'textAlign': 'center',
#             'flex': '1',
#             'fontSize': '14px',
#             'fontWeight': 'bold',
#             'boxShadow': '0 0 5px #00BFFF'
#         }
#
#         summary_cards = html.Div([
#             html.Div([html.Div("Holding Value"), html.Div(f"{sum_netval:,.2f}")], style=card_style),
#             html.Div([html.Div("MTM"), html.Div(f"{sum_mtm:,.2f}")], style=card_style),
#             html.Div([html.Div("MTM %"), html.Div(f"{mtm_percent:.2f}%")], style=card_style),
#             html.Div([html.Div("Diff MTM"), html.Div(f"{sum_diff_mtm:,.2f}")], style=card_style),
#             html.Div([html.Div("Diff MTM %"), html.Div(f"{diff_mtm_percent:.2f}%")], style=card_style),
#         ], style={'display': 'flex', 'justifyContent': 'space-between', 'gap': '8px'})
#
#         # --- Progressive Charts
#         if not df_history.empty:
#             # Chart 1: MTM vs Diff MTM
#             fig_progress_mtm = go.Figure()
#             fig_progress_mtm.add_trace(go.Scatter(
#                 x=df_history['Time'], y=df_history['MTM'],
#                 mode='lines+markers', name='MTM', line=dict(color='blue', width=2, shape='spline', smoothing=1.3)
#             ))
#             fig_progress_mtm.add_trace(go.Scatter(
#                 x=df_history['Time'], y=df_history['Diff_MTM'],
#                 mode='lines+markers', name='Diff MTM', line=dict(color='skyblue', width=2, shape='spline', smoothing=1.3)
#             ))
#             fig_progress_mtm.update_layout(
#                 title="📈 Progressive MTM vs Diff MTM",
#                 paper_bgcolor="#000",
#                 plot_bgcolor="#000",
#                 font_color="white",
#                 title_font_color="#00BFFF",
#                 margin=dict(l=40, r=40, t=50, b=40),
#                 legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
#                 hovermode="x unified",
#                 xaxis=dict(showgrid=False, showline=False, showticklabels=False),  # ⬅️ hides time
#                 yaxis=dict(showgrid=False, showline=True, linecolor='white', showticklabels=True)
#             )
#
#             # Chart 2: MTM % vs Diff MTM %
#             fig_progress_pct = go.Figure()
#             fig_progress_pct.add_trace(go.Scatter(
#                 x=df_history['Time'], y=df_history['MTM %'],
#                 mode='lines+markers', name='MTM %', line=dict(color='blue', width=2, shape='spline', smoothing=1.3)
#             ))
#             fig_progress_pct.add_trace(go.Scatter(
#                 x=df_history['Time'], y=df_history['Diff_MTM %'],
#                 mode='lines+markers', name='Diff MTM %', line=dict(color='skyblue', width=2, shape='spline', smoothing=1.3)
#             ))
#             fig_progress_pct.update_layout(
#                 title="📉 Progressive MTM % vs Diff MTM %",
#                 paper_bgcolor="#000",
#                 plot_bgcolor="#000",
#                 font_color="white",
#                 title_font_color="#00BFFF",
#                 margin=dict(l=40, r=40, t=50, b=40),
#                 legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
#                 hovermode="x unified",
#                 xaxis=dict(showgrid=False, showline=False, showticklabels=False),  # ⬅️ hides time
#                 yaxis=dict(showgrid=False, showline=True, linecolor='white', showticklabels=True)
#             )
#
#
#             charts = html.Div([
#                 dcc.Graph(figure=fig_progress_mtm, style={'height': '300px'}),
#                 dcc.Graph(figure=fig_progress_pct, style={'height': '300px'})
#             ])
#         else:
#             charts = html.Div(
#                 "⏳ Waiting for market time (9:15:30–15:29:30)...",
#                 style={'color': '#AAA', 'textAlign': 'center', 'margin': '20px'}
#             )
#
#         # --- Last Updated Timestamp
#         last_update = datetime.now().strftime("%H:%M:%S")
#         last_update_div = html.Div(f"🕒 Last Updated: {last_update}",
#                                    style={'color': '#00BFFF', 'textAlign': 'right', 'marginTop': '5px'})
#
#         return html.Div([
#             summary_cards,
#             last_update_div,
#             build_table(df_display),  # 🧾 Table first
#             charts  # 📊 Charts below
#         ])
#
#     # === 👤 USER TAB ===
#     elif tab_name == 'tab-user':
#         if df_final.empty:
#             return html.Div("No data available yet.", style={'color': 'white', 'textAlign': 'center'})
#
#         # === Create User Dropdown ===
#         user_list = sorted(df_final['User'].dropna().unique())
#
#         user_dropdown = dcc.Dropdown(
#             id='user-dropdown',
#             options=[{'label': u, 'value': u} for u in user_list],
#             value=user_list[0] if user_list else None,
#             clearable=False,
#             style={
#                 'backgroundColor': '#111',
#                 'color': 'white',  # ✅ White font inside dropdown
#                 'width': '300px',
#                 'margin': '10px auto'
#             }
#         )
#
#         return html.Div([
#             html.H4("👤 User Summary", style={'color': '#00BFFF', 'textAlign': 'center'}),
#             html.Div(user_dropdown, style={'textAlign': 'center'}),
#             html.Div(id='user-content')
#         ])
#
#     # === 📊 STRATEGY TAB ===
#     elif tab_name == 'tab-strategy':
#         if df_final.empty:
#             return html.Div("No data available yet.", style={'color': 'white', 'textAlign': 'center'})
#
#         strat_list = sorted(df_final['CumStrategy'].dropna().unique())
#
#         strat_dropdown = dcc.Dropdown(
#             id='strategy-dropdown',
#             options=[{'label': s, 'value': s} for s in strat_list],
#             value=None,  # 👈 initially blank — we’ll set it from memory
#             clearable=False,
#             style={
#                 'backgroundColor': '#111',
#                 'color': 'white',
#                 'width': '300px',
#                 'margin': '10px auto'
#             }
#         )
#
#         return html.Div([
#             html.H4("📊 Strategy Wise View", style={'color': '#00BFFF', 'textAlign': 'center'}),
#             html.Div(strat_dropdown, style={'textAlign': 'center'}),
#             html.Div(id='strategy-content')
#         ])
#
#
# # === 2️⃣ CHILD CALLBACK: Updates user data & chart ===
# @app.callback(
#     Output('user-content', 'children'),
#     Input('user-dropdown', 'value'),
#     Input('interval-component', 'n_intervals')
# )
# def update_user_tab(selected_user, _):
#     global df_final
#
#     if df_final.empty or selected_user is None:
#         return html.Div("No data to display.", style={'color': 'white', 'textAlign': 'center'})
#
#     # Filter by user and clean
#     df_user = df_final[df_final['User'] == selected_user].copy()
#     df_user.columns = df_user.columns.str.strip()
#     df_user = df_user.sort_values(by='MTM', ascending=False).reset_index(drop=True)
#
#     # Color logic
#     style_data_conditional = [
#         {'if': {'filter_query': f'{{{col}}} > 0', 'column_id': col}, 'color': 'limegreen'}
#         for col in ['MTM', 'Diff_MTM', 'MTM %', 'Diff_MTM %']
#     ] + [
#         {'if': {'filter_query': f'{{{col}}} < 0', 'column_id': col}, 'color': 'red'}
#         for col in ['MTM', 'Diff_MTM', 'MTM %', 'Diff_MTM %']
#     ] + [
#         {'if': {'column_id': col}, 'color': 'white'}
#         for col in ['Exchange', 'User', 'CumStrategy', 'Symbol', 'Ser_Exp', 'NetQty', 'NetVal', 'NetPrice', 'Close', 'LTP']
#     ]
#
#     # Build table
#     table = dash_table.DataTable(
#         columns=[{"name": i, "id": i} for i in df_user.columns],
#         data=df_user.round(2).to_dict('records'),
#         style_table={'overflowX': 'auto', 'border': '1px solid #444'},
#         style_header={'backgroundColor': '#1E1E1E', 'color': 'white', 'fontWeight': 'bold'},
#         style_data={'backgroundColor': '#111', 'textAlign': 'center'},
#         style_data_conditional=style_data_conditional,
#         page_size=20
#     )
#
#     # Build chart
#     fig_user = go.Figure()
#     fig_user.add_trace(go.Scatter(
#         x=df_user['Symbol'], y=df_user['MTM'],
#         mode='lines+markers', name='MTM',
#         line=dict(color='blue', shape='spline', smoothing=1.3)
#     ))
#     fig_user.add_trace(go.Scatter(
#         x=df_user['Symbol'], y=df_user['Diff_MTM'],
#         mode='lines+markers', name='Diff MTM',
#         line=dict(color='skyblue', shape='spline', smoothing=1.3)
#     ))
#     fig_user.update_layout(
#         title=f"📊 MTM vs Diff MTM for {selected_user}",
#         paper_bgcolor='#000',
#         plot_bgcolor='#000',
#         font_color='white',
#         title_font_color='#00BFFF',
#         hovermode="x unified",
#         xaxis=dict(showgrid=False, tickangle=-45),
#         yaxis=dict(showgrid=False),
#         legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
#         margin=dict(l=40, r=40, t=50, b=60)
#     )
#
#     return html.Div([
#         html.Div(table, style={'marginBottom': '20px'}),
#         dcc.Graph(figure=fig_user, style={'height': '400px'})
#     ])
#
# # === 📈 CHILD CALLBACK: Strategy Wise Chart (with Bar/Line toggle) ===
# @app.callback(
#     Output('strategy-content', 'children'),
#     Input('strategy-dropdown', 'value'),
#     Input('interval-component', 'n_intervals'),
#     prevent_initial_call=False
# )
# def update_strategy_tab(selected_strategy, _):
#     global df_final
#
#     # ✅ Keep same dropdown selection even after data refresh
#     ctx = dash.callback_context
#     if not ctx.triggered:
#         trigger = 'initial'
#     else:
#         trigger = ctx.triggered[0]['prop_id'].split('.')[0]
#
#     # If data refreshed but selection exists, don't reset
#     if selected_strategy is None and not df_final.empty:
#         selected_strategy = df_final['CumStrategy'].dropna().unique()[0]
#
#     if df_final.empty or selected_strategy is None:
#         return html.Div("No data to display.", style={'color': 'white', 'textAlign': 'center'})
#
#     # === Filter Data for selected strategy
#     df_strat = df_final[df_final['CumStrategy'] == selected_strategy].copy()
#     df_strat.columns = df_strat.columns.str.strip()
#     df_strat = df_strat.sort_values(by='MTM', ascending=False).reset_index(drop=True)
#
#     # === Always Line Chart
#     fig_strat = go.Figure()
#     fig_strat.add_trace(go.Scatter(
#         x=df_strat['Symbol'], y=df_strat['MTM'],
#         mode='lines+markers', name='MTM',
#         line=dict(color='blue', shape='spline', smoothing=1.3)
#     ))
#     fig_strat.add_trace(go.Scatter(
#         x=df_strat['Symbol'], y=df_strat['Diff_MTM'],
#         mode='lines+markers', name='Diff MTM',
#         line=dict(color='skyblue', shape='spline', smoothing=1.3)
#     ))
#
#     fig_strat.update_layout(
#         title=f"📈 MTM vs Diff MTM — {selected_strategy} Strategy (Line View)",
#         paper_bgcolor='#000',
#         plot_bgcolor='#000',
#         font_color='white',
#         title_font_color='#00BFFF',
#         hovermode="x unified",
#         xaxis=dict(showgrid=False, tickangle=-45),
#         yaxis=dict(showgrid=False),
#         legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
#         margin=dict(l=40, r=40, t=50, b=60)
#     )
#
#     return html.Div([
#         dcc.Graph(figure=fig_strat, style={'height': '500px'})
#     ])
#
# # === 🧠 START THREAD + SERVER ===
# if __name__ == '__main__':
#     import webbrowser
#     import threading
#
#     # ✅ Auto-open the dashboard link in Chrome or your default browser
#     chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
#     webbrowser.get(chrome_path).open("http://127.0.0.1:8050")
#
#     # ✅ Start background data update thread
#     data_thread = threading.Thread(target=update_data_loop, daemon=True)
#     data_thread.start()
#
#     # ✅ Start the Dash server
#     app.run(debug=True, port=8050)
#
#
# # -------------------------------------===== DASHBOARD PLOTLY CODE ====-------------------------------------------------




# LOCAL_CSV.py
# Live MTM Dashboard (Streamlit)
# - Upload Portfolio (CSV / XLS[X]) once
# - Live Trades: auto-read local NetPositionAutoBackup.xls OR upload an XLSX/TSV
# - Refresh live trades every REFRESH_INTERVAL seconds
# - Merge, compute MTM & Diff MTM, show dashboard with 3 tabs

import os
import io
import time
from datetime import datetime
from typing import List, Optional

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

# Optional: TradingView LTP fetch
try:
    from tradingview_screener import Query
    TV_AVAILABLE = True
except Exception:
    TV_AVAILABLE = False

# Optional autorefresh
try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except Exception:
    AUTOREFRESH_AVAILABLE = False

# -----------------------------
# CONFIG (change base_dir as required)
# -----------------------------
DEFAULT_BASE_DIR = r"C:\Users\freedom\Desktop\ORDER B005\backup\GETS_FILES\GETS_EXCEL"
FILE_NAME = "NetPositionAutoBackup.xls"   # fixed file name in dated folder (DDMon)
DEFAULT_REFRESH_INTERVAL = 5  # seconds

# -----------------------------
# PAGE SETUP
# -----------------------------
st.set_page_config(page_title="📊 Live MTM Dashboard", layout="wide")
st.title("📊 Live MTM Dashboard")

# -----------------------------
# SESSION STATE INIT
# -----------------------------
if "csv_df" not in st.session_state:
    st.session_state["csv_df"] = pd.DataFrame()
if "csv_uploaded" not in st.session_state:
    st.session_state["csv_uploaded"] = False
if "live_upload_df" not in st.session_state:
    st.session_state["live_upload_df"] = pd.DataFrame()
if "use_local_live" not in st.session_state:
    st.session_state["use_local_live"] = True
if "base_dir" not in st.session_state:
    st.session_state["base_dir"] = DEFAULT_BASE_DIR
if "refresh_interval" not in st.session_state:
    st.session_state["refresh_interval"] = DEFAULT_REFRESH_INTERVAL
if "last_local_mtime" not in st.session_state:
    st.session_state["last_local_mtime"] = None
if "merged_df" not in st.session_state:
    st.session_state["merged_df"] = pd.DataFrame()
if "history" not in st.session_state:
    st.session_state["history"] = []  # list of snapshots
if "selected_user" not in st.session_state:
    st.session_state["selected_user"] = "-- All --"
if "selected_strategy" not in st.session_state:
    st.session_state["selected_strategy"] = "-- All --"

# -----------------------------
# SIDEBAR: Uploads & Settings
# -----------------------------
st.sidebar.header("Files & Settings")

# Portfolio upload (CSV or Excel) — one time
uploaded_portfolio = st.sidebar.file_uploader("📂 Upload Portfolio (CSV or XLS/XLSX)", type=["csv", "xls", "xlsx"])
if uploaded_portfolio is not None and not st.session_state["csv_uploaded"]:
    # read uploaded file into df
    try:
        name = uploaded_portfolio.name.lower()
        bytes_data = uploaded_portfolio.read()
        if name.endswith(".csv"):
            df_csv = pd.read_csv(io.StringIO(bytes_data.decode("utf-8")), engine="python")
        else:
            df_csv = pd.read_excel(io.BytesIO(bytes_data))
        st.session_state["csv_df"] = df_csv.copy()
        st.session_state["csv_uploaded"] = True
        st.sidebar.success(f"Portfolio loaded: {uploaded_portfolio.name} ({len(df_csv)} rows)")

        # Ensure Strategy column
        if "Strategy" not in st.session_state["csv_df"].columns:
            st.session_state["csv_df"]["Strategy"] = st.session_state["csv_df"].get("NetVal", 0).apply(
                lambda x: "CIRCUIT" if pd.notna(x) and float(x) > 425000 else "CHART"
            )
        else:
            st.session_state["csv_df"]["Strategy"] = st.session_state["csv_df"]["Strategy"].fillna("").astype(str)
            blank_mask = st.session_state["csv_df"]["Strategy"].str.strip() == ""
            if blank_mask.any():
                st.session_state["csv_df"].loc[blank_mask, "Strategy"] = st.session_state["csv_df"].loc[blank_mask, "NetVal"].apply(
                    lambda x: "CIRCUIT" if pd.notna(x) and float(x) > 425000 else "CHART"
                )

        # Ensure Nse_close exists
        if "Nse_close" not in st.session_state["csv_df"].columns:
            st.session_state["csv_df"]["Nse_close"] = 0.0

    except Exception as e:
        st.sidebar.error(f"Failed to read portfolio: {e}")

# Live-trades (NetPosition) upload OR local mode
st.sidebar.markdown("### Live Trades Source")
live_mode = st.sidebar.radio("Select live trades source", ("Auto-read local file", "Upload live trades file"))
if live_mode == "Auto-read local file":
    st.session_state["use_local_live"] = True
else:
    st.session_state["use_local_live"] = False

if st.session_state["use_local_live"]:
    st.sidebar.text_input("Base folder for daily folders", value=st.session_state["base_dir"], key="base_dir")
    st.sidebar.markdown(f"Looking for `{FILE_NAME}` inside folder like `DDMon` (e.g. 04Nov) under base_dir.")
else:
    uploaded_live = st.sidebar.file_uploader("📤 Upload live NetPosition (XLS/XLSX/TSV)", type=["xls", "xlsx", "csv", "tsv"])
    if uploaded_live is not None:
        try:
            name = uploaded_live.name.lower()
            b = uploaded_live.read()

            # Try reading based on file type and content
            if name.endswith(".csv"):
                df_live = pd.read_csv(io.StringIO(b.decode("utf-8")), sep=",", engine="python")
            elif name.endswith(".tsv"):
                df_live = pd.read_csv(io.StringIO(b.decode("utf-8")), sep="\t", engine="python")
            elif name.endswith(".xls") or name.endswith(".xlsx"):
                # Try multiple Excel engines, fallback to TSV if needed
                try:
                    df_live = pd.read_excel(io.BytesIO(b), engine="xlrd")
                except Exception:
                    try:
                        df_live = pd.read_excel(io.BytesIO(b), engine="openpyxl")
                    except Exception:
                        # If it’s actually a TSV saved as .xls
                        df_live = pd.read_csv(io.StringIO(b.decode("utf-8")), sep="\t", engine="python")
            else:
                raise ValueError("Unsupported file type")

            st.session_state["live_upload_df"] = df_live.copy()
            st.sidebar.success(f"Live trades uploaded: {uploaded_live.name} ({len(df_live)} rows)")

        except Exception as e:
            st.sidebar.error(f"Failed to read live trades upload: {e}")

# Refresh interval
st.session_state["refresh_interval"] = st.sidebar.number_input("Refresh interval (seconds)", min_value=1, max_value=60, value=st.session_state["refresh_interval"], step=1)

st.sidebar.markdown("---")
st.sidebar.write("LTP source:", "TradingView (Query)" if TV_AVAILABLE else "Unavailable — uses NetPrice")

# -----------------------------
# Helper: load local live file
# -----------------------------
def load_local_live(base_dir: str, file_name: str) -> pd.DataFrame:
    folder = os.path.join(base_dir, datetime.now().strftime("%d%b"))
    fpath = os.path.join(folder, file_name)
    if not os.path.exists(fpath):
        return pd.DataFrame()
    # attempt excel -> fallback to csv/tsv
    try:
        df = pd.read_excel(fpath, engine="xlrd")
        return df
    except Exception:
        try:
            df = pd.read_csv(fpath, sep="\t", engine="python")
            return df
        except Exception:
            try:
                df = pd.read_excel(fpath, engine="openpyxl")
                return df
            except Exception:
                return pd.DataFrame()

# -----------------------------
# Helper: fetch LTP (cached)
# -----------------------------
@st.cache_data(ttl=5)
def fetch_ltp(symbols: List[str]) -> pd.DataFrame:
    if not TV_AVAILABLE or not symbols:
        return pd.DataFrame(columns=["Symbol", "LTP"])
    try:
        _, tv = (
            Query()
            .select("name", "exchange", "close")
            .set_markets("india")
            .limit(9000)
            .get_scanner_data()
        )
        tv = tv.rename(columns={"name": "Symbol", "close": "LTP"})
        tv = tv.drop_duplicates(subset=["Symbol"], keep="first")
        tv["LTP"] = pd.to_numeric(tv["LTP"], errors="coerce").fillna(0.0).round(2)
        return tv[tv["Symbol"].isin(symbols)][["Symbol", "LTP"]]
    except Exception as e:
        st.warning(f"LTP fetch failed: {e}")
        return pd.DataFrame(columns=["Symbol", "LTP"])

# -----------------------------
# Merge logic (CSV + Live)
# -----------------------------
def merge_local_csv(df_tsv: pd.DataFrame, df_csv: pd.DataFrame) -> pd.DataFrame:
    # Ensure required columns exist
    for col in ["User", "Exchange", "Strategy", "Symbol", "Ser_Exp", "NetQty", "NetVal"]:
        if col not in df_csv.columns:
            df_csv[col] = "" if col not in ["NetQty", "NetVal"] else 0.0
        if col not in df_tsv.columns:
            df_tsv[col] = "" if col not in ["NetQty", "NetVal"] else 0.0

    # Strategy fill for CSV
    if "Strategy" not in df_csv.columns:
        df_csv["Strategy"] = df_csv.get("NetVal", 0).apply(lambda x: "CIRCUIT" if pd.notna(x) and float(x) > 425000 else "CHART")
    else:
        df_csv["Strategy"] = df_csv["Strategy"].fillna("").astype(str)
        blank_mask = df_csv["Strategy"].str.strip() == ""
        if blank_mask.any():
            df_csv.loc[blank_mask, "Strategy"] = df_csv.loc[blank_mask, "NetVal"].apply(lambda x: "CIRCUIT" if pd.notna(x) and float(x) > 425000 else "CHART")

    # If no TSV/live -> return CSV-only (compute NetPrice)
    if df_tsv is None or df_tsv.empty:
        merged = df_csv.copy()
        merged["NetQty"] = pd.to_numeric(merged.get("NetQty", 0), errors="coerce").fillna(0.0)
        merged["NetVal"] = pd.to_numeric(merged.get("NetVal", 0), errors="coerce").fillna(0.0)
        merged["NetPrice"] = merged.apply(lambda r: (r.NetVal / r.NetQty) if r.NetQty else 0.0, axis=1)
        merged = merged[merged["NetQty"] != 0].reset_index(drop=True)
        return merged

    # concat & aggregate
    # Ensure NetPrice may exist; if not compute later
    cols_needed = ["User","Exchange","Strategy","Symbol","Ser_Exp","NetQty","NetVal"]
    concat = pd.concat([
        df_csv[cols_needed].copy(),
        df_tsv[cols_needed].copy()
    ], ignore_index=True, sort=False)

    concat["NetQty"] = pd.to_numeric(concat["NetQty"], errors="coerce").fillna(0.0)
    concat["NetVal"] = pd.to_numeric(concat["NetVal"], errors="coerce").fillna(0.0)

    grouped = concat.groupby(["User","Exchange","Symbol","Ser_Exp"], as_index=False).agg({"NetQty":"sum","NetVal":"sum"})
    grouped["NetPrice"] = grouped.apply(lambda r: (r.NetVal / r.NetQty) if r.NetQty else 0.0, axis=1)
    grouped = grouped[grouped["NetQty"] != 0].reset_index(drop=True)

    # Strategy: prefer CSV strategy if symbol present in csv
    csv_strategy_map = df_csv.set_index("Symbol")["Strategy"].to_dict()
    def decide_strategy(sym, nv):
        s = csv_strategy_map.get(sym, None)
        if s is not None and str(s).strip() != "":
            return s
        return "CIRCUIT" if pd.notna(nv) and float(nv) > 425000 else "CHART"
    grouped["Strategy"] = grouped.apply(lambda r: decide_strategy(r["Symbol"], r["NetVal"]), axis=1)

    return grouped

def merge_and_adjust(df_tsv: pd.DataFrame, df_csv: pd.DataFrame) -> pd.DataFrame:
    merged = merge_local_csv(df_tsv, df_csv)

    # Bring Close from CSV (Nse_close)
    if "Nse_close" not in df_csv.columns:
        df_csv["Nse_close"] = 0.0
    close_map = df_csv[["Symbol","Nse_close"]].rename(columns={"Nse_close":"Close"})
    merged = pd.merge(merged, close_map, on="Symbol", how="left").fillna({"Close": 0.0})

    # Fetch LTP (or fallback)
    symbols = merged["Symbol"].dropna().unique().tolist()
    ltp_df = fetch_ltp(symbols)
    if not ltp_df.empty:
        merged = pd.merge(merged, ltp_df, on="Symbol", how="left").fillna({"LTP":0.0})
    else:
        merged["LTP"] = merged["NetPrice"].astype(float)

    # Numeric coercion
    for c in ["NetQty","NetVal","NetPrice","Close","LTP"]:
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0.0)

    # MTM metrics
    merged["MTM"] = (merged["LTP"] - merged["NetPrice"]) * merged["NetQty"]
    merged["MTM %"] = merged.apply(lambda r: (r["MTM"] / r["NetVal"] * 100) if r["NetVal"] else 0.0, axis=1)
    merged["Diff_MTM"] = (merged["LTP"] - merged["Close"]) * merged["NetQty"]
    merged["Diff_MTM %"] = merged.apply(lambda r: (r["Diff_MTM"] / r["NetVal"] * 100) if r["NetVal"] else 0.0, axis=1)

    # Round numeric columns to 2 decimals
    numeric_cols = ["NetQty","NetVal","NetPrice","Close","LTP","MTM","MTM %","Diff_MTM","Diff_MTM %"]
    for c in numeric_cols:
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0.0).round(2)

    # Add TOTAL row
    total_row = {
        "User":"TOTAL",
        "Exchange":"",
        "Strategy":"",
        "Symbol":"",
        "Ser_Exp":"",
        "NetQty": merged["NetQty"].sum(),
        "NetVal": merged["NetVal"].sum(),
        "NetPrice":"",
        "Close":"",
        "LTP":"",
        "MTM": merged["MTM"].sum(),
        "MTM %": (merged["MTM"].sum() / merged["NetVal"].sum() * 100) if merged["NetVal"].sum() else 0.0,
        "Diff_MTM": merged["Diff_MTM"].sum(),
        "Diff_MTM %": (merged["Diff_MTM"].sum() / merged["NetVal"].sum() * 100) if merged["NetVal"].sum() else 0.0
    }
    merged = pd.concat([merged, pd.DataFrame([total_row])], ignore_index=True)

    # Reorder for display
    col_order = ["User","Strategy","Exchange","Symbol","Ser_Exp","NetQty","NetVal","NetPrice","Close","LTP","MTM","MTM %","Diff_MTM","Diff_MTM %"]
    merged = merged[[c for c in col_order if c in merged.columns]]

    merged = merged.fillna("")
    return merged

# -----------------------------
# Utilities for UI formatting
# -----------------------------
def color_text_html(val):
    try:
        v = float(val)
    except Exception:
        return f"{val}"
    color = "#00FF00" if v >= 0 else "#FF4C4C"
    return f"<span style='color:{color}; font-weight:bold'>{v:,.2f}</span>"

def style_pos_neg(series):
    try:
        s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    except Exception:
        return ["color:white"] * len(series)
    return ["color:limegreen" if v > 0 else ("color:red" if v < 0 else "color:white") for v in s]

# -----------------------------
# MAIN: Auto-read or use upload, merge, display
# -----------------------------
status_col, action_col = st.columns([3,1])
with status_col:
    ts = datetime.now().strftime("%H:%M:%S")
    st.markdown(f"**Last check:** {ts} — Live file mode: **{'Local Auto' if st.session_state['use_local_live'] else 'Uploaded Live'}**")

# Load CSV (must be uploaded)
if not st.session_state["csv_uploaded"]:
    st.warning("Upload a Portfolio file in the sidebar to start the dashboard (CSV or XLS/XLSX).")
else:
    # Determine live-source DataFrame
    df_live = pd.DataFrame()
    if st.session_state["use_local_live"]:
        # try read local file path every refresh interval if changed
        base_dir = st.session_state["base_dir"]
        folder = os.path.join(base_dir, datetime.now().strftime("%d%b"))
        fpath = os.path.join(folder, FILE_NAME)
        if os.path.exists(fpath):
            mtime = os.path.getmtime(fpath)
            # reload on change or first time
            if st.session_state["last_local_mtime"] != mtime or st.session_state["merged_df"].empty:
                try:
                    df_live = load_local_live(base_dir, FILE_NAME)
                    st.session_state["last_local_mtime"] = mtime
                except Exception as e:
                    st.error(f"Failed reading local live file: {e}")
                    df_live = pd.DataFrame()
            else:
                # use previous merged_df's live portion (no reload)
                df_live = pd.DataFrame()  # handled by merge logic expecting empty -> csv-only
        else:
            df_live = pd.DataFrame()
    else:
        # use uploaded live from session_state (if any)
        df_live = st.session_state.get("live_upload_df", pd.DataFrame())

    # Merge
    try:
        merged_df = merge_and_adjust(df_live, st.session_state["csv_df"])
        st.session_state["merged_df"] = merged_df.copy()
        # update history snapshot (use TOTAL row)
        if not merged_df.empty and "User" in merged_df.columns and "TOTAL" in merged_df["User"].values:
            total = merged_df[merged_df["User"] == "TOTAL"].iloc[0]
            snap = {
                "Time": datetime.now().strftime("%H:%M:%S"),
                "MTM": float(total.get("MTM") or 0.0),
                "Diff_MTM": float(total.get("Diff_MTM") or 0.0),
                "MTM %": float(total.get("MTM %") or 0.0),
                "Diff_MTM %": float(total.get("Diff_MTM %") or 0.0)
            }
            st.session_state["history"].append(snap)
            if len(st.session_state["history"]) > 400:
                st.session_state["history"] = st.session_state["history"][-400:]
    except Exception as e:
        st.error(f"Merging error: {e}")
        merged_df = pd.DataFrame()

    # DISPLAY UI: tabs
    merged_display = st.session_state["merged_df"].copy() if not st.session_state["merged_df"].empty else pd.DataFrame()
    history_df = pd.DataFrame(st.session_state["history"])

    tab1, tab2, tab3 = st.tabs(["📈 Dashboard", "👤 User Summary", "📊 Strategy Stats"])

    # --- TAB 1: Dashboard ---
    with tab1:
        st.markdown("### Dashboard")
        if merged_display.empty:
            st.info("No merged data yet.")
        else:
            # total row detection
            total_row = None
            if "User" in merged_display.columns and "TOTAL" in merged_display["User"].values:
                total_row = merged_display[merged_display["User"] == "TOTAL"].iloc[0]
            elif "Strategy" in merged_display.columns and "TOTAL" in merged_display["Strategy"].values:
                total_row = merged_display[merged_display["Strategy"] == "TOTAL"].iloc[0]

            if total_row is not None:
                net_val = float(total_row.get("NetVal") or 0.0)
                mtm = float(total_row.get("MTM") or 0.0)
                mtm_pct = float(total_row.get("MTM %") or 0.0)
                diff_mtm = float(total_row.get("Diff_MTM") or 0.0)
                diff_mtm_pct = float(total_row.get("Diff_MTM %") or 0.0)

                st.markdown(
                    f"""
                    <div style="display:flex; gap:8px; margin-bottom:10px;">
                        <div style="flex:1; background:#0b0b0b; padding:12px; border-radius:8px; text-align:center;">
                          <div style="color:#bbb; font-size:12px;">Holding Value</div>
                          <div style="font-size:18px; font-weight:bold; color:white;">{net_val:,.2f}</div>
                        </div>
                        <div style="flex:1; background:#0b0b0b; padding:12px; border-radius:8px; text-align:center;">
                          <div style="color:#bbb; font-size:12px;">MTM</div>
                          <div style="font-size:18px; font-weight:bold;">{color_text_html(mtm)}</div>
                        </div>
                        <div style="flex:1; background:#0b0b0b; padding:12px; border-radius:8px; text-align:center;">
                          <div style="color:#bbb; font-size:12px;">MTM %</div>
                          <div style="font-size:18px; font-weight:bold;">{color_text_html(mtm_pct)}</div>
                        </div>
                        <div style="flex:1; background:#0b0b0b; padding:12px; border-radius:8px; text-align:center;">
                          <div style="color:#bbb; font-size:12px;">Diff MTM</div>
                          <div style="font-size:18px; font-weight:bold;">{color_text_html(diff_mtm)}</div>
                        </div>
                        <div style="flex:1; background:#0b0b0b; padding:12px; border-radius:8px; text-align:center;">
                          <div style="color:#bbb; font-size:12px;">Diff MTM %</div>
                          <div style="font-size:18px; font-weight:bold;">{color_text_html(diff_mtm_pct)}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown(f"**Last checked:** {datetime.now().strftime('%H:%M:%S')}")

            # Table
            df_show = merged_display.copy()
            for c in ["NetQty","NetVal","NetPrice","Close","LTP","MTM","MTM %","Diff_MTM","Diff_MTM %"]:
                if c in df_show.columns:
                    df_show[c] = pd.to_numeric(df_show[c], errors="coerce").round(2)

            def highlight_col(col):
                return df_show[col].apply(lambda x: "color:limegreen" if pd.to_numeric(x, errors="coerce")>0 else ("color:red" if pd.to_numeric(x, errors="coerce")<0 else "color:white"))

            styler = df_show.style.set_properties(**{"text-align":"center"})
            for col in ["MTM","MTM %","Diff_MTM","Diff_MTM %"]:
                if col in df_show.columns:
                    styler = styler.apply(lambda s: style_pos_neg(s), subset=[col])

            st.dataframe(styler, use_container_width=True, height=420)

            # Charts
            if not history_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=history_df["Time"], y=history_df["MTM"], mode="lines+markers", name="MTM", line=dict(shape="spline", smoothing=1.3)))
                fig.add_trace(go.Scatter(x=history_df["Time"], y=history_df["Diff_MTM"], mode="lines+markers", name="Diff MTM", line=dict(shape="spline", smoothing=1.3)))
                fig.update_layout(title="Progressive MTM vs Diff MTM", paper_bgcolor="#000", plot_bgcolor="#000", font_color="white", height=320)
                st.plotly_chart(fig, use_container_width=True)

                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=history_df["Time"], y=history_df["MTM %"], mode="lines+markers", name="MTM %", line=dict(shape="spline", smoothing=1.3)))
                fig2.add_trace(go.Scatter(x=history_df["Time"], y=history_df["Diff_MTM %"], mode="lines+markers", name="Diff MTM %", line=dict(shape="spline", smoothing=1.3)))
                fig2.update_layout(title="Progressive MTM % vs Diff MTM %", paper_bgcolor="#000", plot_bgcolor="#000", font_color="white", height=320)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No history snapshots yet (will collect when live file is read).")

    # --- TAB 2: User Summary ---
    with tab2:
        st.markdown("### User Summary")
        if merged_display.empty:
            st.info("No data yet.")
        else:
            users = [u for u in sorted(merged_display["User"].unique().tolist()) if u and u!="TOTAL"]
            all_opts = ["-- All --"] + users
            idx = all_opts.index(st.session_state["selected_user"]) if st.session_state["selected_user"] in all_opts else 0
            sel = st.selectbox("Select user", options=all_opts, index=idx)
            st.session_state["selected_user"] = sel

            if sel == "-- All --":
                df_user = merged_display[merged_display["User"] != "TOTAL"].copy()
            else:
                df_user = merged_display[(merged_display["User"] == sel) & (merged_display["User"] != "TOTAL")].copy()

            # Table then chart
            st.subheader("User Table")
            if df_user.empty:
                st.write("No records for this user.")
            else:
                sty = df_user.style.set_properties(**{"text-align":"center"})
                for col in ["MTM","MTM %","Diff_MTM","Diff_MTM %"]:
                    if col in df_user.columns:
                        sty = sty.apply(lambda s: style_pos_neg(s), subset=[col])
                st.dataframe(sty, use_container_width=True, height=340)

            st.subheader("Symbol MTM Chart")
            if df_user.empty:
                st.info("No data to chart.")
            else:
                fig_u = go.Figure()
                fig_u.add_trace(go.Scatter(x=df_user["Symbol"], y=df_user["MTM"], mode="lines+markers", name="MTM", line=dict(shape="spline", smoothing=1.2)))
                fig_u.add_trace(go.Scatter(x=df_user["Symbol"], y=df_user["Diff_MTM"], mode="lines+markers", name="Diff MTM", line=dict(shape="spline", smoothing=1.2)))
                fig_u.update_layout(paper_bgcolor="#000", plot_bgcolor="#000", font_color="white", height=450)
                st.plotly_chart(fig_u, use_container_width=True)

    # --- TAB 3: Strategy Stats ---
    with tab3:
        st.markdown("### Strategy Stats")
        if merged_display.empty:
            st.info("No data yet.")
        else:
            strategies = [s for s in sorted(merged_display["Strategy"].unique().tolist()) if s and s!=""]
            all_opts = ["-- All --"] + strategies
            idx = all_opts.index(st.session_state["selected_strategy"]) if st.session_state["selected_strategy"] in all_opts else 0
            sel_s = st.selectbox("Select strategy", options=all_opts, index=idx)
            st.session_state["selected_strategy"] = sel_s

            if sel_s == "-- All --":
                df_str = merged_display[merged_display["User"] != "TOTAL"].copy()
            else:
                df_str = merged_display[(merged_display["Strategy"] == sel_s) & (merged_display["User"] != "TOTAL")].copy()

            st.subheader("Strategy Chart")
            if df_str.empty:
                st.write("No records.")
            else:
                fig_s = go.Figure()
                fig_s.add_trace(go.Bar(x=df_str["Symbol"], y=df_str["MTM"], name="MTM"))
                fig_s.add_trace(go.Bar(x=df_str["Symbol"], y=df_str["Diff_MTM"], name="Diff MTM"))
                fig_s.update_layout(barmode='group', paper_bgcolor="#000", plot_bgcolor="#000", font_color="white", height=450)
                st.plotly_chart(fig_s, use_container_width=True)

                st.subheader("Strategy Table")
                sty2 = df_str.style.set_properties(**{"text-align":"center"})
                for col in ["MTM","MTM %","Diff_MTM","Diff_MTM %"]:
                    if col in df_str.columns:
                        sty2 = sty2.apply(lambda s: style_pos_neg(s), subset=[col])
                st.dataframe(sty2, use_container_width=True, height=340)

# -----------------------------
# Auto-refresh controller
# -----------------------------
if st.session_state["csv_uploaded"]:
    if AUTOREFRESH_AVAILABLE:
        # this will rerun the script every refresh_interval seconds
        st_autorefresh(interval=st.session_state["refresh_interval"] * 1000, key="autorefresh")
    else:
        st.sidebar.info("Install `streamlit-autorefresh` for automatic polling (pip install streamlit-autorefresh). Otherwise refresh page manually.")
