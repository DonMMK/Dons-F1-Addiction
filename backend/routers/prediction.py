"""Model adapters, immutable forecasts, and post-race scoring."""

import importlib.util
import inspect
import hashlib
import logging
import threading
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.data import ROOT, finished, iso, load_session, number, utc_now
from ..services.loading_errors import SessionDataError
from ..services.empirical_model import artifacts, features, infer
from ..services import prediction_store as store
from .common import get_schedule

router = APIRouter()
PREDICTION_DIR = ROOT / "formula1-prediction"
SIMULATION_LOCK = threading.Lock()
CHANGES = {
    1: "Original long-run regression, fuel assumptions and Monte Carlo framework",
    2: "More simulations and revised stint detection and traffic penalties",
    3: "Revised grid fallbacks and stint assumptions",
    4: "Track-dependent overtaking constraints and race distance",
    5: "Revised traffic and race simulation heuristics",
    6: "Further safety-car and racecraft heuristics",
    7: "Additional pace anomaly and driver adjustments",
    8: "Revised driver and pace adjustments",
    9: "Further anomaly handling and driver-tier assumptions",
    10: "Qualifying-anchored pace, replacing the long-run physics dependency",
    11: "Grid position and track-dependent traffic drag",
    12: "22-car field and winning-margin simulation; hardcoded 2026 driver tiers",
}


def _discover_versions():
    paths = {1: PREDICTION_DIR / "f1_predictor.py"}
    for path in PREDICTION_DIR.glob("f1_predictor_v*.py"):
        tag = path.stem.removeprefix("f1_predictor_v")
        if tag.isdigit():
            paths[int(tag)] = path
    return {f"v{v}": path for v, path in sorted(paths.items()) if path.exists()}


def _load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@router.get("/models")
def list_models():
    models = [
        {
            "id": key,
            "name": f"{key} · Legacy simulation",
            "improvements": [CHANGES.get(int(key[1:]), "Legacy iteration")],
            "limitations": [
                "Heuristic assumptions; no demonstrated calibration or validated improvement over prior versions"
            ],
            "sessions": ["Q"] if key in ("v10", "v11") else ["FP1", "FP2", "FP3", "Q"],
            "metrics": None,
            "trainedThrough": None,
        }
        for key in _discover_versions()
    ]
    for artifact in artifacts():
        models.append(
            {
                key: artifact.get(key)
                for key in (
                    "id",
                    "name",
                    "improvements",
                    "limitations",
                    "metrics",
                    "trainedThrough",
                    "trainingEvents",
                    "baselines",
                    "improvesGridLogLoss",
                    "previousComparable",
                    "heldoutEventKeys",
                )
            }
        )
        models[-1]["sessions"] = ["Q"]
    return {
        "models": [m["id"] for m in models],
        "catalog": models,
        "defaultModel": models[-1]["id"] if models else None,
        "trainingCommand": "python -m backend.train_predictor --from-year 2023 --through-year 2025",
    }


class PredictionRequest(BaseModel):
    year: int = Field(2026, ge=2018, le=2100)
    gp: str = Field("Great Britain", min_length=1, max_length=100)
    session: Literal["FP1", "FP2", "FP3", "Q"] = "Q"
    model: str = Field("v12", max_length=100)
    seed: int = Field(17, ge=0, le=2**32 - 1)


def grid_data(session, kind):
    if kind != "Q":
        from ..services.data import clean_laps

        laps = clean_laps(session.laps)
        if laps.empty:
            raise ValueError("No valid practice laps")
        best = laps.loc[
            laps.groupby("Driver")["LapTime"].idxmin(), ["Driver", "LapTime"]
        ]
        best = (
            best.rename(columns={"Driver": "Abbreviation"})
            .sort_values("LapTime")
            .reset_index(drop=True)
        )
        best["GridPosition"] = np.arange(1, len(best) + 1)
        return best
    return session.results.sort_values("Position").copy()


def normalize_counts(raw):
    counts, margins = raw if isinstance(raw, tuple) else (raw, None)
    total = float(sum(counts.values()))
    if not counts or not np.isfinite(total) or total <= 0:
        raise ValueError("Model returned no finite winner distribution")
    if any(not np.isfinite(v) or v < 0 for v in counts.values()):
        raise ValueError("Model returned invalid winner counts")
    # v1 has a weight-only fallback: normalize actual output, never divide it by configured runs.
    return {str(d): float(w) / total for d, w in counts.items()}, margins, total


