import pandas as pd
from sqlalchemy import create_engine, text

# 1. เชื่อมต่อฐานข้อมูล PostgreSQL
DB_URL = "postgresql://myuser:mypassword@localhost:5432/kaggle_db"
engine = create_engine(DB_URL)

print("🔍 กำลังดึงข้อมูลจากตาราง 'scbd_raw' เพื่อตรวจสอบคุณภาพ...")
df = pd.read_sql("SELECT * FROM scbd_raw", engine)

# 2. รายงานตรวจสอบคุณภาพข้อมูล (Data Quality Report)
print("\n" + "="*50)
print("📊 รายงานคุณภาพข้อมูล (DATA QUALITY REPORT)")
print("="*50)
print(f"• จำนวนแถวทั้งหมด: {len(df):,} แถว")
print(f"• จำนวนคอลัมน์ทั้งหมด: {len(df.columns)} คอลัมน์")

# ตรวจสอบค่าว่าง (Missing Values / NULL)
null_counts = df.isnull().sum()
total_nulls = null_counts.sum()
print(f"• จำนวนค่าว่าง (NULL) ทั้งหมด: {total_nulls} จุด")
if total_nulls > 0:
    print(null_counts[null_counts > 0])

# ตรวจสอบข้อมูลซ้ำ (Duplicates)
dup_all = df.duplicated().sum()
dup_id = df.duplicated(subset=["sample_id"]).sum() if "sample_id" in df.columns else 0
print(f"• แถวที่ข้อมูลซ้ำกันทั้งหมด: {dup_all} แถว")
print(f"• รหัส sample_id ที่ซ้ำกัน: {dup_id} แถว")

# แสดงชนิดข้อมูลและช่วงค่าตัวเลข (Data Types & Summary)
print("\n📋 โครงสร้างคอลัมน์และชนิดข้อมูล:")
print(df.dtypes)

print("\n📈 ค่าสถิติพื้นฐานของตัวแปรอารมณ์ (Summary Statistics):")
print(df.describe().round(4))

# 3. ทำความสะอาดข้อมูล (Data Cleaning)
df_cleaned = df.copy()

# ลบแถวซ้ำและค่าว่าง (ถ้ามี)
if "sample_id" in df_cleaned.columns:
    df_cleaned = df_cleaned.drop_duplicates(subset=["sample_id"])
df_cleaned = df_cleaned.drop_duplicates().dropna()

# แปลงคอลัมน์ข้อความ (Categorical) ให้เป็นตัวพิมพ์เล็กและตัดช่องว่างหัวท้ายให้เป็นมาตรฐานเดียวกัน
cat_cols = ["stimulus", "action", "engagement_level", "learning_state"]
for col in cat_cols:
    if col in df_cleaned.columns:
        df_cleaned[col] = df_cleaned[col].astype(str).str.strip().str.lower()

# 4. บันทึกลงตารางใหม่ชื่อ 'scbd_cleaned' ใน PostgreSQL
cleaned_table = "scbd_cleaned"
print(f"\n💾 กำลังบันทึกข้อมูลที่ทำความสะอาดแล้วลงตาราง '{cleaned_table}'...")
df_cleaned.to_sql(cleaned_table, engine, if_exists="replace", index=False, chunksize=5000)

with engine.connect() as conn:
    cleaned_count = conn.execute(text(f"SELECT COUNT(*) FROM {cleaned_table};")).scalar()

print(f"✅ สร้างตาราง '{cleaned_table}' สำเร็จ! คงเหลือข้อมูลพร้อมใช้งาน: {cleaned_count:,} แถว")