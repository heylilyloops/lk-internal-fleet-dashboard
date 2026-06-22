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
GID_MASTER_LT  = 963114842

# Uppercase lookup — handles any casing from sheet
SITE_MAP = {
    'NDC HCI CIKUPA'    : 'HCI Cikupa',
    'NDC HCI JABABEKA'  : 'HCI Jababeka',
    'NDC SIDOARJO'      : 'Corp Sidoarjo',
    'NDC AHI JABABEKA'  : 'AHI Jababeka',
    'NDC CORP SIDOARJO' : 'Corp Sidoarjo',  # fix: actual value in sheet
}
MONTH_MAP = {}  # tidak dipakai, delivery date diparse langsung

# ── FETCH SHEETS ─────────────────────────────────────────────────
print("Fetching Google Sheets data...")
spreadsheet = client.open_by_key(SPREADSHEET_ID)

ws_int = spreadsheet.get_worksheet_by_id(GID_INTERNAL)
ws_ext = spreadsheet.get_worksheet_by_id(GID_EXTERNAL)
ws_lt  = spreadsheet.get_worksheet_by_id(GID_MASTER_LT)

int_data = ws_int.get_all_values()
ext_data = ws_ext.get_all_values()
lt_data  = ws_lt.get_all_values()
print(f"Internal rows: {len(int_data)-1}, External rows: {len(ext_data)-1}, Master LT rows: {len(lt_data)}")

# ── PARSE INTERNAL ────────────────────────────────────────────────
int_rows = []
for line in int_data[1:]:
    if len(line) < 13: continue
    site = line[0].strip()
    if not site or site == 'Site': continue
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
        del_date = None
        for fmt_str in ('%m/%d/%Y', '%d-%b-%Y', '%d/%m/%Y', '%Y-%m-%d'):
            try:
                del_date = datetime.strptime(del_date_raw, fmt_str).strftime('%Y-%m-%d')
                break
            except:
                continue
        if not del_date: continue
    except:
        continue
    if ci is None: continue
    lt_raw  = line[14].strip() if len(line) > 14 else ''
    lt_ow   = float(lt_raw) if lt_raw and lt_raw not in ('Lead Time One Way',) else None
    ujp_raw  = line[15].strip().replace(',','') if len(line) > 15 else ''
    mpp_raw  = line[16].strip().replace(',','') if len(line) > 16 else ''
    sewa_raw = line[17].strip().replace(',','') if len(line) > 17 else ''
    ujp  = float(ujp_raw)  if ujp_raw  else None
    mpp  = float(mpp_raw)  if mpp_raw  else None
    sewa = float(sewa_raw) if sewa_raw else None
    int_rows.append([site, area, jalur, ci, ce, armada, del_type, del_date, do_val, cbm, lt_ow, ujp, mpp, sewa])

print(f"INT parsed: {len(int_rows)} rows")

# ── PARSE EXTERNAL ────────────────────────────────────────────────
ext_header = ext_data[0]
col = {h.strip(): i for i, h in enumerate(ext_header)}
print(f"EXT header cols: {list(col.keys())[:12]}")

ext_agg_area  = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
ext_agg_jalur = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

skipped = 0
for line in ext_data[1:]:
    if not any(line): continue
    # safe get dengan fallback index
    def get_col(name, fallback):
        idx = col.get(name, fallback)
        return line[idx].strip() if idx < len(line) else ''

    site_raw     = get_col('SITE NAME', 0)
    area         = get_col('Area', 2)
    jalur_raw    = get_col('Jalur', 3)
    delivery_raw = get_col('DELIVERY DATE', 7)

    # uppercase match untuk site
    site = SITE_MAP.get(site_raw.upper())
    if not site or not area:
        skipped += 1
        continue

    # parse delivery date → YYYY-MM-DD
    del_date = None
    for fmt_str in ('%d %b %y', '%d-%b-%y', '%m/%d/%Y', '%Y-%m-%d'):
        try:
            del_date = datetime.strptime(delivery_raw, fmt_str).strftime('%Y-%m-%d')
            break
        except:
            continue
    if not del_date:
        skipped += 1
        continue

    jalur = jalur_raw.title() if jalur_raw else ''

    ext_agg_area[site][del_date][area] += 1
    if jalur:
        ext_agg_jalur[site][del_date][area][jalur] += 1

print(f"EXT skipped: {skipped}")

ext_list_area = [
    {"fleet":"External","site":s,"date":d,"area":a,"trips":t}
    for s, dates in ext_agg_area.items()
    for d, areas in dates.items()
    for a, t in areas.items()
]
ext_list_jalur = [
    {"site":s,"date":d,"area":a,"jalur":j,"trips":t}
    for s, dates in ext_agg_jalur.items()
    for d, areas in dates.items()
    for a, jalurs in areas.items()
    for j, t in jalurs.items()
]

print(f"EXT area entries: {len(ext_list_area)}, EXT jalur entries: {len(ext_list_jalur)}")

# ── BUILD EXT_LT FROM MASTER LEAD TIME ───────────────────────────
# Origin mapping: Cikarang → AHI Jababeka + HCI Jababeka, Cikupa → HCI Cikupa, Sidoarjo → Corp Sidoarjo
ORIGIN_SITE_MAP = {
    'Cikarang' : ['AHI Jababeka', 'HCI Jababeka'],
    'Cikupa'   : ['HCI Cikupa'],
    'Sidoarjo' : ['Corp Sidoarjo'],
    'Cikande'  : ['AHI Jababeka', 'HCI Jababeka', 'HCI Cikupa'],  # fallback
}

master_lt_list = []
for row in lt_data[2:]:  # skip 2 header rows
    if len(row) < 14: continue
    moda   = row[5].strip()
    origin = row[6].strip()
    city   = row[7].strip()
    lt_raw = row[13].strip()
    if not city or not lt_raw: continue
    try:
        lt_val = float(lt_raw)
    except:
        continue
    sites = ORIGIN_SITE_MAP.get(origin, [])
    for site in sites:
        master_lt_list.append({"site": site, "jalur": city, "avg_lt": lt_val})

# Deduplicate — keep first occurrence per site+jalur
seen = set()
ext_lt_list = []
for r in master_lt_list:
    k = (r['site'], r['jalur'])
    if k not in seen:
        seen.add(k)
        ext_lt_list.append(r)

print(f"EXT_LT from master: {len(ext_lt_list)} entries")

# ── BUILD data_block.js ───────────────────────────────────────────
data_block = (
    'const RAW = '       + json.dumps(int_rows,        ensure_ascii=False) + ';\n' +
    'const EXT_AGG = '   + json.dumps(ext_list_area,   ensure_ascii=False) + ';\n' +
    'const EXT_JALUR = ' + json.dumps(ext_list_jalur,  ensure_ascii=False) + ';\n' +
    'const EXT_LT = '    + json.dumps(ext_lt_list,     ensure_ascii=False) + ';\n'
)

# ── INJECT KE HTML ────────────────────────────────────────────────
with open('silk_shell.html', 'r', encoding='utf-8') as f:
    html = f.read()

result = html.replace('__DATA_BLOCK__', data_block)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(result)

print(f"index.html generated — {len(result)/1024:.0f} KB")
print("Done!")
