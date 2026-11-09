"""Apply release quality rules to paired evaluation reports."""
import argparse
import json
from pathlib import Path


TRANSITIONS = {
    "stable_pass": (True, True),
    "stable_fail": (False, False),
    "regression": (True, False),
    "improvement": (False, True),
}


def indexed(rows, read_value):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a non-empty case list.")
    values = {}
    for row in rows:
        identifier = row["id"]
        if not isinstance(identifier, str) or not identifier.strip() or identifier in values:
            raise ValueError("Case IDs must be unique, non-empty strings.")
        values[identifier] = read_value(row)
    return values


def router_pass(row):
    if type(row["passed"]) is not bool:
        raise ValueError("Router case must contain a boolean passed field.")
    return row["passed"]


def pairs(kind, report):
    if kind == "prompt":
        cases = indexed(report["cases"], lambda row: TRANSITIONS[row["change"]])
        return cases
    baseline = indexed(report["results"]["baseline"], router_pass)
    candidate = indexed(report["results"]["router"], router_pass)
    if baseline.keys() != candidate.keys():
        raise ValueError("Baseline and candidate must have the same case IDs.")
    return {identifier: (passed, candidate[identifier]) for identifier, passed in baseline.items()}


def decide(cases, critical, minimum, max_drop_pp):
    unknown = critical - cases.keys()
    if unknown:
        raise ValueError(f"Critical IDs are missing from the report: {', '.join(sorted(unknown))}")
    baseline = sum(before for before, _ in cases.values()) / len(cases)
    candidate = sum(after for _, after in cases.values()) / len(cases)
    drop = (baseline - candidate) * 100
    regressions = sorted(identifier for identifier, (before, after) in cases.items() if before and not after)
    critical_regressions = sorted(critical.intersection(regressions))
    reasons = []
    if critical_regressions:
        reasons.append("critical_regression")
    if candidate + 1e-9 < minimum:
        reasons.append("candidate_below_pass_rate_floor")
    if drop > max_drop_pp + 1e-9:
        reasons.append("pass_rate_drop_exceeded")
    return {
        "decision": "blocked" if reasons else "passed",
        "cases": len(cases), "baseline_pass_rate": baseline, "candidate_pass_rate": candidate,
        "drop_pp": round(drop, 6), "regressions": regressions,
        "critical_regressions": critical_regressions, "reasons": reasons,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("prompt", "router"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--critical", action="append", default=[])
    parser.add_argument("--min-pass-rate", type=float, default=0.9)
    parser.add_argument("--max-drop-pp", type=float, default=5)
    args = parser.parse_args()
    if not (0 <= args.min_pass_rate <= 1 and 0 <= args.max_drop_pp <= 100):
        parser.error("Pass rate must be 0–1 and maximum drop must be 0–100 percentage points.")
    try:
        report = json.loads(args.report.read_text(encoding="utf-8-sig"))
        result = decide(pairs(args.kind, report), set(args.critical), args.min_pass_rate, args.max_drop_pp)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Invalid report or policy: {error}\n")
    print(json.dumps({"report_mode": report.get("mode"), **result}, indent=2))
    return int(result["decision"] == "blocked")


if __name__ == "__main__":
    raise SystemExit(main())
