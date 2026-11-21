#!/usr/bin/env bash
# Install dashboard plan and repository docs in the EXISTING Git checkout.
# Usage: bash plan_dashboard/scripts/install-dashboard.sh [~/velacare]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
(( $# <= 1 )) || { echo "Usage: $0 [repo-root]" >&2; exit 2; }
resolve_repo_root "${1:-$(cd "$STAGE_DIR/.." && pwd -P)}"
INSTALLED=0; CONFLICTS=0
for rel in \
  CODEX_DASHBOARD_GOAL.md \
  assets/data-explorer-reference.png \
  assets/feature-evolution-reference.png \
  docs/DASHBOARD_SETUP.md \
  docs/OPENCODE_SETUP.md \
  docs/EXPERIMENT_OUTPUT_CONTRACT.md \
  docs/DASHBOARD_UX_SPEC.md; do
  copy_if_safe "$rel"
done

# Preserve every original README section; install or update our marked section only.
python3 - "$REPO_ROOT/README.md" "$STAGE_DIR/README_SECTION.md" <<'PY'
from pathlib import Path
import sys
readme,section=map(Path,sys.argv[1:])
if not readme.exists():
    raise SystemExit('ERROR: existing README.md not found. No changes made to README.')
original=readme.read_text(encoding='utf-8')
new_section=section.read_text(encoding='utf-8').strip('\n')
start='<!-- VELACARE_DASHBOARD_DOCS_START -->'
end='<!-- VELACARE_DASHBOARD_DOCS_END -->'
a,b=original.find(start),original.find(end)
if a>=0 and b>=0 and b>a:
    modified=original[:a]+new_section+original[b+len(end):]
elif a<0 and b<0:
    modified=original.rstrip()+'\n\n'+new_section+'\n'
else:
    raise SystemExit('ERROR: README contains only one VelaCare marker; manual resolution needed.')
if modified!=original:
    readme.write_text(modified,encoding='utf-8')
    print('[updated section] README.md (original content preserved)')
else:
    print('[same] README.md')
PY
print_summary
printf '\nDashboard goal is ready: %s/CODEX_DASHBOARD_GOAL.md\n' "$REPO_ROOT"
echo 'No new branch or worktree was created. Implement the dashboard using Codex in this checkout.'
