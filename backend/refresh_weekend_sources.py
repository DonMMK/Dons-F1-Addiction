"""Refresh published FIA car-presentation declarations into local evidence."""

import argparse
import json

from .services.events import get_schedule
from .services.weekend_sources import refresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--round", type=int, help="Omit to index all completed rounds in the season"
    )
    args = parser.parse_args()
    schedule = get_schedule(args.year, include_testing=False)
    import pandas as pd

    failed, selected = 0, 0
    for _, event in schedule.iterrows():
        rd = int(event["RoundNumber"])
        if rd < 1 or (args.round is not None and rd != args.round):
            continue
        if pd.Timestamp(event["EventDate"]).date() > pd.Timestamp.now(tz="UTC").date():
            continue
        selected += 1
        try:
            result = refresh(args.year, rd, str(event["EventName"]))
            print(
                json.dumps(
                    {
                        "round": rd,
                        "teamsIndexed": len(result["teams"]),
                        "status": result["submissionStatus"],
                    }
                )
            )
            if result["submissionStatus"] != "indexed":
                failed += 1
        except Exception as exc:
            failed += 1
            print(
                json.dumps({"round": rd, "status": "not_indexed", "reason": str(exc)})
            )
    if not selected:
        parser.error("No completed matching round was found in the public schedule")
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
