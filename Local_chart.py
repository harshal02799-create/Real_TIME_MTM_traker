import os
import pandas as pd
import yfinance as yf
from datetime import datetime
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots   # ✅ add this
import numpy as np                          # ✅ add this
from tradingview_screener import Query


class LiveMTMDashboard:
    def __init__(self):
        # === CONFIG ===
        self.base_dir = r"C:\Users\freedom\Desktop\ORDER B005\backup\GETS_FILES\GETS_EXCEL"
        self.file_name = "NetPositionAutoBackup.xls"

        # ✅ Proper Streamlit page setup
        st.set_page_config(page_title="📊 Live MTM Dashboard", layout="wide", initial_sidebar_state="expanded")

        # 🚫 Removed st.title() to prevent duplicate heading
        # We'll use a custom centered title in the run() method instead

        # Sidebar file uploader
        self.csv_path = st.sidebar.file_uploader("📂 Upload your Google CSV file", type=["csv"])

    # === Load Local File ===
    def load_local_file(self):
        folder = os.path.join(self.base_dir, datetime.now().strftime("%d%b"))
        fpath = os.path.join(folder, self.file_name)
        if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
            try:
                return pd.read_excel(fpath, engine="xlrd")
            except Exception:
                return pd.read_csv(fpath, sep="\t", engine="python")
        return pd.DataFrame()

    # === Merge TSV + CSV ===
    def merge_local_csv(self, df_tsv, df_csv):
        for col in ["User", "Exchange", "Strategy", "Symbol", "Ser_Exp", "NetQty", "NetVal"]:
            if col not in df_csv.columns:
                df_csv[col] = "" if col in ["User", "Exchange", "Strategy", "Symbol", "Ser_Exp"] else 0
            if col not in df_tsv.columns:
                df_tsv[col] = "" if col in ["User", "Exchange", "Strategy", "Symbol", "Ser_Exp"] else 0

        if "Strategy" not in df_csv.columns or df_csv["Strategy"].isna().all():
            df_csv["Strategy"] = df_csv["NetVal"].apply(lambda x: "CIRCUIT" if x > 425000 else "CHART")
        else:
            df_csv["Strategy"] = df_csv["Strategy"].fillna("")
            df_csv.loc[df_csv["Strategy"] == "", "Strategy"] = df_csv["NetVal"].apply(
                lambda x: "CIRCUIT" if x > 425000 else "CHART"
            )

        merged_df = pd.concat([df_csv, df_tsv], ignore_index=True) if not df_tsv.empty else df_csv.copy()
        merged_df = (
            merged_df.groupby(["User", "Symbol"], as_index=False)
            .agg({
                "Exchange": "first",
                "Ser_Exp": "first",
                "NetQty": "sum",
                "NetVal": "sum",
                "Strategy": "first"
            })
        )

        merged_df["NetPrice"] = merged_df["NetVal"] / merged_df["NetQty"].replace(0, pd.NA)
        merged_df = merged_df[merged_df["NetQty"] != 0].reset_index(drop=True)
        return merged_df

    # === Fetch LTP (from TradingView) ===
    @st.cache_data(ttl=10)
    def fetch_ltp(_self, symbols_needed):
        try:
            _, tv_data = (
                Query()
                .select("name", "exchange", "close")
                .set_markets("india")
                .limit(9000)
                .get_scanner_data()
            )
            tv_data = (
                tv_data.rename(columns={"name": "Symbol", "close": "LTP"})
                .drop_duplicates(subset=["Symbol"], keep="first")
                .fillna(0)
            )
            return tv_data[tv_data["Symbol"].isin(symbols_needed)][["Symbol", "LTP"]]
        except Exception as e:
            st.warning(f"⚠️ LTP fetch failed: {e}")
            return pd.DataFrame(columns=["Symbol", "LTP"])

    def merge_and_adjust(self, df_tsv, df_csv):
        merged = self.merge_local_csv(df_tsv, df_csv)

        # ✅ Merge NSE close by User + Symbol to avoid row multiplication
        if "User" in df_csv.columns:
            close_map = df_csv[["User", "Symbol", "Nse_close"]].rename(columns={"Nse_close": "Close"})
            merged = pd.merge(merged, close_map, on=["User", "Symbol"], how="left").fillna({"Close": 0})
        else:
            close_map = df_csv[["Symbol", "Nse_close"]].rename(columns={"Nse_close": "Close"})
            merged = pd.merge(merged, close_map, on="Symbol", how="left").fillna({"Close": 0})

        symbols = merged["Symbol"].dropna().unique().tolist()
        ltp_df = self.fetch_ltp(symbols)
        merged = pd.merge(merged, ltp_df, on="Symbol", how="left").fillna({"LTP": 0})

        # ✅ Calculate MTM and diff values
        merged["MTM"] = (merged["LTP"] - merged["NetPrice"]) * merged["NetQty"]
        merged["MTM_%"] = merged.apply(lambda r: (r["MTM"] / r["NetVal"] * 100) if r["NetVal"] else 0, axis=1)
        merged["Diff_MTM"] = (merged["LTP"] - merged["Close"]) * merged["NetQty"]
        merged["Diff_MTM_%"] = merged.apply(lambda r: (r["Diff_MTM"] / r["NetVal"] * 100) if r["NetVal"] else 0, axis=1)

        num_cols = ["NetQty", "NetVal", "NetPrice", "Close", "LTP", "MTM", "MTM_%", "Diff_MTM", "Diff_MTM_%"]
        merged[num_cols] = merged[num_cols].astype(float).round(2)

        # ✅ Drop duplicates that appear after merge
        merged = merged.drop_duplicates(subset=["User", "Symbol"], keep="first").reset_index(drop=True)

        total_row = {
            "User": "",
            "Strategy": "TOTAL",
            "Exchange": "",
            "Symbol": "",
            "Ser_Exp": "",
            "NetQty": merged["NetQty"].sum(),
            "NetVal": merged["NetVal"].sum(),
            "NetPrice": "",
            "Close": "",
            "LTP": "",
            "MTM": merged["MTM"].sum(),
            "MTM_%": (merged["MTM"].sum() / merged["NetVal"].sum() * 100) if merged["NetVal"].sum() else 0,
            "Diff_MTM": merged["Diff_MTM"].sum(),
            "Diff_MTM_%": (merged["Diff_MTM"].sum() / merged["NetVal"].sum() * 100) if merged["NetVal"].sum() else 0,
        }
        merged = pd.concat([merged, pd.DataFrame([total_row])], ignore_index=True)
        return merged

    # === Plot OHLC + Indicators + Volume ===

    def show_yfinance_chart(
            self,
            symbol: str,
            period: str = "6mo",
            interval: str = "1d",
            chart_type: str = "Candlestick",
            show_volume: bool = True,
            show_sma10: bool = False,
            show_sma20: bool = False,
            show_sma50: bool = False,
            show_sma100: bool = False,
            show_sma200: bool = False,
            show_rsi: bool = False,
            show_macd: bool = False
    ):
        try:
            # Try NSE → BSE → Global
            for suffix in [".NS", ".BO", ""]:
                data = yf.download(symbol + suffix, period=period, interval=interval, progress=False)
                if not data.empty:
                    break
            else:
                st.warning(f"⚠️ No data found for {symbol}")
                return

            # Normalize columns safely
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [str(col[0]).capitalize() for col in data.columns]
            else:
                data.columns = [str(col).capitalize() for col in data.columns]
            data = data.ffill().bfill()
            data.index = data.index.strftime("%Y-%m-%d")

            # === Add Indicators ===
            # SMAs
            if show_sma10: data["SMA10"] = data["Close"].rolling(10).mean()
            if show_sma20: data["SMA20"] = data["Close"].rolling(20).mean()
            if show_sma50: data["SMA50"] = data["Close"].rolling(50).mean()
            if show_sma100: data["SMA100"] = data["Close"].rolling(100).mean()
            if show_sma200: data["SMA200"] = data["Close"].rolling(200).mean()

            # RSI (14)
            if show_rsi:
                delta = data["Close"].diff()
                gain = np.where(delta > 0, delta, 0)
                loss = np.where(delta < 0, -delta, 0)
                avg_gain = pd.Series(gain).rolling(14).mean()
                avg_loss = pd.Series(loss).rolling(14).mean()
                rs = avg_gain / avg_loss
                data["RSI"] = 100 - (100 / (1 + rs))

            # MACD (12,26,9)
            if show_macd:
                exp1 = data["Close"].ewm(span=12, adjust=False).mean()
                exp2 = data["Close"].ewm(span=26, adjust=False).mean()
                data["MACD"] = exp1 - exp2
                data["Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()

            # === Create subplot layout ===
            rows = 1 + int(show_volume) + int(show_rsi) + int(show_macd)
            fig = make_subplots(
                rows=rows, cols=1, shared_xaxes=True,
                row_heights=[0.6] + [0.2] * (rows - 1),
                vertical_spacing=0.02
            )

            # === Price Chart ===
            if chart_type == "Candlestick":
                fig.add_trace(
                    go.Candlestick(
                        x=data.index,
                        open=data["Open"], high=data["High"], low=data["Low"], close=data["Close"],
                        name="Candles",
                        increasing_line_color="#00C853",  # bright green
                        decreasing_line_color="#D50000",  # red
                    ),
                    row=1, col=1
                )
            else:  # Bar chart
                colors = np.where(data["Close"] >= data["Open"], "#00C853", "#D50000")
                fig.add_trace(go.Bar(x=data.index, y=data["Close"], name="Price", marker_color=colors),
                              row=1, col=1)

            # === SMAs ===
            for sma_col, color in [
                ("SMA10", "#FFD700"), ("SMA20", "#00BFFF"), ("SMA50", "#FF69B4"),
                ("SMA100", "#FFA500"), ("SMA200", "#ADFF2F")
            ]:
                if sma_col in data.columns:
                    fig.add_trace(go.Scatter(x=data.index, y=data[sma_col], mode="lines",
                                             name=sma_col, line=dict(width=1.5, color=color)), row=1, col=1)

            # === Volume ===
            if show_volume:
                vol_colors = np.where(data["Close"] >= data["Open"], "#00C853", "#D50000")
                fig.add_trace(go.Bar(x=data.index, y=data["Volume"], marker_color=vol_colors,
                                     name="Volume", opacity=0.4), row=2, col=1)

            # === RSI ===
            if show_rsi:
                fig.add_trace(go.Scatter(x=data.index, y=data["RSI"], name="RSI",
                                         line=dict(color="#FFD700", width=1.5)),
                              row=rows - int(show_macd), col=1)
                fig.add_hline(y=70, line_dash="dot", line_color="#FF5555", row=rows - int(show_macd), col=1)
                fig.add_hline(y=30, line_dash="dot", line_color="#55FF55", row=rows - int(show_macd), col=1)

            # === MACD ===
            if show_macd:
                fig.add_trace(go.Scatter(x=data.index, y=data["MACD"], name="MACD",
                                         line=dict(color="#00BFFF", width=1.5)), row=rows, col=1)
                fig.add_trace(go.Scatter(x=data.index, y=data["Signal"], name="Signal",
                                         line=dict(color="#FFB6C1", width=1)), row=rows, col=1)

            # === Final Layout ===
            fig.update_layout(
                template="plotly_dark",
                title=f"📈 {symbol} - {chart_type} ({period}, {interval})",
                height=850,
                margin=dict(l=20, r=20, t=50, b=20),
                showlegend=False,
                hovermode="x unified",  # 🔥 TradingView-style crosshair
                plot_bgcolor="#000000",
                paper_bgcolor="#000000",
                xaxis_rangeslider_visible=False,
                xaxis=dict(type="category", showgrid=False, linecolor="#444", tickangle=-45),
                yaxis=dict(showgrid=False, linecolor="#444", zeroline=False),
                font=dict(family="Cambria", size=14, color="#DDD"),
            )

            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"❌ Chart Error: {e}")

    # === Main Dashboard ===
    def run(self):
        if not self.csv_path:
            st.info("👆 Upload your Google CSV to start.")
            return

        df_csv = pd.read_csv(self.csv_path)
        df_tsv = self.load_local_file()
        merged = self.merge_and_adjust(df_tsv, df_csv)

        # === Sidebar Filters ===
        st.sidebar.header("🧭 Filters", divider="rainbow")
        unique_strategies = sorted(merged["Strategy"].dropna().unique().tolist())
        unique_clients = sorted(merged["User"].dropna().unique().tolist())

        selected_strategy = st.sidebar.multiselect(
            "Select Strategy",
            options=unique_strategies,
            default=st.session_state.get("selected_strategy", unique_strategies),
        )
        st.session_state["selected_strategy"] = selected_strategy

        selected_client = st.sidebar.multiselect(
            "Select Client",
            options=unique_clients,
            default=st.session_state.get("selected_client", unique_clients),
        )
        st.session_state["selected_client"] = selected_client

        # === Apply Filters ===
        filtered = merged[
            (merged["Strategy"].isin(selected_strategy)) &
            (merged["User"].isin(selected_client))
        ]

        # ✅ Keep TOTAL in table but not in card totals
        table_df = filtered.copy()
        calc_df = filtered[filtered["Strategy"] != "TOTAL"]

        # === Totals (from calc_df only) ===
        total_holding = calc_df["NetVal"].sum()
        total_mtm = calc_df["MTM"].sum()
        total_mtm_pct = (total_mtm / total_holding * 100) if total_holding else 0
        total_diff_mtm = calc_df["Diff_MTM"].sum()
        total_diff_mtm_pct = (total_diff_mtm / total_holding * 100) if total_holding else 0

        # === Global Font Style ===
        # === Remove excess top padding (but keep title visible) ===
        st.markdown("""
            <style>
                /* Reduce but don't completely remove Streamlit top padding */
                .block-container {
                    padding-top: 0.5rem !important;
                }
                /* Adjust page background alignment */
                header {visibility: hidden;}  /* hides Streamlit default header bar */
            </style>
        """, unsafe_allow_html=True)

        # === Helper: Color Card Values ===
        def color_for_value(val):
            if pd.isna(val): return "#808080"
            if val > 0: return "#2ecc71"  # green
            if val < 0: return "#e74c3c"  # red
            return "#bdc3c7"

        def metric_card(title, value, suffix=""):
            color = color_for_value(value)
            display_val = f"{value:,.2f}{suffix}" if isinstance(value, (int, float)) else value

            st.markdown(f"""
                <div style="
                    background-color:#111;
                    padding:10px 8px;              /* 🔹 reduced padding for compact look */
                    border-radius:8px;
                    text-align:center;
                    box-shadow:0px 0px 6px rgba(255,255,255,0.05);
                    font-family:Cambria;
                    min-height:70px;               /* 🔹 smaller card height */
                    display:flex;
                    flex-direction:column;
                    justify-content:center;
                ">
                    <h5 style="color:#aaa;margin:0 0 3px 0;font-size:14px;font-weight:600;">{title}</h5>
                    <h3 style="color:{color};margin:0;font-size:18px;font-weight:700;">{display_val}</h3>
                </div>
            """, unsafe_allow_html=True)

        # === Remove Top Padding from Streamlit Page ===
        st.markdown("""
            <style>
                .block-container {
                    padding-top: 0rem !important;
                }
            </style>
        """, unsafe_allow_html=True)

        # === Dashboard Title ===
        st.markdown("""
            <h1 style='font-family:Cambria;text-align:center;margin-bottom:6px;font-size:32px;'>
                📊 Live MTM Dashboard
            </h1>
        """, unsafe_allow_html=True)

        # === Last Updated Text ===
        st.markdown(
            f"<p style='text-align:center;color:#aaa;font-family:Cambria;font-size:14px;margin-top:-5px;'>"
            f"⏱️ Last Updated: {datetime.now().strftime('%H:%M:%S')}</p>",
            unsafe_allow_html=True
        )

        # === Compact Metric Cards (20% smaller, same font) ===
        def metric_card(title, value, suffix=""):
            color = color_for_value(value)
            display_val = f"{value:,.2f}{suffix}" if isinstance(value, (int, float)) else value

            st.markdown(f"""
                <div style="
                    background-color:#111;
                    padding:7px 5px;               /* Reduced padding */
                    border-radius:6px;             /* Slightly smaller corners */
                    text-align:center;
                    box-shadow:0px 0px 6px rgba(255,255,255,0.04);
                    font-family:Cambria;
                    min-height:58px;               /* Smaller height */
                    display:flex;
                    flex-direction:column;
                    justify-content:center;
                ">
                    <h5 style="color:#aaa;margin:0 0 3px 0;font-size:14px;font-weight:600;">{title}</h5>
                    <h3 style="color:{color};margin:0;font-size:18px;font-weight:700;">{display_val}</h3>
                </div>
            """, unsafe_allow_html=True)

        # === Metric Row (Compact) ===
        st.markdown("<div style='margin-bottom:4px;'></div>", unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns(5, gap="small")
        with c1:
            metric_card("💰 Holding Value", total_holding)
        with c2:
            metric_card("📈 MTM", total_mtm)
        with c3:
            metric_card("📊 MTM %", total_mtm_pct, "%")
        with c4:
            metric_card("⚖️ Diff MTM", total_diff_mtm)
        with c5:
            metric_card("📉 Diff MTM %", total_diff_mtm_pct, "%")
        st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)

        # === Remember active tab ===
        if "active_tab" not in st.session_state:
            st.session_state["active_tab"] = "Portfolio"

        tab_labels = ["👥 User Portfolio View", "📊 Trading Chart","📋 Portfolio Table"]

        # === Tab Selector (persistent across reruns) ===
        selected_tab = st.radio(
            "",
            tab_labels,
            horizontal=True,
            index=tab_labels.index("📊 Trading Chart") if st.session_state["active_tab"] == "Chart" else 0,
            key="tab_selector",
        )
        # Save active tab
        if selected_tab == "📋 Portfolio Table":
            st.session_state["active_tab"] = "Portfolio"
        elif selected_tab == "📊 Trading Chart":
            st.session_state["active_tab"] = "Chart"
        else:
            st.session_state["active_tab"] = "UserStrategy"

        # === Portfolio Table Tab ===
        if st.session_state["active_tab"] == "Portfolio":
            st.markdown("<h4 style='text-align:center;font-family:Cambria;'>📋 Portfolio Table</h4>", unsafe_allow_html=True)

            # === Highlight TOTAL row visually ===
            def highlight_total(row):
                if row["Strategy"] == "TOTAL":
                    return ['background-color: #333333; font-weight: bold; color: white; text-align: center;' for _ in row]
                return ['text-align: center;' for _ in row]

            # === Conditional Color Function for MTM columns ===
            def highlight_mtm_values(val):
                """Color code positive/negative values in MTM-related columns."""
                try:
                    if pd.isna(val):
                        return "text-align: center;"
                    val = float(val)
                    if val > 0:
                        return "background-color: #0074D9; color: white; font-weight: bold; text-align: center;"  # Blue
                    elif val < 0:
                        return "background-color: #FF4136; color: white; font-weight: bold; text-align: center;"  # Red
                    else:
                        return "text-align: center;"
                except Exception:
                    return "text-align: center;"

            # === Styled DataFrame ===
            styled_df = (
                table_df.style
                .apply(highlight_total, axis=1)  # highlight TOTAL row
                .applymap(highlight_mtm_values, subset=["MTM", "MTM_%", "Diff_MTM", "Diff_MTM_%"])  # color rule
                .format(precision=2)
                .set_table_styles([
                    {"selector": "th", "props": [
                        ("text-align", "center"),
                        ("font-family", "Cambria"),
                        ("font-size", "16px"),
                        ("color", "white"),
                        ("background-color", "#222")
                    ]}
                ])
                .set_properties(**{
                    "text-align": "center",
                    "font-family": "Cambria",
                    "font-size": "14px",
                    "border": "1px solid #333",
                })
            )

            # === Show the styled table ===
            st.dataframe(styled_df, use_container_width=True)

        # === Trading Chart Tab ===
        elif st.session_state["active_tab"] == "Chart":
            st.markdown("<h4 style='text-align:center;font-family:Cambria;font-size:18px;'>📋 Portfolio Table</h4>", unsafe_allow_html=True)

            # --- Compact Filter Row ---
            c1, c2, c3, c4, c5 = st.columns([2.5, 1, 1, 1, 1])
            symbols = [s for s in calc_df["Symbol"].unique().tolist() if s not in ["", "TOTAL"]]

            with c1:
                st.markdown(
                    "<div style='text-align:center;font-size:14px;font-family:Cambria;'>Select or Enter Symbol</div>",
                    unsafe_allow_html=True)
                selected_symbol = st.selectbox("", ["-- Select from Portfolio --"] + symbols, index=0,
                                               label_visibility="collapsed", key="symbol_selector")
                manual_symbol = st.text_input("", "", placeholder="Type manually (e.g., RELIANCE, AAPL, BTC-USD)",
                                              label_visibility="collapsed", key="manual_symbol").strip().upper()
                symbol_to_chart = manual_symbol if manual_symbol else (
                    selected_symbol if selected_symbol != "-- Select from Portfolio --" else None)

            with c2:
                st.markdown("<div style='text-align:center;font-size:14px;font-family:Cambria;'>Chart Period</div>",
                            unsafe_allow_html=True)
                period = st.selectbox("", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd"], index=2,
                                      label_visibility="collapsed")

            with c3:
                st.markdown("<div style='text-align:center;font-size:14px;font-family:Cambria;'>Candle Interval</div>",
                            unsafe_allow_html=True)
                interval = st.selectbox("", ["1d", "1h", "30m", "15m"], index=0, label_visibility="collapsed")

            with c4:
                st.markdown("<div style='text-align:center;font-size:14px;font-family:Cambria;'>Chart Type</div>",
                            unsafe_allow_html=True)
                chart_type = st.selectbox("", ["Candlestick", "Bar"], index=0, label_visibility="collapsed")

            with c5:
                st.markdown("<div style='text-align:center;font-size:14px;font-family:Cambria;'>Volume</div>",
                            unsafe_allow_html=True)
                show_volume = st.toggle("Show", value=True, key="toggle_volume_main")

            st.markdown("<hr style='margin:5px 0;'>", unsafe_allow_html=True)

            # === Chart Settings Compact Grid ===
            with st.expander("⚙️ Chart Settings (Indicators)", expanded=False):
                st.markdown(
                    "<div style='text-align:center;font-family:Cambria;font-size:15px;'>Toggle Indicators</div>",
                    unsafe_allow_html=True)
                col_set1, col_set2, col_set3, col_set4 = st.columns(4)

                with col_set1:
                    show_sma10 = st.toggle("SMA 10", False, key="toggle_sma10")
                    show_sma20 = st.toggle("SMA 20", False, key="toggle_sma20")

                with col_set2:
                    show_sma50 = st.toggle("SMA 50", False, key="toggle_sma50")
                    show_sma100 = st.toggle("SMA 100", False, key="toggle_sma100")

                with col_set3:
                    show_sma200 = st.toggle("SMA 200", False, key="toggle_sma200")
                    show_rsi = st.toggle("RSI (14)", False, key="toggle_rsi")

                with col_set4:
                    show_macd = st.toggle("MACD (12,26,9)", False, key="toggle_macd")

            # === Render Chart ===
            if symbol_to_chart:
                st.session_state["active_tab"] = "Chart"
                with st.spinner(f"📈 Fetching chart for {symbol_to_chart}..."):
                    self.show_yfinance_chart(
                        symbol_to_chart, period, interval, chart_type,
                        show_volume, show_sma10, show_sma20, show_sma50,
                        show_sma100, show_sma200, show_rsi, show_macd
                    )
            else:
                st.info("🔎 Please select or enter a symbol to view its chart.")

        # === TAB 3: User Portfolio View ===
        elif st.session_state["active_tab"] == "UserStrategy":
            st.markdown("<h4 style='text-align:center;font-family:Cambria;'>👥 User Portfolio View</h4>",
                        unsafe_allow_html=True)

            # --- Unique Users ---
            users = sorted([u for u in merged["User"].dropna().unique() if u.strip() != ""])

            if not users:
                st.warning("⚠️ No users found in the dataset.")
            else:
                # === User Selector ===
                selected_user = st.selectbox("Select User", ["All Users"] + users, index=0)

                # === Filter by User ===
                if selected_user == "All Users":
                    filtered_user_df = merged[merged["Strategy"] != "TOTAL"].copy()
                else:
                    filtered_user_df = merged[
                        (merged["User"] == selected_user) & (merged["Strategy"] != "TOTAL")
                        ].copy()

                # === Recalculate summary totals (for cards) ===
                total_holding = filtered_user_df["NetVal"].sum()
                total_mtm = filtered_user_df["MTM"].sum()
                total_mtm_pct = (total_mtm / total_holding * 100) if total_holding else 0
                total_diff_mtm = filtered_user_df["Diff_MTM"].sum()
                total_diff_mtm_pct = (total_diff_mtm / total_holding * 100) if total_holding else 0

                # === Top summary cards ===
                st.markdown("<br>", unsafe_allow_html=True)
                c1, c2, c3, c4, c5 = st.columns(5)
                with c1:
                    metric_card("💰 Holding Value", total_holding)
                with c2:
                    metric_card("📈 MTM", total_mtm)
                with c3:
                    metric_card("📊 MTM %", total_mtm_pct, "%")
                with c4:
                    metric_card("⚖️ Diff MTM", total_diff_mtm)
                with c5:
                    metric_card("📉 Diff MTM %", total_diff_mtm_pct, "%")
                st.markdown("---")
                # ✅ Always show all user tables
                grouped = merged[merged["Strategy"] != "TOTAL"].groupby("User")

                user_tables = list(grouped)

                # === Styling helpers ===
                def highlight_total(row):
                    """Highlight the TOTAL row."""
                    if str(row["Symbol"]).upper() == "TOTAL":
                        return ["background-color: #222; color: white; font-weight: bold; text-align: center;"] * len(
                            row)
                    return ["text-align: center;"] * len(row)

                def color_mtm(val):
                    """Green for +, Red for - in MTM / Diff MTM columns."""
                    try:
                        if pd.isna(val): return "text-align:center;"
                        val = float(val)
                        if val > 0:
                            return "color:#00FF7F; font-weight:bold; text-align:center;"
                        elif val < 0:
                            return "color:#FF4444; font-weight:bold; text-align:center;"
                        else:
                            return "text-align:center;"
                    except Exception:
                        return "text-align:center;"

                # === Display collapsible tables in 2-column layout ===
                for i in range(0, len(user_tables), 2):
                    col1, col2 = st.columns(2)

                    # --- Left user table ---
                    user1, df1 = user_tables[i]
                    df1 = df1[["Symbol", "NetVal", "NetQty", "NetPrice", "MTM", "Diff_MTM"]].sort_values(by="MTM",
                                                                                                         ascending=False)

                    # ✅ Add total summary row
                    total_row = pd.DataFrame([{
                        "Symbol": "TOTAL",
                        "NetVal": df1["NetVal"].sum(),
                        "NetQty": df1["NetQty"].sum(),
                        "NetPrice": "",
                        "MTM": df1["MTM"].sum(),
                        "Diff_MTM": df1["Diff_MTM"].sum()
                    }])

                    # Combine table + total
                    df1 = pd.concat([df1, total_row], ignore_index=True)

                    with col1:
                        total_mtm_user = df1["MTM"].iloc[:-1].sum()
                        total_diff_user = df1["Diff_MTM"].iloc[:-1].sum()
                        with st.expander(f"👤 {user1} — MTM ₹{total_mtm_user:,.0f} | Diff ₹{total_diff_user:,.0f}",
                                         expanded=False):

                            def safe_fmt(val, fmt="{:,.2f}"):
                                try:
                                    return fmt.format(float(val))
                                except:
                                    return val  # leave as-is if not numeric

                            styled_df1 = (
                                df1.style
                                .apply(highlight_total, axis=1)
                                .applymap(color_mtm, subset=["MTM", "Diff_MTM"])
                                .format({
                                    "NetVal": lambda x: safe_fmt(x, "{:,.0f}"),
                                    "NetQty": lambda x: safe_fmt(x, "{:,.0f}"),
                                    "NetPrice": lambda x: safe_fmt(x, "{:,.2f}"),
                                    "MTM": lambda x: safe_fmt(x, "{:,.2f}"),
                                    "Diff_MTM": lambda x: safe_fmt(x, "{:,.2f}")
                                })
                                .set_properties(**{
                                    "font-family": "Cambria",
                                    "font-size": "16px",
                                    "border": "1px solid #333",
                                    "text-align": "center"
                                })
                            )
                            st.dataframe(styled_df1, use_container_width=True, height=360)

                    # --- Right user table ---
                    if i + 1 < len(user_tables):
                        user2, df2 = user_tables[i + 1]
                        df2 = df2[["Symbol", "NetVal", "NetQty", "NetPrice", "MTM", "Diff_MTM"]].sort_values(by="MTM",
                                                                                                             ascending=False)

                        # ✅ Add total summary row
                        total_row2 = pd.DataFrame([{
                            "Symbol": "TOTAL",
                            "NetVal": df2["NetVal"].sum(),
                            "NetQty": df2["NetQty"].sum(),
                            "NetPrice": "",
                            "MTM": df2["MTM"].sum(),
                            "Diff_MTM": df2["Diff_MTM"].sum()
                        }])

                        # Combine table + total
                        df2 = pd.concat([df2, total_row2], ignore_index=True)

                        with col2:
                            total_mtm_user2 = df2["MTM"].iloc[:-1].sum()
                            total_diff_user2 = df2["Diff_MTM"].iloc[:-1].sum()
                            with st.expander(f"👤 {user2} — MTM ₹{total_mtm_user2:,.0f} | Diff ₹{total_diff_user2:,.0f}",
                                             expanded=False):

                                def safe_fmt(val, fmt="{:,.2f}"):
                                    try:
                                        return fmt.format(float(val))
                                    except:
                                        return val  # leave as-is if not numeric

                                styled_df2 = (
                                    df2.style
                                    .apply(highlight_total, axis=1)
                                    .applymap(color_mtm, subset=["MTM", "Diff_MTM"])
                                    .format({
                                        "NetVal": lambda x: safe_fmt(x, "{:,.0f}"),
                                        "NetQty": lambda x: safe_fmt(x, "{:,.0f}"),
                                        "NetPrice": lambda x: safe_fmt(x, "{:,.2f}"),
                                        "MTM": lambda x: safe_fmt(x, "{:,.2f}"),
                                        "Diff_MTM": lambda x: safe_fmt(x, "{:,.2f}")
                                    })
                                    .set_properties(**{
                                        "font-family": "Cambria",
                                        "font-size": "13px",
                                        "border": "1px solid #333",
                                        "text-align": "center"
                                    })
                                )
                                st.dataframe(styled_df2, use_container_width=True, height=360)

        # === Auto Refresh ===
        st.sidebar.markdown("---")
        refresh_time = st.sidebar.slider("⏱️ Auto-Refresh (seconds)", 0, 60, 0)
        if refresh_time:
            st.experimental_rerun()



