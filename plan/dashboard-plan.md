# Codex Goal: Implement VelaCare Data Explorer and reporting integration

## Outcome

Build and test a real, responsive, medical-research-grade **VelaCare Data Explorer** dashboard in the **existing `~/velacare` Git repository on its dashboard feature branch**. It must read the Python genetic algorithm's experiment files directly from the same Agentic Space filesystem, support complete interactive reconstruction of EVERY generation and EVERY candidate population, and integrate cleanly with a branded OpenCode Report Agent and PowerPoint reporting template.

**Do not stop at a plan.** Implement, run, inspect screenshots, and test acceptance criteria. The existing genetic algorithm is working and is located in `src/velacare/`, with tests under `tests/`, a root `pyproject.toml` and `uv.lock`, the launch shortcut `./run-demo`, and working data under `./agentic-space/`. **Do not overwrite the GA, rewrite its package structure, or create another Python project.** Do not commit, push, or deploy without explicit direction. The user manages the feature branch; DO NOT create/switch a Git worktree or branch during implementation.

## Visual references (required)

Open and inspect both provided references BEFORE implementation:

1. `assets/data-explorer-reference.png` — VelaCare dark/navy data explorer, blue best-fitness line, teal mean line, synchronized generation slider, right-hand selected-generation metrics, 30-bit feature subset.
2. `assets/feature-evolution-reference.png` — rows of generations with selected/excluded feature tiles and fitness scores.

Extend these into a genuine research application with a persistent navigation sidebar, accessible forms, responsive layout, labeled units, reproducible plots, useful legends and empty/loading/error states. Use the included `brand/velacare_logo.png` and `brand/velacare_icon.png` in the UI; consult `brand/BRAND_GUIDELINES.md`.

## Non-negotiable product principles

- **No data transfers.** The Coding Agent, Data Explorer, and Report Agent run in the same Agentic Space workspace (repository-local `./agentic-space/` during development, `/agentic-space/` when deployed) and open identical filesystem paths. Do not add an API, DB, object store or sync job to exchange experiment data.
- **Full-population history is the core research feature.** At every generation, show its entire stored candidate population, not just the winner. A 40-generation/60-candidate experiment implies 2,400 candidate snapshots. Never downsample persisted records; plotting may aggregate for legibility.
- **Historical reconstruction, not rerunning.** Changing the generation slider must load existing records and instantly reconstruct best/mean/min/median fitness, all candidate chromosomes, diversity, and feature-selection frequency WITHOUT evaluating a model or rerunning the GA.
- **Live progressive updates.** While GA executes, read only *complete* committed generations, automatically refresh roughly every 2 seconds, and expand slider max without resetting the researcher's selection. Never expose an incomplete generation as completed.
- **Scientific clarity.** Fitness is a composite optimization score, NOT clinical accuracy or diagnostic confidence. Display separate CV and held-out test metrics, avoid testing leakage, and note the research-only nature of the work.
- **Brand and usability.** Reproduce the screenshots' hierarchy and visual identity; new research views should feel like a cohesive clinical research platform rather than generic Plotly defaults.

## Six research views

A permanent left sidebar must offer:

### 1. Overview

- Active experiment and status; run selector; dataset identity and seed.
- Best and mean fitness across generations, synced generation marker and time axis.
- At selected generation: best fitness (score), mean fitness, feature count, candidate count, diversity and completion timestamp.
- The winning 30-bit feature mask and selected feature names; reproducibility metadata link.
- A genuine slider from 1 through last **fully completed** generation.

### 2. Evolution

- Best, mean, median and minimum fitness curves, plus selected-feature-count and population-diversity curves.
- Live generation selector synchronized with other views; move to any generation and show *entire population* fitness distribution (histogram/boxplot) and candidate table.
- Explain whether candidates improved through selection, crossover, mutation and elitism if ancestry metadata exists; gracefully label unavailable lineage fields rather than inventing them.
- Inspect one candidate (candidate ID, chromosome, selected feature names, exact fitness components, parents/operators if available) and compare with another candidate.

### 3. Feature Selection

**Required full-history matrix:** Show 30 stable feature columns in the UCI dataset's canonical feature order. Provide (a) a **generation × 30 best-candidate matrix** (all complete generations, no sampling) and (b) a **candidate × 30 population matrix** for the selected generation (every candidate). Each cell indicates selected/excluded; include hover tooltips with feature name, generation, candidate ID and selection state.

- Clicking a row in the best-candidate matrix must move the global generation slider. Clicking a candidate row highlights it and updates the detail panel.
- Feature-selection frequency per generation (proportion of candidates selecting each of 30 features); top-feature ranking and evolution heatmap.
- Population diversity vs generation, at least unique-chromosome ratio plus mean pairwise Hamming distance or entropy, computed from persisted chromosomes when not supplied. Explain how calculated.
- Selected-feature-count distribution over population and generations; comparison between two chosen candidate chromosomes with Hamming distance and changes highlighted.
- Make explicit that algorithmic mask mutations are NOT biological cancer mutations.

