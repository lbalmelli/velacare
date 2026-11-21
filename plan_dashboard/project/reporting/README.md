# VelaCare Report Agent: deterministic PowerPoint generator

The OpenCode `velacare-report` agent uses the supplied `create-report-slide` skill and branded PPTX template. This Python helper provides a baseline, reproducible report built **only** from experiment files already present in the Agentic Space.

```bash
python -m pip install -r reporting/requirements.txt
python reporting/create_report.py \
  --run ./agentic-space/analysis/experiments/run_001 \
  --output ./agentic-space/presentations/velacare_research_findings.pptx
```

For deployment inside SecurSpaces, use `--run /agentic-space/analysis/experiments/run_001` and `--output /agentic-space/presentations/velacare_research_findings.pptx`.

The generator expects a complete run manifest and history CSV. It recognizes common field aliases for fitness and metrics; adapt the data loader to the genetic algorithm's *actual* schema if it differs. It deliberately displays `Not available` for missing metrics. It never invents results.

Template path: `brand/VelaCare_Research_Reporting_Template.pptx`.

To use the OpenCode reporting agent: select `velacare-report` or invoke `/velacare-report --run ./agentic-space/analysis/experiments/run_001` from within the project. The same Agentic Space filesystem is used by every application; repository-local paths are preferred for development. OpenCode may require explicit permission to read outside its project directory in deployment.

Not clinically validated. No patient-specific advice.

See `docs/OPENCODE_SETUP.md` for installing the OpenCode configuration and `docs/DASHBOARD_SETUP.md` for running the Data Explorer.
