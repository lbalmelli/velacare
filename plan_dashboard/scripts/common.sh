#!/usr/bin/env bash
# Shared installer routines. Scripts make no Git branch or worktree changes.
set -euo pipefail

STAGE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
BUNDLE_PROJECT="$STAGE_DIR/project"

resolve_repo_root() {
  local root
  if [[ $# -eq 1 ]]; then
    root=$(cd "$1" && pwd -P)
  else
    root=$(cd "$STAGE_DIR/.." && pwd -P)
  fi
  [[ -d "$root/.git" || -f "$root/.git" ]] || { echo "ERROR: Not a Git checkout: $root" >&2; exit 1; }
  local toplevel
  toplevel=$(git -C "$root" rev-parse --show-toplevel)
  [[ "$root" == "$toplevel" ]] || { echo "ERROR: Expected the repository root ($toplevel), got $root" >&2; exit 1; }
  [[ -d "$root/src/velacare" && -f "$root/pyproject.toml" && -f "$root/run-demo" ]] || {
    echo "ERROR: Expected the existing velacare Python project in $root (src/velacare, pyproject.toml, run-demo)" >&2
    exit 1
  }
  REPO_ROOT="$root"
  INCOMING="$STAGE_DIR/incoming"
  [[ -d "$BUNDLE_PROJECT" ]] || { echo "ERROR: Missing bundle project directory: $BUNDLE_PROJECT" >&2; exit 1; }
  echo "Repository root: $REPO_ROOT"
}

# Keep original user files and place divergent files under plan_dashboard/incoming.
copy_if_safe() {
  local rel="$1"
  local source="$BUNDLE_PROJECT/$rel" destination="$REPO_ROOT/$rel" incoming="$INCOMING/$rel"
  [[ -f "$source" ]] || { echo "ERROR: Package missing file: $rel" >&2; exit 1; }
  if [[ -f "$destination" ]]; then
    if cmp -s "$source" "$destination"; then
      printf '[same] %s\n' "$rel"
    else
      mkdir -p "$(dirname "$incoming")"
      cp -f "$source" "$incoming"
      printf '[conflict, preserved] %s (incoming copy: %s)\n' "$rel" "${incoming#"$REPO_ROOT"/}"
      CONFLICTS=$((CONFLICTS+1))
    fi
  elif [[ -e "$destination" ]]; then
    echo "ERROR: $destination exists but is not a regular file; left unchanged" >&2
    CONFLICTS=$((CONFLICTS+1))
  else
    mkdir -p "$(dirname "$destination")"
    cp "$source" "$destination"
    printf '[installed] %s\n' "$rel"
    INSTALLED=$((INSTALLED+1))
  fi
}

print_summary() {
  printf '\nNew files: %d; conflicting files preserved: %d\n' "$INSTALLED" "$CONFLICTS"
  if (( CONFLICTS > 0 )); then
    echo 'Review plan_dashboard/incoming/ and merge intentional changes manually.'
  fi
}
