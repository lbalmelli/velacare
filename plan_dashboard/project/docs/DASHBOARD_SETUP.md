# Running VelaCare Data Explorer

## Status

The genetic algorithm under `src/velacare/` is already working. The Data Explorer is the **Codex implementation task** described in [`../CODEX_DASHBOARD_GOAL.md`](../CODEX_DASHBOARD_GOAL.md); `./run-dashboard` only exists after Codex implements it. The installation script provides the goal and assets, not a completed dashboard.

## Repository layout

- Working Python application: `src/velacare/`.
- Existing CLI: `./run-demo`.
- Dashboard Python modules to implement: `src/velacare/dashboard/`.
- Dashboard launcher to implement: `./run-dashboard`.
- Shared persistent data root: `./agentic-space/` during development, `/agentic-space/` when deployed.
- Current runs: `./agentic-space/analysis/experiments/`.
- Visual references: `assets/data-explorer-reference.png`, `assets/feature-evolution-reference.png`.

## Prepare environment

Use the repository's existing Python/uv setup, not a separate project or virtual environment. Verify dependencies using your existing `uv sync` workflow. Codex should add Plotly Dash and any other needed dependencies to **the existing** `pyproject.toml` and update `uv.lock` coherently.

## Start the genetic algorithm

```bash
cd ~/velacare
./run-demo --generations 40 --population 60 --seed 42
```

## Start the dashboard (after implementation)

```bash
cd ~/velacare
./run-dashboard --workspace ./agentic-space --host 127.0.0.1 --port 8050
```

Open `http://127.0.0.1:8050` in a browser. `--workspace /agentic-space` selects the deployment path when all applications share that mounted workspace; do not add file-copy or sync steps.

The initial view should be **Evolution**; the left navigation provides Overview, Evolution, Feature Selection, Model Evaluation, Dataset and Compare Runs. A single generation slider controls the selected chromosome, metrics, full candidate population, frequencies and diversity measurements. All values must come from persisted run records, not screenshots.

## Live evolution and comparison

Start the dashboard, then run another experiment in the same shared workspace. New completed generations should appear automatically without moving the selected generation unexpectedly. Compare the 40- and 80-generation runs from the Compare Runs view.

## Missing data and troubleshooting

The dashboard must detect runs from real files. If `candidate_history.jsonl` or another assumed output is absent or different, inspect the writer in `src/velacare/` and implement a typed read-only adapter. Missing candidate-level records must be reported explicitly; don't reconstruct fake candidate populations from summary rows.

For reporting setup see [OpenCode Report Agent Setup](OPENCODE_SETUP.md). Not clinically validated.
