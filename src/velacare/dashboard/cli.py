"""Command-line entry point for the VelaCare Data Explorer."""

from __future__ import annotations

import argparse
from pathlib import Path

from .app import create_app
from .data import DashboardDataError, load_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Explore VelaCare genetic-algorithm run files without rerunning models.")
    parser.add_argument("--workspace", type=Path, default=Path("./agentic-space"), help="shared workspace root (default: ./agentic-space)")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8050, help="port to bind (default: 8050)")
    parser.add_argument("--base-path", default="/", help="URL base path for ingress, such as /research/")
    parser.add_argument("--debug", action="store_true", help="enable Dash debug mode")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.workspace.expanduser().resolve()
    try:
        snapshot = load_workspace(root)
    except DashboardDataError as exc:
        print(f"Dashboard startup validation failed: {exc}")
        return 2
    print(f"VelaCare Data Explorer workspace: {root}")
    print(f"Discovered {len(snapshot.runs)} readable run(s); {len(snapshot.errors)} run(s) with history issues.")
    if not snapshot.runs:
        print("No readable experiment runs yet. Use ./run-demo --workspace <workspace> to create one.")
    if snapshot.dataset_error:
        print(f"Local dataset unavailable: {snapshot.dataset_error}")
    base = args.base_path
    if not base.startswith("/"):
        base = "/" + base
    if not base.endswith("/"):
        base += "/"
    app = create_app(root, base_path=base)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0
