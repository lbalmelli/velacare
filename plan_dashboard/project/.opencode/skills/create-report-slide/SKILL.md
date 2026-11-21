---
name: create-report-slide
description: Create or revise VelaCare-branded PowerPoint research reports or individual slides using saved Agentic Space experiment artifacts, company logo, and reporting template. Trigger for slide, PPTX, executive research summary, publication-style methods and findings presentations.
---

# Create a branded research presentation

1. Resolve the workspace root: requested `--workspace`, else `./agentic-space` for local development, else `/agentic-space` in deployment.
2. Read `brand/BRAND_GUIDELINES.md`; use `brand/velacare_logo.png` and `brand/VelaCare_Research_Reporting_Template.pptx`. If runtime brand folder is not provisioned, use the *repository's* `brand/` assets while reading original experiment files from their workspace path.
3. Read the exact selected run's `run_manifest.json`, `generation_history.csv`, `candidate_history.jsonl`, `best_candidates.json`, and `model_metrics.json`. Maintain source run ID and schema version.
4. Use `interpret-medical-research` to review source integrity, metric definitions, limitations and labeling BEFORE drafting any conclusion.
5. Build a 16:9 PowerPoint using the actual branded template. Use `reporting/create_report.py --run <run_dir> --output <pptx>` as a baseline generator if available, and enhance only using real source data. If modifying template placeholders, retain theme, VelaCare logo, footer, standard fonts, and accent colors. Avoid unreadable tiny text or screenshots of entire slides.
6. Minimum report progression: title + provenance; executive summary; methodology and split strategy; fitness evolution with generation chart; feature selection and frequency; model evaluation separating CV from held-out; clinical/research limitations and reproducibility details. Add caveats when artifacts do not support a visualization.
7. Generated charts always show axes, units, legends, experiment ID, and whether values are fitness scores or genuine classification metrics. Don't present screenshots of the **illustrative** demo figures as real evidence.
8. Save under `WORKSPACE/presentations/`, not into repo source or experiment directory; never rewrite experiment files. Render/check visual output and include source run in speaker notes or footer.
9. When only a single slide is requested, use the branded template's layout while retaining source attribution and limitations.

**Scientific guardrails:** Do not claim diagnostic performance, clinical validity, or actionable medical guidance without properly qualified real evidence. Use labels `research demonstration`, `not clinically validated`, and `not available` as needed.
