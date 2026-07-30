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
GID_EXT_RDC    = 1448086752
GID_INTERNAL_2025 = 1000808421
GID_EXTERNAL_2025 = 1015095105

SITE_MAP = {
    'NDC HCI CIKUPA'    : 'HCI Cikupa',
    'NDC HCI JABABEKA'  : 'HCI Jababeka',
    'NDC SIDOARJO'      : 'Corp Sidoarjo',
    'NDC AHI JABABEKA'  : 'AHI Jababeka',
    'NDC CORP SIDOARJO' : 'Corp Sidoarjo',
    'IND JABABEKA'      : 'IND Jababeka',
    'NDC IND JABABEKA'  : 'IND Jababeka',
    'DC HCI CIKUPA'     : 'HCI Cikupa',
    'DC HCI JABABEKA'   : 'HCI Jababeka',
    'DC AHI JABABEKA'   : 'AHI Jababeka',
    'DC AHI SIDOARJO'   : 'Corp Sidoarjo',
    'DC HCI SIDOARJO'   : 'Corp Sidoarjo',
}
MONTH_MAP = {}

# Scope area resmi per site (mirror SAVING_SCOPE di silk_shell.html) — dipakai buat
# nyaring anomali data entry (mis. area ketulis 'Jawa Timur' padahal site-nya AHI Jababeka).
SAVING_SCOPE_PY = {
    'AHI Jababeka':  ['Jawa Barat', 'Lampung'],
    'HCI Jababeka':  ['Jawa Barat', 'Lampung'],
    'HCI Cikupa':    ['Jawa Barat', 'Lampung'],
    'Corp Sidoarjo': ['Jawa Timur'],
    'Corp Tamora':   ['Sumatera Utara'],
    'Corp Tallo':    ['Sulawesi Selatan'],
    'IND Jababeka':  ['Jawa Barat'],
}

# ── FETCH SHEETS ─────────────────────────────────────────────────
print("Fetching Google Sheets data...")
spreadsheet = client.open_by_key(SPREADSHEET_ID)

ws_int = spreadsheet.get_worksheet_by_id(GID_INTERNAL)
ws_ext = spreadsheet.get_worksheet_by_id(GID_EXTERNAL)
ws_lt  = spreadsheet.get_worksheet_by_id(GID_MASTER_LT)
ws_rdc = spreadsheet.get_worksheet_by_id(GID_EXT_RDC)
ws_2025 = spreadsheet.get_worksheet_by_id(GID_INTERNAL_2025)
ws_ext2025 = spreadsheet.get_worksheet_by_id(GID_EXTERNAL_2025)

int_data = ws_int.get_all_values()
ext_data = ws_ext.get_all_values()
lt_data  = ws_lt.get_all_values()
rdc_data = ws_rdc.get_all_values()
data_2025 = ws_2025.get_all_values()
data_ext2025 = ws_ext2025.get_all_values()
print(f"Internal rows: {len(int_data)-1}, External rows: {len(ext_data)-1}, Master LT rows: {len(lt_data)}, External RDC rows: {len(rdc_data)-1}, Internal 2025 rows: {len(data_2025)-1}, External 2025 rows: {len(data_ext2025)-1}")

# ── PARSE INTERNAL ────────────────────────────────────────────────
int_header = int_data[0]
int_col = {h.strip(): i for i, h in enumerate(int_header)}
OWNER_IDX = int_col.get('Owner', 18)
KAP_IDX   = int_col.get('Kapasitas Armada', 21)
print(f"INT header — Owner idx: {OWNER_IDX}, Kapasitas Armada idx: {KAP_IDX}")

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
    kap_raw  = line[KAP_IDX].strip().replace(',','') if len(line) > KAP_IDX else ''
    try:
        kap = float(kap_raw) if kap_raw and kap_raw not in ('#N/A','#VALUE!','#REF!','#DIV/0!','#NULL!','#NAME?') else None
    except:
        kap = None
    owner = line[OWNER_IDX].strip() if len(line) > OWNER_IDX else ''
    int_rows.append([site, area, jalur, ci, ce, armada, del_type, del_date, do_val, cbm, lt_ow, ujp, mpp, sewa, kap, owner])

