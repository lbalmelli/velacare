# Source this file from ~/.bash_aliases to enable: run <generations>
_VELACARE_RUN_DEMO_REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"

run() {
    if (( $# != 1 )) || [[ ! "$1" =~ ^[1-9][0-9]*$ ]]; then
        printf 'Usage: run <positive-generation-count>\n' >&2
        return 2
    fi

    local repo_root="${VELACARE_REPO:-$_VELACARE_RUN_DEMO_REPO_ROOT}"
    if [[ ! -x "$repo_root/run-demo" ]]; then
        printf 'run: cannot find executable %s/run-demo; set VELACARE_REPO to the repository path.\n' "$repo_root" >&2
        return 127
    fi

    "$repo_root/run-demo" --generations "$1" --population 60 --seed 42
}
