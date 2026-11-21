# VelaCare repository instructions

## Context and structure

This repository already contains a working genetic algorithm implemented as a Python package in `src/velacare/`. Keep `run-demo`, its algorithm, and the existing tests working. This dashboard feature is implemented **in this repository on the user's selected feature branch**, not in a worktree. Do not switch branches, create a worktree, push, or deploy unless asked.

- Repo-local shared workspace: `./agentic-space/` (under SecurSpaces deployment use `/agentic-space/`).
- Shared dataset: `$WORKSPACE/data/breast_cancer.csv`.
- Shared run artifacts: `$WORKSPACE/analysis/experiments/`.
- Dashboard Python source: `src/velacare/dashboard/`.
- Python dependencies: existing `pyproject.toml`, `uv.lock`, no second application environment.
- Dashboard runner: new root `./run-dashboard`.
- Report helper: `reporting/create_report.py`.
- Branding: `brand/`.
- OpenCode agent and skills: `.opencode/`.

## Dashboard rules

Read `CODEX_DASHBOARD_GOAL.md` and `docs/EXPERIMENT_OUTPUT_CONTRACT.md`. Inspect actual GA output before assuming schemas. Reconstruct any complete generation and all candidate chromosomes from files, including best/mean fitness, feature-selection frequency and diversity. Build all six research views, history heatmaps, generation slider, live refresh and run comparisons. Do not use a network service or data synchronization to exchange GA results.

Fitness is a composite optimization score, not clinical sensitivity or accuracy. Keep CV vs held-out test evaluation strictly separate and say 'not available' for unsupported values. This is a research demonstration, not clinically validated software.

## OpenCode Report Agent

Read `docs/OPENCODE_SETUP.md`; load the `velacare-report` agent with `create-report-slide` and `interpret-medical-research` skills. Presentations are generated from existing run artifacts and VelaCare's official fictitious brand template, saved under `$WORKSPACE/presentations/`. Never invent metrics or clinical claims.

## Version control and validation

Preserve uncommitted changes and root `CODEX_GOAL.md`. Run the existing GA suite, new dashboard tests, visual checks and report-generation smoke tests. Do not claim a behavior without a successful validation.