print(f"INT parsed: {len(int_rows)} rows")

# ── PARSE EXTERNAL NDC ───────────────────────────────────────────
ext_header = ext_data[0]
col = {h.strip(): i for i, h in enumerate(ext_header)}
print(f"EXT header cols: {list(col.keys())[:12]}")

ext_agg_area  = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0.0])))  # [trips, cbm]
ext_agg_jalur = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0.0, 0]))))  # [trips, cbm, olf_sum, olf_n]
ext_agg_owner = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0.0])))  # [site][date][owner/BU] = [trips, cbm] — only filled where BU column present (currently Corp Sidoarjo)
ext_agg_armada = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0.0]))))  # [site][date][jalur][armada] = [trips, cbm] — buat Demand Trip Internal vs External

skipped = 0
for line in ext_data[1:]:
    if not any(line): continue
    def get_col(name, fallback):
        idx = col.get(name, fallback)
        return line[idx].strip() if idx < len(line) else ''

    site_raw     = get_col('SITE NAME', 0)
    area         = get_col('Area', 2)
    jalur_raw    = get_col('Jalur', 3)
    delivery_raw = get_col('DELIVERY DATE', 7)
    moda_raw     = get_col('MODA', 6).upper()

    site = SITE_MAP.get(site_raw.upper())
    if not site or not area:
        skipped += 1
        continue

    # Only LAND moda
    if moda_raw not in ('LAND', 'DARAT', ''):
        skipped += 1
        continue

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
    cbm_raw2 = get_col('CBM', 11)
    kap_raw2 = get_col('Kapasitas Armada', 12)
    bu_raw   = get_col('BU', 14).strip()
    arm_raw  = get_col('TYPE ARMADA', 4).strip()
    try: cbm2 = float(cbm_raw2.replace(',','')) if cbm_raw2 else 0.0
    except: cbm2 = 0.0
    try: kap2 = float(kap_raw2.replace(',','')) if kap_raw2 and kap_raw2 not in ('#N/A','#VALUE!','#REF!','') else 0.0
    except: kap2 = 0.0
    olf_ext = (cbm2/kap2*100) if kap2>0 and cbm2>0 else 0.0
    ext_agg_area[site][del_date][area][0] += 1
    ext_agg_area[site][del_date][area][1] += cbm2
    if bu_raw:
        ext_agg_owner[site][del_date][bu_raw][0] += 1
        ext_agg_owner[site][del_date][bu_raw][1] += cbm2
    if jalur:
        ext_agg_jalur[site][del_date][area][jalur][0] += 1
        ext_agg_jalur[site][del_date][area][jalur][1] += cbm2
        if olf_ext > 0:
            ext_agg_jalur[site][del_date][area][jalur][2] += olf_ext
            ext_agg_jalur[site][del_date][area][jalur][3] += 1
        if arm_raw:
            ext_agg_armada[site][del_date][jalur][arm_raw][0] += 1
            ext_agg_armada[site][del_date][jalur][arm_raw][1] += cbm2

print(f"EXT skipped: {skipped}")

# ── PARSE EXTERNAL RDC ───────────────────────────────────────────
rdc_header = rdc_data[0]
rdc_col = {h.strip(): i for i, h in enumerate(rdc_header)}
print(f"RDC header cols: {list(rdc_col.keys())[:11]}")

rdc_skipped = 0
rdc_lt_sum = defaultdict(lambda: defaultdict(lambda: [0, 0]))

