"""transform.py : raw_data -> production   (ขั้นที่ 2 ของ pipeline: Transform)

อ่านจาก
  - raw_data.current_catalog        (รายการวัตถุในวงโคจร ~17.8 พันแถว)
  - raw_data.trajectory_timeseries  (ข้อมูลรายวันของวัตถุเดิม ~5.7 ล้านแถว)
ทำงาน 4 อย่างตามโจทย์ ด้วย pandas แล้วเขียนผลลง schema production
  1. Cleaning            ทำความสะอาด (ลบซ้ำ, จัดการค่าว่าง, แปลงชนิดข้อมูล)
  2. Feature Engineering สร้างคอลัมน์ใหม่
  3. Joining             รวมสองไฟล์เข้าด้วยกันด้วย norad_id
  4. Aggregation         สรุปเป็นตารางเล็ก ๆ สำหรับทำ Dashboard

ตารางที่ publish.py จะส่งขึ้น Google Sheets คือตาราง agg_* (ขนาดเล็ก)
fact_catalog เก็บไว้ใน DB ใช้อ้างอิง ส่วน trajectory 5.7 ล้านแถวไม่ถูกเขียนซ้ำ
เพราะเกินข้อจำกัดของ Google Sheets (10 ล้านเซลล์)
"""
import numpy as np
import pandas as pd
from sqlalchemy import text

from ingest import RAW_SCHEMA, get_engine    # ใช้ตัวเชื่อมต่อ DB ร่วมกับ ingest.py

# ---------------------------------------------------------------- ค่าคงที่
PROD_SCHEMA = "production"                          # schema ปลายทางตามที่โจทย์กำหนด
CATALOG_TABLE = f"{RAW_SCHEMA}.current_catalog"
TRAJ_TABLE = f"{RAW_SCHEMA}.trajectory_timeseries"
STREAM_ROWS = 500_000                               # อ่านไฟล์ใหญ่ทีละ 500,000 แถว

# คอลัมน์ตัวเลขหลักที่ต้องมีค่า ถ้าว่างจะตัดแถวนั้นทิ้ง
CORE_NUM = ["altitude_km", "inclination", "eccentricity", "mean_motion"]
# คอลัมน์ข้อความที่ถ้าว่างจะเติมคำว่า 'UNKNOWN' (ไม่ลบแถว)
FILL_UNKNOWN = ["name", "object_type", "satellite_constellation", "altitude_category",
                "orbital_band", "congestion_risk", "country"]
# คอลัมน์ที่ตัดทิ้งเพราะไม่มีข้อมูลหรือค่าผิดพลาด (เหตุผลอยู่ใน cleaning_log)
DROP_COLS = ["launch_year_estimate", "days_in_orbit_estimate", "orbit_lifetime_category", "data_source"]

# ลำดับชั้นความสูง (ใช้เรียงแท่งกราฟใน Dashboard ให้เรียงจากต่ำไปสูง)
ALTITUDE_ORDER = {"Very Low LEO": 1, "Low LEO": 2, "Mid LEO": 3, "High LEO": 4,
                  "MEO": 5, "GEO": 6, "Beyond GEO": 7}
# จัดกลุ่มชั้นความสูงย่อยให้เป็นกลุ่มใหญ่ (LEO / MEO / GEO / Beyond GEO)
ORBIT_REGIME = {"Very Low LEO": "LEO", "Low LEO": "LEO", "Mid LEO": "LEO", "High LEO": "LEO",
                "MEO": "MEO", "GEO": "GEO", "Beyond GEO": "Beyond GEO"}
TOP_COUNTRIES = 5                                    # จำนวนประเทศที่แยกชื่อ ที่เหลือรวมเป็น OTHER


def _log(log, dataset, step, removed, detail):
    """บันทึกขั้นตอนการทำความสะอาด 1 บรรทัด (ไปอยู่ในตาราง cleaning_log ใช้เขียนรายงานได้)"""
    log.append({"dataset": dataset, "step": step, "rows_removed": int(removed), "detail": detail})


