from fastapi import APIRouter, HTTPException
from ..services.weekend import weekend

router = APIRouter()


@router.get("/{year}/{round_number}")
def get_weekend(year: int, round_number: int):
    try:
        return weekend(year, round_number)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            502,
            "Weekend timing data could not be analysed. Retry when the data is published.",
        ) from exc
