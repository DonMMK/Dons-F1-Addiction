"""Diagnose public classifications and historical timing without credentials."""

import argparse
import json
import sys

import fastf1
from .services.data import CACHE_DIR, load_session, optional_data
from .services.data import timing_provider
from .services.f1_access import MIN_VERSION, auth_status
from .services.loading_errors import SessionDataError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument(
        "--session", choices=["FP1", "FP2", "FP3", "Q", "R", "S", "SQ"], default="Q"
    )
    parser.add_argument(
        "--timing", action="store_true", help="Also verify raw lap timing access"
    )
    parser.add_argument(
        "--telemetry-driver",
        help="Also verify recorded fastest-lap telemetry for this driver code or number",
    )
    args = parser.parse_args()
    report = {
        "fastf1Version": fastf1.__version__,
        "minimumVersion": MIN_VERSION,
        "cacheDirectory": str(CACHE_DIR),
        "authentication": auth_status(),
        "timingProvider": timing_provider(),
    }
    failed = False
    if args.session in ("Q", "R", "S"):
        try:
            session = load_session(
                args.year, args.round, args.session, results_only=True
            )
            report["classification"] = {
                "source": session.data_source,
                "drivers": len(session.results),
            }
        except SessionDataError as exc:
            report["classification"] = {"code": exc.code, "detail": exc.detail}
            failed = True
    if args.timing or args.telemetry_driver or args.session not in ("Q", "R", "S"):
        try:
            session = load_session(args.year, args.round, args.session)
            report["timing"] = {
                "source": session.data_source,
                "laps": len(session.laps),
                "warnings": session.data_warnings,
            }
            if args.telemetry_driver:
                lap = session.laps.pick_drivers(args.telemetry_driver).pick_fastest()
                if lap is None:
                    raise SessionDataError(
                        "lap_unavailable",
                        "No screened timed lap is available for this driver.",
                        425,
                        60,
                    )
                report["telemetry"] = {
                    "driver": args.telemetry_driver,
                    "samples": len(lap.get_telemetry()),
                }
        except SessionDataError as exc:
            report["timing"] = {"code": exc.code, "detail": exc.detail}
            failed = True
    print(json.dumps(report, indent=2))
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
