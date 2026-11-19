"""Create an auditable model iteration: python -m backend.train_predictor --help."""

import argparse
import json
from .services.empirical_model import train

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-year", type=int, default=2023)
    parser.add_argument("--through-year", type=int, required=True)
    parser.add_argument("--through-round", type=int)
    args = parser.parse_args()
    if args.from_year > args.through_year:
        parser.error("from-year must not exceed through-year")
    result = train(args.from_year, args.through_year, args.through_round)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "id",
                    "trainingEvents",
                    "trainedThrough",
                    "metrics",
                    "baselines",
                    "improvesGridLogLoss",
                    "skipped",
                )
            },
            indent=2,
        )
    )
