import sqlite3
import random
from pathlib import Path

DB_PATH = Path(__file__).parent / "energy.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS facilities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            type TEXT NOT NULL,
            area_m2 INTEGER NOT NULL,
            baseline_year INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS energy_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            total_kwh REAL NOT NULL,
            avg_monthly_kwh REAL NOT NULL,
            FOREIGN KEY (facility_id) REFERENCES facilities(id)
        );

        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            consumption_kwh REAL NOT NULL,
            FOREIGN KEY (facility_id) REFERENCES facilities(id)
        );

        CREATE TABLE IF NOT EXISTS energy_measures (
            id TEXT PRIMARY KEY,
            facility_id TEXT NOT NULL,
            name TEXT NOT NULL,
            implementation_date TEXT NOT NULL,
            projected_saving_kwh REAL NOT NULL,
            actual_saving_kwh REAL,
            status TEXT NOT NULL,
            FOREIGN KEY (facility_id) REFERENCES facilities(id)
        );
    """)

    # --- Facilities ---
    facilities = [
        ("FAC-001", "Hamburg-Nord",  "Hamburg",  "Manufacturing", 8400, 2022),
        ("FAC-002", "Berlin-Mitte",  "Berlin",   "Office/Logistics", 3200, 2022),
        ("FAC-003", "Muenchen-Sued", "Munich",   "Warehouse", 5600, 2022),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO facilities VALUES (?,?,?,?,?,?)",
        facilities
    )

    # --- Monthly consumption seed ---
    # Realistic seasonal profiles per facility type
    seasonal = [1.18, 1.12, 1.05, 0.97, 0.88, 0.82, 0.80, 0.83, 0.92, 1.02, 1.10, 1.17]

    base_monthly = {
        "FAC-001": 68000,
        "FAC-002": 22000,
        "FAC-003": 38000,
    }

    # Efficiency improvements per year after baseline
    year_factor = {2022: 1.000, 2023: 0.965, 2024: 0.931}

    random.seed(42)
    for fac_id, base in base_monthly.items():
        for year in [2022, 2023, 2024]:
            for month in range(1, 13):
                noise = random.uniform(0.97, 1.03)
                kwh = round(base * seasonal[month-1] * year_factor[year] * noise, 1)
                c.execute(
                    "INSERT OR IGNORE INTO measurements (facility_id, year, month, consumption_kwh) VALUES (?,?,?,?)",
                    (fac_id, year, month, kwh)
                )

    # --- Baselines (2022 totals) ---
    for fac_id in base_monthly:
        c.execute(
            "SELECT SUM(consumption_kwh), AVG(consumption_kwh) FROM measurements WHERE facility_id=? AND year=2022",
            (fac_id,)
        )
        row = c.fetchone()
        c.execute(
            "INSERT OR IGNORE INTO energy_baselines (facility_id, year, total_kwh, avg_monthly_kwh) VALUES (?,?,?,?)",
            (fac_id, 2022, round(row[0], 1), round(row[1], 1))
        )

    # --- Energy-saving measures ---
    measures = [
        ("MSR-001", "FAC-001", "LED Lighting Retrofit",         "2023-03-01", 42000, 39800,  "completed"),
        ("MSR-002", "FAC-001", "HVAC Variable Speed Drives",    "2023-09-01", 55000, 51200,  "completed"),
        ("MSR-003", "FAC-002", "Building Insulation Upgrade",   "2023-06-01", 18000, 19100,  "completed"),
        ("MSR-004", "FAC-003", "Solar Panel Installation",      "2024-01-01", 72000, 68400,  "completed"),
        ("MSR-005", "FAC-003", "Compressed Air System Optimisation", "2024-06-01", 31000, None, "in_progress"),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO energy_measures VALUES (?,?,?,?,?,?,?)",
        measures
    )

    conn.commit()
    conn.close()
    print(f"Database initialised at {DB_PATH}")

if __name__ == "__main__":
    init_db()
