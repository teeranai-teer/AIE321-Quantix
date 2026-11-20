# AIE321-Quantix

AIE321 Data Pipeline Project by Team Quantix. Analyzing the Satellite Orbital Catalog dataset from Kaggle with Python and PostgreSQL (Docker), publishing summary tables to Google Sheets and visualizing them in Looker Studio to explore satellite orbital parameters, congestion risk, and trajectory patterns.

- Dashboard (Looker Studio): https://datastudio.google.com/reporting/1d6f082e-06ae-4a62-b41b-ad05b560af2f

## Team Quantix

| หน้าที่ | ผู้รับผิดชอบ | งานที่ทำ | ไฟล์/ผลงาน |
|---|---|---|---|
| 1. Ingestion & Docker | ณัฐนิชา | PostgreSQL ด้วย Docker, โหลด CSV เข้า `raw_data`, GitHub, Google Cloud / Service Account | `docker-compose.yml`, `ingest.py`, `.env.example`, `README.md` |
| 2. Transform & Pipeline | ธีรนัย | ทำความสะอาด/สร้างฟีเจอร์/สรุปข้อมูลลง `production`, ส่งขึ้น Google Sheets, รวมเป็นคำสั่งเดียว | `transform.py`, `publish.py`, `run_pipeline.py` |
| 3. Dashboard & Insights | บัณฑิตา | Looker Studio (≥ 5 กราฟ), ตอบคำถามธุรกิจ, สรุป insight | Dashboard, ส่วน Insights ในรายงาน |

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

ดาวน์โหลดโปรเจกต์ (ทำครั้งเดียว):
```powershell
git clone https://github.com/teeranai-teer/AIE321-Quantix.git
cd AIE321-Quantix
```

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

## Sample Output

ผลลัพธ์ตัวอย่าง (รันจริงแบบ `--skip-ingest`):

```
[transform] อ่าน raw_data.current_catalog: 17,861 rows
[transform] -> production.fact_catalog: 17,861 rows
[transform] -> production.agg_daily_objects: 372 rows
[transform] -> production.cleaning_log: 12 rows
[pipeline] 2/3 TRANSFORM  (raw_data -> production) เสร็จใน 24.8 วินาที
[publish] รวม 17,391 เซลล์ (เพดาน 5,000,000)
[publish] agg_overview -> แท็บ 'agg_overview' เขียนแล้ว 1 แถว
...
[publish] cleaning_log -> แท็บ 'cleaning_log' เขียนแล้ว 12 แถว
[pipeline] สำเร็จทั้งหมด ใช้เวลารวม 46.1 วินาที
```

## Data Transformation (transform.py)

### Ingest (ingest.py)

โหลด CSV ทุกไฟล์ใน `data/` เข้า `raw_data.<ชื่อไฟล์>` โดยไม่แก้ข้อมูล (ทุกคอลัมน์เป็นข้อความ) อ่านทีละ 200,000 แถวและใช้ COPY ของ PostgreSQL จึงโหลดไฟล์ 1.09 GB ได้โดยไม่กิน RAM ตรวจจำนวนแถวใน DB เทียบกับ CSV ทุกครั้ง ถ้าไม่เท่ากันจะหยุด

### Cleaning

| ปัญหา | วิธีจัดการ |
|---|---|
| `launch_year_estimate` มีแค่ปี 2023 (114 ชิ้น) และ 2024 (17,747 ชิ้น) | ตัดคอลัมน์ |
| `days_in_orbit_estimate` ค่า 0-30 วันเท่านั้น | ตัดคอลัมน์ |
| `orbit_lifetime_category` ค่า "<1yr" 99.98% | ตัดคอลัมน์ |
| `data_source` มีค่าเดียว (celestrak) | ตัดคอลัมน์ |
| `object_type` และ `country` ว่างอย่างละ 15 ชิ้น | เติม `UNKNOWN` (ไม่ลบแถว) |
| catalog: `norad_id` ซ้ำ / ค่าตัวเลขหลักว่าง | ตรวจแล้วไม่พบ (ลบ 0 แถว) |
| trajectory: แถวซ้ำ (norad_id + snapshot_date เดียวกัน) 13,163 แถว | ลบ เก็บแถวที่ epoch ใหม่สุด (SQL `DISTINCT ON`) เหลือ 5,681,284 แถว |
| `country` ในไฟล์รายวันไม่คงที่ (491 วัตถุ) | ใช้ค่าจาก catalog (Join ด้วย `norad_id`) |

