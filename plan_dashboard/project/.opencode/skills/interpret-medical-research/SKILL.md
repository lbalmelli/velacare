---
name: interpret-medical-research
description: Evaluate the scientific validity and limitations of VelaCare Wisconsin Breast Cancer feature-selection experiments; distinguish optimization fitness from diagnostic performance and produce conservative, reproducible research interpretations for reports, dashboards and presentations.
---

# Review medical machine-learning evidence

This skill applies to the public Wisconsin Breast Cancer (Diagnostic) dataset (UCI dataset 17; 569 records, 30 features) and the educational genetic feature-selection demonstration. It does not provide clinical advice.

## Evidence discipline

1. Read `run_manifest.json` for dataset provenance, feature order, label mapping, population, generations, fitness weights, CV scheme, seed, train/test split and status.
2. Read results from saved records only; ensure the run is complete or clearly identify its last committed generation.
3. Treat fitness as a **dimensionless composite objective**, not accuracy, AUC, malignant sensitivity or probability of cancer. State the exact fitness formula if available; otherwise label as 'fitness (definition not documented)'.
4. Verify which diagnostic class is considered positive (typically malignant), and whether metrics are measured by CV or on the independent held-out set. Do not mix metrics from different evaluation sets.
5. Cross-validation performance is model selection evidence; held-out performance is a one-time external-to-search estimate (not true external clinical validation). Do not reuse test scores to select GA candidates.
6. Compare 40- and 80-generation runs only if dataset, preprocessing, evaluation, fitness definition, model and seeds/validation procedures support a fair comparison. If different seeds, include stochastic variability as a caveat.
7. Feature frequency and mutations describe selection *of measured inputs*, not mutations in cells or tumor biology. Avoid causal claims, discovery claims or mechanistic interpretations from simple feature-selection patterns.
8. For missing data, label 'not available in persisted run artifacts'; never fill gaps with illustrative screenshot values, invented p-values, confidence intervals, citations, patients or performance claims.
9. Always include a limitations section: small public historical dataset, feature-selection optimism if validation is insufficient, sample composition and data provenance, possible distribution shift, lack of prospective/external validation, no patient-level decisions.
10. Quote reproducibility metadata: run ID, seed, dataset version/checksum, algorithm/classifier versions, GA population/generations and date whenever present.

## Reporting format

Use headings `Research question`, `Dataset and methods`, `Observed results`, `Evaluation`, `Limitations`, `Reproducibility`. Use plain English with precise metric names. Every chart labels axes and evaluation population. End with: **Research demonstration only. Not clinically validated.**

## Reference source

UCI Machine Learning Repository: https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic
