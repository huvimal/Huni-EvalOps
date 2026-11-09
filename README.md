# Huni EvalOps

Huni EvalOps compares a candidate with a recorded baseline on a versioned
support dataset. It saves a run report and fails a pull-request check when
the candidate violates release policy. The project also compares an automatic
judge with sample human labels.

## Run the full workflow locally

Python 3.11 is sufficient. There are no external dependencies or API keys.

```powershell
python evalops.py release
python evalops.py calibrate
Get-Content reports/release.json -Encoding utf8
Get-Content reports/calibrate.json -Encoding utf8
```

The release run records a timestamp, dataset version, policy, and SHA-256
fingerprints for the input and evaluator files. It scores both sets of outputs
against the same references. The baseline is a checked-in snapshot and the
candidate is an offline classifier. Commit the dataset and baseline together
when creating a new dataset version. Keep the dataset, policy, and baseline
fixed when testing a candidate change.

The calibration file contains six prepared human labels for the demo.
Disagreements show a schema violation a human accepted and a multi-intent
request the exact-match judge accepted. Agreement is descriptive, and the
calibration result is not a release gate. To collect your own labels, copy the
dataset to `private_data/`, read each request and output first, then record
`human_pass` as a JSON boolean and write the reason in `note`. Run
`python evalops.py calibrate --reviews private_data/my-reviews.json`.
For a stronger experiment, get independent reviews and keep a separate set
for checking judge changes.

## Demonstrate a blocked and fixed pull request

1. Push the unmodified project to a new GitHub repository on `main`.
2. After Actions reports a successful `quality-gate`, configure the repository's
   ruleset or branch protection for `main` to require a pull request and that
   status check, if supported by the repository settings.
3. Create a branch. In `candidate.py`, change the account return value from
   `"urgent": "người lạ" in text` to `"urgent": False`. Commit and push the
   branch, then open a pull request into `main`.
4. Expect `account-02` to fail, 5/6 candidate passes, and exit code 1.
   The workflow saves the report as an artifact even when the check fails.
5. Restore `"urgent": "người lạ" in text` on the same branch. Commit and push
   again. Expect 6/6 and a passing check on the same PR.

If status checks are not required in the repository settings, the workflow
still detects regressions. Required checks are what enforce the merge rule.
The public fixtures are synthetic. Review private data before publishing
datasets or reports.

## Import reports from earlier projects

Run from this folder with Python 3.11:

```powershell
python gate.py --kind prompt --report ../Prompt-Regression-Lab/reports/comparison.json --critical account-02
python gate.py --kind router --report ../ModelRouter/reports/live-test.json --min-pass-rate 0.90
```

Use the synthetic reports in `examples/` to try both outcomes without an API:

```powershell
python gate.py --kind prompt --report examples/prompt.json --critical account-02
python gate.py --kind router --report examples/router.json
```

Exit codes: 0 passed, 1 blocked, 2 invalid input. The gate compares the same
paired cases, blocks critical regressions and enforces a candidate pass-rate
floor and a maximum drop in percentage points. It does not judge text,
train a model or publish a release. Thresholds are release policy choices,
not estimates of real-world quality.

