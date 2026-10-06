"""T1 cold onboarding (AC2.2, AC2.3): each image builds on the 0.4.7 layer and on a
candidate wheel; the unchanged grader passes a hand-onboarded workspace and fails an empty one.

Docker and uv are required: a missing tool or lib path fails the row, never skips it.
"""

import functools
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
T1 = "t1-cold-onboarding"


def sh(*cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise AssertionError(f"{cmd}: exit {p.returncode}\n{p.stderr[-3000:]}")
    return p.stdout


def lib_path():
    """The dadaia-workspace checkout the candidate wheel is built from: $DADAIA_WORKSPACE_LIB
    (ci.yml, eval.yml), else the enclosing workspace's repos/dadaia-workspace."""
    env = os.environ.get("DADAIA_WORKSPACE_LIB")
    tried = [Path(env)] if env else [p / "repos/dadaia-workspace" for p in ROOT.parents]
    lib = next((p for p in tried if (p / "pyproject.toml").is_file()), None)
    if lib is None:
        raise AssertionError(f"no dadaia-workspace lib: set DADAIA_WORKSPACE_LIB (tried {tried[0]})")
    return lib


@functools.cache
def wheel():
    out = Path(tempfile.mkdtemp())
    sh("uv", "build", "--wheel", str(lib_path()), "-o", str(out))
    return next(out.glob("*.whl"))


@functools.cache
def image(task, version):
    """tasks/<task>/environment built with the lib layer eval.yml writes: a PyPI pin, or "candidate"."""
    with tempfile.TemporaryDirectory() as d:
        ctx = Path(d) / "environment"
        shutil.copytree(ROOT / "tasks" / task / "environment", ctx)
        (ctx / "lib").mkdir()
        if version == "candidate":
            shutil.copy(wheel(), ctx / "lib")
            req = f"/lib/{wheel().name}"
        else:
            req = f"dadaia-workspace=={version}"
        (ctx / "lib/requirements.txt").write_text(req + "\n")
        tag = f"dadaia-evals-{task}:{version}"
        sh("docker", "build", "-q", "-t", tag, str(ctx))
    return tag


def reward(task, version, script):
    """Run `script` in a fresh container, then the task's grader as Harbor does; the reward written."""
    tests = ROOT / "tasks" / task / "tests"
    out = sh("docker", "run", "--rm", "--mount", f"type=bind,src={tests},dst=/tests,readonly",
             image(task, version), "bash", "-c",
             f"({script}) >&2; mkdir -p /logs/verifier; bash /tests/test.sh >&2; cat /logs/verifier/reward.txt")
    return out.strip()


# Each version's documented onboarding, typed by hand.
INIT = "dadaia init /workspace --harness claude --repo file:///srv/demo.git"
HAND = {
    "0.4.7": INIT,
    "candidate": f"{INIT} && /workspace/.dadaia/.venv/bin/dadaia specs init --context demo",
}


class ColdOnboarding(unittest.TestCase):
    def test_the_grader_passes_a_hand_onboarded_workspace_of_each_version(self):
        for version, script in HAND.items():
            with self.subTest(version):
                self.assertEqual(reward(T1, version, script), "1")

    def test_the_grader_fails_an_empty_workspace(self):
        for version in HAND:
            with self.subTest(version):
                self.assertEqual(reward(T1, version, "true"), "0")

    def test_no_run_output_is_committed(self):
        self.assertEqual(sh("git", "-C", str(ROOT), "ls-files", "jobs"), "")


if __name__ == "__main__":
    unittest.main()
