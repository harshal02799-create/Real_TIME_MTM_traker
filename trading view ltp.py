# import os, time, pandas as pd
# from tradingview_ta import TA_Handler
# from tradingview_screener import Query, Column
# import os, time, pandas as pd
# from tradingview_screener import Query
#
# # Google Sheet holdings data
# url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQyY0N1hFIGML56I49kSRPWd7loDPQsa284rBn6o902zphvLQmtda5Rh76dCEm-3SjL3at9F2SVSltE/pub?gid=1440088474&single=true&output=csv"
# base_path = r'C:\Users\freedom\Desktop\ORDER B005\backup\GETS_FILES\GETS_EXCEL'
#
# # ----------------------------
# # Helper: Weighted Average
# # ----------------------------
# def weighted_avg(df, value_col, qty_col):
#     total_qty = df[qty_col].sum()
#     return 0 if total_qty == 0 else (df[value_col] * df[qty_col]).sum() / total_qty
#
# # ----------------------------
# # Main Loop
# # ----------------------------
# while True:
#     # 🔹 Find the latest NetPositionAutoBackup.xls
#     folders = [os.path.join(base_path, f, 'NetPositionAutoBackup.xls') for f in os.listdir(base_path)
#                if os.path.isdir(os.path.join(base_path, f)) and os.path.exists(os.path.join(base_path, f, 'NetPositionAutoBackup.xls'))]
#     latest = max(folders, key=os.path.getmtime) if folders else None
#
#     if latest:
#         print(f"\n🟢 Latest Net Position File: {latest}")
#
#         # 🔹 Read holdings from Google Sheet
#         holdings = pd.read_csv(url, skiprows=3)
#         holdings.columns = holdings.columns.str.strip()
#         holdings = holdings[holdings['Quantity'] != 0].reset_index(drop=True)
#         holdings['STRATEGY'] = holdings['STRATEGY'].replace({'GREEKSOFT': 'CHART'})
#
#         # 🔹 Read Net Position and remove rows with NetQty = 0
#         netpos = pd.read_csv(latest, sep='\t')
#         netpos.columns = netpos.columns.str.strip()
#         netpos['STRATEGY'] = netpos.get('CumStrategy', netpos.get('STRATEGY', 'CIRCUIT')).replace({'GREEKSOFT': 'CHART'})
#         netpos = netpos[netpos['NetQty'] != 0].reset_index(drop=True)
#         netpos['NetVal'] = netpos['NetVal'].abs()
#
#         # 🔹 Clean net position
#         clean_net = pd.DataFrame({
#             'Symbol': netpos['Symbol'],
#             'STRATEGY': netpos['STRATEGY'],
#             'Client_code': netpos['User'],
#             'Quantity': netpos['NetQty'],
#             'BUY AVG': netpos['NetPrice'],
#             'Closing': netpos['NetPrice']
#         })
#
#         # 🔹 Merge holdings + net positions
#         merged = pd.concat([holdings[['Symbol','STRATEGY','Client_code','Quantity','BUY AVG','Closing']], clean_net], ignore_index=True)
#
#         # 🔹 Group and summarize using agg (avoids deprecated apply warning)
#         final = merged.groupby('Symbol', as_index=False).agg({
#             'STRATEGY': 'first',
#             'Client_code': lambda x: ','.join(x.astype(str).unique()),
#             'Quantity': 'sum',
#             'BUY AVG': lambda x: weighted_avg(merged.loc[x.index], 'BUY AVG', 'Quantity'),
#             'Closing': 'first'
#         })
#
#         # 🔹 Calculate Holding Value
#         final['Holding Value'] = final['Quantity'] * final['BUY AVG']
#
#         # 🔹 Fetch all TradingView data at once
#         print("📡 Fetching all LTP data from TradingView...")
#         n_rows, tradingview = Query().select('name', 'exchange', 'close').set_markets('india').limit(9000).get_scanner_data()
#         tradingview = tradingview.rename(columns={'name': 'Symbol'}).round(2).fillna(0)
#
#         # 🔹 Prefer NSE over BSE and remove duplicates
#         tradingview = tradingview.sort_values(by='exchange', key=lambda x: x.eq('NSE'), ascending=False)
#         tradingview = tradingview.drop_duplicates(subset=['Symbol'], keep='first')
#
#         # 🔹 Merge final data with LTP (only LTP, drop Exchange)
#         final = pd.merge(final, tradingview[['Symbol', 'close']], on='Symbol', how='left')
#         final.rename(columns={'close': 'LTP'}, inplace=True)
#
#         # 🔹 Print final merged output
#         pd.set_option('display.max_rows', None)
#         pd.set_option('display.max_columns', None)
#         print(final)
#
#     else:
#         print("⚠️ No valid NetPositionAutoBackup.xls found.")
#
#     # 🔁 Repeat every 30 seconds
#     time.sleep(30)
#