def _clean_text(s):
    """ตัดช่องว่างหน้าหลังข้อความ และเปลี่ยนข้อความว่างให้เป็นค่าว่างจริง (NA)"""
    s = s.astype("string").str.strip()
    return s.mask(s == "")


# ------------------------------------------------------- Catalog (ไฟล์เล็ก ใช้ pandas ทั้งก้อน)
def clean_catalog(raw, log):
    """ทำความสะอาดตาราง catalog คืน DataFrame ที่สะอาดแล้ว"""
    df = raw.copy()
    n0 = len(df)
    _log(log, "catalog", "start", 0, f"{n0:,} rows, {df.shape[1]} columns")

    # 1) ตัดช่องว่าง และแปลงคอลัมน์ตัวเลขจากข้อความ (ใน raw_data ทุกอย่างเป็น TEXT)
    for c in df.columns:
        df[c] = _clean_text(df[c])
    for c in CORE_NUM + ["norad_id"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")   # แปลงไม่ได้ -> NaN

    # 2) ลบแถวที่ norad_id ซ้ำ (1 วัตถุ = 1 แถว)
    b = len(df)
    df = df.drop_duplicates(subset=["norad_id"], keep="first")
    _log(log, "catalog", "drop_duplicate_norad_id", b - len(df), "norad_id ซ้ำ")

    # 3) ลบแถวที่ตัวเลขหลักว่าง
    b = len(df)
    df = df.dropna(subset=["norad_id"] + CORE_NUM)
    _log(log, "catalog", "drop_missing_numeric", b - len(df), "altitude/inclination/eccentricity/mean_motion ว่าง")

    # 4) เติม 'UNKNOWN' ในคอลัมน์ข้อความที่ว่าง (ไม่ลบแถว) และทำตัวพิมพ์ใหญ่ให้เหมือนกัน
    for c in FILL_UNKNOWN:
        n_fill = int(df[c].isna().sum())
        df[c] = df[c].fillna("UNKNOWN").str.upper() if c not in ("name", "altitude_category") else df[c].fillna("UNKNOWN")
        if n_fill:
            _log(log, "catalog", f"fill_unknown:{c}", 0, f"เติม 'UNKNOWN' {n_fill} แถว (ไม่ลบแถว)")

    # 5) แปลงชนิดข้อมูลวันที่/เวลา
    df["norad_id"] = df["norad_id"].astype(int)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce").dt.date
    df["epoch"] = pd.to_datetime(df["epoch"], errors="coerce")

    # 6) ตัดคอลัมน์ที่ใช้ไม่ได้ (เหตุผลบันทึกไว้ใน log)
    df = df.drop(columns=DROP_COLS)
    _log(log, "catalog", "drop_unreliable_columns", 0,
         "ตัด " + ", ".join(DROP_COLS) + " (launch_year_estimate มีแค่ 2023/2024, days_in_orbit 0-30, "
         "orbit_lifetime '<1yr' 99.98%, data_source ค่าเดียว)")
    _log(log, "catalog", "end", n0 - len(df), f"{len(df):,} rows")
    return df.reset_index(drop=True)


def engineer_catalog(df):
    """Feature Engineering: สร้างคอลัมน์ใหม่จากคอลัมน์เดิม"""
    df = df.copy()
    # กลุ่มวงโคจรใหญ่ (LEO/MEO/GEO/Beyond GEO) และลำดับความสูงสำหรับเรียงกราฟ
    df["orbit_regime"] = df["altitude_category"].map(ORBIT_REGIME).fillna("UNKNOWN")
    df["altitude_order"] = df["altitude_category"].map(ALTITUDE_ORDER).fillna(99).astype(int)
    # คาบการโคจร (นาที) = 1440 นาทีต่อวัน / จำนวนรอบต่อวัน
    df["orbital_period_min"] = (1440 / df["mean_motion"]).round(2)
    # อายุของข้อมูลวงโคจร (วัน) = วันที่บันทึก - วันที่ของ epoch
    df["epoch_age_days"] = (pd.to_datetime(df["snapshot_date"]) - df["epoch"].dt.normalize()).dt.days
    # ธง: เป็นดาวเทียม Starlink หรือไม่
    df["is_starlink"] = df["satellite_constellation"].str.startswith("STARLINK")

    # country_group: แยกชื่อ 5 ประเทศที่มีวัตถุมากสุด (ไม่นับ UNKNOWN/TBD) ที่เหลือรวมเป็น OTHER
    ranked = df.loc[~df["country"].isin(["UNKNOWN", "TBD"]), "country"].value_counts()
    top = list(ranked.head(TOP_COUNTRIES).index)
    df["country_group"] = np.where(df["country"].isin(top), df["country"], "OTHER")
    return df


def aggregate_catalog(df):
    """Aggregation: สรุปตาราง catalog เป็นตารางเล็ก ๆ ตอบคำถามธุรกิจ (คืน dict ชื่อตาราง -> DataFrame)"""
    n = len(df)
    t = {}

    # จำนวนวัตถุแยกตามประเทศ: แสดง 14 ประเทศแรก ที่เหลือรวมเป็นแถว "OTHER (...)"
    g = df.groupby("country").size().rename("n").reset_index().sort_values("n", ascending=False)
    head, rest = g.head(14), g.iloc[14:]
    if len(rest):
        head = pd.concat([head, pd.DataFrame([{"country": f"OTHER ({len(rest)} countries)", "n": rest["n"].sum()}])])
    head["pct"] = (head["n"] / n * 100).round(2)
    t["agg_country_counts"] = head.reset_index(drop=True)

    # จำนวนวัตถุแยกตามกลุ่มดาวเทียม (constellation)
    g = df.groupby("satellite_constellation").size().rename("n").reset_index().sort_values("n", ascending=False)
    g["pct"] = (g["n"] / n * 100).round(2)
    t["agg_constellation_counts"] = g.reset_index(drop=True)

    # ความเสี่ยงชนกัน (congestion_risk) ในแต่ละชั้นความสูง พร้อมสัดส่วนภายในชั้นเดียวกัน
    g = (df.groupby(["altitude_category", "altitude_order", "congestion_risk"]).size()
         .rename("n").reset_index())
    g["pct_within_altitude"] = (g["n"] / g.groupby("altitude_category")["n"].transform("sum") * 100).round(2)
    t["agg_risk_by_altitude"] = g.sort_values(["altitude_order", "congestion_risk"]).reset_index(drop=True)

    # ลักษณะของวงโคจรแต่ละแบบ (orbital_band): ความสูง ความเอียง ความรี คาบการโคจร
    t["agg_orbital_band_profile"] = (
        df.groupby("orbital_band")
        .agg(n=("norad_id", "size"), median_altitude_km=("altitude_km", "median"),
             median_inclination=("inclination", "median"), avg_eccentricity=("eccentricity", "mean"),
             median_period_min=("orbital_period_min", "median"))
        .round(3).reset_index().sort_values("n", ascending=False))
    return t


# --------------------------------------- Trajectory (ไฟล์ใหญ่ ประมวลผลทีละ chunk)
def process_trajectory(engine, catalog, log):
    """ลบซ้ำ + ตัดค่าว่างฝั่งฐานข้อมูล แล้วอ่านทีละ chunk มา Join กับ catalog
    และรวมยอดรายวันด้วย pandas (ไม่โหลด 5.7 ล้านแถวเข้า RAM ทีเดียว)"""
    cols = ("norad_id, snapshot_date, altitude_km, inclination, eccentricity, mean_motion, congestion_risk")
    not_null = " AND ".join(f"{c} IS NOT NULL" for c in CORE_NUM + ["norad_id", "snapshot_date"])
    # DISTINCT ON: ถ้า (norad_id, snapshot_date) ซ้ำ ให้เก็บแถวที่ epoch ใหม่สุดเพียงแถวเดียว
    query = f"""
        SELECT DISTINCT ON (norad_id, snapshot_date) {cols}
        FROM {TRAJ_TABLE}
        WHERE {not_null}
        ORDER BY norad_id, snapshot_date, epoch DESC
    """
    # นับแถวเพื่อบันทึกใน cleaning_log
    with engine.connect() as conn:
        raw_n = conn.execute(text(f"SELECT COUNT(*) FROM {TRAJ_TABLE}")).scalar()
        valid_n = conn.execute(text(f"SELECT COUNT(*) FROM {TRAJ_TABLE} WHERE {not_null}")).scalar()
    _log(log, "trajectory", "start", 0, f"{raw_n:,} rows")
    _log(log, "trajectory", "drop_missing_numeric", raw_n - valid_n, "ค่าตัวเลขหลักหรือวันที่ว่าง")

    # Joining: ใช้ constellation และ country_group ของ catalog เป็นกลุ่มมาตรฐานของแต่ละวัตถุ
    # (ในไฟล์รายวัน country ของ 491 วัตถุเปลี่ยนค่าไปมา จึงไม่ใช้ค่าในไฟล์รายวัน)
    lookup = catalog[["norad_id", "satellite_constellation", "country_group"]]

    # ที่เก็บผลรวมของแต่ละ chunk (ภายหลังนำมารวมกันอีกครั้ง)
    d_all, d_con, d_cty = [], [], []
    streamed = unmatched = 0
    with engine.connect().execution_options(stream_results=True) as conn:   # อ่านแบบ stream ไม่ดึงทั้งก้อน
        for ch in pd.read_sql(text(query), conn, chunksize=STREAM_ROWS):
            streamed += len(ch)
            # แปลงชนิดข้อมูล (ใน raw_data เป็นข้อความ)
            ch["norad_id"] = pd.to_numeric(ch["norad_id"], errors="coerce").astype("Int64")
            ch["altitude_km"] = pd.to_numeric(ch["altitude_km"], errors="coerce")
            ch["is_high"] = (ch["congestion_risk"].str.strip().str.upper() == "HIGH").astype(int)
            # Join กับ catalog ด้วย norad_id (left join: เก็บทุกแถวของ trajectory)
            ch = ch.merge(lookup, on="norad_id", how="left")
            unmatched += int(ch["satellite_constellation"].isna().sum())
            ch["satellite_constellation"] = ch["satellite_constellation"].fillna("UNKNOWN")
            ch["country_group"] = ch["country_group"].fillna("UNKNOWN")

            # รวมยอดของ chunk นี้ (เก็บผลรวม ไม่ใช่ค่าเฉลี่ย เพื่อให้นำไปรวมข้าม chunk ได้ถูกต้อง)
            d_all.append(ch.groupby("snapshot_date").agg(
                objects=("norad_id", "size"), alt_sum=("altitude_km", "sum"), high=("is_high", "sum")))
            d_con.append(ch.groupby(["snapshot_date", "satellite_constellation"]).agg(
                objects=("norad_id", "size"), alt_sum=("altitude_km", "sum")))
            d_cty.append(ch.groupby(["snapshot_date", "country_group"]).agg(objects=("norad_id", "size")))

    _log(log, "trajectory", "drop_duplicates", valid_n - streamed,
         "แถวซ้ำ (norad_id + snapshot_date เดียวกัน) เก็บแถวที่ epoch ใหม่สุด")
    _log(log, "trajectory", "join_catalog", 0, f"Join กับ catalog ด้วย norad_id: ไม่พบคู่ {unmatched} แถว")
    _log(log, "trajectory", "end", raw_n - streamed, f"{streamed:,} rows")

    def combine(parts):
        """รวมผลของทุก chunk เข้าด้วยกัน (บวกผลรวมของกลุ่มเดียวกัน) แล้วเรียงตามวันที่"""
        out = pd.concat(parts).groupby(level=list(range(parts[0].index.nlevels))).sum().reset_index()
        out["snapshot_date"] = pd.to_datetime(out["snapshot_date"]).dt.date
        return out.sort_values("snapshot_date").reset_index(drop=True)

    # ตารางรายวันรวมทุกวัตถุ: จำนวนวัตถุ, ความสูงเฉลี่ย, % ความเสี่ยงสูง
    daily = combine(d_all)
    daily["avg_altitude_km"] = (daily["alt_sum"] / daily["objects"]).round(2)
    daily["pct_high_risk"] = (daily["high"] / daily["objects"] * 100).round(2)
    daily = daily.rename(columns={"objects": "objects_tracked"})[
        ["snapshot_date", "objects_tracked", "avg_altitude_km", "pct_high_risk"]]

    # ตารางรายวันแยกตามกลุ่มดาวเทียม
    by_con = combine(d_con)
    by_con["avg_altitude_km"] = (by_con["alt_sum"] / by_con["objects"]).round(2)
    by_con = by_con.rename(columns={"objects": "objects_tracked"})[
        ["snapshot_date", "satellite_constellation", "objects_tracked", "avg_altitude_km"]]

    # ตารางรายวันแยกตามกลุ่มประเทศ
    by_cty = combine(d_cty).rename(columns={"objects": "objects_tracked"})
    return {"agg_daily_objects": daily, "agg_daily_by_constellation": by_con, "agg_daily_by_country": by_cty}


# ------------------------------------------------------------------- main
def overview(catalog, daily):
    """ตารางตัวเลขภาพรวม 1 แถว สำหรับ Scorecard ใน Dashboard"""
    return pd.DataFrame([{
        "total_objects": len(catalog),
        "n_countries": catalog["country"].nunique(),
        "n_constellations": catalog["satellite_constellation"].nunique(),
        "pct_starlink": round(catalog["is_starlink"].mean() * 100, 2),
        "pct_high_risk_now": round((catalog["congestion_risk"] == "HIGH").mean() * 100, 2),
        "median_altitude_km": round(catalog["altitude_km"].median(), 1),
        "first_snapshot": daily["snapshot_date"].min(),
        "last_snapshot": daily["snapshot_date"].max(),
        "days_covered": daily["snapshot_date"].nunique(),
    }])


def main():
    """จุดเริ่มต้น: อ่าน raw_data -> ทำความสะอาด/สร้างฟีเจอร์/Join/สรุป -> เขียนลง production"""
    engine = get_engine()
    log = []                                              # เก็บบันทึกการทำความสะอาด

    # ขั้น 1: catalog (ไฟล์เล็ก)
    raw_cat = pd.read_sql(f"SELECT * FROM {CATALOG_TABLE}", engine)
    print(f"[transform] อ่าน {CATALOG_TABLE}: {len(raw_cat):,} rows")
    catalog = engineer_catalog(clean_catalog(raw_cat, log))

    # ขั้น 2: trajectory (ไฟล์ใหญ่ ทีละ chunk) และ Join กับ catalog
    print(f"[transform] ประมวลผล {TRAJ_TABLE} ทีละ chunk (ใช้เวลาสักครู่)...")
    traj = process_trajectory(engine, catalog, log)

    # ขั้น 3: รวมทุกตารางที่จะเขียนลง production
    tables = {"fact_catalog": catalog}
    tables.update(aggregate_catalog(catalog))
    tables.update(traj)
    tables["agg_overview"] = overview(catalog, traj["agg_daily_objects"])
    tables["cleaning_log"] = pd.DataFrame(log)

    # ขั้น 4: เขียนลง schema production (ตารางเดิมถูกแทนที่ รันซ้ำได้)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {PROD_SCHEMA}"))
    for name, df in tables.items():
        df.to_sql(name, engine, schema=PROD_SCHEMA, if_exists="replace", index=False, chunksize=10000)
        print(f"[transform] -> {PROD_SCHEMA}.{name}: {len(df):,} rows")

    # แสดงบันทึกการทำความสะอาด (ใช้เขียนรายงานหัวข้อขั้นตอนการทำงานได้)
    print("\n[transform] cleaning log:")
    with pd.option_context("display.max_colwidth", 90, "display.width", 200):
        print(tables["cleaning_log"].to_string(index=False))


if __name__ == "__main__":
    main()
