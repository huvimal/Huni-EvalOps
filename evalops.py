"""Run a versioned release check or compare a deterministic judge with human labels."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import candidate
from gate import decide, indexed

ROOT = Path(__file__).resolve().parent


def snapshot(path):
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()


def judge(output, expected):
    return (
        isinstance(output, dict)
        and set(output) == {"category", "urgent"}
        and type(output["urgent"]) is bool
        and output == expected
    )


def release():
    dataset, dataset_sha = snapshot(ROOT / "datasets/support-v1.json")
    baseline, baseline_sha = snapshot(ROOT / "datasets/baseline-support-v1.json")
    policy, policy_sha = snapshot(ROOT / "policy.json")
    items = indexed(dataset["cases"], lambda row: row)
    if baseline["dataset_version"] != dataset["version"] or items.keys() != baseline["outputs"].keys():
        raise ValueError("Baseline must match the dataset version and case IDs.")
    if not (0 <= policy["min_pass_rate"] <= 1 and 0 <= policy["max_drop_pp"] <= 100):
        raise ValueError("Invalid release thresholds.")
    critical = {identifier for identifier, row in items.items() if row["critical"] is True}
    rows = []
    for identifier, row in items.items():
        output = candidate.classify(row["text"])
        before = baseline["outputs"][identifier]
        rows.append({"id": identifier, "expected": row["expected"], "baseline": before,
                     "candidate": output, "baseline_pass": judge(before, row["expected"]),
                     "candidate_pass": judge(output, row["expected"])})
    outcomes = {row["id"]: (row["baseline_pass"], row["candidate_pass"]) for row in rows}
    decision = decide(outcomes, critical, policy["min_pass_rate"], policy["max_drop_pp"])
    return {
        "dataset_version": dataset["version"],
        "sha256": {"dataset": dataset_sha, "baseline": baseline_sha, "policy": policy_sha,
                   "candidate": hashlib.sha256((ROOT / "candidate.py").read_bytes()).hexdigest(),
                   "evaluator": hashlib.sha256((ROOT / "evalops.py").read_bytes()).hexdigest(),
                   "gate": hashlib.sha256((ROOT / "gate.py").read_bytes()).hexdigest()},
        "policy": policy, "critical_ids": sorted(critical), "decision": decision, "cases": rows,
    }


def calibration(path):
    dataset, dataset_sha = snapshot(path)
    items = indexed(dataset["cases"], lambda row: row)
    rows = []
    for identifier, row in items.items():
        if type(row["human_pass"]) is not bool:
            raise ValueError(f"{identifier}: human_pass must be a boolean.")
        automatic = judge(row["output"], row["expected"])
        rows.append({"id": identifier, "human_pass": row["human_pass"], "automatic_pass": automatic,
                     "agrees": automatic == row["human_pass"], "note": row.get("note", "")})
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for row in rows:
        label = {(True, True): "tp", (False, True): "fp", (False, False): "tn", (True, False): "fn"}
        counts[label[row["human_pass"], row["automatic_pass"]]] += 1
    return {"dataset_version": dataset["version"], "dataset_sha256": dataset_sha,
            "cases": len(rows), "agreement": sum(row["agrees"] for row in rows) / len(rows),
            "counts": counts, "disagreements": [row for row in rows if not row["agrees"]], "reviews": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("release", "calibrate"))
    parser.add_argument("--reviews", type=Path, default=ROOT / "datasets/calibration-v1.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = release() if args.command == "release" else calibration(args.reviews)
        report["run_at_utc"] = datetime.now(timezone.utc).isoformat()
        target = args.output or ROOT / "reports" / f"{args.command}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Invalid run input: {error}\n")
    if args.command == "release":
        print(json.dumps(report["decision"], indent=2))
    else:
        print(f"Agreement: {report['agreement']:.1%} over {report['cases']} cases. Counts: {report['counts']}")
    print(f"Report: {target}")
    return int(args.command == "release" and report["decision"]["decision"] == "blocked")


if __name__ == "__main__":
    raise SystemExit(main())
