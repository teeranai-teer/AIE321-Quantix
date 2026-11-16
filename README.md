# AIE321-Quantix

AIE321 Data Science Project by Team Quantix. Analyzing the **Satellite Orbital Catalog** dataset from Kaggle using Python, PostgreSQL, Exploratory Data Analysis (EDA), and Machine Learning to explore satellite orbital parameters, congestion risk, and trajectory patterns.

## Database Architecture & Data Pipeline
1. **satellite_current_raw**: ข้อมูลดิบสถานะวงโคจรปัจจุบัน (17,861 แถว จาก current_catalog.csv)
2. **satellite_trajectory_raw**: ข้อมูลดิบอนุกรมเวลาการเคลื่อนที่ย้อนหลัง (5,694,447 แถว จาก trajectory_timeseries.csv)
3. **satellite_current_cleaned**: ตารางสถานะปัจจุบันที่ทำความสะอาดแล้ว (17,861 แถว)
4. **satellite_trajectory_cleaned**: ตารางอนุกรมเวลาที่ทำความสะอาดแล้ว (5,681,284 แถว)

## Setup Guide
1. วางไฟล์ current_catalog.csv และ trajectory_timeseries.csv ในโฟลเดอร์หลัก
2. เปิดฐานข้อมูล PostgreSQL: docker-compose up -d
3. ติดตั้ง Library: pip install -r requirements.txt
4. นำเข้าและทำความสะอาดข้อมูล: python ingest.py && python data_quality_and_clean.py

##