### 4. Model Evaluation

- Separate cross-validation metrics from **held-out test** results; do not show a final test metric evolving over generations or as if independently measured for each candidate.
- Display malignant-class sensitivity, specificity, balanced accuracy, accuracy, confusion matrix and ROC/AUC only if actual saved evaluation inputs support them.
- If scores, predictions, label mapping or fold data are missing, show 'not available in run artifact' rather than fabricate graphics.
- Explain the positive class and sample counts; prohibit unsupported diagnostic claims.

### 5. Dataset

- Browse dataset rows with paging/search, the 30 numerical feature definitions and units where documented, class distribution, missingness, descriptive statistics and pairwise correlations.
- Clearly label source `UCI Breast Cancer Wisconsin (Diagnostic), dataset ID 17` and its license/attribution.
- Use local `./agentic-space/data/breast_cancer.csv` (or `$WORKSPACE/data/breast_cancer.csv`); do not request data from UCI during dashboard usage.

### 6. Compare Runs

- Discover all `run_NNN` directories from filesystem; choose any two existing runs (e.g. 40 vs 80 generations).
- Overlay best and mean fitness by generation, with differing run lengths and seeds clearly labeled.
- Compare final or selected-generation best feature masks, feature count, overlap/Jaccard, model metrics (when available), and time-to-best.
- Do not claim superiority based on the last generation if different datasets, validation designs or fitness formulas were used; show a comparability warning.

## Synchronized interaction model

Use a single shared UI state containing `run_id`, selected `generation`, and optionally selected `candidate_id` (plus second run when comparing). The global generation selection controls line-plot marker, cards, best-mask row, population heatmap and candidate inspector. Changing runs resets/clamps generation appropriately and does not reference stale candidate IDs. Keyboard accessibility and numeric input alternative to slider are required.

**Acceptance illustration**: Open a saved 40-generation run. Select generation 17. The app reconstructs generation 17's full population of 60 candidates, their 30-bit masks, fitness distribution, selected-feature frequencies, and best/mean/diversity metrics solely from files. Switch to generation 1, 40 or another run without re-running Python GA. While run 2 reaches generation 41, the max generation increases automatically.

## Existing repository structure and filesystem contract (inspect real files first)

The user provided this project layout. **Extend it; do not replace it:**

```text
~/velacare/
├── agentic-space/                 # shared runtime working data, already exists
│   ├── analysis/
│   │   └── experiments/           # inspect actual run files/schema
│   └── data/                      # Wisconsin CSV, already exists
├── assets/
│   ├── velacare-evolution-tui-reference.png  # preserve existing
│   ├── data-explorer-reference.png           # added by installer
│   └── feature-evolution-reference.png       # added by installer
├── brand/                         # company logo, PPTX template, styles
├── src/
│   └── velacare/                 # GA Python package; add dashboard subpackage here
│       └── dashboard/            # app, loader, views, components, assets
├── reporting/                     # Python baseline PPTX generator
├── docs/
│   ├── DASHBOARD_SETUP.md
│   ├── OPENCODE_SETUP.md
│   └── EXPERIMENT_OUTPUT_CONTRACT.md
├── .opencode/
│   ├── agents/velacare-report.md
│   ├── commands/velacare-report.md
│   └── skills/{create-report-slide,interpret-medical-research}/SKILL.md
├── tests/                         # add dashboard tests alongside current GA tests
├── pyproject.toml                 # use existing Python packaging/dependency setup
├── uv.lock                        # update coherently if dependencies change
├── run-demo                       # MUST continue to work untouched
├── run-dashboard                  # new shortcut to implement
├── README.md                      # preserve original; installer adds documentation links
├── CODEX_GOAL.md                  # original GA goal; preserve
└── CODEX_DASHBOARD_GOAL.md        # this goal; add to repository root
```

`agentic-space/` is the source of truth for runtime data, **NOT** `src/velacare/` and not a new top-level `analysis/` or `dashboard/` runtime copy. Keep UI Python code under `src/velacare/dashboard/`, while historical experiment outputs remain in `agentic-space/analysis/experiments/`. Use repo-local `./agentic-space` by default for local running; accept `--workspace /agentic-space` for deployment.

Before implementing a schema adapter, **inspect actual** `src/velacare/` writers, manifest generation, real saved runs, and tests under `tests/test_history.py`. The earlier design contract is a target, not a claim that existing files have identical names or keys.

Typical *expected* run artifacts may include:

```text
agentic-space/analysis/experiments/
├── latest.json
└── run_001/
    ├── run_manifest.json
    ├── generation_history.csv
    ├── candidate_history.jsonl
    ├── best_candidates.json
    └── model_metrics.json
```

