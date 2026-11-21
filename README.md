# VelaCare Evolution Engine

A reproducible Python research demo that evolves feature subsets for the UCI Breast Cancer Wisconsin (Diagnostic) dataset. It runs a seeded binary genetic algorithm, evaluates candidates with training-only stratified cross-validation, scores the chosen subset once on a held-out test split, and records every candidate in every generation.

The terminal dashboard follows the supplied VelaCare reference at [`assets/velacare-evolution-tui-reference.png`](assets/velacare-evolution-tui-reference.png). The screenshot's values are mock values; all values shown by the application come from the current computation.

This is an educational feature-selection demonstration. It is not clinically validated and does not evolve biological cancer mutations.

## Run it

Python 3.11 or newer is required. On the first invocation, the root launcher creates `.venv`, installs the pinned packages from `requirements.lock`, and installs this project. No virtual-environment activation is needed.

```bash
./run-demo --generations 40 --population 60 --seed 42
```

Other CLI options:

```text
--generations N       Positive number of generations (default: 40)
--population N        Population size, at least 4 (default: 60)
--seed N              Random seed (default: 42)
--mutation-rate P     Per-bit mutation probability in [0, 1] (default: 0.03)
--crossover-rate P    Uniform crossover probability in [0, 1] (default: 0.8)
--workspace PATH      Shared filesystem root override
--download-only       Fetch and validate the dataset, then exit
--no-color            Disable ANSI colors
--help                Show full usage
```

The default workspace is `/agentic-space` when it exists and is writable. Otherwise the application uses `./agentic-space`. `--workspace /some/path` overrides either choice. Example for a dataset-only fetch:

```bash
./run-demo --download-only --workspace ./agentic-space
```

## Dataset and scientific method

The application downloads UCI dataset 17 from the [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/17/breast-cancer-wisconsin-diagnostic), then caches a normalized 569-row, 30-feature CSV and provenance metadata. Feature order follows the original WDBC variable sequence. Labels are mapped as benign = 0 and malignant = 1. The normalized CSV checksum is checked on later runs.

Each chromosome is a nonempty 30-bit mask. A stratified 80/20 split is made once. Candidate fitness uses three-fold stratified cross-validation over only the 80% training side. Standardization is fit inside each training fold, followed by balanced logistic regression. The held-out 20% is not available to feature selection. After the GA finishes, the selected candidate is refit on the full training split and evaluated once on the untouched held-out split.

Fitness is:

```text
0.60 × CV malignant sensitivity
+ 0.40 × CV balanced accuracy
- 0.02 × selected feature count / 30
```

This makes malignant sensitivity explicit while applying a small linear feature-count penalty. Exact chromosome evaluations are cached, but every candidate still gets a complete record in its generation. The GA uses seeded initialization, tournament selection, uniform crossover, independent bit mutation, and two elite candidates per generation.

The held-out result is descriptive of this run and dataset split. It is not evidence of clinical performance.

## Workspace output and schema

The application writes directly into the shared workspace; it has no transfer service or dashboard API.

```text
WORKSPACE/
├── data/
│   ├── breast_cancer.csv
│   └── dataset_metadata.json
└── analysis/experiments/
    ├── latest.json
    ├── run_001/
    │   ├── run_manifest.json
    │   ├── generation_history.csv
    │   ├── candidate_history.jsonl
    │   ├── best_candidates.json
    │   └── model_metrics.json
    └── run_002/...
```

Run directories are allocated by exclusive creation and are never overwritten. `latest.json` points to the newest run's manifest. The output schema is versioned (`schema_version: 1.0.0`) and records the engine and dependency versions, feature and label order, dataset checksum, run parameters, CV setup, timestamps, and status.

### History fields

- `generation_history.csv` has one row per committed generation: population size; best, mean, minimum, and median fitness; best candidate ID, chromosome, and feature list; unique-mask count; bit entropy; mean pairwise Hamming distance; and elapsed timings.
- `candidate_history.jsonl` has one complete record per `(run_id, generation, candidate_id)`. It includes the 30-bit chromosome, selected names/count, fitness and its components, CV classifier metrics, ancestry, operator names, and whether the deterministic CV cache supplied the metrics.
- `best_candidates.json` stores the complete best-candidate record for every committed generation and the current final-best snapshot.
- `model_metrics.json` separates out-of-fold training CV metrics from held-out test metrics and stores accuracy, balanced accuracy, malignant sensitivity, specificity, and confusion matrices. Confusion-matrix row/column order is malignant, benign.
- `run_manifest.json` is the visibility boundary for consumers: `last_fully_committed_generation` advances only after the population JSONL records, generation CSV row, and best-candidate snapshot have been flushed. Consumers should read no generation beyond that value. On an interruption, completed generations remain readable and the run status is `interrupted` (or `failed`); no partial generation is marked committed.

All generations store all candidates, including elites and chromosomes whose classifier results came from cache. For a completed run with `G` generations and population `P`, there are exactly `G` committed summary rows and `G × P` candidate records.

### Reconstruct without rerunning

`velacare.reader` reads only saved files. It does not import the genetic algorithm or classifier code. For example:

```python
from pathlib import Path
from velacare.reader import reconstruct_generation, validate_run_history

run = Path("/agentic-space/analysis/experiments/run_001")
report = validate_run_history(run)  # validates and reconstructs every committed generation
generation_17 = reconstruct_generation(run, 17)

print(report["candidate_records"])
for candidate in generation_17["candidates"]:
    print(candidate["candidate_id"], candidate["chromosome"], candidate["fitness"])
print("best features:", generation_17["best_candidate"]["selected_features"])
print("fitness distribution:", generation_17["fitness_values"])
```

Generation numbers are one-based. A request beyond the manifest's committed generation raises `HistoryError`. Candidate records also carry ancestry references to the parent generation and candidate IDs for lineage visualizations.

## Development and verification

```bash
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements.lock
.venv/bin/pip install --no-deps -e .
.venv/bin/pytest
```

Tests exercise dataset validation and feature ordering, label mapping, genetic operators, deterministic seeded evolution, elitism, exact chromosome/name reconstruction, full candidate histories, CV/test metric separation, interrupted-generation visibility, and no-color TUI output. The end-to-end history test reconstructs every small-run generation from its saved files.

Dataset attribution: Wolberg, Mangasarian, Street, and Street (1993), *Breast Cancer Wisconsin (Diagnostic)*, UCI Machine Learning Repository, DOI [10.24432/C5DW2B](https://doi.org/10.24432/C5DW2B), licensed CC BY 4.0.

<!-- VELACARE_DASHBOARD_DOCS_START -->

## VelaCare Data Explorer and OpenCode reporting

The genetic Evolution Engine runs through `./run-demo`, using data in `./agentic-space/`.

### Run the dashboard

See the [dashboard setup guide](docs/DASHBOARD_SETUP.md), then run:

```bash
./run-dashboard --workspace ./agentic-space --host 127.0.0.1 --port 8050
```

- **OpenCode Report Agent:** [install, configure, and generate VelaCare PowerPoint reports](docs/OPENCODE_SETUP.md).

The Coding Agent, Data Explorer and Report Agent share the **same `./agentic-space/` filesystem**. No file export or synchronization between them is required.

<!-- VELACARE_DASHBOARD_DOCS_END -->