def legacy(req, session):
    model = req.model.lower()
    if model == "v1 (original – physics + ml)":
        model = "v1"
    paths = _discover_versions()
    if model not in paths:
        raise ValueError("Unknown model; select an exact ID from the catalog")
    if model in ("v10", "v11") and req.session != "Q":
        raise ValueError("This qualifying-only model cannot use a practice session")
    module = _load_module(paths[model])
    frame = grid_data(session, req.session)
    grid = frame["Abbreviation"].dropna().tolist()
    profile, warnings = {}, list(getattr(session, "data_warnings", [])) + [
        "Legacy simulation uses manually configured assumptions and may contain driver-specific bonuses. These are not empirical skill estimates."
    ]
    params = inspect.signature(module.RaceSimulator.__init__).parameters
    # UI event names differ from legacy dictionary keys (e.g. British GP / Great Britain).
    aliases = {
        "British Grand Prix": "Great Britain",
        "Australian Grand Prix": "Australia",
        "Italian Grand Prix": "Italy",
        "Japanese Grand Prix": "Japan",
        "Belgian Grand Prix": "Belgium",
        "Spanish Grand Prix": "Spain",
        "Canadian Grand Prix": "Canada",
        "Austrian Grand Prix": "Austria",
        "Hungarian Grand Prix": "Hungary",
        "Dutch Grand Prix": "Netherlands",
        "Brazilian Grand Prix": "Brazil",
        "São Paulo Grand Prix": "Brazil",
        "Mexico City Grand Prix": "Mexico",
        "United States Grand Prix": "United States",
    }
    gp_name = aliases.get(req.gp, req.gp.removesuffix(" Grand Prix"))
    with SIMULATION_LOCK:
        # Legacy modules use NumPy's global generator. Restore it after every request.
        before = np.random.get_state()
        try:
            np.random.seed(req.seed)
            if "physics_profile" in params:
                practice = session if req.session != "Q" else None
                if practice is None:
                    for kind in ("FP3", "FP2", "FP1"):
                        try:
                            candidate = session.event.get_session(kind)
                            if pd.Timestamp(candidate.date) < pd.Timestamp(
                                session.date
                            ):
                                candidate = load_session(req.year, req.gp, kind)
                                if finished(candidate):
                                    practice = candidate
                                    break
                        except Exception:
                            continue
                if practice is not None:
                    warnings.extend(getattr(practice, "data_warnings", []))
                    analyzer = module.TelemetryAnalyzer.__new__(
                        module.TelemetryAnalyzer
                    )
                    profile = analyzer.analyze_stints(practice)
                    # Original v1 keys profiles by driver number; simulation uses abbreviations.
                    profile = {
                        (
                            str(practice.get_driver(k)["Abbreviation"])
                            if str(k).isdigit()
                            else str(k)
                        ): v
                        for k, v in profile.items()
                    }
                if not profile:
                    warnings.append(
                        "No usable pre-cutoff long runs: grid-based fallback, not a measured race-pace estimate"
                    )
                kwargs = {"gp_name": gp_name} if "gp_name" in params else {"laps": 58}
                # Do not load the target race to discover laps (would leak future information).
                if "laps" in kwargs:
                    kwargs = {"laps": 58}
                    warnings.append("Legacy v1–v3 race distance defaults to 58 laps")
                sim = module.RaceSimulator(profile, grid, **kwargs)
            else:
                sim = module.RaceSimulator(frame, gp_name)
            probs, margins, total = normalize_counts(sim.run_simulation())
        finally:
            np.random.set_state(before)
    return probs, margins, total, warnings, model


