from sqlalchemy import create_engine, text

DB_URL = "postgresql://myuser:mypassword@localhost:5432/kaggle_db"
engine = create_engine(DB_URL)

print("\n" + "="*60)
print("🔍 กำลังตรวจสอบและทำความสะอาดตารางใน PostgreSQL...")
print("="*60)

with engine.begin() as conn:
    # 1. สร้าง satellite_current_cleaned
    conn.execute(text("DROP TABLE IF EXISTS satellite_current_cleaned;"))
    conn.execute(text("""
        CREATE TABLE satellite_current_cleaned AS
        SELECT DISTINCT ON (norad_id)
            norad_id,
            COALESCE(NULLIF(TRIM(name), ''), 'unknown') AS name,
            COALESCE(NULLIF(TRIM(object_type), ''), 'unknown') AS object_type,
            COALESCE(NULLIF(TRIM(satellite_constellation), ''), 'unknown') AS satellite_constellation,
            altitude_km,
            COALESCE(NULLIF(TRIM(altitude_category), ''), 'unknown') AS altitude_category,
            COALESCE(NULLIF(TRIM(orbital_band), ''), 'unknown') AS orbital_band,
            COALESCE(NULLIF(TRIM(congestion_risk), ''), 'unknown') AS congestion_risk,
            inclination,
            eccentricity,
            launch_year_estimate,
            days_in_orbit_estimate,
            COALESCE(NULLIF(TRIM(orbit_lifetime_category), ''), 'unknown') AS orbit_lifetime_category,
            mean_motion,
            epoch,
            COALESCE(NULLIF(TRIM(data_source), ''), 'unknown') AS data_source,
            snapshot_date,
            COALESCE(NULLIF(TRIM(country), ''), 'unknown') AS country,
            last_seen
        FROM satellite_current_raw
        WHERE altitude_km IS NOT NULL
          AND inclination IS NOT NULL
          AND eccentricity IS NOT NULL
          AND mean_motion IS NOT NULL
        ORDER BY norad_id;
    """))
    cur_raw = conn.execute(text("SELECT COUNT(*) FROM satellite_current_raw;")).scalar()
    cur_clean = conn.execute(text("SELECT COUNT(*) FROM satellite_current_cleaned;")).scalar()
    print(f"✅ 'satellite_current_cleaned' สำเร็จ! (ดิบ: {cur_raw:,} -> พร้อมใช้งาน: {cur_clean:,} แถว)")

    # 2. สร้าง satellite_trajectory_cleaned
    print("⏳ กำลังสร้าง 'satellite_trajectory_cleaned' จากข้อมูล 5.7 ล้านแถว...")
    conn.execute(text("DROP TABLE IF EXISTS satellite_trajectory_cleaned;"))
    conn.execute(text("""
        CREATE TABLE satellite_trajectory_cleaned AS
        SELECT DISTINCT ON (norad_id, snapshot_date)
            norad_id,
            COALESCE(NULLIF(TRIM(name), ''), 'unknown') AS name,
            COALESCE(NULLIF(TRIM(object_type), ''), 'unknown') AS object_type,
            COALESCE(NULLIF(TRIM(satellite_constellation), ''), 'unknown') AS satellite_constellation,
            altitude_km,
            COALESCE(NULLIF(TRIM(altitude_category), ''), 'unknown') AS altitude_category,
            COALESCE(NULLIF(TRIM(orbital_band), ''), 'unknown') AS orbital_band,
            COALESCE(NULLIF(TRIM(congestion_risk), ''), 'unknown') AS congestion_risk,
            inclination,
            eccentricity,
            launch_year_estimate,
            days_in_orbit_estimate,
            COALESCE(NULLIF(TRIM(orbit_lifetime_category), ''), 'unknown') AS orbit_lifetime_category,
            mean_motion,
            epoch,
            COALESCE(NULLIF(TRIM(data_source), ''), 'unknown') AS data_source,
            snapshot_date,
            COALESCE(NULLIF(TRIM(country), ''), 'unknown') AS country,
            last_seen
        FROM satellite_trajectory_raw
        WHERE altitude_km IS NOT NULL
          AND inclination IS NOT NULL
          AND eccentricity IS NOT NULL
          AND mean_motion IS NOT NULL
        ORDER BY norad_id, snapshot_date;
    """))
    traj_raw = conn.execute(text("SELECT COUNT(*) FROM satellite_trajectory_raw;")).scalar()
    traj_clean = conn.execute(text("SELECT COUNT(*) FROM satellite_trajectory_cleaned;")).scalar()
    print(f"✅ 'satellite_trajectory_cleaned' สำเร็จ! (ดิบ: {traj_raw:,} -> พร้อมใช้งาน: {traj_clean:,} แถว)")
