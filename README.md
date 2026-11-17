# AIE321-Quantix

AIE321 Data Pipeline Project by Team Quantix. Analyzing the Satellite Orbital Catalog dataset from Kaggle with Python and PostgreSQL (Docker), publishing summary tables to Google Sheets and visualizing them in Looker Studio to explore satellite orbital parameters, congestion risk, and trajectory patterns.

- Dashboard (Looker Studio): _____ ใส่ link Looker Studio

## Team Quantix

| หน้าที่ | ผู้รับผิดชอบ | งานที่ทำ | ไฟล์/ผลงาน |
|---|---|---|---|
| 1. Ingestion & Docker | มิ้น | PostgreSQL ด้วย Docker, โหลด CSV เข้า `raw_data`, GitHub, Google Cloud / Service Account | `docker-compose.yml`, `ingest.py`, `.env.example`, `README.md` |
| 2. Transform & Pipeline | Tonn | ทำความสะอาด/สร้างฟีเจอร์/สรุปข้อมูลลง `production`, ส่งขึ้น Google Sheets, รวมเป็นคำสั่งเดียว | `transform.py`, `publish.py`, `run_pipeline.py` |
| 3. Dashboard & Insights | แตงกวา | Looker Studio (≥ 5 กราฟ), ตอบคำถามธุรกิจ, สรุป insight | Dashboard, ส่วน Insights ในรายงาน |

## Database Architecture & Data Pipeline

**Pipeline:** `data/*.csv` → `ingest.py` → PostgreSQL `raw_data` → `transform.py` → PostgreSQL `production` → `publish.py` → Google Sheets → Looker Studio
รันทั้งหมดด้วยคำสั่งเดียว: `python run_pipeline.py`

```
┌──────────────┐  ingest.py   ┌───────────────────────────┐  transform.py  ┌────────────────────────────┐
│ Kaggle CSV   │ ───────────▶ │ PostgreSQL 15 (Docker)    │ ─────────────▶ │ PostgreSQL 15 (Docker)     │
│ current_     │  pandas +    │ schema: raw_data          │  pandas + SQL  │ schema: production         │
│ catalog.csv  │  COPY        │  ├ current_catalog (ดิบ)  │  clean/feature │  ├ fact_catalog            │
│ trajectory_  │              │  └ trajectory_timeseries  │  join/agg      │  ├ agg_country_counts      │
│ timeseries   │              └───────────────────────────┘                │  ├ agg_constellation_counts│
└──────────────┘                                                           │  ├ agg_risk_by_altitude    │
                                                                           │  ├ agg_orbital_band_profile│
┌──────────────┐   connector  ┌───────────────────────────┐  publish.py    │  ├ agg_daily_objects       │
│ Looker Studio│ ◀─────────── │ Google Sheets             │ ◀───────────── │  ├ agg_daily_by_country    │
│ Dashboard    │ Google Sheets│ 1 ตาราง = 1 worksheet     │  gspread       │  ├ agg_daily_by_constellat.│
└──────────────┘              └───────────────────────────┘                │  ├ agg_overview            │
                                                                           │  └ cleaning_log            │
                     run_pipeline.py = รัน ingest → transform → publish    └────────────────────────────┘
                                       ด้วยคำสั่งเดียว
```

| ขั้นตอน | เครื่องมือ | ไฟล์ |
|---|---|---|
| Source | Kaggle Dataset (CSV) | `data/current_catalog.csv`, `data/trajectory_timeseries.csv` |
| Ingestion & Load | Python, pandas, SQLAlchemy, psycopg 3 (COPY ทีละ 200,000 แถว) | `ingest.py` |
| Data Warehouse | PostgreSQL 15 บน Docker | `docker-compose.yml` |
| Transformation | Python, pandas, SQL | `transform.py` |
| Publish | Python, gspread, Google Service Account | `publish.py` |
| Orchestration | Python | `run_pipeline.py` |
| Visualization | Looker Studio | - |

