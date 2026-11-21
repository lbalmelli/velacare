#!/usr/bin/env bash
# Install only VelaCare OpenCode agent/skills/command, brand, and report support.
# Never touches Git branches, existing GA files, or user-edited config files.
# Usage: bash plan_dashboard/scripts/install-opencode.sh [~/velacare]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
(( $# <= 1 )) || { echo "Usage: $0 [repo-root]" >&2; exit 2; }
resolve_repo_root "${1:-$(cd "$STAGE_DIR/.." && pwd -P)}"
INSTALLED=0; CONFLICTS=0
for rel in \
  AGENTS.md \
  opencode.jsonc \
  .opencode/agents/velacare-report.md \
  .opencode/commands/velacare-report.md \
  .opencode/skills/create-report-slide/SKILL.md \
  .opencode/skills/interpret-medical-research/SKILL.md \
  brand/velacare_logo.png \
  brand/velacare_icon.png \
  brand/BRAND_GUIDELINES.md \
  brand/VelaCare_Research_Reporting_Template.pptx \
  reporting/README.md \
  reporting/create_report.py \
  reporting/requirements.txt; do
  copy_if_safe "$rel"
done
print_summary
printf '\nOpenCode project assets installed. See: %s/docs/OPENCODE_SETUP.md\n' "$REPO_ROOT"
echo 'The report helper requires existing Python deps; see docs/OPENCODE_SETUP.md.'
