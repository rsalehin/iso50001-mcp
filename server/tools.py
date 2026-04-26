import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parent.parent / ".env")
DB_PATH = Path(__file__).parent / "energy.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_energy_baseline(facility_id: str, year: int) -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,))
    facility = c.fetchone()
    if not facility:
        conn.close()
        return {"error": f"Facility '{facility_id}' not found."}
    c.execute("SELECT * FROM energy_baselines WHERE facility_id = ? AND year = ?", (facility_id, year))
    baseline = c.fetchone()
    if not baseline:
        conn.close()
        return {"error": f"No baseline found for {facility_id} in {year}."}
    c.execute("SELECT month, consumption_kwh FROM measurements WHERE facility_id = ? AND year = ? ORDER BY month", (facility_id, year))
    monthly = [{"month": r["month"], "consumption_kwh": r["consumption_kwh"]} for r in c.fetchall()]
    conn.close()
    return {
        "facility_id": facility["id"],
        "facility_name": facility["name"],
        "location": facility["location"],
        "type": facility["type"],
        "area_m2": facility["area_m2"],
        "baseline_year": year,
        "total_kwh": baseline["total_kwh"],
        "avg_monthly_kwh": baseline["avg_monthly_kwh"],
        "intensity_kwh_per_m2": round(baseline["total_kwh"] / facility["area_m2"], 2),
        "monthly_breakdown": monthly,
    }

def compare_current_vs_baseline(facility_id: str, period: str) -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,))
    facility = c.fetchone()
    if not facility:
        conn.close()
        return {"error": f"Facility '{facility_id}' not found."}
    try:
        parts = period.split("-")
        year = int(parts[0])
        qualifier = parts[1].upper()
    except Exception:
        conn.close()
        return {"error": "Period must be formatted as 'YYYY-Q1' through 'YYYY-Q4' or 'YYYY-full'."}
    if qualifier == "FULL":
        months = list(range(1, 13))
    elif qualifier == "Q1":
        months = [1, 2, 3]
    elif qualifier == "Q2":
        months = [4, 5, 6]
    elif qualifier == "Q3":
        months = [7, 8, 9]
    elif qualifier == "Q4":
        months = [10, 11, 12]
    else:
        conn.close()
        return {"error": f"Unknown qualifier '{qualifier}'. Use Q1-Q4 or full."}
    placeholders = ",".join("?" * len(months))
    c.execute(f"SELECT SUM(consumption_kwh) as total FROM measurements WHERE facility_id=? AND year=? AND month IN ({placeholders})", [facility_id, year] + months)
    current_total = c.fetchone()["total"]
    baseline_year = facility["baseline_year"]
    c.execute(f"SELECT SUM(consumption_kwh) as total FROM measurements WHERE facility_id=? AND year=? AND month IN ({placeholders})", [facility_id, baseline_year] + months)
    baseline_total = c.fetchone()["total"]
    conn.close()
    if not current_total or not baseline_total:
        return {"error": "Insufficient data for the requested period."}
    delta_kwh = round(current_total - baseline_total, 1)
    delta_pct = round((delta_kwh / baseline_total) * 100, 2)
    status = "below_baseline" if delta_kwh < 0 else "above_baseline"
    return {
        "facility_id": facility_id,
        "facility_name": facility["name"],
        "period": period,
        "baseline_year": baseline_year,
        "baseline_kwh": round(baseline_total, 1),
        "current_kwh": round(current_total, 1),
        "delta_kwh": delta_kwh,
        "delta_percent": delta_pct,
        "status": status,
        "performance_summary": f"{abs(delta_pct)}% below baseline" if delta_kwh < 0 else f"{abs(delta_pct)}% above baseline",
    }

