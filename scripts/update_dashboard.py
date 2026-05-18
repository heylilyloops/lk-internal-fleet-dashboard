import gspread
import json
import os
import csv
from datetime import datetime
from collections import defaultdict
from google.oauth2.service_account import Credentials

# ── AUTH ─────────────────────────────────────────────────────────
creds_json = os.environ['GOOGLE_CREDENTIALS']
creds_dict = json.loads(creds_json)
scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# ── CONFIG ────────────────────────────────────────────────────────
SPREADSHEET_ID = '1d_AzKPEc6GE_8t2WpND7ECmYK03ytubr7c2fGicKcvk'
GID_INTERNAL   = 2055243006
GID_EXTERNAL   = 1514192890

SITE_MAP = {
    'DC HCI CIKUPA'   : 'HCI Cikupa',
    'DC HCI JABABEKA' : 'HCI Jababeka',
    'DC SIDOARJO'     : 'Corp Sidoarjo',
    'DC AHI JABABEKA' : 'AHI Jababeka'
}
MONTH_MAP = {
    '1':'January','2':'February','3':'March','4':'April','5':'May',
    '6':'June','7':'July','8':'August','9':'September','10':'October',
    '11':'November','12':'December'
}

# ── FETCH SHEETS ─────────────────────────────────────────────────
print("Fetching Google Sheets data...")
spreadsheet = client.open_by_key(SPREADSHEET_ID)

ws_int = spreadsheet.get_worksheet_by_id(GID_INTERNAL)
ws_ext = spreadsheet.get_worksheet_by_id(GID_EXTERNAL)

int_data = ws_int.get_all_values()
ext_data = ws_ext.get_all_values()
print(f"Internal rows: {len(int_data)-1}, External rows: {len(ext_data)-1}")

# ── PARSE INTERNAL ────────────────────────────────────────────────
int_rows = []
header = int_data[0]
for line in int_data[1:]:
    if len(line) < 13: continue
    site = line[0].strip()
    if not site or site == 'Site': continue
    if 'Tamora' in site or 'Tallo' in site: continue
    area  = line[2].strip()
    jalur = line[3].strip()
    ci_raw = line[4].strip().replace(',','')
    ce_raw = line[5].strip().replace(',','')
    armada   = line[7].strip()
    del_type = line[9].strip()
    del_date_raw = line[10].strip()
    do_raw   = line[11].strip()
    cbm_raw  = line[12].strip()
    if not jalur or not del_date_raw: continue
    try:
        ci = float(ci_raw) if ci_raw else None
        ce = float(ce_raw) if ce_raw else None
        do_val = int(float(do_raw)) if do_raw else 0
        cbm = float(cbm_raw) if cbm_raw else 0.0
        del_date = datetime.strptime(del_date_raw, '%m/%d/%Y').strftime('%Y-%m-%d')
    except:
        continue
    if ci is None: continue
    int_rows.append([site, area, jalur, ci, ce, armada, del_type, del_date, do_val, cbm])

print(f"INT parsed: {len(int_rows)} rows")

# ── PARSE EXTERNAL ────────────────────────────────────────────────
ext_header = ext_data[0]
col = {h.strip(): i for i, h in enumerate(ext_header)}

ext_agg_area  = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
ext_agg_jalur = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

for line in ext_data[1:]:
    if len(line) < max(col.values()) + 1: continue
    site_raw   = line[col.get('SITE NAME', 0)].strip()
    area       = line[col.get('Area', 2)].strip()
    jalur      = line[col.get('Jalur', 3)].strip().title()
    month_num  = line[col.get('Month Num', 9)].strip()
    site       = SITE_MAP.get(site_raw)
    if not site or not area: continue
    month_name = MONTH_MAP.get(month_num)
    if not month_name: continue
    ext_agg_area[site][month_name][area] += 1
    if jalur:
        ext_agg_jalur[site][month_name][area][jalur] += 1

ext_list_area = [
    {"fleet":"External","site":s,"month":m,"area":a,"trips":t}
    for s, months in ext_agg_area.items()
    for m, areas in months.items()
    for a, t in areas.items()
]
ext_list_jalur = [
    {"site":s,"month":m,"area":a,"jalur":j,"trips":t}
    for s, months in ext_agg_jalur.items()
    for m, areas in months.items()
    for a, jalurs in areas.items()
    for j, t in jalurs.items()
]

print(f"EXT area: {len(ext_list_area)}, EXT jalur: {len(ext_list_jalur)}")

# ── BUILD data_block.js ───────────────────────────────────────────
data_block = (
    'const RAW = '      + json.dumps(int_rows,       ensure_ascii=False) + ';\n' +
    'const EXT_AGG = '  + json.dumps(ext_list_area,  ensure_ascii=False) + ';\n' +
    'const EXT_JALUR = '+ json.dumps(ext_list_jalur, ensure_ascii=False) + ';\n'
)

# ── INJECT KE HTML ────────────────────────────────────────────────
with open('silk_shell.html', 'r', encoding='utf-8') as f:
    html = f.read()

result = html.replace('__DATA_BLOCK__', data_block)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(result)

print(f"index.html generated — {len(result)/1024:.0f} KB")
print("Done!")