for line in rdc_data[1:]:
    if not any(line): continue
    def get_rdc(name, fallback):
        idx = rdc_col.get(name, fallback)
        return line[idx].strip() if idx < len(line) else ''

    site     = get_rdc('SITE NAME', 0)
    area     = get_rdc('Area', 2)
    jalur_r  = get_rdc('Jalur', 3).title()
    del_raw  = get_rdc('DELIVERY DATE', 7)
    lt_r     = get_rdc('Lead Time', 10)
    moda_rdc = get_rdc('MODA', 6).upper()

    if not site: rdc_skipped += 1; continue

    # Only LAND moda
    if moda_rdc not in ('LAND', 'DARAT', ''):
        rdc_skipped += 1; continue

    del_date = None
    for fmt_str in ('%m/%d/%Y', '%d-%b-%Y', '%d %b %y', '%Y-%m-%d'):
        try:
            del_date = datetime.strptime(del_raw, fmt_str).strftime('%Y-%m-%d')
            break
        except: continue
    if not del_date: rdc_skipped += 1; continue

    # Area kosong → pakai mapping jalur → area untuk RDC
    RDC_JALUR_AREA = {
        'Pekanbaru'        : 'Riau',
        'Dumai'            : 'Riau',
        'Banda Aceh'       : 'Aceh',
        'Langsa'           : 'Aceh',
        'Aceh Tamiang'     : 'Aceh',
        'Lhokseumawe'      : 'Aceh',
        'Padang'           : 'Sumatera Barat',
        'Bukit Tinggi'     : 'Sumatera Barat',
        'Bukittinggi'      : 'Sumatera Barat',
        'Rantau Parapat'   : 'Sumatera Utara',
        'Siantar'          : 'Sumatera Utara',
        'Sibolga'          : 'Sumatera Utara',
        'Tarutung'         : 'Sumatera Utara',
        'Tapanuli'         : 'Sumatera Utara',
        'Kisaran'          : 'Sumatera Utara',
        'Percut Sei Tuan'  : 'Sumatera Utara',
        'Tanjung Morawa'   : 'Sumatera Utara',
        'Samosir'          : 'Sumatera Utara',
        'Tobasa'           : 'Sumatera Utara',
        'Sidikalang'       : 'Sumatera Utara',
        'Medan Polonia'    : 'Sumatera Utara',
        'Porsea'           : 'Sumatera Utara',
        'Jakarta'          : 'Jabodetabek',
        'Batam'            : 'Kepri',
    }
    area_key = area if area else RDC_JALUR_AREA.get(jalur_r, jalur_r)

    cbm_rdc_raw = get_rdc('CBM', 11)
    try: cbm_rdc = float(cbm_rdc_raw.replace(',','')) if cbm_rdc_raw else 0.0
    except: cbm_rdc = 0.0
    arm_rdc_raw = get_rdc('TYPE ARMADA', 4).strip()
    ext_agg_area[site][del_date][area_key][0] += 1
    ext_agg_area[site][del_date][area_key][1] += cbm_rdc
    if jalur_r:
        ext_agg_jalur[site][del_date][area_key][jalur_r][0] += 1
        ext_agg_jalur[site][del_date][area_key][jalur_r][1] += cbm_rdc
        if arm_rdc_raw:
            ext_agg_armada[site][del_date][jalur_r][arm_rdc_raw][0] += 1
            ext_agg_armada[site][del_date][jalur_r][arm_rdc_raw][1] += cbm_rdc

    # Collect LT for benchmark
    try:
        lt_val = float(lt_r)
        rdc_lt_sum[site][jalur_r][0] += lt_val
        rdc_lt_sum[site][jalur_r][1] += 1
    except: pass

print(f"RDC EXT skipped: {rdc_skipped}")

ext_list_area = [
    {"fleet":"External","site":s,"date":d,"area":a,"trips":v[0],"cbm":round(v[1],2)}
    for s, dates in ext_agg_area.items()
    for d, areas in dates.items()
    for a, v in areas.items()
]
ext_list_jalur = [
    {"site":s,"date":d,"area":a,"jalur":j,"trips":v[0],"cbm":round(v[1],2),"olf_ext":round(v[2]/v[3],1) if v[3]>0 else None}
    for s, dates in ext_agg_jalur.items()
    for d, areas in dates.items()
    for a, jalurs in areas.items()
    for j, v in jalurs.items()
]
ext_list_owner = [
    {"site":s,"date":d,"owner":o,"trips":v[0],"cbm":round(v[1],2)}
    for s, dates in ext_agg_owner.items()
    for d, owners in dates.items()
    for o, v in owners.items()
]
ext_list_armada = [
    {"site":s,"date":d,"jalur":j,"armada":a,"trips":v[0],"cbm":round(v[1],2)}
    for s, dates in ext_agg_armada.items()
    for d, jalurs in dates.items()
    for j, armadas in jalurs.items()
    for a, v in armadas.items()
]
print(f"EXT area entries (incl RDC): {len(ext_list_area)}, EXT jalur entries: {len(ext_list_jalur)}, EXT owner (BU) entries: {len(ext_list_owner)}, EXT armada entries: {len(ext_list_armada)}")

