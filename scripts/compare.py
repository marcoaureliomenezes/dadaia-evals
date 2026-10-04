"""Gate a candidate run against a baseline run (ADR 0178 (2), AC11.5).

Usage: compare.py BASE_JOBS_DIR CAND_JOBS_DIR. Reads every harbor trial
result.json. Blocks (exit 1) when a task passing >=2/3 on the baseline passes
<=1/3 on the candidate, or T1 passes below 3/3 on the candidate. A missing
trial is a fail. Prints a Markdown table, the readout, with the trials found per side.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

TRIALS = 3
T1 = "t1-cold-onboarding"


def passes(jobs_dir):
    count, found = Counter(), Counter()
    for f in Path(jobs_dir).rglob("result.json"):
        r = json.loads(f.read_text())
        if "task_name" in r:  # skip the job-level result.json
            task = r["task_name"].rsplit("/", 1)[-1]
            reward = ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward", 0)
            count[task] += reward >= 1
            found[task] += 1
    return count, found


def main(base_dir, cand_dir):
    (base, nb), (cand, nc) = passes(base_dir), passes(cand_dir)
    block = False
    print(f"| task | {os.environ.get('BASELINE', 'baseline')} | candidate | verdict |\n|---|---|---|---|")
    for task in sorted(set(base) | set(cand) | {T1}):
        drop = base[task] >= 2 and cand[task] <= 1
        t1 = task == T1 and cand[task] < TRIALS
        block |= drop or t1
        verdict = "BLOCK: drop" if drop else "BLOCK: T1 below 3/3" if t1 else "readout"
        print(f"| {task} | {base[task]}/{TRIALS} ({nb[task]} found) | {cand[task]}/{TRIALS} ({nc[task]} found) | {verdict} |")
    print(f"\n**{'BLOCKING' if block else 'non-blocking'}**")
    return 1 if block else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
