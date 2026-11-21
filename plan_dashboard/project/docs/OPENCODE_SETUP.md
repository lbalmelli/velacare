# OpenCode Report Agent Setup

This document explains how to install and run the **VelaCare Research Report Agent** in the existing `~/velacare` checkout. The reporter reads the genetic-algorithm results from the **same shared filesystem** as Data Explorer and creates a VelaCare-branded `.pptx` presentation. No data export, sync or transfer is necessary.

## 1. Install project files

Unpack the new bundle into **`~/velacare/plan_dashboard/`**, preserving its `project/` and `scripts/` directories. From the existing Git repository root:

```bash
cd ~/velacare
bash plan_dashboard/scripts/install-dashboard.sh
bash plan_dashboard/scripts/install-opencode.sh
```

The OpenCode installer copies `AGENTS.md` (if missing), `opencode.jsonc` (if missing), `.opencode/agents`, `.opencode/skills`, `.opencode/commands`, `brand/` and `reporting/` to the repository root. Existing conflicting files are **not overwritten**: incoming copies are placed under `plan_dashboard/incoming/` for review. Re-running the scripts is safe.

The installer does not install OpenCode itself or change Git branches. The `brand/` template and logo are checked into the source tree; the report reads runtime experimental files directly from `./agentic-space` (local) or `/agentic-space` (deployment). If the operational SecurSpaces template needs brand assets at `/agentic-space/brand/`, provision them there **once** as part of that template, not between agents.

## 2. Check discovery

Verify the following exist in the repository root:

```text
AGENTS.md
opencode.jsonc
.opencode/agents/velacare-report.md
.opencode/commands/velacare-report.md
.opencode/skills/create-report-slide/SKILL.md
.opencode/skills/interpret-medical-research/SKILL.md
brand/velacare_logo.png
brand/VelaCare_Research_Reporting_Template.pptx
reporting/create_report.py
```

OpenCode's project agent/skills are discovered under `.opencode/`, while `AGENTS.md` provides repository instructions. The command is named `/velacare-report`. These conventions follow https://opencode.ai/docs/agents , https://opencode.ai/docs/skills and https://opencode.ai/docs/commands .

## 3. Install report helper dependencies

For the Python report helper, use the repository's existing environment and dependency conventions. For a local smoke test, the exact helper dependencies are listed in `reporting/requirements.txt`; prefer adding them to the existing project extras rather than creating another Python project.

## 4. Launch the reporting assistant

```bash
cd ~/velacare
opencode
```

Select the `velacare-report` agent or run its command in the TUI:

```text
/velacare-report ./agentic-space/analysis/experiments/run_001
```

The agent must first load `interpret-medical-research` and `create-report-slide`, verify the run directory and source metric definitions, then render a branded PowerPoint. A direct deterministic baseline is also available:

```bash
python reporting/create_report.py \
  --run ./agentic-space/analysis/experiments/run_001 \
  --output ./agentic-space/presentations/velacare_research_findings.pptx
```

Change `run_001` to an actual completed run discovered in your local `agentic-space/analysis/experiments/`. The report template is loaded from the repository `brand/` directory automatically.

## 5. Scientific safeguards

- No invented experimental values, statistics, patient stories or clinical claims.
- Genetic-algorithm **fitness != diagnostic accuracy**; show performance metrics only if present and qualified.
- Label cross-validation versus held-out test clearly.
- Selection/mutation of feature masks is not mutation in biological tissue.
- All presentations carry 'Research demonstration - Not clinically validated'.
- Only write reports to the selected workspace's `presentations/` subdirectory; keep source runs immutable.

## 6. Troubleshooting

If OpenCode doesn't show the agent/skill, verify project root (`~/velacare`), the hidden `.opencode/` paths, and config conflicts in `plan_dashboard/incoming/`. If the generated helper reports a missing field, adapt it to the *actual* run output; never invent data. Run the Python helper directly first to separate environment problems from agent configuration.

See also [Dashboard Setup](DASHBOARD_SETUP.md).
