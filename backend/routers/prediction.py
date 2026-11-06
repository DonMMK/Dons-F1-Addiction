"""
Prediction API routes.
Wraps all predictor model versions (v1 through v12) and exposes them via REST.
"""

import os
import sys
import importlib.util
import numpy as np
import pandas as pd
import fastf1
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

router = APIRouter()

PREDICTION_DIR = Path(__file__).parent.parent.parent / "formula1-prediction"
CACHE_DIR = Path(__file__).parent.parent.parent / "f1_cache"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

# ---------------------------------------------------------------------------
# Dynamically discover available predictor versions
# ---------------------------------------------------------------------------

def _discover_versions() -> dict:
    """Scan formula1-prediction/ and return {label: filename} for each predictor."""
    versions = {}
    pred_dir = PREDICTION_DIR
    if not pred_dir.exists():
        return versions

    for f in sorted(pred_dir.glob("f1_predictor*.py")):
        name = f.stem  # e.g. "f1_predictor_v12"
        if name == "f1_predictor":
            versions["v1 (Original – Physics + ML)"] = f
        else:
            tag = name.replace("f1_predictor_", "")   # "v12"
            versions[tag] = f
    return versions


def _load_module(path: Path):
    """Import a predictor module by file path."""
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------

class PredictionRequest(BaseModel):
    year: int = 2026
    gp: str = "Great Britain"
    session: str = "Q"
    model: str = "v12"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/models")
def list_models():
    """Return available predictor model versions."""
    versions = _discover_versions()
    return {"models": list(versions.keys())}


@router.post("/run")
def run_prediction(req: PredictionRequest):
    """
    Run a race prediction using the selected model version.
    Returns win-probability table for top drivers.
    """
    versions = _discover_versions()

    # Find matching version key
    matched_key = None
    for key in versions:
        if req.model.lower() in key.lower():
            matched_key = key
            break
    if matched_key is None:
        raise HTTPException(status_code=400, detail=f"Unknown model '{req.model}'. Available: {list(versions.keys())}")

    mod = _load_module(versions[matched_key])

    # --- Load session data ------------------------------------------------
    try:
        cache_dir = str(CACHE_DIR)
        os.makedirs(cache_dir, exist_ok=True)
        fastf1.Cache.enable_cache(cache_dir)
        session = fastf1.get_session(req.year, req.gp, req.session)
        session.load()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load session data: {e}")

    # --- Determine grid_data depending on session type --------------------
    if req.session in ("FP1", "FP2", "FP3"):
        laps = session.laps
        if laps.empty:
            raise HTTPException(status_code=404, detail="No lap data for this session")
        best_laps = laps.loc[laps.groupby("Driver")["LapTime"].idxmin()]
        best_laps = best_laps[["Driver", "LapTime"]].copy()
        best_laps = best_laps.rename(columns={"Driver": "Abbreviation"})
        best_laps = best_laps.sort_values("LapTime").reset_index(drop=True)
        best_laps["GridPosition"] = range(1, len(best_laps) + 1)
        grid_data = best_laps
        session_label = f"{req.session} (Preliminary)"
    else:
        grid_data = session.results
        session_label = "Qualifying"

    # --- Run simulation ---------------------------------------------------
    SimClass = getattr(mod, "RaceSimulator", None)
    ConfigClass = getattr(mod, "Config", None)
    if SimClass is None or ConfigClass is None:
        raise HTTPException(status_code=500, detail="Predictor module missing RaceSimulator or Config")

    monte_carlo_runs = getattr(ConfigClass, "MONTE_CARLO_RUNS", 5000)

    # Different constructor signatures across versions
    import inspect
    sig = inspect.signature(SimClass.__init__)
    params = list(sig.parameters.keys())

    if "grid_data" in params and "gp_name" in params:
        sim = SimClass(grid_data, req.gp)
    elif "physics_profile" in params:
        # v1 original needs physics + grid
        grid = grid_data["Abbreviation"].head(20).tolist() if "Abbreviation" in grid_data.columns else []
        sim = SimClass({}, grid)
    else:
        sim = SimClass(grid_data, req.gp)

    win_counts = sim.run_simulation()

    sorted_wins = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)
    predictions = []
    for i, (driver, wins) in enumerate(sorted_wins, 1):
        prob = (wins / monte_carlo_runs) * 100
        if prob > 0:
            predictions.append({
                "position": i,
                "driver": driver,
                "winProbability": round(prob, 1),
            })

    return {
        "year": req.year,
        "gp": req.gp,
        "session": req.session,
        "sessionLabel": session_label,
        "model": matched_key,
        "monteCarloRuns": monte_carlo_runs,
        "predictions": predictions,
    }


@router.get("/grand-prix/{year}")
def list_grand_prix(year: int):
    """Return list of Grand Prix events for a year (non-testing)."""
    try:
        schedule = fastf1.get_event_schedule(year)
        events = []
        for _, row in schedule.iterrows():
            fmt = str(row.get("EventFormat", "")).lower()
            if fmt == "testing":
                continue
            if pd.isna(row.get("RoundNumber")) or row.get("RoundNumber") == 0:
                continue
            events.append({
                "roundNumber": int(row["RoundNumber"]),
                "eventName": str(row.get("EventName", "")),
                "country": str(row.get("Country", "")),
                "date": str(row.get("EventDate", ""))[:10],
            })
        return {"year": year, "events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