ทุกขั้นบันทึกไว้ในตาราง `production.cleaning_log` (ส่งขึ้นแท็บ `cleaning_log` ใน Sheets ด้วย)

**Feature Engineering** (`fact_catalog` มี 21 คอลัมน์ = 15 เดิม + 6 ใหม่): `orbit_regime` (LEO/MEO/GEO/Beyond GEO), `altitude_order` (1-7), `orbital_period_min` (= 1440 หาร mean_motion), `epoch_age_days`, `is_starlink`, `country_group` (5 ประเทศที่มีวัตถุมากสุด: US, PRC, UK, CIS, JPN ที่เหลือเป็น OTHER)

**Joining:** กลุ่มดาวเทียมและกลุ่มประเทศของแต่ละวัตถุใน trajectory ใช้ค่าจาก catalog (Join ด้วย `norad_id` ไม่พบคู่ 0 แถว)

**Aggregation:** อ่านและสรุป trajectory ทีละ 500,000 แถว แล้วรวมเป็นตารางรายวันขนาดเล็ก

| ตารางใน `production` | แถว | ใช้ตอบ |
|---|---|---|
| `fact_catalog` | 17,861 | ตารางหลัก (ไม่ส่งขึ้น Sheets) |
| `agg_country_counts` | 15 | Q1 |
| `agg_constellation_counts` | 6 | Q1 |
| `agg_risk_by_altitude` | 14 | Q2 |
| `agg_daily_objects` | 372 | Q3 |
| `agg_daily_by_country` | 2,232 | Q3 |
| `agg_daily_by_constellation` | 2,232 | Q4 |
| `agg_orbital_band_profile` | 8 | Q5 |
| `agg_overview` | 1 | Scorecard |
| `cleaning_log` | 12 | หลักฐานการทำความสะอาด |

ส่งขึ้น Google Sheets เฉพาะ 9 ตารางสรุป (ไม่รวม `fact_catalog`) รวม 17,391 เซลล์ ต่ำกว่าเพดาน 10 ล้านเซลล์ของ Sheets มาก

## Business Questions & Insights

ตัวเลขคำนวณจากตารางใน `production` (จาก current_catalog 17,861 ชิ้น และ trajectory 5,681,284 แถว)

**Q1. ประเทศและกลุ่มดาวเทียมใดมีวัตถุมากที่สุด และคิดเป็นสัดส่วนเท่าไร?**

- สหรัฐฯ (US) 13,336 ชิ้น (74.7%) สามอันดับแรก (US, PRC, UK) รวม 88.1% จาก 98 ประเทศ
- Starlink 11,730 ชิ้น (65.7%) รองลงมา OTHER 5,359 (30.0%) และ OneWeb 651 (3.6%)
- ข้อควรระวัง: ชื่อกลุ่มเป็นไปตามที่ dataset ระบุ ยังไม่ได้ตรวจว่า "GEN 1" ครอบคลุม Starlink รุ่นอื่นด้วยหรือไม่

**Q2. ชั้นความสูงใดมีสัดส่วนวัตถุเสี่ยงจากความหนาแน่น (congestion_risk) สูงที่สุด?**

- GEO สูงสุดที่ 98.6% (570 จาก 578 ชิ้น) แต่ในแง่จำนวน Very Low LEO สำคัญกว่า: 11,067 ชิ้นเป็น HIGH (86.1% ของชั้น) คิดเป็น 78.6% ของวัตถุ HIGH ทั้งหมด 14,086 ชิ้น
- ข้อควรระวัง: ใน Very Low LEO มี Starlink 89.4% ของวัตถุ (HIGH 88.9% เทียบกับ 63.2% ของวัตถุอื่นในชั้นเดียวกัน) ผลผูกกับ Starlink มาก และเกณฑ์ความเสี่ยงคำนวณโดยผู้ประกอบ dataset ทีมไม่ทราบสูตร

