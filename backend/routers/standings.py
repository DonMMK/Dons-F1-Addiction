"""Championship snapshots from Jolpica through FastF1's maintained interface."""

import time
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query
from fastf1.ergast import Ergast

from ..services.data import number, utc_now

router = APIRouter()


def rows(response):
    if not response.content:
        return [], None
    return response.content[0].to_dict("records"), int(
        response.description.iloc[0]["round"]
    )


def driver_row(row):
    teams = row.get("constructorNames", [])
    return {
        "id": row["driverId"],
        "label": row.get("driverCode") or row["familyName"],
        "name": f'{row["givenName"]} {row["familyName"]}',
        "team": " / ".join(teams) if isinstance(teams, list) else str(teams),
        "position": int(row["position"]),
        "points": number(row["points"]),
        "wins": int(row["wins"]),
    }


def constructor_row(row):
    return {
        "id": row["constructorId"],
        "label": row["constructorName"],
        "name": row["constructorName"],
        "team": row["constructorName"],
        "position": int(row["position"]),
        "points": number(row["points"]),
        "wins": int(row["wins"]),
    }


def changes(current, previous):
    lookup = {r["id"]: r for r in previous}
    for row in current:
        before = lookup.get(row["id"])
        row.update(
            previousPosition=before["position"] if before else None,
            previousPoints=before["points"] if before else None,
            positionChange=before["position"] - row["position"] if before else None,
            pointsChange=number(row["points"] - before["points"]) if before else None,
        )
    return sorted(current, key=lambda r: r["position"])


@lru_cache(maxsize=24)
def snapshot(year, requested_round, bucket):
    client = Ergast()
    raw, actual_round = rows(
        client.get_driver_standings(
            season=year, round=requested_round or "last", limit=100
        )
    )
    if actual_round is None:
        return {
            "year": year,
            "round": None,
            "previousRound": None,
            "drivers": [],
            "constructors": [],
            "asOf": utc_now(),
            "source": "Jolpica-F1 via FastF1",
        }
    cons, cons_round = rows(
        client.get_constructor_standings(season=year, round=actual_round, limit=100)
    )
    if cons_round != actual_round:
        raise ValueError(
            "Driver and constructor standings are not published for the same round yet"
        )
    prev_d, prev_c = [], []
    if actual_round > 1:
        prev_d, prev_round = rows(
            client.get_driver_standings(season=year, round=actual_round - 1, limit=100)
        )
        prev_c, prev_c_round = rows(
            client.get_constructor_standings(
                season=year, round=actual_round - 1, limit=100
            )
        )
        if prev_round != actual_round - 1 or prev_c_round != actual_round - 1:
            raise ValueError(
                "Previous-round standings unavailable; change cannot be calculated reliably"
            )
    return {
        "year": year,
        "round": actual_round,
        "previousRound": actual_round - 1 if actual_round > 1 else None,
        "drivers": changes(
            [driver_row(r) for r in raw], [driver_row(r) for r in prev_d]
        ),
        "constructors": changes(
            [constructor_row(r) for r in cons], [constructor_row(r) for r in prev_c]
        ),
        "asOf": utc_now(),
        "source": "Jolpica-F1 via FastF1",
        "comparison": "Previous completed Grand Prix round; sprint points and published adjustments included.",
    }


@router.get("/{year}")
def get_standings(year: int, round: int | None = Query(None, ge=1, le=40)):
    try:
        return snapshot(year, round, int(time.time() // 300))
    except Exception as exc:
        raise HTTPException(
            502,
            "Championship data unavailable. Retry after the provider publishes the results.",
        ) from exc