`candidate_history.jsonl` (or the actual GA's equivalent complete candidate store) is the source of truth for population reconstruction. Preserve canonical `(run_id, generation, candidate_id)` identity, stable 30-feature order and exact chromosomes. Treat only validated, complete generations as committed. If the GA output differs, implement a **bounded, tested read-only adapter** and document the mapping in `docs/DATA_EXPLORER_CONTRACT.md`. If a necessary data field is absent, explain it and propose the smallest compatible producer change; do not quietly fake values or modify the GA without documenting and testing the change.

**Do not implement any file transfer** between the GA, dashboard, and report agent. They must resolve the same runtime root.

## Technology and launch

Prefer **Python 3.11+ and Plotly Dash** with responsive custom CSS branded to VelaCare. Use local file readers (`pathlib`, `csv`, `json`) and Pandas/NumPy where beneficial, Plotly for interactive charts and Dash state/callbacks. No remote backend or additional persistent DB.

Create executable repository root shortcut:

```bash
./run-dashboard --workspace ./agentic-space --host 127.0.0.1 --port 8050
```

Modify the existing `pyproject.toml` and `uv.lock` using its current `uv` workflow, rather than introducing a second project, `venv` management layer, or separately maintained dashboard lockfile. Include fast validation on startup, meaningful empty-state instructions when no experiment exists, graceful handling of file changes, and no unnecessary watch/refresh when a run is idle. Dashboard should be usable behind an ingress proxy with a configurable base URL path if relevant.

## Branded Report Agent integration

This bundle already supplies:

- `AGENTS.md` repository guidance.
- `.opencode/agents/velacare-report.md` configured OpenCode reporting agent.
- `.opencode/skills/create-report-slide/SKILL.md` and `.opencode/skills/interpret-medical-research/SKILL.md`.
- `.opencode/commands/velacare-report.md` invocation shortcut.
- `brand/velacare_logo.png`, `brand/velacare_icon.png`, `brand/VelaCare_Research_Reporting_Template.pptx`.
- `reporting/create_report.py` deterministic reporting helper (adapt if actual run schema differs).

Preserve these project files. Verify they are discoverable by OpenCode (or document compatible installation for local version), and that the reporting agent can create an actual branded PowerPoint from a completed run without manually copying data between applications. Generate the PPTX under the selected workspace root `presentations/` directory, e.g. `./agentic-space/presentations/` locally or `/agentic-space/presentations/` in SecurSpaces. No fabricated performance numbers, validation claims or conclusions.

## Verification and done criteria

- [ ] Work takes place in the user-selected dashboard branch in the **existing `~/velacare` checkout**; no new Git worktree and no changes to the working GA CLI or its existing tests.
- [ ] Both reference screenshots and logo are reflected in final design; screenshots of implemented UI included in documentation.
- [ ] All six views work with real files; responsive sidebar, clear controls, helpful error/empty states.
- [ ] Slider and synchronized views reconstruct every generation; source of all data is persisted experiment files, not model execution.
- [ ] Both complete 30-feature matrices exist (per-generation best mask AND selected-generation entire population).
- [ ] Candidate selection, chromosome comparisons, feature frequencies and diversity trends work across every generation.
- [ ] Complete history test: `G × P` candidate records read or safely accounted for; malformed rows flagged, not silently dropped.
- [ ] Live updates show only fully completed generations, and do not reset slider unexpectedly.
- [ ] CV vs held-out test separation is visible, and research-only caveat present on evaluation/report views.
- [ ] 40- vs 80-generation comparison works and preserves both run histories.
- [ ] Report Agent has access to branded assets, generates `.pptx` with sourced data, and documents limitations.
- [ ] Automated unit + UI integration tests + one smoke run complete; no omitted layout/image assets.
- [ ] Provide exact commands to launch dashboard and report, screenshots, test output and list of changed files. Do not push/deploy.

## Documentation and installation requirements

- `README.md` must link to `docs/DASHBOARD_SETUP.md` and `docs/OPENCODE_SETUP.md` and explain how to launch the existing GA and the new dashboard without mixing paths.
- `docs/DASHBOARD_SETUP.md` documents Python dependency setup using `uv`, `./run-demo`, `./run-dashboard`, the workspace flag, local URL, outputs, run selectors and troubleshooting.
- `docs/OPENCODE_SETUP.md` documents `bash plan_dashboard/scripts/install-opencode.sh`, OpenCode setup, agent selection, `/velacare-report` usage, dependencies, branded PPTX generation, and validation.
- Preserve `CODEX_GOAL.md` and the existing root `README.md` content. Only change or append the relevant dashboard sections.

## Execution steps for Codex

1. Verify the existing checkout and user-selected branch with `git status` / `git branch --show-current`, without switching branches; inspect the real GA package and artifacts; read `AGENTS.md`, `docs/DASHBOARD_SETUP.md` and `docs/EXPERIMENT_OUTPUT_CONTRACT.md`.
2. Validate schema and data contract first; demonstrate reconstruction of arbitrary generation from file alone.
3. Implement typed data loader, complete population reconstruction and tests.
4. Implement six-view dashboard, state synchronization, dynamic updates, charts and styling.
5. Run visual comparison against attached screenshots, fix UX, and add tests.
6. Verify reporting agent/template can generate a genuine presentation from saved experiment artifacts.
7. Report evidence, screenshots and tests. Only mark complete when all acceptance criteria pass.
