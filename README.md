# dadaia-evals

Agent-behavior evals for [dadaia-workspace](https://github.com/marcoaureliomenezes/dadaia-workspace): an agent runs scripted Harbor tasks (`tasks/<id>/`) against a lib version in Docker, graded on the final state.

- `t1-cold-onboarding` — onboard a `file://` project into a new workspace, specs initialized, `dadaia doctor` clean.
- `t2-block-list-bug` — register and fix an operator-confirmed bug under the workspace's law, no assert rewritten.

The checks (`python3 -m unittest discover -s tests`) need Docker and `uv`: they build each task image on the 0.4.7 release and on a candidate wheel built from `$DADAIA_WORKSPACE_LIB` (default: the enclosing workspace's `repos/dadaia-workspace`).

Agents working here: read `AGENTS.md`. Specs live in the `dadaia-workspace` repo.
