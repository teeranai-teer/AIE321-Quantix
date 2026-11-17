"""ingest.py : data/*.csv -> PostgreSQL schema raw_data   (ขั้นที่ 1 ของ pipeline: Extract & Load)

หน้าที่ของไฟล์นี้
- อ่านไฟล์ CSV ทุกไฟล์ในโฟลเดอร์ data/ แล้วโหลดเข้าฐานข้อมูล PostgreSQL ใน schema ชื่อ raw_data
- ชื่อตาราง = ชื่อไฟล์  เช่น data/current_catalog.csv -> raw_data.current_catalog

หลักการสำคัญ
- โหลดข้อมูล "ดิบ" ตามที่เป็นจริง ห้ามทำความสะอาดในขั้นนี้ (การทำความสะอาดอยู่ใน transform.py)
- ทุกคอลัมน์ถูกเก็บเป็นข้อความ (TEXT) แล้วค่อยแปลงชนิดข้อมูลใน transform.py
- อ่านไฟล์ทีละ chunk และใช้ COPY ของ PostgreSQL จึงโหลดไฟล์ขนาด 1 GB ได้โดยไม่กิน RAM
- รันซ้ำได้ ผลลัพธ์เท่าเดิมทุกครั้ง (ตารางเดิมถูกแทนที่)
"""
import glob
import os
import re
import time

import pandas as pd
from dotenv import load_dotenv          # อ่านค่าตั้งต้นจากไฟล์ .env
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# ---------------------------------------------------------------- ค่าคงที่
BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # โฟลเดอร์ที่ไฟล์นี้อยู่ (รันจากที่ไหนก็ได้)
DATA_DIR = os.path.join(BASE_DIR, "data")                # โฟลเดอร์ที่วางไฟล์ CSV
RAW_SCHEMA = "raw_data"                                  # ชื่อ schema ตามที่โจทย์กำหนด
CHUNK_ROWS = 200_000                                     # อ่านทีละ 200,000 แถว เพื่อไม่ให้ RAM เต็ม

# โหลดไฟล์ .env (ถ้ามี) เพื่อให้ os.getenv() ด้านล่างอ่านค่าได้
load_dotenv(os.path.join(BASE_DIR, ".env"))


def get_engine():
    """สร้างตัวเชื่อมต่อฐานข้อมูล (engine)
    อ่านค่าจากไฟล์ .env ถ้าไม่มีไฟล์นั้นจะใช้ค่าเดียวกับ docker-compose.yml
    ฟังก์ชันนี้ถูกเรียกใช้ใน transform.py และ publish.py ด้วย"""
    url = URL.create(
        drivername="postgresql+psycopg",  # psycopg เวอร์ชัน 3 ให้ตรงกับ requirements.txt
        username=os.getenv("DB_USER", "myuser"),
        password=os.getenv("DB_PASSWORD", "mypassword"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "kaggle_db"),
    )
    return create_engine(url)


def table_name_from_path(path):
    """แปลงชื่อไฟล์เป็นชื่อตาราง: ตัดนามสกุล, ตัวพิมพ์เล็ก, อักขระแปลก ๆ เป็น _
    เช่น 'Current Catalog.csv' -> 'current_catalog'"""
    name = os.path.splitext(os.path.basename(path))[0].lower()
    return re.sub(r"[^a-z0-9_]+", "_", name).strip("_")


def _copy_method(table, conn, keys, data_iter):
    """วิธีเขียนข้อมูลลง DB แบบ COPY ของ PostgreSQL ผ่าน psycopg3
    เร็วกว่า INSERT ธรรมดาหลายสิบเท่า (ไฟล์ 5.7 ล้านแถวใช้เวลาประมาณ 35 วินาที)
    ถูกส่งให้ pandas to_sql ผ่านพารามิเตอร์ method=..."""
    cols = ", ".join(f'"{k}"' for k in keys)              # รายชื่อคอลัมน์
    target = f'"{table.schema}"."{table.name}"'            # ชื่อตารางปลายทาง
    with conn.connection.cursor() as cur:
        with cur.copy(f"COPY {target} ({cols}) FROM STDIN") as copy:
            for row in data_iter:
                copy.write_row(row)                        # เขียนทีละแถวเข้า COPY stream


def load_csv(engine, path):
    """โหลดไฟล์ CSV 1 ไฟล์เข้าตารางใน raw_data"""
    table = table_name_from_path(path)
    t0, total = time.time(), 0                             # จับเวลา และนับจำนวนแถวที่อ่าน

    # dtype=str : เก็บทุกคอลัมน์เป็นข้อความดิบ (ช่องว่างในไฟล์จะกลายเป็น NULL)
    for i, chunk in enumerate(pd.read_csv(path, dtype=str, chunksize=CHUNK_ROWS)):
        # chunk แรก: สร้างตารางใหม่ทับของเดิม (replace)  chunk ถัดไป: ต่อท้าย (append)
        chunk.to_sql(table, engine, schema=RAW_SCHEMA, index=False,
                     if_exists="replace" if i == 0 else "append", method=_copy_method)
        total += len(chunk)
        print(f"[ingest]   {os.path.basename(path)}: {total:,} rows", end="\r")

    # ตรวจความถูกต้อง: จำนวนแถวใน DB ต้องเท่ากับจำนวนแถวที่อ่านจากไฟล์
    with engine.connect() as conn:
        n = conn.execute(text(f'SELECT COUNT(*) FROM {RAW_SCHEMA}."{table}"')).scalar()
    if n != total:
        raise RuntimeError(f"{table}: โหลดไม่ครบ (CSV {total:,} แถว, DB {n:,} แถว)")
    print(f"[ingest] {os.path.basename(path)} -> {RAW_SCHEMA}.{table}: {n:,} rows ({time.time() - t0:.0f}s)")


def main():
    """จุดเริ่มต้น: หาไฟล์ CSV ทั้งหมดใน data/ แล้วโหลดทีละไฟล์"""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
    if not files:
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV ใน {DATA_DIR} (วางไฟล์จาก Kaggle ไว้ในโฟลเดอร์ data/)")
    engine = get_engine()
    with engine.begin() as conn:                           # สร้าง schema raw_data ถ้ายังไม่มี
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}"))
    for path in files:
        load_csv(engine, path)


if __name__ == "__main__":
    main()
