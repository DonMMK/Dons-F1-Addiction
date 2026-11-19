import fastf1
from fastapi import APIRouter
from ..services.f1_access import MIN_VERSION, auth_status
from ..services.data import timing_provider

router = APIRouter()


@router.get("/status")
def data_status():
    return {
        "fastf1Version": fastf1.__version__,
        "minimumVersion": MIN_VERSION,
        "authentication": auth_status(),
        "timingProvider": timing_provider(),
        "historicalAccess": {
            "requiresAccount": False,
            "firstOpenF1Season": 2023,
            "liveWindowMinutesAfterSession": 30,
        },
        "sources": {
            "classifications": "Jolpica-F1 (public)",
            "timing": "Existing FastF1 cache, then free OpenF1 historical timing (2023+); authenticated archive is optional",
        },
    }
