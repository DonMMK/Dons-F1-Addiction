"""Fast cache reads; session downloads and analysis happen in the worker."""

from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException, Path, Query
from ..services.performance import get_performance

router = APIRouter()


@router.get("/{year}")
def performance(
    year: int = Path(ge=2018),
    round_number: int | None = Query(None, alias="round", ge=1, le=100),
    condition: Literal["slick", "wet", "cool", "warm", "all"] = "slick",
):
    if year > datetime.now(timezone.utc).year + 1:
        raise HTTPException(422, "Select a published past, current or next season")
    return get_performance().response(year, condition, round_number)