**Schema `raw_data`** (ข้อมูลดิบตามไฟล์ต้นฉบับ ไม่แก้ไข ทุกคอลัมน์เก็บเป็นข้อความ)
1. **raw_data.current_catalog**: ข้อมูลดิบสถานะวงโคจรปัจจุบัน (17,861 แถว จาก current_catalog.csv)
2. **raw_data.trajectory_timeseries**: ข้อมูลดิบอนุกรมเวลาการเคลื่อนที่ย้อนหลัง (5,694,447 แถว จาก trajectory_timeseries.csv)

**Schema `production`** (ข้อมูลที่ทำความสะอาดแล้วและตารางสรุป)
3. **production.fact_catalog**: ตารางสถานะปัจจุบันที่ทำความสะอาดแล้วพร้อมคอลัมน์ที่สร้างเพิ่ม เช่น orbit_regime, orbital_period_min (17,861 แถว)
4. **production.agg_\***: ตารางสรุปสำหรับ dashboard (agg_overview, agg_country_counts, agg_constellation_counts, agg_risk_by_altitude, agg_orbital_band_profile, agg_daily_objects, agg_daily_by_constellation, agg_daily_by_country)
5. **production.cleaning_log**: บันทึกทุกขั้นตอนการทำความสะอาด (ใช้เป็นหลักฐานในรายงาน)

ข้อมูลอนุกรมเวลา (trajectory) หลังลบแถวซ้ำเหลือ 5,681,284 แถว (ลบ 13,163 แถว) และสรุปเป็นตาราง `agg_daily_*` แทนการเก็บเป็นตารางเต็ม

**Google Sheets:** ส่งขึ้นเฉพาะตารางสรุป 9 ตาราง (agg_* 8 ตาราง + cleaning_log) หนึ่งตารางต่อหนึ่งแท็บ รวมประมาณ 17,000 เซลล์

## Setup Guide

สิ่งที่ต้องมี: Docker Desktop, Python 3.13 หรือ version ที่มีการรองรับ package, ไฟล์ CSV จาก Kaggle, บัญชี Google

1. วางไฟล์ `current_catalog.csv` และ `trajectory_timeseries.csv` ในโฟลเดอร์ **`data/`**
2. เปิดฐานข้อมูล PostgreSQL: `docker compose up -d`
3. สร้าง virtual environment และติดตั้ง Library:
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
4. ตั้งค่า Google Sheets (ทำครั้งเดียว ดูหัวข้อด้านล่าง) แล้วสร้างไฟล์ `.env` จาก `.env.example` และใส่ `GSHEET_ID`
5. รัน pipeline ทั้งหมด:
```powershell
.\.venv\Scripts\python.exe run_pipeline.py
```

ตัวเลือก: `--skip-ingest` (ข้ามการโหลด CSV เมื่อ raw_data มีข้อมูลแล้ว), `--skip-publish` (ไม่ส่งขึ้น Google Sheets)
เวลาโดยประมาณทั้งหมด 1 นาที (ingest 20-40 วินาที, transform ~25 วินาที, publish ~20 วินาที) รันซ้ำได้ผลเหมือนเดิม

### ตั้งค่า Google Sheets (ครั้งเดียว)
1. [Google Cloud Console](https://console.cloud.google.com/) สร้างโปรเจกต์ แล้วเปิด **Google Sheets API** และ **Google Drive API**
2. IAM & Admin → Service Accounts → สร้าง Service Account (ไม่ต้องกำหนด Role)
3. แท็บ Keys → Add key → JSON แล้วเปลี่ยนชื่อเป็น `credentials.json` วางข้าง `run_pipeline.py`
4. สร้าง Google Sheet ว่าง แชร์ให้อีเมล `client_email` ในไฟล์ key สิทธิ์ **Editor**
5. ใส่ ID ของ Sheet (ส่วนระหว่าง `/d/` กับ `/edit` ใน URL) ในไฟล์ `.env`: `GSHEET_ID=...`
**ห้าม commit `credentials.json` และ `.env`** (อยู่ใน `.gitignore` แล้ว) ตรวจด้วย `git status` ก่อน push

## Troubleshooting

