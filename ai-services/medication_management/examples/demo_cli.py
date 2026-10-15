"""Command Line Interface (CLI) for running Medication Adherence calculations."""

import argparse
import json
import sys
from pathlib import Path

from medication_management import calculate_mpr, calculate_pdc


def process_single(fills, start_date, end_date, metric, detailed):
    res = {}
    if metric in ("both", "pdc"):
        res["PDC"] = calculate_pdc(
            fills, start_date, end_date, include_metadata=detailed
        )
    if metric in ("both", "mpr"):
        res["MPR"] = calculate_mpr(
            fills, start_date, end_date, include_metadata=detailed
        )
    return res


def main():
    parser = argparse.ArgumentParser(
        description="Calculate Medication Adherence metrics (PDC & MPR)."
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to JSON file containing fills, start_date, and end_date (or samples collection).",
    )
    parser.add_argument("--start", type=str, help="Observation start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="Observation end date (YYYY-MM-DD)")
    parser.add_argument(
        "--metric",
        choices=["both", "pdc", "mpr"],
        default="both",
        help="Metric to calculate (default: both)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed metadata (gaps, intervals)",
    )

    args = parser.parse_args()

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: file '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "samples" in data and isinstance(data["samples"], list):
            output = {"results": []}
            for sample in data["samples"]:
                s_in = sample.get("input", {})
                res = process_single(
                    s_in.get("fills", []),
                    s_in.get("start_date"),
                    s_in.get("end_date"),
                    args.metric,
                    args.detailed,
                )
                output["results"].append(
                    {
                        "name": sample.get("name"),
                        "description": sample.get("description"),
                        "output": res,
                    }
                )
        else:
            fills = data.get("fills", [])
            start_date = data.get("start_date")
            end_date = data.get("end_date")
            output = process_single(
                fills, start_date, end_date, args.metric, args.detailed
            )
    else:
        if not args.start or not args.end:
            print(
                "Error: Either --file or both --start and --end must be specified.",
                file=sys.stderr,
            )
            sys.exit(1)
        fills = []
        start_date = args.start
        end_date = args.end
        output = process_single(fills, start_date, end_date, args.metric, args.detailed)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
