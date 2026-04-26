from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from tools import get_energy_baseline, compare_current_vs_baseline, assess_measure_effectiveness, draft_management_review_section

app = FastAPI(title="ISO 50001 Energy Baseline API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "ISO 50001 Energy Baseline MCP Server", "version": "1.0.0"}

@app.get("/tools/get_baseline")
def api_get_baseline(facility_id: str, year: int = 2022):
    result = get_energy_baseline(facility_id, year)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/tools/compare")
def api_compare(facility_id: str, period: str):
    result = compare_current_vs_baseline(facility_id, period)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/tools/assess_measure")
def api_assess_measure(measure_id: str):
    result = assess_measure_effectiveness(measure_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.post("/tools/draft_review")
def api_draft_review(facility_id: str, period: str):
    result = draft_management_review_section(facility_id, period)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
