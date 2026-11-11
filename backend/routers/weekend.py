from fastapi import APIRouter, HTTPException, Query
from ..services.weekend import weekend
from typing import Literal
from ..services.data import load_session
from ..services.pace_evidence import analyse
from ..services.track_evidence import speed_map, lap_options
from ..services.strategy_evidence import load_strategy

router = APIRouter()


@router.get("/{year}/{round_number}")
def get_weekend(
    year: int,
    round_number: int,
    condition: Literal["all", "slick", "wet", "cool", "warm"] = "slick",
):
    try:
        return weekend(year, round_number, condition)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            502,
            "Weekend timing data could not be analysed. Retry when the data is published.",
        ) from exc


@router.get("/{year}/{round_number}/pace/{session_type}")
def session_pace(
    year: int,
    round_number: int,
    session_type: Literal["FP1", "FP2", "FP3", "R"],
    condition: Literal["all", "slick", "wet", "cool", "warm"] = "slick",
):
    session = load_session(year, round_number, session_type)
    return {
        "pace": analyse(session, condition),
        "source": getattr(session, "data_source", "FastF1"),
        "warnings": getattr(session, "data_warnings", []),
    }


@router.get("/{year}/{round_number}/track/{session_type}/{first}/{second}")
def track_comparison(
    year: int,
    round_number: int,
    session_type: Literal["Q", "R", "FP1", "FP2", "FP3"],
    first: str,
    second: str,
    lap_a: int | None = Query(default=None, ge=1),
    lap_b: int | None = Query(default=None, ge=1),
):
    return speed_map(year, round_number, session_type, first, second, lap_a, lap_b)


@router.get("/{year}/{round_number}/laps/{session_type}/{driver}")
def comparison_laps(
    year: int,
    round_number: int,
    session_type: Literal["Q", "R", "FP1", "FP2", "FP3"],
    driver: str,
):
    return lap_options(year, round_number, session_type, driver)


@router.get("/{year}/{round_number}/strategy")
def strategy(year: int, round_number: int):
    return load_strategy(year, round_number)
