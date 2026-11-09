"""Non-blocking cached FIA evidence and background discovery status."""

from datetime import datetime, timezone
from fastapi import APIRouter, Path

from ..services.fia_documents import get_indexer
from ..services.weekend_sources import report, snapshots

router = APIRouter()


@router.get("/{year}/{round_number}")
def documents(year: int = Path(ge=1950), round_number: int = Path(ge=1, le=100)):
    # Limit new work to seasons that can plausibly have a published schedule.
    if year > datetime.now(timezone.utc).year + 1:
        from fastapi import HTTPException

        raise HTTPException(
            422,
            "FIA discovery supports past seasons, the current year and the next season.",
        )
    indexer = get_indexer()
    indexer.request(year)
    payload = indexer.event_payload(year, round_number)
    current = snapshots(year).get(round_number)
    name = payload.get("eventName") or (current or {}).get("eventName")
    roster = payload.get("roster") or [
        r["team"] for r in (current or {}).get("teams", [])
    ]
    if name:
        indexer.request(year, round_number, name, roster)
    return report(
        year,
        round_number,
        name or f"Round {round_number}",
        roster,
        schedule_refresh=False,
    )
