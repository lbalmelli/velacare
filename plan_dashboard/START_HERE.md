# VelaCare Dashboard: in-place Codex implementation package

This package updates `~/velacare` **in place**. It creates NO Git worktree and it does not switch branches. Existing genetic algorithm code (`src/velacare/`, `run-demo`, `CODEX_GOAL.md`), local experiment files (`agentic-space/`), `pyproject.toml` and `uv.lock` are preserved.

## Where to unpack

Extract the ZIP contents into the **existing** `~/velacare/plan_dashboard/` folder. The archive contains `START_HERE.md`, `project/` and `scripts/` at its root, so do not extract directly into `~/velacare/`.

```bash
cd ~/velacare
unzip -o ~/Downloads/VelaCare_Dashboard_InPlace_Codex_Package.zip -d plan_dashboard
```

Your old `plan_dashboard/bootstrap/create-worktree.sh` might remain from the earlier bundle. **Do not run it.** This new package uses only `scripts/install-dashboard.sh` and `scripts/install-opencode.sh`.

## Branch (manual, in this existing checkout)

When ready to start the dashboard work, create a feature branch in this checkout, not a worktree. First inspect `git status --short` and your current branch; ensure your current GA implementation is safe. If not already on the desired branch:

```bash
git switch -c feat/velacare-data-explorer
```

If this branch already exists locally, use `git switch feat/velacare-data-explorer` instead. Branch commands are manual to avoid touching a running Codex session.

## Install the planning files and OpenCode reporter

```bash
cd ~/velacare
bash plan_dashboard/scripts/install-dashboard.sh
bash plan_dashboard/scripts/install-opencode.sh
```

The first installer adds `CODEX_DASHBOARD_GOAL.md`, dashboard reference images and `docs/DASHBOARD_SETUP.md`, and appends a linked 'Data Explorer and OpenCode' section to the existing root `README.md` (never replaces the rest). The second installs `.opencode/`, `AGENTS.md`, brand files, reporting helper and `opencode.jsonc` if they do not conflict with existing files. **Both are idempotent** and move conflicting incoming files to `plan_dashboard/incoming/` for manual merging rather than overwriting.

## Start Codex

```bash
cd ~/velacare
codex -i assets/data-explorer-reference.png -i assets/feature-evolution-reference.png \
  "Read CODEX_DASHBOARD_GOAL.md and AGENTS.md. Inspect real GA outputs and preserve run-demo. Implement the six-view VelaCare Data Explorer in src/velacare/dashboard, add run-dashboard, verify full population history/slider and tests. No worktree, branch switch, commit or push."
```

The goal is implementation work for Codex; the bundle does **not** pretend that `./run-dashboard` already exists. When built, follow `docs/DASHBOARD_SETUP.md` to launch it and `docs/OPENCODE_SETUP.md` to launch the Report Agent.

## Notable files

- `project/CODEX_DASHBOARD_GOAL.md`: full implementation and acceptance criteria.
- `project/assets/`: the original UI reference screenshots.
- `project/brand/`: logo/icon and an editable PowerPoint report template.
- `project/.opencode/`: Report Agent, skills and command.
- `project/reporting/create_report.py`: baseline report generator reading persisted runs.
- `project/docs/DASHBOARD_SETUP.md`: complete dashboard run and troubleshooting guide.
- `project/docs/OPENCODE_SETUP.md`: complete Report Agent setup guide.
- `scripts/install-dashboard.sh`: safe in-place dashboard setup.
- `scripts/install-opencode.sh`: safe in-place OpenCode setup.