**Q3. จำนวนวัตถุที่ติดตามได้เปลี่ยนไปอย่างไรใน 372 วัน และกลุ่มประเทศใดเพิ่มมากที่สุด?**

- เพิ่มจาก 13,135 เป็น 16,894 ชิ้น (+3,759, +28.6%) สหรัฐฯ เพิ่มมากสุด +2,941 ชิ้น (78.2% ของการเพิ่มทั้งหมด) จีน (PRC) เพิ่มเป็นสัดส่วนสูงสุด +37.2% ส่วน UK แทบไม่เปลี่ยน (+1.3%)
- ข้อควรระวัง: ไฟล์รายวันมีเฉพาะวัตถุที่อยู่ใน catalog ปัจจุบัน จึงไม่รวมวัตถุที่ตกหรือถูกถอดออกไปแล้ว ตัวเลขนี้ไม่ใช่จำนวนดาวเทียมทั้งโลก และวันสุดท้าย (16,894) ต่างจาก catalog (17,861) 967 ชิ้น ยังไม่ได้ตรวจสาเหตุ

**Q4. ความสูงเฉลี่ยของแต่ละกลุ่มดาวเทียม โดยเฉพาะ Starlink เปลี่ยนไปอย่างไรตามเวลา?**

- ความสูงเฉลี่ยของ Starlink ลดจาก 501.5 เป็น 459.2 กม. (-42.3 กม.) ขณะที่จำนวนเพิ่มจาก 8,688 เป็น 11,188 ชิ้น
- ข้อควรระวัง: ค่าเฉลี่ยลดได้จากดาวเทียมใหม่ที่เข้ามาในกลุ่ม (+2,500 ชิ้น) ไม่ใช่ดาวเทียมเดิมลดวงโคจรอย่างเดียว การพิสูจน์ต้องติดตามรายดวงด้วย `norad_id` ซึ่งยังไม่ได้ทำ

**Q5. วงโคจรแต่ละแบบ (orbital_band) ต่างกันที่ความสูง มุมเอียง และคาบการโคจรอย่างไร?**

| วงโคจร | จำนวน | ความสูงมัธยฐาน (กม.) | มุมเอียงมัธยฐาน (°) | คาบมัธยฐาน (นาที) |
|---|---|---|---|---|
| LEO-Inclined | 7,538 | 463 | 53.2 | 93.9 |
| LEO-Polar | 5,426 | 503 | 97.3 | 94.7 |
| LEO-Equatorial | 4,026 | 483 | 43.0 | 94.3 |
| GEO | 431 | 35,787 | 0.04 | 1,436 |
| MEO | 293 | 21,526 | 54.3 | 773 |
| GEO-Inclined | 78 | 35,787 | 8.2 | 1,436 |
| HEO | 57 | 36,163 | 5.8 | 1,455 |
| LEO-Retrograde | 12 | 531 | 120.5 | 95.3 |

- วงโคจรระดับต่ำ (LEO) ทุกแบบอยู่ที่ราว 463-531 กม. คาบ 94-95 นาที ต่างกันที่มุมเอียงเป็นหลัก GEO คาบ 1,436 นาที (ประมาณ 23.9 ชั่วโมง) ใกล้ 1 รอบการหมุนของโลก
- ใช้ค่ามัธยฐานเพราะมีค่าสูงสุดถึง 242,362 กม. (อาจเป็นวงโคจรรีสูงที่ถูกต้อง ยังไม่ยืนยัน) ชื่อวงโคจรเป็นไปตาม dataset

## Dashboard on Looker Studio