#
#
#
#
#
#
#
# import os, time
# import pandas as pd
# from datetime import datetime
# from tradingview_screener import Query
#
# # Google Sheet holdings data
# url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQyY0N1hFIGML56I49kSRPWd7loDPQsa284rBn6o902zphvLQmtda5Rh76dCEm-3SjL3at9F2SVSltE/pub?gid=1440088474&single=true&output=csv"
# base_path = r'C:\Users\freedom\Desktop\ORDER B005\backup\GETS_FILES\GETS_EXCEL'
#
# def weighted_avg(df, value_col, qty_col):
#     total_qty = df[qty_col].sum()
#     return 0 if total_qty == 0 else (df[value_col] * df[qty_col]).sum() / total_qty
#
# def is_market_open():
#     now = datetime.now()
#     start = now.replace(hour=9, minute=15, second=10, microsecond=0)
#     end = now.replace(hour=17, minute=29, second=50, microsecond=0)
#     return start <= now <= end
#
# while True:
#     if not is_market_open():
#         print("⚠️ Market is closed. Waiting for next session...")
#         time.sleep(30)
#         continue
#
#     # Find latest NetPositionAutoBackup.xls
#     folders = [os.path.join(base_path, f, 'NetPositionAutoBackup.xls')
#                for f in os.listdir(base_path)
#                if os.path.isdir(os.path.join(base_path, f)) and os.path.exists(os.path.join(base_path, f, 'NetPositionAutoBackup.xls'))]
#     latest = max(folders, key=os.path.getmtime) if folders else None
#
#     # Google Sheet holdings
#     holdings = pd.read_csv(url, skiprows=3)
#     holdings.columns = holdings.columns.str.strip()
#     holdings = holdings[holdings['Quantity'] != 0].reset_index(drop=True)
#     holdings['STRATEGY'] = holdings['STRATEGY'].astype(str).replace({'GREEKSOFT': 'CHART'})
#     holdings['Type'] = 'GOOGLE'
#     holdings = holdings.rename(columns={'Closing': 'Close'})
#     holdings['BUY AVG'] = pd.to_numeric(holdings['BUY AVG'], errors='coerce').fillna(0)
#     holdings['Quantity'] = pd.to_numeric(holdings['Quantity'], errors='coerce').fillna(0)
#     holdings['Close'] = pd.to_numeric(holdings['Close'], errors='coerce').fillna(0)
#
#     # Net Position
#     clean_net = pd.DataFrame(columns=['Symbol','STRATEGY','Client_code','Quantity','BUY AVG','Close','Type'])
#     if latest:
#         print(f"\n🟢 Latest Net Position File: {latest}")
#         try:
#             netpos = pd.read_excel(latest)
#             netpos.columns = netpos.columns.str.strip()
#             if 'NetQty' in netpos.columns and netpos['NetQty'].sum() > 0:
#                 netpos = netpos[netpos['NetQty'] != 0].reset_index(drop=True)
#                 netpos['STRATEGY'] = netpos.get('CumStrategy', netpos.get('STRATEGY', 'CIRCUIT')).astype(str).replace({'GREEKSOFT': 'CHART'})
#                 netpos['NetVal'] = pd.to_numeric(netpos['NetVal'], errors='coerce').abs().fillna(0)
#                 netpos['NetQty'] = pd.to_numeric(netpos['NetQty'], errors='coerce').fillna(0)
#                 netpos['NetPrice'] = pd.to_numeric(netpos['NetPrice'], errors='coerce').fillna(0)
#                 netpos['Type'] = 'NET'
#
#                 clean_net = pd.DataFrame({
#                     'Symbol': netpos['Symbol'].astype(str),
#                     'STRATEGY': netpos['STRATEGY'],
#                     'Client_code': netpos['User'].astype(str),
#                     'Quantity': netpos['NetQty'],
#                     'BUY AVG': netpos['NetPrice'],
#                     'Close': netpos['NetPrice'],
#                     'Type': 'NET'
#                 })
#         except Exception as e:
#             print(f"⚠️ Could not read NetPosition file, using only Google Sheet: {e}")
#
#     # Merge Holdings + NetPosition
#     merged = pd.concat([holdings[['Symbol','STRATEGY','Client_code','Quantity','BUY AVG','Close','Type']],
#                         clean_net], ignore_index=True)
#
#     # Group by Symbol
#     final = merged.groupby('Symbol', as_index=False).agg({
#         'STRATEGY': 'first',
#         'Client_code': lambda x: ','.join(x.astype(str).unique()),
#         'Quantity': 'sum',
#         'BUY AVG': lambda x: weighted_avg(merged.loc[x.index], 'BUY AVG', 'Quantity'),
#         'Close': 'first',
#         'Type': 'first'
#     })
#
#     # Ensure numeric
#     for col in ['Quantity','BUY AVG','Close']:
#         final[col] = pd.to_numeric(final[col], errors='coerce').fillna(0)
#     final['Holding Value'] = final['Quantity'] * final['BUY AVG']
#
#     # TradingView LTP
#     print("📡 Fetching all LTP data from TradingView...")
#     n_rows, tradingview = Query().select('name', 'exchange', 'close').set_markets('india').limit(9000).get_scanner_data()
#     tradingview = tradingview.rename(columns={'name': 'Symbol', 'close': 'LTP'}).round(2).fillna(0)
#     tradingview = tradingview.sort_values(by='exchange', key=lambda x: x.eq('NSE'), ascending=False)
#     tradingview = tradingview.drop_duplicates(subset=['Symbol'], keep='first')
#
#     final = pd.merge(final, tradingview[['Symbol', 'LTP']], on='Symbol', how='left')
#     final['LTP'] = pd.to_numeric(final['LTP'], errors='coerce').fillna(0)
#
#     # MTM calculations
#     final['MTM'] = ((final['LTP'] - final['BUY AVG']) * final['Quantity']).where(final['Type']=='NET', 0)
#     final['Diff MTM'] = (final['LTP'] - final['Close']) * final['Quantity']
#     final['MTM'] = pd.to_numeric(final['MTM'], errors='coerce').fillna(0)
#     final['Diff MTM'] = pd.to_numeric(final['Diff MTM'], errors='coerce').fillna(0)
#
#     final['MTM %'] = (final['MTM'] / final['Holding Value'] * 100).round(2).fillna(0)
#     final['Diff MTM %'] = (final['Diff MTM'] / final['Holding Value'] * 100).round(2).fillna(0)
#
#     # Totals row
#     totals = pd.DataFrame({
#         'Symbol': ['TOTAL'],
#         'STRATEGY': ['-'],
#         'Client_code': ['-'],
#         'Quantity': [final['Quantity'].sum()],
#         'BUY AVG': [0],
#         'Close': [0],
#         'Type': ['-'],
#         'Holding Value': [final['Holding Value'].sum()],
#         'LTP': [0],
#         'MTM': [final['MTM'].sum()],
#         'Diff MTM': [final['Diff MTM'].sum()],
#         'MTM %': [(final['MTM'].sum() / final['Holding Value'].sum() * 100).round(2)],
#         'Diff MTM %': [(final['Diff MTM'].sum() / final['Holding Value'].sum() * 100).round(2)]
#     })
#     final = pd.concat([final, totals], ignore_index=True)
#
#     # Display
#     pd.set_option('display.max_rows', None)
#     pd.set_option('display.max_columns', None)
#     pd.set_option('display.width', 1200)
#     pd.set_option('display.max_colwidth', None)
#     pd.set_option('display.float_format', '{:.2f}'.format)
#     print(final)
#
#     time.sleep(10)



from tradingview_screener import Query

# TradingView LTP
print("📡 Fetching all LTP data from TradingView...")
n_rows, tradingview = Query().select('name', 'exchange', 'close', 'high','close|1').set_markets('india').limit(9000).get_scanner_data()
tradingview = tradingview.rename(columns={'name': 'Symbol', 'close': 'LTP'}).round(2).fillna(0)
tradingview = tradingview.sort_values(by='exchange', key=lambda x: x.eq('NSE'), ascending=False)
tradingview = tradingview.drop_duplicates(subset=['Symbol'], keep='first')
pd.set_option('display.max_rows', 20)
pd.set_option('display.max_columns', None)
# print(tradingview)
print(tradingview.columns.tolist())
