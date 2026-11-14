import pandas as pd
from sqlalchemy import create_engine, text

# 1. ตั้งค่าการเชื่อมต่อ PostgreSQL (ตรงกับค่าใน docker-compose.yml)
DB_URL = "postgresql://myuser:mypassword@localhost:5432/kaggle_db"
engine = create_engine(DB_URL)

# 2. อ่านไฟล์ข้อมูล CSV
csv_file = "synthetic_human_training_data.csv"
print(f"กำลังอ่านไฟล์ {csv_file}...")
df = pd.read_csv(csv_file)

# 3. นำข้อมูลเข้าตารางชื่อ 'scbd_raw' ใน PostgreSQL
table_name = "scbd_raw"
print(f"กำลังส่งข้อมูลทั้งหมด {len(df):,} แถว เข้าสู่ตาราง '{table_name}'...")
df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=5000)

# 4. ตรวจสอบความถูกต้องหลังนำเข้าข้อมูล
with engine.connect() as conn:
    result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name};"))
    row_count = result.scalar()

print(f"✅ นำเข้าข้อมูลสำเร็จ! จำนวนข้อมูลในฐานข้อมูลทั้งหมด: {row_count:,} แถว")