1. ไปที่ [lookerstudio.google.com](https://lookerstudio.google.com/) → Create → Report → เพิ่มข้อมูลจาก Google Sheets
2. เลือกไฟล์ Google Sheet ของโปรเจกต์ → เลือกแท็บที่ต้องใช้ (แต่ละแท็บเป็นแหล่งข้อมูลแยกกัน) → ติ๊ก Use first row as headers → Add
3. ตรวจชนิดฟิลด์: `snapshot_date` = Date, ตัวเลข = Number
4. ตั้ง Data credentials ของแหล่งข้อมูลเป็น Owner's credentials เพื่อให้ผู้ชมที่ไม่มีสิทธิ์ใน Sheet เห็นกราฟได้
5. สร้าง Scorecard (แท็บ `agg_overview`): `total_objects`, `n_countries`, `pct_starlink`, `pct_high_risk_now`, `median_altitude_km`

### 5 Visualization ที่ตอบคำถาม

| # | คำถาม | Chart | แท็บข้อมูล | Dimension / Metric |
|---|---|---|---|---|
| 1 | Q1 | Bar แนวนอน | `agg_country_counts`, `agg_constellation_counts` | country / n |
| 2 | Q2 | 100% Stacked bar | `agg_risk_by_altitude` | altitude_category (เรียงตาม altitude_order) แยกสีตาม congestion_risk / n |
| 3 | Q3 | Stacked area | `agg_daily_by_country` | snapshot_date แยกสีตาม country_group / objects_tracked |
| 4 | Q4 | Line | `agg_daily_by_constellation` | snapshot_date แยกเส้นตาม satellite_constellation / avg_altitude_km |
| 5 | Q5 | Bar + Table | `agg_orbital_band_profile` | orbital_band / median_altitude_km, median_inclination, median_period_min |

ข้อควรระวัง: ในกราฟที่ 4 ความสูง BeiDou (~27,385 กม.) กับ Starlink (~459 กม.) ต่างกันมาก ให้เพิ่ม Filter control เลือกกลุ่มดาวเทียม (ค่าเริ่มต้น STARLINK GEN 1) ส่วนกราฟที่ 5 ให้ใช้มุมเอียงเป็นแท่ง เพราะความสูง GEO ทำให้แท่ง LEO สั้นจนมองไม่เห็น

เพิ่ม Filter controls: `satellite_constellation`, `country_group` และ Date range control บน `snapshot_date` แชร์รายงาน: Share → Manage access → Anyone with the link → Viewer แล้วทดสอบในหน้าต่างไม่ระบุตัวตน

## Project Structure

```
.
├── docker-compose.yml   # PostgreSQL 15
├── .env.example         # ตัวอย่างค่าตั้งค่า (คัดลอกเป็น .env)
├── .gitignore           # กัน credentials.json, .env, .venv, data/*.csv
├── requirements.txt
├── ingest.py            # Kaggle CSV -> raw_data
├── transform.py         # raw_data -> production
├── publish.py           # production -> Google Sheets
├── run_pipeline.py      # รันทั้งหมดด้วยคำสั่งเดียว
└── data/                # วางไฟล์ CSV ที่นี่ (ไม่ถูก commit)
```

## Troubleshooting

| อาการ | วิธีแก้ |
|---|---|
| `pip install` ไม่ผ่านบน Python 3.15 | ใช้ Python 3.13 |
| VS Code ขีดแดงที่ import | Ctrl+Shift+P → Python: Select Interpreter → เลือก `.venv` |
| `ModuleNotFoundError: dotenv` | `pip install -r requirements.txt` (package ชื่อ `python-dotenv`) |
| `FileNotFoundError: ไม่พบไฟล์ CSV` | วางไฟล์ CSV ในโฟลเดอร์ `data/` |
| เชื่อมฐานข้อมูลไม่ได้ (connection refused) | ยังไม่ได้ `docker compose up -d` หรือพอร์ต 5432 ชนกับ Postgres ในเครื่อง → เปลี่ยน `DB_PORT` ใน `.env` |
| `ไม่พบไฟล์ ...credentials.json` | วางไฟล์ key ผิดที่หรือชื่อผิด (ระวัง `credentials.json.json`) |
| หน้า "ไม่พบเพจ" (APIError พร้อม HTML ยาว) | `GSHEET_ID` ผิดหรือไม่ครบ ให้ใส่เฉพาะส่วนระหว่าง `/d/` กับ `/edit` หรือลบค่าแล้วใช้ `GSHEET_NAME` |
| `เปิด Google Sheet ไม่ได้` | ยังไม่ได้แชร์ Sheet ให้ `client_email` สิทธิ์ Editor หรือชื่อไม่ตรง |
| 403 หรือ `API has not been used in project` | ยังไม่ได้เปิด Google Sheets API / Drive API |
| 429 Quota exceeded | รอ 1 นาทีแล้วรันใหม่ |