import streamlit as st
import json, os, hashlib
import pandas as pd
from datetime import datetime

# ====================== 🔐 LOGIN SYSTEM ======================
USERS_FILE = "users.json"
ADMIN_USER = "Harshal_admin"
ADMIN_PASS = "Admin.1221"
ADMIN_HASH = hashlib.sha256(ADMIN_PASS.encode()).hexdigest()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# Load or init users
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f:
        try:
            USERS = json.load(f)
        except:
            USERS = {}
else:
    USERS = {}

# Ensure admin exists
if (ADMIN_USER not in USERS) or (USERS[ADMIN_USER]["password"] != ADMIN_HASH):
    USERS[ADMIN_USER] = {
        "password": ADMIN_HASH,
        "role": "admin",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(USERS_FILE, "w") as f:
        json.dump(USERS, f, indent=4)


def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(USERS, f, indent=4)


# Session
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["role"] = None

# ====================== 🔑 LOGIN SCREEN ======================
if not st.session_state["authenticated"]:
    st.set_page_config(page_title="🔒 Login - Live MTM Dashboard", layout="centered")

    st.markdown("""
        <h2 style='text-align:center;font-family:Cambria;'>🔐 Secure Login</h2>
        <p style='text-align:center;color:#aaa;'>Enter your username and password</p>
    """, unsafe_allow_html=True)

    username = st.text_input("👤 Username")
    password = st.text_input("🔑 Password", type="password")
    if st.button("Login"):
        if username in USERS and USERS[username]["password"] == hash_password(password):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.session_state["role"] = USERS[username].get("role", "user")
            st.success(f"✅ Welcome, {username}!")
            st.rerun()
        else:
            st.error("❌ Invalid username or password.")

# ====================== AFTER LOGIN ======================
else:
    st.sidebar.markdown(
        f"<p style='font-family:Cambria;color:#aaa;'>👤 Logged in as: <b>{st.session_state['username']}</b> "
        f"({st.session_state['role'].capitalize()})</p>",
        unsafe_allow_html=True
    )

    # Logout
    if st.sidebar.button("🚪 Logout"):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.session_state["role"] = None
        st.rerun()

    # ============ ADMIN PANEL ============
    if st.session_state["username"] == ADMIN_USER:
        st.markdown("""
            <h2 style='text-align:center;color:#00BFFF;font-family:Cambria;'>⚙️ Admin Panel</h2>
        """, unsafe_allow_html=True)

        _, col, _ = st.columns([1, 2, 1])
        with col:
            action = st.radio("", ["➕ Add User", "♻️ Reset Password", "❌ Remove User", "👥 View Users"], horizontal=True)
            st.markdown("---")

            if action == "➕ Add User":
                new_user = st.text_input("👤 New Username")
                new_pass = st.text_input("🔑 Password", type="password")
                if st.button("Create User"):
                    if not new_user or not new_pass:
                        st.warning("⚠️ Fields cannot be empty.")
                    elif new_user in USERS:
                        st.warning("⚠️ User already exists.")
                    else:
                        USERS[new_user] = {
                            "password": hash_password(new_pass),
                            "role": "user",
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        save_users()
                        st.success(f"✅ User '{new_user}' created!")

            elif action == "♻️ Reset Password":
                user_sel = st.selectbox("Select user", [u for u in USERS.keys() if u != ADMIN_USER])
                new_pass = st.text_input("New Password", type="password")
                if st.button("Reset"):
                    USERS[user_sel]["password"] = hash_password(new_pass)
                    save_users()
                    st.success(f"Password reset for {user_sel}")

            elif action == "❌ Remove User":
                user_sel = st.selectbox("Select user", [u for u in USERS.keys() if u != ADMIN_USER])
                if st.button("Delete User"):
                    USERS.pop(user_sel)
                    save_users()
                    st.success(f"User '{user_sel}' deleted")
                    st.rerun()

            elif action == "👥 View Users":
                df = pd.DataFrame([
                    {"Username": u, "Role": info.get("role", "user"), "Created": info.get("created_at")}
                    for u, info in USERS.items()
                ])
                st.dataframe(df, use_container_width=True)

    # ================= DEMO CSV + UPLOAD =================
    st.sidebar.markdown("---")
    st.sidebar.subheader("📂 Upload Portfolio CSV")

    # Demo CSV to download
    demo_data = pd.DataFrame({
        "User": ["12345", "B2005"],
        "Symbol": ["TCS", "INFY"],
        "Exchange": ["NSE", "NSE"],
        "Ser_Exp": ["EQ", "EQ"],
        "NetQty": [100, 50],
        "NetVal": [325000, 190000],
        "Nse_close": [3250.5, 3799.3],
        "Strategy": ["Chart", "Chart"]
    })
    st.sidebar.download_button("⬇️ Download Demo CSV", demo_data.to_csv(index=False), "demo_portfolio.csv")

    # Upload CSV
    uploaded_csv = st.sidebar.file_uploader("Choose file", type=["csv"])

    if not uploaded_csv:
        st.info("👆 Please upload your portfolio CSV file to view dashboard.")
        st.stop()

    # ✅ Run your LiveMTMDashboard class after file upload
    import pandas as pd
    import io

    try:
        # Make a fresh copy of uploaded file before reading
        uploaded_bytes = uploaded_csv.getvalue()

        # 1️⃣ Try reading it once for validation
        df_test = pd.read_csv(io.BytesIO(uploaded_bytes))
        if df_test.empty:
            st.error("⚠️ Uploaded CSV is empty. Please check file content.")
            st.stop()

        # 2️⃣ Now give a fresh copy to dashboard
        csv_copy = io.BytesIO(uploaded_bytes)

        # Create dashboard instance
        app = LiveMTMDashboard()
        app.csv_path = csv_copy  # give the copy so it's readable inside class
        app.run()

    except pd.errors.EmptyDataError:
        st.error("⚠️ Uploaded file is empty or invalid CSV format.")
    except pd.errors.ParserError:
        st.error("⚠️ Unable to parse CSV. Please check the file format (comma-separated).")
    except Exception as e:
        st.error(f"⚠️ Error running dashboard: {e}")

