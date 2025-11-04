
import pandas as pd
import os
import time
import threading
from datetime import datetime
from tradingview_screener import Query
import plotly.graph_objects as go
import streamlit as st

# === CONFIG ===
google_csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQyY0N1hFIGML56I49kSRPWd7loDPQsa284rBn6o902zphvLQmtda5Rh76dCEm-3SjL3at9F2SVSltE/pub?gid=0&single=true&output=csv"
base_dir = r"C:\Users\freedom\Desktop\ORDER B005\backup\GETS_FILES\GETS_EXCEL"
file_name = "NetPositionAutoBackup.xls"
refresh_interval = 5  # seconds

# === GLOBALS ===
df_final = pd.DataFrame()
df_history = pd.DataFrame(columns=['Time', 'MTM', 'Diff_MTM', 'MTM %', 'Diff_MTM %'])
stop_flag = False


# === LOAD LOCAL & GOOGLE DATA ===
def load_data(load_google=False):
    today_folder = datetime.now().strftime("%d%b")
    folder_path = os.path.join(base_dir, today_folder)
    file_path = os.path.join(folder_path, file_name)

    try:
        df_local = pd.read_csv(file_path, sep="\t", engine="python")
        df_local.columns = df_local.columns.str.strip().str.replace(" ", "_")
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
    except Exception:
        df_local = pd.DataFrame()

    if not load_google:
        return df_local, pd.DataFrame()

    try:
        df_google = pd.read_csv(google_csv_url, header=0, skiprows=range(1, 6))
        df_google.columns = df_google.columns.str.strip().str.replace(" ", "_")
        df_google.dropna(subset=["User", "Symbol"], inplace=True)

        for col in ["BuyQty", "BuyVal", "SellQty", "SellVal", "NetQty", "NetVal", "NetPrice", "Nse_close"]:
            if col in df_google.columns:
                df_google[col] = pd.to_numeric(df_google[col], errors="coerce").fillna(0)

        df_google = (
            df_google.groupby(["User", "Symbol"], as_index=False)
            .agg({
                "Exchange": "first", "Ser_Exp": "first",
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
    except Exception:
        df_google = pd.DataFrame()

    return df_local, df_google


# === MERGE DATA ===
def merge_local_google(df_local, df_google):
    if df_google.empty:
        return df_local
    if df_local.empty:
        return df_google

    merged = pd.concat([df_local, df_google], ignore_index=True)
    merged = (
        merged.groupby(["User", "Symbol"], as_index=False)
        .agg({
            "Exchange": "first", "Ser_Exp": "first",
            "BuyQty": "sum", "BuyVal": "sum",
            "SellQty": "sum", "SellVal": "sum",
            "NetQty": "sum", "NetVal": "sum",
            "CumStrategy": "first"
        })
    )
    merged["NetPrice"] = merged["NetVal"] / merged["NetQty"].replace(0, pd.NA)
    return merged[merged["NetQty"] != 0].reset_index(drop=True)


# === FETCH LTP ===
def fetch_ltp(symbols):
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
            .drop_duplicates("Symbol")
        )
        return tv_data[tv_data["Symbol"].isin(symbols)][["Symbol", "LTP"]]
    except Exception:
        return pd.DataFrame(columns=["Symbol", "LTP"])


# === BACKGROUND REFRESH THREAD ===
def data_refresh():
    global df_final, df_history, stop_flag
    _, df_google = load_data(load_google=True)
    df_local, df_google = load_data(load_google=True)

    while not stop_flag:
        df_local, _ = load_data(load_google=False)  # only local refresh
        df = merge_local_google(df_local, df_google)

        if not df.empty:
            symbols = df["Symbol"].dropna().unique().tolist()
            df_ltp = fetch_ltp(symbols)
            df = df.merge(df_ltp, on="Symbol", how="left")
            df = df.merge(
                df_google[["Symbol", "Nse_close", "NetQty", "NetVal"]],
                on="Symbol",
                how="left",
                suffixes=("", "_google")
            )
            df["Close"] = df["Nse_close"].fillna(0)
            df["MTM"] = (df["LTP"] - df["NetPrice"]) * df["NetQty"]
            df["MTM %"] = (df["MTM"] / df["NetVal"].replace(0, pd.NA)) * 100
            df["Diff_MTM"] = (df["LTP"] - df["Close"]) * df["NetQty_google"].fillna(0)
            df["Diff_MTM %"] = (df["Diff_MTM"] / df["NetVal_google"].replace(0, pd.NA)) * 100

            df_final = df

            now = datetime.now()
            if 9 <= now.hour <= 20:
                total_mtm = df["MTM"].sum()
                total_diff_mtm = df["Diff_MTM"].sum()
                total_netval = df["NetVal"].sum()

                mtm_pct = (total_mtm / total_netval * 100) if total_netval != 0 else 0
                diff_mtm_pct = (total_diff_mtm / total_netval * 100) if total_netval != 0 else 0

                df_history = pd.concat([
                    df_history,
                    pd.DataFrame([{
                        'Time': now.strftime("%H:%M:%S"),
                        'MTM': round(total_mtm, 2),
                        'Diff_MTM': round(total_diff_mtm, 2),
                        'MTM %': round(mtm_pct, 2),
                        'Diff_MTM %': round(diff_mtm_pct, 2)
                    }])
                ])
        time.sleep(refresh_interval)


# === STREAMLIT UI ===
st.set_page_config(page_title="📊 Live MTM Dashboard", layout="wide")
st.title("📊 Live MTM Dashboard")

tab_dashboard, tab_user, tab_strategy = st.tabs(["📈 Dashboard", "👤 User Summary", "📊 Strategy Stats"])

# Start thread once
if "started" not in st.session_state:
    threading.Thread(target=data_refresh, daemon=True).start()
    st.session_state.started = True

with tab_dashboard:
    st.subheader("📊 Live Portfolio Overview")

    if df_final.empty:
        st.info("⏳ Loading data... Please wait for first refresh.")
        st.stop()

    # 🔧 Normalize column names (handles "Net Val", "Net_Val", etc.)
    df_display = df_final.copy()
    df_display.columns = (
        df_display.columns.fillna("Unnamed")
        .astype(str)
        .str.strip()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    # 🧠 Ensure required columns exist
    required_cols = ["NetVal", "MTM", "Diff_MTM"]
    for col in required_cols:
        if col not in df_display.columns:
            st.warning(f"⚠️ Missing column: {col}. Waiting for valid data refresh.")
            st.stop()

    # 🧮 Compute totals safely
    total_netval = df_display["NetVal"].sum() if "NetVal" in df_display else 0
    total_mtm = df_display["MTM"].sum() if "MTM" in df_display else 0
    total_diff = df_display["Diff_MTM"].sum() if "Diff_MTM" in df_display else 0

    mtm_pct = (total_mtm / total_netval * 100) if total_netval != 0 else 0
    diff_mtm_pct = (total_diff / total_netval * 100) if total_netval != 0 else 0

    # 💡 Dashboard metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Holding Value", f"{total_netval:,.2f}")
    col2.metric("MTM", f"{total_mtm:,.2f}")
    col3.metric("MTM %", f"{mtm_pct:.2f}%")
    col4.metric("Diff MTM", f"{total_diff:,.2f}")
    col5.metric("Diff MTM %", f"{diff_mtm_pct:.2f}%")

    # 📋 Show live data
    st.dataframe(df_display, use_container_width=True)

    if not df_history.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_history["Time"], y=df_history["MTM"], mode='lines', name='MTM'))
        fig.add_trace(go.Scatter(x=df_history["Time"], y=df_history["Diff_MTM"], mode='lines', name='Diff MTM'))
        fig.update_layout(template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Waiting for market time (9:15–15:30)...")

with tab_user:
    if df_final.empty:
        st.info("No data yet.")
    else:
        users = sorted(df_final["User"].unique())
        user = st.selectbox("Select User", users)
        df_user = df_final[df_final["User"] == user]
        st.dataframe(df_user, use_container_width=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_user["Symbol"], y=df_user["MTM"], name="MTM"))
        fig.add_trace(go.Bar(x=df_user["Symbol"], y=df_user["Diff_MTM"], name="Diff MTM"))
        fig.update_layout(barmode="group", template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab_strategy:
    if df_final.empty:
        st.info("No data yet.")
    else:
        strats = sorted(df_final["CumStrategy"].unique())
        strat = st.selectbox("Select Strategy", strats)
        df_strat = df_final[df_final["CumStrategy"] == strat]
        st.dataframe(df_strat, use_container_width=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_strat["Symbol"], y=df_strat["MTM"], mode="lines+markers", name="MTM"))
        fig.add_trace(go.Scatter(x=df_strat["Symbol"], y=df_strat["Diff_MTM"], mode="lines+markers", name="Diff MTM"))
        fig.update_layout(template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)

import os
import sys
import webbrowser
import time

if __name__ == "__main__":
    # 🟢 Detect if we're not already inside Streamlit
    if not any("streamlit" in arg for arg in sys.argv):
        script_path = os.path.abspath(__file__)


        # 🌐 Auto open browser link after 2 seconds
        def open_browser():
            time.sleep(2)
            webbrowser.open("http://localhost:8501")


        import threading

        threading.Thread(target=open_browser).start()

        # 🚀 Run Streamlit automatically
        os.system(f'python -m streamlit run "{script_path}"')
        sys.exit()
