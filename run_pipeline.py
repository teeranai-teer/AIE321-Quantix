"""run_pipeline.py : รันทั้ง pipeline ด้วยคำสั่งเดียว   python run_pipeline.py

ลำดับ: ingest (CSV -> raw_data) -> transform (raw_data -> production) -> publish (production -> Google Sheets)
ถ้าขั้นใดล้มเหลว จะหยุดทันทีและบอกว่าล้มที่ขั้นไหน (ไม่รันขั้นถัดไปด้วยข้อมูลที่ไม่ครบ)

ตัวเลือก
  --skip-ingest   ข้ามขั้นโหลด CSV (เมื่อ raw_data มีข้อมูลอยู่แล้ว ประหยัดเวลาตอน demo)
  --skip-publish  ไม่ส่งขึ้น Google Sheets (ใช้ทดสอบตอนยังไม่มี credentials.json)
"""
import argparse
import sys
import time

import ingest
import publish
import transform


def run_step(name, fn):
    """รัน 1 ขั้นตอน พร้อมจับเวลา ถ้า error ให้หยุดทั้ง pipeline"""
    print(f"\n{'=' * 60}\n  {name}\n{'=' * 60}")
    t0 = time.time()
    try:
        fn()
    except Exception as exc:
        print(f"\n[pipeline] ล้มเหลวที่ขั้น {name}: {type(exc).__name__}: {exc}")
        sys.exit(1)
    print(f"[pipeline] {name} เสร็จใน {time.time() - t0:.1f} วินาที")


def main():
    parser = argparse.ArgumentParser(description="รัน pipeline: ingest -> transform -> publish")
    parser.add_argument("--skip-ingest", action="store_true", help="ข้ามขั้นโหลด CSV เข้า raw_data")
    parser.add_argument("--skip-publish", action="store_true", help="ข้ามขั้นส่งขึ้น Google Sheets")
    args = parser.parse_args()

    t0 = time.time()
    if not args.skip_ingest:
        run_step("1/3 INGEST  (CSV -> raw_data)", ingest.main)
    run_step("2/3 TRANSFORM  (raw_data -> production)", transform.main)
    if not args.skip_publish:
        run_step("3/3 PUBLISH  (production -> Google Sheets)", publish.main)
    print(f"\n[pipeline] สำเร็จทั้งหมด ใช้เวลารวม {time.time() - t0:.1f} วินาที")


if __name__ == "__main__":
    main()
