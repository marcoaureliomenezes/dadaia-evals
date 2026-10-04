"""ADR 0177's check: exit 1 when a workflow breaks a model-API clause.

Every workflow runs on an exact GitHub-hosted label, never on
pull_request_target, reads secrets only in a job-level `env`, and publishes
(upload, summary, any action but checkout/setup-uv) only in unconditional
steps right after the canonical scan. A model-capable workflow (the word
`secrets` beyond secrets.GITHUB_TOKEN, or a job `environment`) runs only on
workflow_dispatch/schedule.
"""

import re
import sys
from pathlib import Path

import yaml  # preinstalled in the GitHub-hosted Ubuntu image's system python3

HOSTED = {"ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04", "windows-latest", "windows-2025",
          "windows-2022", "macos-latest", "macos-15", "macos-14"}
SCAN = "python3 scripts/scan.py jobs summary.md"
QUIET = ("actions/checkout@", "astral-sh/setup-uv@")  # write no summary, upload nothing


def has_secrets(node):
    return re.search("secrets", re.sub(r"secrets\.GITHUB_TOKEN", "", yaml.safe_dump(node), flags=re.I), re.I)


def publishes(step):
    uses = str(step.get("uses", ""))
    return "GITHUB_STEP_SUMMARY" in str(step.get("run")) or bool(uses) and not uses.startswith(QUIET)


def problems(path):
    wf = yaml.safe_load(path.read_text())
    on = wf["on"] if "on" in wf else wf.get(True)  # YAML 1.1 reads a bare `on` as True
    triggers = {on} if isinstance(on, str) else set(on or ())
    jobs = wf["jobs"]
    model = has_secrets(wf) or any("environment" in j for j in jobs.values())
    if "pull_request_target" in triggers or model and (not triggers or triggers - {"workflow_dispatch", "schedule"}):
        yield f"triggered by {sorted(triggers)}"
    if has_secrets({k: v for k, v in wf.items() if k != "jobs"}):
        yield "secret outside a job-level env"
    for name, job in jobs.items():
        if str(job.get("runs-on")) not in HOSTED:
            yield f"{name}: runs-on {job.get('runs-on')!r} is not an exact GitHub-hosted label"
        if has_secrets({k: v for k, v in job.items() if k != "env"}):
            yield f"{name}: secret outside the job-level env"
        steps = job.get("steps", [])
        pub = [i for i, s in enumerate(steps) if publishes(s)]
        scan = next((i for i, s in enumerate(steps) if s.get("run") == SCAN and len(s) == 1), len(steps))
        if pub and (pub[0] < scan or any(not publishes(s) or "if" in s for s in steps[scan + 1:pub[-1] + 1])):
            yield f"{name}: a publishing step is not an unconditional step right after the scan"


def main(paths):
    bad = [f"{p}: {m}" for p in map(Path, paths) for m in problems(p)]
    print("\n".join(bad) or f"ok: {len(paths)} workflow(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or sorted(Path(".github/workflows").glob("*.y*ml"))))
