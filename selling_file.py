import pandas as pd
import os
# CONFIG
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQyY0N1hFIGML56I49kSRPWd7loDPQsa284rBn6o902zphvLQmtda5Rh76dCEm-3SjL3at9F2SVSltE/pub?gid=1001224097&single=true&output=csv"
CSV_PATH = r"C:\Users\freedom\Desktop\ORDER B005\B005 EXCEL FILE\selling file.csv"

# Convert Google Sheet link to direct CSV export URL
csv_url = GOOGLE_SHEET_URL.replace("/edit#gid=", "/export?format=csv&gid=")

# Read the entire Google Sheet
df = pd.read_csv(csv_url)

# Save (overwrite) the CSV file completely
df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

print(f"✅ Entire Google Sheet copied successfully to:\n{CSV_PATH}")
print(f"📊 Total rows copied: {len(df)}")

# SHOW FILE IN CONSOLE
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)
pd.set_option("display.width", None)

print("\n=== 📄 FILE CONTENTS ===")
print(df.to_string(index=False))