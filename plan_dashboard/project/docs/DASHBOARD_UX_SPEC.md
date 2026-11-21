# VelaCare Research Data Explorer: interaction contract

## Sidebar views

1. Overview
2. Evolution
3. Feature Selection
4. Model Evaluation
5. Dataset
6. Compare Runs

## Global controls

A run dropdown and generation slider (plus keyboard-navigable numeric field) appear on evolution-centric pages. Shared selection state is `run_id`, `generation`, `candidate_id` and optional comparison run. All graphs and metrics reflect the same snapshot.

## Two mandatory heatmaps

**A. Entire evolutionary history**: G rows × 30 columns. One row is the best candidate from each fully committed generation. Fixed feature order. Clicking a row changes global selection; clicking a cell opens feature details.

**B. Entire candidate population**: P rows × 30 columns for chosen generation. Never display only top candidates and pretend it is the whole population. Candidate rows sortable by fitness, feature count or ID. Clicking a row opens exact score, selected names and lineage.

## Further research visuals

- Feature-selection frequency across generations (frequency per feature from P stored candidates per generation)
- Heatmap of 30 features × G generations colored by selection frequency
- Unique chromosome ratio, average pairwise Hamming distance and/or entropy by generation
- Mean/min/median/best fitness curves and population fitness distribution
- Chromosome compare viewer showing selected/excluded/changed loci and Hamming distance
- Compare runs: differing generation counts, provenance, charts and feature overlap

## Rendering ethics

The provided screenshots are illustrative mockups with fictitious numeric values. The implementation must not hardcode those example values. Fitness scores are not medical classification metrics. Do not label a 0.91 fitness as '91% accuracy'. Test AUC/confusion matrix only if actual predictions/scores are present.

## Workspace paths

Direct filesystem integration, no API or sync:

`/agentic-space/analysis/experiments/<run_id>/candidate_history.jsonl` and adjacent manifest/history files.
