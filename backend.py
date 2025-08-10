from fastapi import FastAPI
from pydantic import BaseModel, Field
import requests

app = FastAPI(title="Bolt Backend", description="CS2 Prop Evaluation API", version="2.0")

class PropInput(BaseModel):
    player_name: str = Field(..., description="Name of the player")
    kill_line: float = Field(..., description="Kill line from PrizePicks")
    hs_line: float = Field(..., description="Headshot line from PrizePicks")
    salary: float = Field(..., description="Player salary or cost")
    map_count: int = Field(default=2, description="Number of maps in match")

class PropResult(BaseModel):
    verdict: str
    value_score: float
    expected_kills: float
    used_kpr: float
    used_hs: float
    notes: str

@app.get("/")
def home():
    return {"status": "live", "message": "Bolt backend is running with Pydantic v2"}

@app.post("/evaluate", response_model=PropResult)
def evaluate_prop(data: PropInput):
    # Dummy example — replace with HLTV scraping / real logic
    used_kpr = 0.75
    used_hs = 0.42
    expected_kills = used_kpr * data.map_count * 24  # assume 24 rounds/map avg
    value_score = (data.hs_line * 0.65 + (data.kill_line / data.map_count) * 0.35) - data.salary

    verdict = "Good Value" if value_score >= 12.5 else "Pass"

    return PropResult(
        verdict=verdict,
        value_score=round(value_score, 2),
        expected_kills=round(expected_kills, 2),
        used_kpr=used_kpr,
        used_hs=used_hs,
        notes="Demo calculation — integrate HLTV stats for real results."
    )
