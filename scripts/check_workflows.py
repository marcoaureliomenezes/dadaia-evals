"""ADR 0177's check: exit 1 when a workflow breaks a model-API clause.

Every workflow: an exact GitHub-hosted runs-on; push, pull_request,
workflow_dispatch or schedule only; no `defaults` (a shell could swallow the
scan's exit); secrets only in a job-level `env`; publishing steps (upload,
the one canonical summary line) unconditional, right after the canonical
scan, uploading only what it covers; actions only checkout, setup-uv, upload. Model-capable (`secrets`
beyond secrets.GITHUB_TOKEN, or a job `environment`): dispatch/schedule only.
"""

import re
import sys
from pathlib import Path

import yaml  # preinstalled in the GitHub-hosted Ubuntu image's system python3

HOSTED = {"ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04", "windows-latest", "windows-2025",
          "windows-2022", "macos-latest", "macos-15", "macos-14"}
OUT = {"jobs/", "summary.md"}  # what the scan covers
SCAN = "python3 scripts/scan.py jobs summary.md"
SUMMARY = 'cat summary.md >> "$GITHUB_STEP_SUMMARY"'
ACTIONS = ("actions/checkout@", "astral-sh/setup-uv@", "actions/upload-artifact@")  # every other action is red


def has_secrets(node):
    return re.search("secrets", re.sub(r"secrets\.GITHUB_TOKEN", "", yaml.safe_dump(node), flags=re.I), re.I)


def publishes(step):
    return "GITHUB_STEP_SUMMARY" in str(step.get("run")) or str(step.get("uses")).startswith(ACTIONS[2])


def problems(path):
    wf = yaml.safe_load(path.read_text())
    on = wf["on"] if "on" in wf else wf.get(True)  # YAML 1.1 reads a bare `on` as True
    triggers = {on} if isinstance(on, str) else set(on or ())
    jobs = wf["jobs"]
    model = has_secrets(wf) or any("environment" in j for j in jobs.values())
    if triggers - {"push", "pull_request", "workflow_dispatch", "schedule"} or model and (not triggers or triggers - {"workflow_dispatch", "schedule"}):
        yield f"triggered by {sorted(triggers)}"
    if has_secrets({k: v for k, v in wf.items() if k != "jobs"}) or "defaults" in wf:
        yield "secret or defaults outside a job-level env"
    for name, job in jobs.items():
        if str(job.get("runs-on")) not in HOSTED:
            yield f"{name}: runs-on {job.get('runs-on')!r} is not an exact GitHub-hosted label"
        if has_secrets({k: v for k, v in job.items() if k != "env"}) or "defaults" in job:
            yield f"{name}: secret or defaults outside the job-level env"
        steps = job.get("steps", [])
        if any("uses" in s and not str(s["uses"]).startswith(ACTIONS) for s in steps):
            yield f"{name}: an action outside {ACTIONS}"
        pub = [i for i, s in enumerate(steps) if publishes(s)]
        scan = next((i for i, s in enumerate(steps) if s.get("run") == SCAN and len(s) == 1), len(steps))
        if pub and (pub[0] < scan or any(not publishes(s) or "run" in s and s != {"run": SUMMARY} or "if" in s or not OUT >= set(
                str((s.get("with") or {}).get("path", "")).split()) for s in steps[scan + 1:pub[-1] + 1])):
            yield f"{name}: a publishing step is not an unconditional step right after the scan"


def main(paths):
    bad = [f"{p}: {m}" for p in map(Path, paths) for m in problems(p)]
    print("\n".join(bad) or f"ok: {len(paths)} workflow(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or sorted(Path(".github/workflows").glob("*.y*ml"))))
