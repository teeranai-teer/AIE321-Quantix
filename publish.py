"""publish.py : production -> Google Sheets   (ขั้นที่ 3 ของ pipeline: Publish)

อ่านตารางสรุป (agg_*) จาก schema production แล้วส่งขึ้น Google Sheets
แต่ละตาราง = 1 แท็บ (worksheet) ชื่อเดียวกับตาราง และเขียนทับข้อมูลเดิมทุกครั้ง (รันซ้ำได้)

ต้องตั้งค่าก่อนรัน (ดูขั้นตอนในรายงานหัวข้อ Google Credentials)
  1. วางไฟล์ credentials.json (Service Account key) ไว้ในโฟลเดอร์โปรเจกต์ (ห้าม commit ขึ้น GitHub)
  2. สร้าง Google Sheet ว่าง แล้วแชร์ให้อีเมล client_email ใน credentials.json สิทธิ์ Editor
  3. ใส่ชื่อไฟล์ (GSHEET_NAME) หรือ ID (GSHEET_ID) ในไฟล์ .env

รันทดสอบโดยไม่ส่งขึ้น Google:  python publish.py --dry-run
"""
import argparse
import os

import pandas as pd
from dotenv import load_dotenv

from ingest import BASE_DIR, get_engine
from transform import PROD_SCHEMA

load_dotenv(os.path.join(BASE_DIR, ".env"))

# ตารางที่ส่งขึ้น Sheets (ตารางสรุปขนาดเล็กเท่านั้น ไม่ส่ง fact_catalog)
PUBLISH_TABLES = [
    "agg_overview",
    "agg_country_counts",
    "agg_constellation_counts",
    "agg_risk_by_altitude",
    "agg_orbital_band_profile",
    "agg_daily_objects",
    "agg_daily_by_constellation",
    "agg_daily_by_country",
    "cleaning_log",
]
# Google Sheets จำกัด 10 ล้านเซลล์ต่อไฟล์ ตั้งเพดานไว้ครึ่งหนึ่งเพื่อความปลอดภัย
MAX_CELLS = 5_000_000


def table_to_rows(df):
    """แปลง DataFrame เป็นลิสต์ของแถว (แถวแรกคือหัวคอลัมน์) ที่ Google Sheets รับได้
    - วันที่ -> ข้อความ 'YYYY-MM-DD' (Looker Studio จะรู้จักเป็นชนิด Date)
    - ค่าว่าง (NaN/None) -> ช่องว่าง เพราะ JSON ไม่รองรับ NaN
    - ตัวเลขเป็นชนิด Python ปกติ (ไม่ใช่ numpy)"""
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
        elif out[c].dtype == object:
            # คอลัมน์ที่เป็นวัตถุ date ของ Python -> เปลี่ยนเป็นข้อความ ISO
            out[c] = out[c].map(lambda v: v.isoformat() if hasattr(v, "isoformat") else v)
    out = out.astype(object).where(out.notna(), "")
    return [list(out.columns)] + out.values.tolist()


def open_spreadsheet(gc):
    """เปิดไฟล์ Google Sheet จาก GSHEET_ID (ถ้ามี) หรือ GSHEET_NAME"""
    sheet_id, sheet_name = os.getenv("GSHEET_ID"), os.getenv("GSHEET_NAME")
    if sheet_id:
        return gc.open_by_key(sheet_id)
    if sheet_name:
        return gc.open(sheet_name)
    raise RuntimeError("ไม่ได้ตั้ง GSHEET_NAME หรือ GSHEET_ID ในไฟล์ .env")


def main(dry_run=False):
    # 1) อ่านตารางจาก production และเตรียมแถวข้อมูล
    engine = get_engine()
    payload = {}
    for table in PUBLISH_TABLES:
        df = pd.read_sql(f"SELECT * FROM {PROD_SCHEMA}.{table}", engine)
        payload[table] = table_to_rows(df)

    # 2) ตรวจขนาดก่อนส่ง (จำนวนเซลล์ทั้งหมดต้องไม่เกินเพดาน)
    total_cells = sum(len(rows) * len(rows[0]) for rows in payload.values())
    for table, rows in payload.items():
        print(f"[publish] {table}: {len(rows) - 1:,} rows x {len(rows[0])} cols")
    print(f"[publish] รวม {total_cells:,} เซลล์ (เพดาน {MAX_CELLS:,})")
    if total_cells > MAX_CELLS:
        raise RuntimeError("ข้อมูลใหญ่เกินข้อจำกัดของ Google Sheets ให้ลดขนาดตารางสรุป")
    if dry_run:
        print("[publish] --dry-run: ไม่ส่งขึ้น Google Sheets")
        return

    # 3) เชื่อมต่อ Google ด้วย Service Account
    import gspread
    cred_path = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
    if not os.path.isabs(cred_path):
        cred_path = os.path.join(BASE_DIR, cred_path)
    if not os.path.exists(cred_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ {cred_path} (ดาวน์โหลด key จาก Google Cloud Console แล้วตั้งชื่อ credentials.json)")
    gc = gspread.service_account(filename=cred_path)
    try:
        sh = open_spreadsheet(gc)
    except gspread.SpreadsheetNotFound:
        raise RuntimeError("เปิด Google Sheet ไม่ได้: ตรวจชื่อ/ID และต้องแชร์ไฟล์ให้อีเมล client_email "
                           "ใน credentials.json สิทธิ์ Editor")

    # 4) เขียนทีละแท็บ: ไม่มีแท็บให้สร้าง มีแล้วล้างข้อมูลเดิมก่อนเขียนทับ
    for table, rows in payload.items():
        try:
            ws = sh.worksheet(table)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=table, rows=len(rows), cols=len(rows[0]))
        ws.clear()
        ws.resize(rows=len(rows), cols=len(rows[0]))
        # USER_ENTERED: ให้ Sheets แปลงวันที่และตัวเลขให้เหมือนพิมพ์เอง
        ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")
        print(f"[publish] {table} -> แท็บ '{table}' เขียนแล้ว {len(rows) - 1:,} แถว")
    print(f"[publish] เสร็จ: {sh.url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ส่งตารางสรุปจาก production ขึ้น Google Sheets")
    parser.add_argument("--dry-run", action="store_true", help="ตรวจและแปลงข้อมูลเท่านั้น ไม่ส่งขึ้น Google")
    main(dry_run=parser.parse_args().dry_run)