def assess_measure_effectiveness(measure_id: str) -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT m.*, f.name as facility_name FROM energy_measures m JOIN facilities f ON m.facility_id = f.id WHERE m.id = ?", (measure_id,))
    measure = c.fetchone()
    conn.close()
    if not measure:
        return {"error": f"Measure '{measure_id}' not found."}
    result = {
        "measure_id": measure["id"],
        "facility_id": measure["facility_id"],
        "facility_name": measure["facility_name"],
        "measure_name": measure["name"],
        "implementation_date": measure["implementation_date"],
        "status": measure["status"],
        "projected_saving_kwh": measure["projected_saving_kwh"],
        "actual_saving_kwh": measure["actual_saving_kwh"],
    }
    if measure["actual_saving_kwh"] is not None:
        variance = round(measure["actual_saving_kwh"] - measure["projected_saving_kwh"], 1)
        variance_pct = round((variance / measure["projected_saving_kwh"]) * 100, 2)
        result["variance_kwh"] = variance
        result["variance_percent"] = variance_pct
        result["effectiveness"] = "met_target" if variance >= 0 else "below_target"
        if variance >= 0:
            result["assessment_summary"] = f"Achieved {measure['actual_saving_kwh']:,.0f} kWh savings vs {measure['projected_saving_kwh']:,.0f} kWh projected ({abs(variance_pct)}% above target)."
        else:
            result["assessment_summary"] = f"Achieved {measure['actual_saving_kwh']:,.0f} kWh savings vs {measure['projected_saving_kwh']:,.0f} kWh projected ({abs(variance_pct)}% below target)."
    else:
        result["assessment_summary"] = "Measure in progress - actual savings not yet recorded."
    return result

def draft_management_review_section(facility_id: str, period: str) -> dict:
    baseline_data = get_energy_baseline(facility_id, 2022)
    comparison_data = compare_current_vs_baseline(facility_id, period)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM energy_measures WHERE facility_id = ? ORDER BY implementation_date", (facility_id,))
    measures = [dict(r) for r in c.fetchall()]
    conn.close()
    if "error" in baseline_data or "error" in comparison_data:
        return {"error": "Could not retrieve required data for drafting."}
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY not set"}
        
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    measures_text = "\n".join([
        f"- {m['name']} ({m['implementation_date']}): projected {m['projected_saving_kwh']:,.0f} kWh, actual {m['actual_saving_kwh']:,.0f} kWh, status: {m['status']}"
        if m["actual_saving_kwh"] else
        f"- {m['name']} ({m['implementation_date']}): projected {m['projected_saving_kwh']:,.0f} kWh, status: {m['status']}"
        for m in measures
    ])
    
    prompt_text = f"""You are an ISO 50001 compliance specialist. Draft the Energy Performance section for a management review document based on the following verified data.

FACILITY: {baseline_data['facility_name']} ({facility_id})
TYPE: {baseline_data['type']} | AREA: {baseline_data['area_m2']} m2
REVIEW PERIOD: {period}

ENERGY BASELINE (Reference Year 2022):
- Total annual consumption: {baseline_data['total_kwh']:,.0f} kWh
- Average monthly consumption: {baseline_data['avg_monthly_kwh']:,.0f} kWh
- Energy intensity: {baseline_data['intensity_kwh_per_m2']} kWh/m2

CURRENT PERFORMANCE vs BASELINE:
- Baseline period consumption: {comparison_data['baseline_kwh']:,.0f} kWh
- Current period consumption: {comparison_data['current_kwh']:,.0f} kWh
- Delta: {comparison_data['delta_kwh']:,.0f} kWh ({comparison_data['delta_percent']}%)
- Status: {comparison_data['status']}

ENERGY-SAVING MEASURES:
{measures_text}

Write a professional management review section (250-350 words) following ISO 50001:2018 clause 9.3 structure.
Include: energy performance trend, measure effectiveness, EnPI commentary, and recommended actions.
Use formal but clear language suitable for senior management. Output plain text, no markdown."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt_text}]
    )
    drafted_text = message.content[0].text
    return {
        "facility_id": facility_id,
        "facility_name": baseline_data["facility_name"],
        "period": period,
        "structured_inputs": {
            "baseline": baseline_data,
            "comparison": comparison_data,
            "measures_count": len(measures),
        },
        "drafted_section": drafted_text,
        "llm_used": True,
        "model": "claude-sonnet-4-20250514",
    }
