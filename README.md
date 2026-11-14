# AIE321-Quantix
AIE321 Data Science Project by Team Quantix. Analyzing the Synthetic Cognitive Behavior Dataset (SCBD) using Python, Exploratory Data Analysis (EDA), Data Visualization, and Machine Learning to explore human behavior and decision-making patterns.
# AIE321-Quantix

AIE321 Data Science Project by Team Quantix. Analyzing the Synthetic Cognitive Behavior Dataset (SCBD) using Python, Exploratory Data Analysis (EDA), Data Visualization, and Machine Learning to explore human behavior and decision-making patterns.

---

## 🗄️ Database Architecture & Data Pipeline

โปรเจกต์นี้ใช้ **PostgreSQL 15** รันผ่าน **Docker** เป็นศูนย์กลางจัดเก็บข้อมูล และใช้ Python (`pandas` + `SQLAlchemy`) สำหรับทำ ETL (Extract, Transform, Load)

### โครงสร้างตารางในฐานข้อมูล (`kaggle_db`)
1. **`scbd_raw`**: ตารางเก็บข้อมูลดิบทั้งหมด 100,000 แถว นำเข้าโดยตรงจากชุดข้อมูล Kaggle (`synthetic_human_training_data.csv`)
2. **`scbd_cleaned`**: ตารางข้อมูลที่ผ่านการตรวจสอบคุณภาพ (Data Quality Check) ลบค่าซ้ำ/ค่าว่าง และปรับมาตรฐานข้อความเรียบร้อยแล้ว พร้อมสำหรับงาน EDA และ Machine Learning

---

## 🚀 คู่มือการติดตั้งและรันระบบ (Setup Guide)

### 1. เตรียมไฟล์ข้อมูล
ดาวน์โหลดชุดข้อมูล **Synthetic Cognitive Behavior Dataset (SCBD)** จาก Kaggle และนำไฟล์ `synthetic_human_training_data.csv` มาวางไว้ในโฟลเดอร์หลักของโปรเจกต์

### 2. เปิดใช้งานฐานข้อมูล PostgreSQL ด้วย Docker
```bash
docker-compose up -d