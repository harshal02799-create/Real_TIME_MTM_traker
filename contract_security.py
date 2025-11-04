import pandas as pd
import os
from tkinter import Tk, filedialog
from datetime import date

# === Open file explorer dialog ===
Tk().withdraw()  # hide the small Tkinter window
file_path = filedialog.askopenfilename(
    title="Select your security.txt file",
    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
)

if not file_path:
    print("❌ No file selected. Exiting.")
    exit()

print(f"📂 Selected file: {file_path}")

# === Read file from 2nd row, skip first line ===
df = pd.read_csv(
    file_path,
    sep="|",
    header=None,
    skiprows=1,
    on_bad_lines='skip',
    engine='python'
)

# === Assign headers 1, 2, 3, ... ===
df.columns = [i + 1 for i in range(df.shape[1])]

# === Keep only columns 1, 2, 3, 7, and 22 (if they exist) ===
cols_to_keep = [1, 2, 3, 7, 22]
df = df[[c for c in cols_to_keep if c in df.columns]]

# === Rename selected columns ===
rename_map = {
    1: "Code",
    2: "Symbol",
    3: "Ser",
    7: "DPR",
    22: "Script_Name"
}
df.rename(columns=rename_map, inplace=True)

# === Filter only where Ser == "EQ" ===
df = df[df["Ser"] == "EQ"]

# === Remove rows where Symbol or Script_Name contain unwanted patterns ===
patterns = [
    r"-RE",          # -RE
    r"ETF",          # ETF
    r"BEES",         # BEES
    r"NAV",          # NAV
    r"LLIQUID",      # LLIQUID
    r"NIFTY",        # NIFTY
    r"BANKNIFTY",    # BANKNIFTY
    r"MIDCAP",       # MIDCAP
    r"SMALLCAP",     # SMALLCAP
    r"\d+$"          # ends with number (e.g. ABC1, XYZ123)
]
combined_pattern = "(" + "|".join(patterns) + ")"

df = df[
    ~df["Symbol"].astype(str).str.upper().str.contains(combined_pattern, regex=True, na=False) &
    ~df["Script_Name"].astype(str).str.upper().str.contains(combined_pattern, regex=True, na=False)
]

# === Remove duplicates based on DPR ===
df = df.drop_duplicates(subset=["DPR"], keep="first")

# === Remove rows where the first number in DPR (like 180.00-220.00) < 20.00 ===
def valid_range(value):
    try:
        s = str(value).strip()
        if "-" in s:
            first = float(s.split("-")[0])
            if first < 20:
                return False
        return True
    except:
        return True

df = df[df["DPR"].apply(valid_range)]

# === Export to CSV on Desktop ===
desktop_path = r"C:\Users\freedom\Desktop"
today_str = date.today().strftime("%Y-%m-%d")
output_csv = os.path.join(desktop_path, f"today_security_file_{today_str}.csv")
df.to_csv(output_csv, index=False)

# === Show summary ===
print("\n✅ File processed successfully!")
print(f"📊 Total rows after all filters: {df.shape[0]}")
print(f"💾 Output saved to: {output_csv}")
