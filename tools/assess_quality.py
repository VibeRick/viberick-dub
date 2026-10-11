"""Usage: python -m tools.assess_quality RUN [RUN ...] --output NEW_REPORT.json.

Reads only local cached artifacts; refuses to overwrite a previous report.
No credentials, provider clients, or network calls are used.
"""
import argparse
import json
from pathlib import Path

from dub.quality import audit_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold-dbfs", type=float, default=-40.0)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new report path.")
    reports = [audit_run(run, args.threshold_dbfs) for run in args.runs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump({"audits": reports}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
