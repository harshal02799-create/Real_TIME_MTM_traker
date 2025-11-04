import pandas as pd, os, time
from datetime import datetime
from tradingview_screener import Query
import streamlit as st

# === CONFIG ===
base_dir = r"C:\Users\freedom\Desktop\ORDER B005\backup\GETS_FILES\GETS_EXCEL"
file_name = "NetPositionAutoBackup.xls"
refresh_interval = 5  # seconds
csv_path = st.sidebar.file_uploader("📂 Upload your Google CSV file", type=["csv"])

# === Functions ===
def load_local_file():
    folder = os.path.join(base_dir, datetime.now().strftime("%d%b"))
    fpath = os.path.join(folder, file_name)
    if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
        try:
            return pd.read_excel(fpath, engine="xlrd")
        except Exception:
            return pd.read_csv(fpath, sep="\t", engine="python")
    return pd.DataFrame()


def merge_local_csv(df_tsv, df_csv):
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

    if df_tsv.empty:
        merged_df = df_csv.copy()
    else:
        merged_df = pd.concat([df_csv, df_tsv], ignore_index=True)
        merged_df = merged_df.sort_values(["User", "Symbol"]).reset_index(drop=True)
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

@st.cache_data(ttl=10)
def fetch_ltp(symbols_needed):
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

def merge_and_adjust(df_tsv, df_csv):
    merged = merge_local_csv(df_tsv, df_csv)
    if "Nse_close" not in df_csv.columns:
        df_csv["Nse_close"] = 0
    close_map = df_csv[["Symbol", "Nse_close"]].rename(columns={"Nse_close": "Close"})
    merged = pd.merge(merged, close_map, on="Symbol", how="left").fillna({"Close": 0})

    symbols = merged["Symbol"].dropna().unique().tolist()
    ltp_df = fetch_ltp(symbols)
    merged = pd.merge(merged, ltp_df, on="Symbol", how="left").fillna({"LTP": 0})

    merged["MTM"] = (merged["LTP"] - merged["NetPrice"]) * merged["NetQty"]
    merged["MTM_%"] = merged.apply(lambda r: (r["MTM"] / r["NetVal"] * 100) if r["NetVal"] else 0, axis=1)
    merged["Diff_MTM"] = (merged["LTP"] - merged["Close"]) * merged["NetQty"]
    merged["Diff_MTM_%"] = merged.apply(lambda r: (r["Diff_MTM"] / r["NetVal"] * 100) if r["NetVal"] else 0, axis=1)

    num_cols = ["NetQty", "NetVal", "NetPrice", "Close", "LTP", "MTM", "MTM_%", "Diff_MTM", "Diff_MTM_%"]
    merged[num_cols] = merged[num_cols].astype(float).round(2)

    # === Add total row ===
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

    # === Reorder columns ===
    col_order = [
        "User", "Strategy", "Exchange", "Symbol", "Ser_Exp",
        "NetQty", "NetVal", "NetPrice", "Close", "LTP",
        "MTM", "MTM_%", "Diff_MTM", "Diff_MTM_%"
    ]
    merged = merged[[c for c in col_order if c in merged.columns]]

    return merged


# === STREAMLIT LIVE DASHBOARD ===
st.set_page_config("📊 Live MTM Dashboard", layout="wide")
st.title("📊 Live MTM Dashboard")
if csv_path:
    df_csv = pd.read_csv(csv_path)
    placeholder = st.empty()  # creates a live-updating zone

    while True:
        df_tsv = load_local_file()
        merged = merge_and_adjust(df_tsv, df_csv)

        # Convert numeric columns to proper type
        numeric_cols = ["NetQty", "NetVal", "NetPrice", "Close", "LTP", "MTM", "MTM_%", "Diff_MTM", "Diff_MTM_%"]
        for col in numeric_cols:
            if col in merged.columns:
                merged[col] = pd.to_numeric(merged[col], errors="coerce")

        # Define column display order
        col_order = [
            "User", "Strategy", "Exchange", "Symbol", "Ser_Exp",
            "NetQty", "NetVal", "NetPrice", "Close", "LTP",
            "MTM", "MTM_%", "Diff_MTM", "Diff_MTM_%"
        ]
        merged = merged[[c for c in col_order if c in merged.columns]]

        # === Summary Cards ===
        total_row = merged[merged["Strategy"] == "TOTAL"].iloc[0] if "TOTAL" in merged["Strategy"].values else None
        if total_row is not None:
            net_val = total_row["NetVal"]
            mtm = total_row["MTM"]
            mtm_pct = total_row["MTM_%"]
            diff_mtm = total_row["Diff_MTM"]
            diff_mtm_pct = total_row["Diff_MTM_%"]


            def color_text(value):
                color = "#00FF00" if value >= 0 else "#FF4C4C"  # neon green/red
                return f"<span style='color:{color}; font-weight:bold;'>{value:,.2f}</span>"


            with placeholder.container():
                # === Compact Dark Cards ===
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:space-between; margin-bottom:15px; gap:8px;">
                        <div style="flex:1; background-color:#000; border-radius:10px; padding:10px; text-align:center; color:white;">
                            <div style="font-size:13px; opacity:0.7;">Net Value</div>
                            <div style="font-size:18px; font-weight:bold;">{net_val:,.2f}</div>
                        </div>
                        <div style="flex:1; background-color:#000; border-radius:10px; padding:10px; text-align:center; color:white;">
                            <div style="font-size:13px; opacity:0.7;">MTM</div>
                            <div style="font-size:18px; font-weight:bold;">{color_text(mtm)}</div>
                        </div>
                        <div style="flex:1; background-color:#000; border-radius:10px; padding:10px; text-align:center; color:white;">
                            <div style="font-size:13px; opacity:0.7;">MTM %</div>
                            <div style="font-size:18px; font-weight:bold;">{color_text(mtm_pct)}</div>
                        </div>
                        <div style="flex:1; background-color:#000; border-radius:10px; padding:10px; text-align:center; color:white;">
                            <div style="font-size:13px; opacity:0.7;">Diff MTM</div>
                            <div style="font-size:18px; font-weight:bold;">{color_text(diff_mtm)}</div>
                        </div>
                        <div style="flex:1; background-color:#000; border-radius:10px; padding:10px; text-align:center; color:white;">
                            <div style="font-size:13px; opacity:0.7;">Diff MTM %</div>
                            <div style="font-size:18px; font-weight:bold;">{color_text(diff_mtm_pct)}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # === Data Table ===
                st.subheader(f"⏱️ Last Updated: {datetime.now().strftime('%H:%M:%S')}")
                st.dataframe(
                    merged.style
                    .set_properties(**{"text-align": "center"})  # center all values
                    .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
                    .background_gradient(subset=["MTM"], cmap="RdYlGn")
                    .format({col: "{:,.2f}" for col in numeric_cols if col in merged.columns}, na_rep="-"),
                    use_container_width=True
                )

        time.sleep(refresh_interval)

    else:
        st.warning("⬆️ Please upload your Google CSV file to begin.")
