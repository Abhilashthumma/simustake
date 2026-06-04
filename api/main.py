import os
import uuid
import json
from datetime import datetime, timezone

from fastapi              import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic             import BaseModel
from dotenv               import load_dotenv
from supabase             import create_client, Client

load_dotenv()

_supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
)

TABLE = "simulations"

app = FastAPI(title="SimuStake API", version="0.1.0")

# ── CORS — updated for Render + Vercel ───────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",               # local dev
        "https://simustake.vercel.app",        # ← replace with your Vercel URL
        "https://simustake-api.onrender.com",  # ← replace with your Render URL
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / response schemas ────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    scenario:             str
    avg_revenue_per_user: float = 50.0
    max_reruns:           int   = 2


class SimulateResponse(BaseModel):
    simulation_id:        str
    confidence_score:     float
    churn_pct_range:      tuple[float, float]
    revenue_impact_range: tuple[float, float]
    pr_risk_score:        float
    unexpected_effects:   list[str]
    recommendations:      list[str]
    citations:            dict[str, str]
    emergent_events:      list[dict]
    personas:             list[dict]
    rerun_count:          int
    error:                str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _persist(sim_id: str, final_state: dict) -> None:
    try:
        report = final_state.get("outcome_report") or {}
        _supabase.table(TABLE).upsert({
            "id":             sim_id,
            "created_at":     datetime.now(timezone.utc).isoformat(),
            "scenario":       final_state.get("raw_scenario", ""),
            "confidence":     final_state.get("confidence_score", 0.0),
            "rerun_count":    final_state.get("rerun_count", 0),
            "outcome_report": json.dumps(report),
            "full_state":     json.dumps(final_state),
        }).execute()
    except Exception as e:
        print(f"[warn] Supabase persist failed: {e}")


def _state_to_response(sim_id: str, state: dict) -> SimulateResponse:
    report   = state.get("outcome_report") or {}
    personas = [
        {
            "id":                 p["id"],
            "name":               p["name"],
            "archetype":          p["archetype"],
            "emotional_baseline": p["emotional_baseline"],
            "chosen_action":      next(
                (r["chosen_action"] for r in state.get("reactions", [])
                 if r["persona_id"] == p["id"]), "unknown"
            ),
        }
        for p in state.get("personas", [])
    ]
    emergent = [
        {
            "name":        e["name"],
            "severity":    e["severity"],
            "description": e["description"],
        }
        for e in state.get("emergent_events", [])
    ]
    return SimulateResponse(
        simulation_id        = sim_id,
        confidence_score     = state.get("confidence_score", 0.0),
        churn_pct_range      = report.get("churn_pct_range",      (0.0, 0.0)),
        revenue_impact_range = report.get("revenue_impact_range", (0.0, 0.0)),
        pr_risk_score        = report.get("pr_risk_score",        0.0),
        unexpected_effects   = report.get("unexpected_effects",   []),
        recommendations      = report.get("recommendations",      []),
        citations            = report.get("citations",            {}),
        emergent_events      = emergent,
        personas             = personas,
        rerun_count          = state.get("rerun_count", 0),
        error                = state.get("error", ""),
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/simulate", response_model=SimulateResponse)
async def simulate(req: SimulateRequest):
    if not req.scenario.strip():
        raise HTTPException(status_code=400, detail="scenario must not be empty")

    sim_id = uuid.uuid4().hex

    from graph.orchestrator import compiled_graph
    from models.state       import SimulationState

    init = SimulationState(
        raw_scenario  = req.scenario,
        simulation_id = sim_id,
        max_reruns    = req.max_reruns,
    ).model_dump()

    try:
        final = compiled_graph.invoke(init)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {e}")

    _persist(sim_id, final)
    return _state_to_response(sim_id, final)


@app.get("/simulation/{sim_id}", response_model=SimulateResponse)
async def get_simulation(sim_id: str):
    try:
        row = (
            _supabase.table(TABLE)
            .select("full_state")
            .eq("id", sim_id)
            .single()
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {e}")

    if not row.data:
        raise HTTPException(status_code=404, detail="Simulation not found")

    state = json.loads(row.data["full_state"])
    return _state_to_response(sim_id, state)


@app.get("/health")
async def health():
    return {"status": "ok"}