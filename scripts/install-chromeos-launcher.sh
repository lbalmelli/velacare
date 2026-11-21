#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/install-chromeos-launcher.sh [--uninstall]

Install or remove the user-scoped VelaCare Data Explorer Linux app shortcut.
No root privileges are required.
USAGE
}

script_path="$(readlink -f -- "${BASH_SOURCE[0]}")"
repo_root="$(cd -- "$(dirname -- "$script_path")/.." && pwd -P)"
data_home="${XDG_DATA_HOME:-${HOME:?HOME must be set}/.local/share}"
applications_dir="$data_home/applications"
icons_dir="$data_home/icons/hicolor/512x512/apps"
desktop_file="$applications_dir/velacare-data-explorer.desktop"
icon_file="$icons_dir/velacare-data-explorer.png"

refresh_desktop_cache() {
  if command -v update-desktop-database >/dev/null 2>&1 && [[ -d "$applications_dir" ]]; then
    update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1 && [[ -d "$data_home/icons/hicolor" ]]; then
    gtk-update-icon-cache -f -t "$data_home/icons/hicolor" >/dev/null 2>&1 || true
  fi
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -f -- "$desktop_file" "$icon_file"
  refresh_desktop_cache
  printf 'Removed the VelaCare launcher and icon installed by this script.\n'
  exit 0
fi

if [[ $# -ne 0 ]]; then
  usage >&2
  exit 2
fi

if [[ ! -x "$repo_root/run-dashboard" ]]; then
  printf 'VelaCare launcher: missing executable %s/run-dashboard\n' "$repo_root" >&2
  exit 1
fi
if [[ ! -s "$repo_root/brand/velacare_icon.png" ]]; then
  printf 'VelaCare launcher: missing brand icon at %s/brand/velacare_icon.png\n' "$repo_root" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  printf 'VelaCare launcher: uv is required. Install uv, then rerun this script.\n' >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf 'VelaCare launcher: Python 3 is required.\n' >&2
  exit 1
fi

exec_arg="$(python3 - "$repo_root/scripts/launch-chromeos-dashboard.sh" <<'PY'
import sys
value = sys.argv[1]
if "\n" in value or "\r" in value:
    raise SystemExit("Repository paths containing line breaks are not supported.")
value = value.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
print(f'"{value}"')
PY
)"
icon_value="$(python3 - "$icon_file" <<'PY'
import sys
value = sys.argv[1]
if "\n" in value or "\r" in value:
    raise SystemExit("Icon paths containing line breaks are not supported.")
value = value.replace("\\", "\\\\").replace(" ", "\\s").replace("\t", "\\t")
print(value)
PY
)"

install -d -m 0755 "$applications_dir" "$icons_dir"
install -m 0644 "$repo_root/brand/velacare_icon.png" "$icon_file"
desktop_tmp="$(mktemp "$applications_dir/.velacare-data-explorer.XXXXXX")"
trap 'rm -f -- "${desktop_tmp:-}"' EXIT
cat > "$desktop_tmp" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=VelaCare Data Explorer
Comment=Explore saved VelaCare research runs
Exec=$exec_arg
Icon=$icon_value
Terminal=false
StartupNotify=true
Categories=Education;Science;Development;
EOF
chmod 0644 "$desktop_tmp"
mv -f -- "$desktop_tmp" "$desktop_file"
trap - EXIT
refresh_desktop_cache

printf 'Installed VelaCare Data Explorer in %s\n' "$desktop_file"
printf 'Find it in ChromeOS Launcher > Linux apps.\n'