# ── BUILD EXT_LT FROM MASTER LEAD TIME ───────────────────────────
ORIGIN_SITE_MAP = {
    'Cikarang' : ['AHI Jababeka', 'HCI Jababeka'],
    'Cikupa'   : ['HCI Cikupa'],
    'Sidoarjo' : ['Corp Sidoarjo'],
    'Cikande'  : ['AHI Jababeka', 'HCI Jababeka', 'HCI Cikupa'],
}

master_lt_list = []
for row in lt_data[2:]:
    if len(row) < 14: continue
    origin = row[6].strip()
    city   = row[7].strip()
    lt_raw = row[13].strip()
    if not city or not lt_raw: continue
    try:
        lt_val = float(lt_raw)
    except:
        continue
    for site in ORIGIN_SITE_MAP.get(origin, []):
        master_lt_list.append({"site": site, "jalur": city, "avg_lt": lt_val})

seen = set()
ext_lt_list = []
for r in master_lt_list:
    k = (r['site'], r['jalur'])
    if k not in seen:
        seen.add(k)
        ext_lt_list.append(r)

print(f"EXT_LT from master: {len(ext_lt_list)} entries")

# Add RDC LT
for s, jalurs in rdc_lt_sum.items():
    for j, v in jalurs.items():
        if v[1] > 0 and (s, j) not in seen:
            seen.add((s, j))
            ext_lt_list.append({"site": s, "jalur": j, "avg_lt": round(v[0]/v[1], 2)})

print(f"EXT_LT total (incl RDC): {len(ext_lt_list)} entries")

# ── PARSE INTERNAL 2025 (trip volume only, no cost — YoY comparison) ──
h2025 = data_2025[0]
col2025 = {h.strip(): i for i, h in enumerate(h2025)}
SITE_IDX_25  = col2025.get('Site', 0)
MONTH_IDX_25 = col2025.get('Month', 6)
AREA_IDX_25  = col2025.get('Area', 2)
DEST_IDX_25  = col2025.get('Destination', 3)

agg_2025 = defaultdict(lambda: defaultdict(int))  # [site][month(1-12)] = trips
agg_2025_area = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # [site][month][area] = trips
for line in data_2025[1:]:
    if len(line) <= max(SITE_IDX_25, MONTH_IDX_25): continue
    site25 = line[SITE_IDX_25].strip()
    if not site25 or site25 == 'Site': continue
    site25 = SITE_MAP.get(site25, site25)
    m_raw = line[MONTH_IDX_25].strip()
    try:
        m = int(float(m_raw))
    except:
        continue
    if not (1 <= m <= 12): continue
    agg_2025[site25][m] += 1
    # Area untuk breakdown "Per Area": Lampung tidak pernah muncul sbg nilai Area mentah
    # (sama seperti data 2026), tapi keisi di kolom Destination — override ke 'Lampung' kalau match.
    area25 = line[AREA_IDX_25].strip() if len(line) > AREA_IDX_25 else ''
    dest25 = line[DEST_IDX_25].strip() if len(line) > DEST_IDX_25 else ''
    if dest25 == 'Lampung':
        area25 = 'Lampung'
    # Hanya masukkan kalau area itu memang scope resmi site-nya — data entry error
    # (mis. AHI Jababeka ke-tag 'Jawa Timur') difilter di sini.
    if area25 and area25 in SAVING_SCOPE_PY.get(site25, []):
        agg_2025_area[site25][m][area25] += 1

trip_2025_list = [
    {"site": s, "m": f"{m:02d}", "trips": v}
    for s, months in agg_2025.items()
    for m, v in months.items()
]
trip_2025_area_list = [
    {"site": s, "m": f"{m:02d}", "area": a, "trips": v}
    for s, months in agg_2025_area.items()
    for m, areas in months.items()
    for a, v in areas.items()
]
print(f"TRIP2025 entries: {len(trip_2025_list)} (sites: {sorted(agg_2025.keys())})")
print(f"TRIP2025_AREA entries: {len(trip_2025_area_list)}")

