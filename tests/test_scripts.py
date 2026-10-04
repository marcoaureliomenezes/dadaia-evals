"""The 0177 workflow check, the secret scan and compare.py, through their exit codes."""

import json
import re
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLANTS = ROOT / "tests" / "plants"


def proc(script, *args, env=None, cwd=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
        capture_output=True, text=True, env={**os.environ, **(env or {})}, cwd=cwd,
    )


def run(script, *args, **kw):
    return proc(script, *args, **kw).returncode


def pin_mismatches(root):
    """Dockerfiles whose CLAUDE_CODE_VERSION ARG is not exactly eval.yml's (its one owner)."""
    pin = yaml.safe_load((root / ".github/workflows/eval.yml").read_text())["env"]["CLAUDE_CODE_VERSION"]
    return [f for f in sorted(root.glob("tasks/*/environment/Dockerfile"))
            if re.findall(r"^ARG CLAUDE_CODE_VERSION=(.*)$", f.read_text(), re.M) != [pin]]


class WorkflowCheck(unittest.TestCase):
    def test_each_planted_workflow_is_red(self):
        for plant in sorted(p.stem for p in PLANTS.glob("*.yml") if p.stem != "ok"):
            with self.subTest(plant):
                p = proc("check_workflows.py", PLANTS / f"{plant}.yml")
                self.assertEqual((p.returncode, "Traceback" in p.stderr), (1, False))

    def test_a_compliant_model_workflow_and_this_repo_pass(self):
        self.assertEqual(run("check_workflows.py", PLANTS / "ok.yml"), 0)
        self.assertEqual(run("check_workflows.py", cwd=ROOT), 0)

    def test_a_yaml_extension_is_checked_too(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".github/workflows").mkdir(parents=True)
            (Path(d) / ".github/workflows/x.yaml").write_text((PLANTS / "trigger-push.yml").read_text())
            self.assertEqual(run("check_workflows.py", cwd=d), 1)


class ClaudeCliPin(unittest.TestCase):
    def tree(self, d, *args):
        (d / ".github/workflows").mkdir(parents=True)
        (d / ".github/workflows/eval.yml").write_text((ROOT / ".github/workflows/eval.yml").read_text())
        pin = yaml.safe_load((ROOT / ".github/workflows/eval.yml").read_text())["env"]["CLAUDE_CODE_VERSION"]
        for i, line in enumerate(args):
            (d / f"tasks/t{i}/environment").mkdir(parents=True)
            (d / f"tasks/t{i}/environment/Dockerfile").write_text(f"FROM x\n{line.format(pin=pin)}\n")
        return pin_mismatches(d)

    def test_every_task_dockerfile_pins_eval_yml_value(self):
        # No task dir yet passes; 185/186 add theirs under this test.
        self.assertEqual(pin_mismatches(ROOT), [])

    def test_a_mismatched_or_quoted_arg_is_red(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(len(self.tree(Path(d), "ARG CLAUDE_CODE_VERSION={pin}", "ARG CLAUDE_CODE_VERSION=0.0.1",
                                           'ARG CLAUDE_CODE_VERSION="{pin}"')), 2)


class Scan(unittest.TestCase):
    def scan(self, text, env=None, name="transcript.txt"):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "jobs" / "trial").mkdir(parents=True)
            f = Path(d) / "jobs" / "trial" / name
            f.write_bytes(text) if isinstance(text, bytes) else f.write_text(text)
            return run("scan.py", Path(d) / "jobs", env=env)

    def test_a_token_in_json_or_binary_is_red(self):
        token = "sk-ant-" + "oat01-" + "PLANTED" * 6
        self.assertEqual(self.scan(json.dumps({"t": token}), name="result.json"), 1)
        self.assertEqual(self.scan(b"\x00\xff" + token.encode() + b"\x00", name="blob.bin"), 1)

    def test_a_missing_path_is_red(self):
        self.assertEqual(run("scan.py", ROOT / "no-such-dir"), 1)

    def test_a_planted_token_shape_is_red(self):
        # Composed at runtime: no token-shaped literal is tracked.
        self.assertEqual(self.scan("log " + "sk-ant-" + "oat01-" + "PLANTED" * 6), 1)

    def test_the_secret_value_itself_is_red(self):
        self.assertEqual(self.scan("x planted-fake-value x", {"SCAN_SECRET": "planted-fake-value"}), 1)

    def test_a_clean_tree_passes(self):
        self.assertEqual(self.scan("nothing here", {"SCAN_SECRET": "planted-fake-value"}), 0)


def job(root, task, rewards):
    # As harbor 0.23.0 writes: a job-level result.json beside one per trial,
    # task_name possibly namespaced by task.toml's [task] name.
    root.mkdir(parents=True, exist_ok=True)
    (root / "result.json").write_text(json.dumps({"stats": {}}))
    for i, r in enumerate(rewards):
        d = root / f"{task}__{i}"
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps(
            {"task_name": f"dadaia-evals/{task}", "verifier_result": {"rewards": {"reward": r}}}))


class Compare(unittest.TestCase):
    def compare(self, base, cand):
        with tempfile.TemporaryDirectory() as d:
            b, c = Path(d) / "base", Path(d) / "cand"
            for task, rewards in base.items():
                job(b, task, rewards)
            for task, rewards in cand.items():
                job(c, task, rewards)
            return run("compare.py", b, c)

    T1, T2 = "t1-cold-onboarding", "t2-seeded-bug"

    def test_a_planted_drop_blocks(self):
        self.assertEqual(self.compare({self.T1: [1, 1, 1], self.T2: [1, 1, 0]},
                                      {self.T1: [1, 1, 1], self.T2: [1, 0, 0]}), 1)

    def test_t1_at_two_of_three_blocks(self):
        self.assertEqual(self.compare({self.T1: [0, 0, 0], self.T2: [0, 0, 0]},
                                      {self.T1: [1, 1, 0], self.T2: [0, 0, 0]}), 1)

    def test_a_missing_candidate_trial_counts_as_a_fail(self):
        self.assertEqual(self.compare({self.T1: [1, 1, 1], self.T2: [1, 1, 1]},
                                      {self.T1: [1, 1, 1], self.T2: [1]}), 1)

    def test_a_task_absent_from_the_candidate_blocks(self):
        self.assertEqual(self.compare({self.T1: [1, 1, 1], self.T2: [1, 1, 1]}, {self.T1: [1, 1, 1]}), 1)

    def test_a_fractional_reward_is_a_fail(self):
        self.assertEqual(self.compare({self.T1: [1, 1, 1]}, {self.T1: [1, 1, 0.5]}), 1)

    def test_t1_absent_from_the_candidate_blocks(self):
        self.assertEqual(self.compare({self.T2: [0, 0, 0]}, {self.T2: [0, 0, 0]}), 1)

    def test_anything_else_is_readout(self):
        # base 1/3 -> cand 0/3 is no drop by the rule; T1 at 3/3.
        self.assertEqual(self.compare({self.T1: [1, 1, 0], self.T2: [1, 0, 0]},
                                      {self.T1: [1, 1, 1], self.T2: [0, 0, 0]}), 0)


if __name__ == "__main__":
    unittest.main()