@router.post("/run")
def run_prediction(req: PredictionRequest):
    try:
        session = load_session(
            req.year, req.gp, req.session, results_only=req.session == "Q"
        )
        if not finished(session):
            raise ValueError(
                "Prediction input session has not finished; timing may still be provisional"
            )
        cutoff, trained_through, margins = iso(session.date), None, None
        inputs = {
            "sessionStart": cutoff,
            "dataSource": getattr(session, "data_source", "FastF1"),
        }
        source_hash = None
        if req.model.startswith("v13-"):
            artifact = next((a for a in artifacts() if a["id"] == req.model), None)
            if artifact is None:
                raise ValueError(
                    "Trained model not found; run the documented training command first"
                )
            if req.session != "Q":
                raise ValueError("Empirical v13 is trained for qualifying inputs only")
            session, entries, meta = features(req.year, req.gp)
            if pd.Timestamp(artifact["trainedThrough"]) >= pd.Timestamp(meta["cutoff"]):
                raise ValueError(
                    "This model was trained on results after the selected feature cutoff. Select an earlier-trained iteration."
                )
            inputs = {**meta, "entries": entries}
            source_hash = hashlib.sha256(
                __import__("json").dumps(artifact, sort_keys=True).encode()
            ).hexdigest()
            probs = dict(
                zip([e["driver"] for e in entries], infer(artifact, entries).tolist())
            )
            total, trained_through, model = (
                0,
                artifact["trainedThrough"],
                artifact["id"],
            )
            warnings = artifact["limitations"] + meta.get("dataWarnings", [])
        else:
            probs, margins, total, warnings, model = legacy(req, session)
            source_hash = hashlib.sha256(
                _discover_versions()[model].read_bytes()
            ).hexdigest()
        created = utc_now()
        race_start = iso(session.event.get("Session5DateUtc"))
        # Get race date by name: sprint weekends need not use a fixed session slot.
        for index in range(1, 6):
            if session.event.get(f"Session{index}") == "Race":
                race_start = iso(session.event.get(f"Session{index}DateUtc"))
        mode = (
            "pre-race"
            if race_start and pd.Timestamp(created) < pd.Timestamp(race_start)
            else "retrospective"
        )
        order = sorted(probs, key=probs.get, reverse=True)
        return store.save(
            {
                "year": req.year,
                "gp": str(session.event["EventName"]),
                "round": int(session.event["RoundNumber"]),
                "session": req.session,
                "sessionLabel": (
                    "Qualifying"
                    if req.session == "Q"
                    else f"{req.session} · provisional grid"
                ),
                "model": model,
                "seed": req.seed,
                "monteCarloRuns": int(total),
                "createdAt": created,
                "featureCutoff": cutoff,
                "trainedThrough": trained_through,
                "mode": mode,
                "warnings": warnings,
                "probabilities": probs,
                "modelSourceHash": source_hash,
                "inputs": inputs,
                "winningMargins": (
                    {
                        k: number(v / sum(margins.values()) * 100)
                        for k, v in margins.items()
                    }
                    if margins
                    else None
                ),
                "predictions": [
                    {
                        "position": i + 1,
                        "driver": d,
                        "winProbability": number(probs[d] * 100, 3),
                    }
                    for i, d in enumerate(order)
                ],
            }
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logging.exception("Prediction execution failed")
        raise HTTPException(
            502,
            "Prediction failed while loading data or running the model. Check the backend log.",
        ) from exc


@router.get("/history")
def history():
    return {
        "runs": [
            {
                k: r.get(k)
                for k in ("runId", "year", "gp", "round", "model", "mode", "createdAt")
            }
            for r in store.recent()
        ]
    }


@router.get("/evaluate/{run_id}")
def evaluate(run_id: str):
    run = store.get(run_id)
    if run is None:
        raise HTTPException(404, "Prediction snapshot not found")
    try:
        race = load_session(run["year"], run["round"], "R", results_only=True)
        if not finished(race):
            return {
                "status": "pending",
                "detail": "Race not finished or results not published yet",
            }
        results = race.results.dropna(subset=["Position"]).sort_values("Position")
        if results.empty or float(results.iloc[0]["Position"]) != 1:
            return {"status": "pending", "detail": "Winner classification unavailable"}
        winner = str(results.iloc[0]["Abbreviation"])
        drivers = set(run["probabilities"]) | set(results["Abbreviation"].astype(str))
        p = run["probabilities"]
        brier = sum((p.get(d, 0) - int(d == winner)) ** 2 for d in drivers)
        leader = max(p, key=p.get)
        return {
            "status": "scored",
            "mode": run["mode"],
            "winner": winner,
            "predictedWinner": leader,
            "winnerProbability": number(p.get(winner, 0) * 100),
            "correct": leader == winner,
            "brier": number(brier),
            "logLoss": number(-np.log(max(p.get(winner, 0), 1e-15))),
            "asOf": utc_now(),
            "note": "Winner-distribution score, not finishing-order accuracy. Lower Brier/log loss is better. Results may change after penalties.",
            "results": [
                {
                    "position": int(r["Position"]),
                    "driver": str(r["Abbreviation"]),
                    "predictedProbability": number(
                        p.get(str(r["Abbreviation"]), 0) * 100
                    ),
                }
                for _, r in results.iterrows()
            ],
        }
    except SessionDataError as exc:
        if exc.status_code == 425:
            return {"status": "pending", "detail": str(exc.detail)}
        raise
    except Exception:
        return {
            "status": "pending",
            "detail": "Race results not available from provider; retry later",
        }


@router.get("/grand-prix/{year}")
def list_grand_prix(year: int):
    result = get_schedule(year)
    result["events"] = [e for e in result["events"] if not e["isTesting"]]
    return result
