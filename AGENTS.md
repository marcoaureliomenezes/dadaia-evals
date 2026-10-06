# dadaia-evals — the repo law

- This repo measures agent behaviour against the `dadaia-workspace` distribution; it is an evals repo, an associated repo of that spec context.
- Its specs, backlog, releases and ADRs live in the main repo (`dadaia-workspace`); this repo has no `specs/`.

## What lives here

- `tasks/<id>/` — one Harbor task each: `instruction.md`, `task.toml`, `environment/Dockerfile`, `tests/test.sh`, `tests/test_grade.py`.
- A Dockerfile holds the environment only; its last layer is `COPY lib/ /lib/` and an install from `/lib/requirements.txt`, which names a pinned PyPI release or a wheel beside it (ADR 0179). `eval.yml` writes each task's `environment/lib/` per run; it is never committed.
- `.github/workflows/eval.yml` — the check job, then the model job; `.github/workflows/ci.yml` — the secret-free checks.
- `scripts/` — the result comparison, the workflow check and the secret scan.
- Nothing else of substance: no operator repo, workspace or credential is ever copied in.

## How to run

- In CI: `gh workflow run eval.yml -f lib_ref=<ref>`; read the verdict from the job summary and its artifact.
- Locally: `eval.yml`'s steps that write `environment/lib/` and run `harbor run`, Docker running, with your own `CLAUDE_CODE_OAUTH_TOKEN`; those steps are the one source of the pins and flags.
- `jobs/` is the run output (trial logs, transcripts): never committed, ignored by `.gitignore`.

## Gate lines (ADR 0207: read from the work branch)

verify: python3 -m unittest discover -s tests -v
verify-stage: python3 -m unittest discover -s tests -v
verify-task: python3 -c "import sys, unittest; sys.exit(not unittest.main(module=None, argv=['unittest', 'discover', '-s', 'tests'], exit=False).result.wasSuccessful())"
tests: tests/** tasks/*/tests/**

## The model-API law (ADR 0177)

- Source: dadaia-workspace `dd-gitflow-default` §3b and ADR 0177; on a difference, that text wins.
- A job that calls a model API runs only on `workflow_dispatch` or `schedule`; no `push`, `pull_request` or `pull_request_target` trigger calls a model.
- No workflow here runs on a self-hosted runner.
- The model secret is read only by those jobs, at job level, never at workflow level.
- Artifacts and transcripts come only from synthetic projects built inside the run.
- Every artifact (the `jobs/` tree included) and the job summary pass a secret scan, the model secret's value included, before any upload and before the summary is written; a hit fails the job and uploads nothing.
