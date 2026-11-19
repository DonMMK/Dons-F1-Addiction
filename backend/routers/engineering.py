"""Cited engineering context, separated from measured on-track outcomes."""

from fastapi import APIRouter

router = APIRouter()

TOPICS = {
    "2025": [
        {
            "id": "brakes",
            "title": "McLaren MCL39 · Brake cooling and tyre temperature",
            "documented": "F1 technical reporting links McLaren's rear brake-duct approach with tyre temperature control, while noting that its internal configuration was not widely known.",
            "measure": "Compare matched-compound race pace and adjusted lap-time trends, with track temperature shown for context.",
            "cannotInfer": "Timing does not measure brake-disc or tyre carcass temperature, airflow rate, or how many seconds this design caused.",
            "sourceLabel": "Formula 1 technical analysis · 20 May 2025",
            "sourceUrl": "https://www.formula1.com/en/latest/article/tech-weekly-mclarens-ingenious-design-is-the-latest-step-in-a-spectacular.1zl8gcMuEAgJ1r2zefjrVb",
        },
    ],
    "2023": [
        {
            "id": "floor",
            "title": "Red Bull RB19 · Floor and aerodynamic platform",
            "documented": "F1's launch analysis identifies revised floor edges following the 2023 floor-height regulation changes. Exact underfloor performance cannot be read from public lap times.",
            "measure": "Inspect speed traces, throttle application and corner-speed differences at the same event; compare normalized qualifying advantage across rounds.",
            "cannotInfer": "No public downforce map, ride-height trace or floor pressure data is available here. A speed advantage alone does not isolate the floor.",
            "sourceLabel": "Formula 1 technical analysis · 28 February 2023",
            "sourceUrl": "https://www.formula1.com/en/latest/article/tech-tuesday-dissecting-the-design-secrets-of-the-rb19-and-why-red-bulls.359CpeSh3M73afoQ5hEVfr",
        },
    ],
    "2020": [
        {
            "id": "suspension",
            "title": "Mercedes W11 · Suspension and aero packaging",
            "documented": "Mercedes' launch description explains that the rear suspension layout created further aerodynamic development opportunities.",
            "measure": "Compare corner entry, minimum speed, exit acceleration and qualifying advantage at the same circuit.",
            "cannotInfer": "Public telemetry does not isolate suspension geometry, damper settings or its individual lap-time contribution.",
            "sourceLabel": "Mercedes-AMG W11 launch technical statement · 2020",
            "sourceUrl": "https://media.mercedesamgf1.com/marsF1/en/instance/ko/Herzlich-willkommen-W11-The-Mercedes-AMG-Petronas-F1-Teams-2020-car-hits-the-track-at-Silverstone.xhtml?oid=180290999",
        },
        {
            "id": "engine",
            "title": "Mercedes W11 · Power unit and cooling",
            "documented": "Mercedes described larger radiators and higher engine operating temperatures as part of the W11 cooling development.",
            "measure": "Examine straight-line speed, throttle and gear traces alongside the session's ambient and track temperatures.",
            "cannotInfer": "Straight-line speed also reflects drag, tow, gearing and energy deployment; it is not a horsepower measurement.",
            "sourceLabel": "Mercedes-AMG W11 launch technical statement · 2020",
            "sourceUrl": "https://media.mercedesamgf1.com/marsF1/en/instance/ko/Herzlich-willkommen-W11-The-Mercedes-AMG-Petronas-F1-Teams-2020-car-hits-the-track-at-Silverstone.xhtml?oid=180290999",
        },
    ],
}


@router.get("/topics")
def topics():
    return {
        "eras": TOPICS,
        "note": "Source descriptions are engineering context. Charts show observed outcomes, not isolated component gains. Schematic animations are conceptual, not CFD or proprietary geometry.",
    }
