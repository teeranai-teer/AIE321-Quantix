import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = "postgresql://myuser:mypassword@localhost:5432/kaggle_db"
engine = create_engine(DB_URL)

datasets = [
    ("current_catalog.csv", "satellite_current_raw"),
    ("trajectory_timeseries.csv", "satellite_trajectory_raw"),
]

for csv_file, table_name in datasets:
    print(f"\n📂 กำลังอ่านไฟล์ {csv_file}...")
    df = pd.read_csv(csv_file, low_memory=False)
    print(f"⏳ กำลังส่งข้อมูลทั้งหมด {len(df):,} แถว เข้าสู่ตาราง '{table_name}'...")
    df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=10000)
    with engine.connect() as conn:
        row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name};")).scalar()
    print(f"✅ นำเข้าตาราง '{table_name}' สำเร็จ! จำนวนข้อมูลทั้งหมด: {row_count:,} แถว")