# ── PARSE EXTERNAL 2025 (trip volume only, no cost — YoY & Kontribusi comparison) ──
hExt25 = data_ext2025[0]
colExt25 = {h.strip(): i for i, h in enumerate(hExt25)}
SITE_IDX_E25  = colExt25.get('SITE NAME', 0)
AREA_IDX_E25  = colExt25.get('Area', 2)
JALUR_IDX_E25 = colExt25.get('Jalur', 3)
MODA_IDX_E25  = colExt25.get('MODA', 6)
DATE_IDX_E25  = colExt25.get('DELIVERY DATE', 7)
CBM_IDX_E25   = colExt25.get('CBM', 11)

def parse_date_e25(d):
    """DELIVERY DATE format M/D/YYYY -> YYYY-MM-DD, month only really needed."""
    d = d.strip()
    if not d:
        return None
    try:
        mm, dd, yyyy = d.split('/')
        return f"{yyyy}-{int(mm):02d}"
    except:
        return None

agg_ext2025_area = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # [site][month][area] = trips
skipped_e25 = 0
for line in data_ext2025[1:]:
    if len(line) <= max(SITE_IDX_E25, MODA_IDX_E25, DATE_IDX_E25):
        skipped_e25 += 1
        continue
    site_e25 = line[SITE_IDX_E25].strip()
    if not site_e25 or site_e25 == 'SITE NAME':
        skipped_e25 += 1
        continue
    site_e25 = SITE_MAP.get(site_e25, site_e25)
    moda_e25 = line[MODA_IDX_E25].strip().lower() if len(line) > MODA_IDX_E25 else ''
    if moda_e25 != 'land':
        continue  # cuma darat, biar apples-to-apples sama armada internal
    ym = parse_date_e25(line[DATE_IDX_E25]) if len(line) > DATE_IDX_E25 else None
    if not ym:
        skipped_e25 += 1
        continue
    m = ym.split('-')[1]
    area_e25 = line[AREA_IDX_E25].strip() if len(line) > AREA_IDX_E25 else ''
    jalur_e25 = line[JALUR_IDX_E25].strip().title() if len(line) > JALUR_IDX_E25 else ''
    if jalur_e25 == 'Lampung':
        area_e25 = 'Lampung'
    if area_e25 and area_e25 in SAVING_SCOPE_PY.get(site_e25, []):
        agg_ext2025_area[site_e25][m][area_e25] += 1

ext_2025_area_list = [
    {"site": s, "m": m, "area": a, "trips": v}
    for s, months in agg_ext2025_area.items()
    for m, areas in months.items()
    for a, v in areas.items()
]
print(f"EXT2025_AREA entries: {len(ext_2025_area_list)} (skipped rows: {skipped_e25})")

# ── BUILD data_block.js ───────────────────────────────────────────
data_block = (
    'const RAW = '       + json.dumps(int_rows,        ensure_ascii=False) + ';\n' +
    'const EXT_AGG = '   + json.dumps(ext_list_area,   ensure_ascii=False) + ';\n' +
    'const EXT_JALUR = ' + json.dumps(ext_list_jalur,  ensure_ascii=False) + ';\n' +
    'const EXT_LT = '    + json.dumps(ext_lt_list,     ensure_ascii=False) + ';\n' +
    'const EXT_OWNER = '  + json.dumps(ext_list_owner,  ensure_ascii=False) + ';\n' +
    'const TRIP2025 = '   + json.dumps(trip_2025_list,  ensure_ascii=False) + ';\n' +
    'const TRIP2025_AREA = ' + json.dumps(trip_2025_area_list, ensure_ascii=False) + ';\n' +
    'const EXT2025_AREA = ' + json.dumps(ext_2025_area_list, ensure_ascii=False) + ';\n' +
    'const EXT_ARMADA = ' + json.dumps(ext_list_armada, ensure_ascii=False) + ';\n'
)

# ── INJECT KE HTML ────────────────────────────────────────────────
with open('silk_shell.html', 'r', encoding='utf-8') as f:
    html = f.read()

result = html.replace('__DATA_BLOCK__', data_block)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(result)

print(f"index.html generated — {len(result)/1024:.0f} KB")
print("Done!")
