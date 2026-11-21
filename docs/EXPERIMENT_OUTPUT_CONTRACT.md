# Genetic algorithm files consumed by Data Explorer and Report Agent

The exact schema must be audited against the implemented genetic algorithm and, where needed, adapted in the dashboard loader. These paths are the agreed expected contract from `VelaCare_Codex_Goal_Package.zip`:

- `agentic-space/analysis/experiments/latest.json`: latest run identifier/pointer.
- `run_NNN/run_manifest.json`: schema_version, status, last_completed_generation, parameters, seed, dataset identity/checksum, feature order, classifier/CV configuration, versions.
- `run_NNN/generation_history.csv`: one complete generation record per generation, best/mean/min/median fitness, feature count, diversity, timing, best candidate ID.
- `run_NNN/candidate_history.jsonl`: **one record per evaluated candidate in every generation**, 30-bit chromosome, selected names, candidate ID, fitness, component metrics and genetic ancestry. G×P snapshots expected when P candidates evaluated each generation.
- `run_NNN/best_candidates.json`: best candidate mask at every generation.
- `run_NNN/model_metrics.json`: final CV and **separate** held-out test evaluation, with diagnostic label mapping.

Never lose full population rows by sampling or skipping generations. Use last_completed_generation plus verified records to avoid partial data being mistaken for committed state. If schema differs, document adapter decisions in this file and test with actual files.

The Data Explorer and Report Agent **read these files directly in the same workspace**. No export/transfer/synchronization, or extra service is required.

Local workspace root: `~/velacare/agentic-space`; SecurSpaces deployment root: `/agentic-space`. Source schemas must be checked against the current working GA code before assuming the expected contract matches.

## Observed GA schema and dashboard adapter

The current writer in `src/velacare/persistence.py` and the saved `run_001`–`run_007` artifacts use `last_fully_committed_generation` as the manifest visibility field. The dashboard requires that exact field and does not fall back to the contract draft's `last_completed_generation` alias. It reads `generation_history.csv` and `candidate_history.jsonl`, validates one candidate per configured population slot for every generation through the commit boundary, recomputes fitness summaries and diversity from chromosomes, and rejects inconsistencies. Records after the boundary are ignored as uncommitted. A malformed, unterminated JSONL tail is reported as a warning only when all committed populations are complete.

The GA writes `model_metrics.json` with `cv_metrics` and `held_out_test_metrics`. The dashboard uses these separately and renders ROC/AUC as “not available in run artifact” because saved artifacts contain no ROC scores or thresholds. Per-generation completion timestamps are not written; the UI shows “not available in run artifact” and may show the saved generation duration.

The canonical feature order is the 30 display names in `src/velacare/dataset.py::FEATURE_NAMES`, matching the normalized CSV header after `diagnosis`. The dashboard verifies the manifest order and the local dataset metadata checksum. No schema changes to the GA writer were needed.
