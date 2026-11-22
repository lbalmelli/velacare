"""Dash application and synchronized controls for the VelaCare Data Explorer."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html
from flask import jsonify, make_response, request, send_file, send_from_directory

from .activation import (
    ActivationProvider,
    ActivationState,
    ActivationStatus,
    MockActivationProvider,
    activation_provider_for_mode,
)
from .data import WorkspaceData, load_workspace
from .views import render_view


VIEWS = [
    ("overview", "Overview", "01"),
    ("evolution", "Evolution", "02"),
    ("features", "Feature Selection", "03"),
    ("evaluation", "Model Evaluation", "04"),
    ("dataset", "Dataset", "05"),
    ("compare", "Compare Runs", "06"),
]


def _run_options(snapshot: WorkspaceData) -> list[dict[str, str]]:
    options = []
    for run_id in sorted(set(snapshot.runs) | set(snapshot.errors)):
        if run_id in snapshot.errors:
            label = f"{run_id} · history issue"
        else:
            run = snapshot.runs[run_id]
            label = f"{run_id} · {run.status.replace('_', ' ')} · {run.committed_generation} generations"
        options.append({"label": label, "value": run_id})
    return options


def _initial_controls(snapshot: WorkspaceData) -> tuple[str | None, int, str | None, str | None, str | None]:
    run_id = snapshot.latest_run_id
    run = snapshot.runs.get(run_id or "")
    generation = run.committed_generation if run and run.committed_generation else 1
    candidate_id = run.generations[generation].best_candidate["candidate_id"] if run and generation in run.generations else None
    run_ids = sorted(snapshot.runs)
    compare_a = run_ids[0] if run_ids else None
    compare_b = run_ids[1] if len(run_ids) > 1 else compare_a
    return run_id, generation, candidate_id, compare_a, compare_b


def _marks(maximum: int) -> dict[int, str]:
    points = {1, maximum}
    step = 10 if maximum > 20 else 5
    points.update(range(step, maximum + 1, step))
    return {point: str(point) for point in sorted(points)}


def _other_candidate(candidates: Any, selected_id: str | None) -> str | None:
    selected = next((item for item in candidates if item["candidate_id"] == selected_id), None)
    different = next((item for item in candidates if item["candidate_id"] != selected_id and selected and item["chromosome"] != selected["chromosome"]), None)
    fallback = next((item for item in candidates if item["candidate_id"] != selected_id), None)
    return (different or fallback or selected or {}).get("candidate_id")


def _startup_screen(base_path: str) -> html.Div:
    return html.Div([
        html.Div([
            html.Img(src=f"{base_path}pwa/icons/icon-192.png", alt="", className="startup-logo"),
            html.Div("VELACARE DATA EXPLORER", className="startup-brand"),
            html.H1("Connecting to VelaCare", id="startup-heading"),
            html.P("Checking dashboard and workspace availability…", id="startup-detail", className="startup-detail", role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
            html.P("", id="startup-simulated", className="startup-simulated", **{"aria-live": "polite"}),
            html.Div(className="startup-spinner", id="startup-spinner", **{"aria-hidden": "true"}),
            html.Div([
                html.Button("Retry", id="startup-retry", className="startup-button", type="button", hidden=True),
                html.Button("Simulate workspace start", id="startup-demo-start", className="startup-button secondary", type="button", hidden=True),
            ], className="startup-actions"),
        ], className="startup-card"),
    ], id="startup-screen", className="startup-screen", role="region", **{"aria-labelledby": "startup-heading", "data-state": "connecting"})


def _layout(snapshot: WorkspaceData, base_path: str = "/") -> html.Div:
    run_id, generation, candidate_id, compare_a, compare_b = _initial_controls(snapshot)
    run = snapshot.runs.get(run_id or "")
    max_generation = max(1, run.committed_generation if run else 1)
    candidate_options = []
    candidate_compare = None
    if run and generation in run.generations:
        candidate_options = [{"label": candidate["candidate_id"], "value": candidate["candidate_id"]}
                             for candidate in run.generations[generation].candidates]
        candidate_compare = _other_candidate(run.generations[generation].candidates, candidate_id)
    run_options = _run_options(snapshot)
    compare_options = [{"label": run_id, "value": run_id} for run_id in sorted(snapshot.runs)]
    refresh = bool(run and run.status == "running")
    return html.Div([
        _startup_screen(base_path),
        dcc.Store(id="active-view", data="overview"),
        dcc.Store(id="generation-click-store"),
        dcc.Store(id="candidate-click-store"),
        dcc.Interval(id="refresh-timer", interval=2000, n_intervals=0, disabled=not refresh),
        html.Aside([
            html.Div([html.Img(src="assets/velacare_icon.png", alt="VelaCare emblem", className="brand-icon"), html.Div([html.Strong("VELACARE"), html.Span("RESEARCH")], className="brand-wordmark")], className="sidebar-brand"),
            html.Div("WORKSPACE", className="nav-label"),
            html.Nav([html.Button([html.Span(number, className="nav-number"), html.Span(label)], id=f"nav-{key}", n_clicks=0, className="nav-item active" if key == "overview" else "nav-item", **{"aria-current": "page" if key == "overview" else "false"}) for key, label, number in VIEWS], className="sidebar-nav"),
            html.Div([html.Span("RESEARCH DEMONSTRATION"), html.P("Not clinically validated")], className="sidebar-footnote"),
        ], className="sidebar", role="navigation", **{"aria-label": "Research views"}),
        html.Main([
            html.Header([
                html.Div([html.Div([html.Div(html.Img(src="assets/velacare_logo.png", alt="VelaCare Research", className="brand-logo"), className="brand-logo-wrap"), html.Span("/"), html.Span("Data Explorer", className="breadcrumb-current")], className="breadcrumbs"),
                          html.Div([html.Span("LOCAL WORKSPACE", className="sync-dot"), html.Span(id="workspace-status", children="Loading saved artifacts…")], className="workspace-status")], className="topbar"),
                html.Div([
                    html.Div([html.Label("Active experiment", htmlFor="run-selector"), dcc.Dropdown(id="run-selector", options=run_options, value=run_id, clearable=False, searchable=True, placeholder="Choose a saved run")], className="control-field run-field"),
                    html.Div([html.Label("Selected generation", htmlFor="generation-number"), html.Div([dcc.Input(id="generation-number", type="number", min=1, max=max_generation, step=1, value=generation, inputMode="numeric"), html.Span(f"of {max_generation}", id="generation-count", className="generation-count")], className="generation-input-row")], className="control-field generation-number-field"),
                    html.Div([html.Label("Candidate in generation", htmlFor="candidate-selector"), dcc.Dropdown(id="candidate-selector", options=candidate_options, value=candidate_id, clearable=False, searchable=True, placeholder="Select a candidate")], className="control-field candidate-field"),
                ], className="control-strip"),
                html.Div([html.Div([html.Label("Explore generation", htmlFor="generation-slider", className="slider-label"), html.Span(f"{generation} / {max_generation}", id="slider-count", className="slider-count")], className="slider-heading"),
                          dcc.Slider(id="generation-slider", min=1, max=max_generation, step=1, value=generation, marks=_marks(max_generation), updatemode="mouseup", tooltip={"placement": "bottom", "always_visible": False})], className="generation-slider-wrap"),
        html.Details([html.Summary("Comparison setup"),
                      html.Div([html.Div([html.Label("Compare candidate", htmlFor="candidate-compare"), dcc.Dropdown(id="candidate-compare", options=candidate_options, value=candidate_compare, clearable=False, searchable=True)], className="control-field")], className="candidate-compare-control"),
                              html.Div([html.Div([html.Label("Run A", htmlFor="compare-a"), dcc.Dropdown(id="compare-a", options=compare_options, value=compare_a, clearable=False, searchable=True)], className="control-field"),
                                        html.Div([html.Label("Run B", htmlFor="compare-b"), dcc.Dropdown(id="compare-b", options=compare_options, value=compare_b, clearable=False, searchable=True)], className="control-field")], className="compare-controls")], className="compare-settings"),
            ], className="app-header"),
            html.Div([html.Div([html.Div([html.Span("Research workspace", className="eyebrow"), html.H1(id="view-title", children="Overview")], className="page-heading"), html.P("Fitness is a composite optimization score. It is not clinical sensitivity, accuracy, or diagnostic confidence.", className="page-context")], className="page-intro"),
                      html.Div(id="view-content", className="view-content")], className="page-shell"),
            html.Footer([html.Span("Research demonstration • Not clinically validated"), html.Span("Source: saved Agentic Space files · no model reruns")], className="app-footer"),
        ], className="main-shell", role="main"),
    ], className="app-root")


def create_app(
    workspace: Path | str,
    *,
    base_path: str = "/",
    initial_snapshot: WorkspaceData | None = None,
    activation_provider: ActivationProvider | None = None,
    activation_mode: str = "disabled",
) -> Dash:
    root = Path(workspace).expanduser().resolve()
    base_path = "/" + base_path.strip("/") + "/" if base_path.strip("/") else "/"
    route_prefix = base_path.rstrip("/")
    pwa_dir = Path(__file__).parent / "pwa"
    provider = activation_provider or activation_provider_for_mode(activation_mode)
    readiness: dict[str, Any] = {"initialized": False, "initialization_error": False}
    try:
        snapshot = initial_snapshot if initial_snapshot is not None else load_workspace(root)
        readiness["initialized"] = True
        readiness["dataset_status"] = "available" if snapshot.dataset is not None else "missing"
        readiness["experiments_status"] = "available" if snapshot.runs or snapshot.errors else "empty"
    except Exception:
        snapshot = WorkspaceData(root, {}, {}, None, None, "Dashboard initialization failed.")
        readiness["initialization_error"] = True

    app = Dash(
        __name__,
        title="VelaCare Data Explorer",
        assets_folder=str(Path(__file__).parent / "assets"),
        requests_pathname_prefix=base_path,
        routes_pathname_prefix=base_path,
        suppress_callback_exceptions=True,
        update_title=None,
    )
    app.layout = _layout(snapshot, base_path)
    app.server.extensions["velacare_readiness"] = readiness
    app.server.extensions["velacare_activation_provider"] = provider
    app.index_string = f"""<!DOCTYPE html>
<html lang="en">
<head>
    {{%metas%}}
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#0b1422">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="VelaCare">
    <meta name="velacare-base-path" content="{base_path}">
    <link rel="manifest" href="{base_path}manifest.webmanifest">
    <link rel="icon" type="image/png" sizes="192x192" href="{base_path}pwa/icons/icon-192.png">
    <link rel="apple-touch-icon" href="{base_path}pwa/icons/icon-192.png">
    <link rel="stylesheet" href="{base_path}pwa/startup.v1.css">
    <title>{{%title%}}</title>
    {{%favicon%}}
    {{%css%}}
</head>
<body>
    {{%app_entry%}}
    <footer>
        {{%config%}}
        {{%scripts%}}
        {{%renderer%}}
    </footer>
    <script defer src="{base_path}pwa/startup.v1.js"></script>
</body>
</html>"""

    @app.server.get(f"{route_prefix}/health/live")
    def health_live():
        return jsonify({"service": "velacare-dashboard", "status": "live"}), 200

    @app.server.get(f"{route_prefix}/health/ready")
    def health_ready():
        if not readiness["initialized"]:
            dashboard_state = "initializing"
        elif readiness["initialization_error"]:
            dashboard_state = "unavailable"
        else:
            dashboard_state = "ready"

        accessible = root.is_dir() and os.access(root, os.R_OK | os.X_OK)
        for directory in (root / "data", root / "analysis", root / "analysis" / "experiments"):
            if directory.exists() and (not directory.is_dir() or not os.access(directory, os.R_OK | os.X_OK)):
                accessible = False
        if not accessible and dashboard_state == "ready":
            dashboard_state = "unavailable"
        http_status = 200 if dashboard_state == "ready" else 503

        try:
            activation = provider.get_status({}).as_dict()
        except Exception:
            activation = ActivationStatus(
                ActivationState.ERROR,
                "Workspace status provider failed.",
            ).as_dict()
        payload = {
            "service": "velacare-dashboard",
            "status": dashboard_state,
            "dashboard": {"status": dashboard_state},
            "local_workspace": {
                "status": "available" if accessible else "unavailable",
                "experiments": readiness.get("experiments_status", "unknown"),
                "dataset": readiness.get("dataset_status", "unknown"),
            },
            "activation": activation,
        }
        return jsonify(payload), http_status

    @app.server.get(f"{route_prefix}/manifest.webmanifest")
    def pwa_manifest():
        response = make_response(send_file(pwa_dir / "manifest.webmanifest", mimetype="application/manifest+json"))
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.server.get(f"{route_prefix}/service-worker.js")
    def pwa_service_worker():
        response = make_response(send_file(pwa_dir / "service-worker.js", mimetype="application/javascript"))
        response.headers["Service-Worker-Allowed"] = base_path
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.server.get(f"{route_prefix}/offline-shell.html")
    def pwa_offline_shell():
        shell = (pwa_dir / "offline-shell.html").read_text(encoding="utf-8")
        response = make_response(shell.replace("__VELACARE_BASE_PATH__", base_path))
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.server.get(f"{route_prefix}/pwa/<path:filename>")
    def pwa_public_asset(filename: str):
        response = make_response(send_from_directory(pwa_dir, filename, conditional=True))
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.server.post(f"{route_prefix}/activation/start")
    def mock_activation_start():
        if not isinstance(provider, MockActivationProvider):
            return jsonify({"accepted": False, "status": "unavailable", "detail": "Activation demo is disabled."}), 404
        key = request.headers.get("Idempotency-Key", "")
        if not key or len(key) > 128:
            return jsonify({"accepted": False, "status": "error", "detail": "A valid idempotency key is required."}), 400
        result = provider.request_start({}, key)
        return jsonify(result.as_dict()), 202 if result.accepted else 409

    @app.callback(Output("generation-click-store", "data"), Input({"type": "history-heatmap", "index": ALL}, "clickData"), prevent_initial_call=True)
    def capture_history_click(click_events: list[dict[str, Any] | None]) -> dict[str, int] | None:
        click_data = next((item for item in click_events if item and item.get("points")), None)
        if not click_data:
            return None
        point = click_data["points"][0]
        custom = point.get("customdata")
        return {"generation": int(custom[0] if custom else point["y"])}

    @app.callback(
        Output("candidate-click-store", "data"),
        Input({"type": "population-heatmap", "index": ALL}, "clickData"),
        Input({"type": "candidate-table", "index": ALL}, "selected_row_ids"),
        prevent_initial_call=True,
    )
    def capture_candidate_click(click_events: list[dict[str, Any] | None], selected_rows: list[list[str] | None]) -> dict[str, str] | None:
        triggered = ctx.triggered_id
        if isinstance(triggered, dict) and triggered.get("type") == "population-heatmap":
            click_data = next((item for item in click_events if item and item.get("points")), None)
        else:
            click_data = None
        if click_data and click_data.get("points"):
            custom = click_data["points"][0].get("customdata")
            if custom:
                return {"candidate_id": str(custom[0])}
        if isinstance(triggered, dict) and triggered.get("type") == "candidate-table":
            selected_row_ids = next((rows for rows in selected_rows if rows), None)
            if selected_row_ids:
                return {"candidate_id": str(selected_row_ids[0])}
        return None

    output_ids: list[Output] = [
        Output("view-title", "children"), Output("view-content", "children"), Output("active-view", "data"),
        Output("generation-slider", "max"), Output("generation-slider", "value"), Output("generation-slider", "marks"),
        Output("generation-number", "max"), Output("generation-number", "value"), Output("generation-count", "children"),
        Output("slider-count", "children"), Output("candidate-selector", "options"), Output("candidate-selector", "value"),
        Output("candidate-compare", "options"), Output("candidate-compare", "value"),
        Output("run-selector", "options"), Output("run-selector", "value"), Output("compare-a", "options"),
        Output("compare-a", "value"), Output("compare-b", "options"), Output("compare-b", "value"),
        Output("refresh-timer", "disabled"), Output("workspace-status", "children"),
    ] + [Output(f"nav-{key}", "className") for key, _label, _number in VIEWS]
    inputs: list[Input] = [
        Input("run-selector", "value"), Input("generation-slider", "value"), Input("generation-number", "value"),
        Input("candidate-selector", "value"), Input("candidate-compare", "value"), Input("compare-a", "value"), Input("compare-b", "value"),
        Input("refresh-timer", "n_intervals"), Input("active-view", "data"),
    ] + [Input(f"nav-{key}", "n_clicks") for key, _label, _number in VIEWS] + [
        Input("generation-click-store", "data"), Input("candidate-click-store", "data"),
    ]

    @app.callback(output_ids, inputs)
    def update_dashboard(*args: Any) -> tuple[Any, ...]:
        selected_run, slider_generation, number_generation, selected_candidate, compare_candidate, compare_a, compare_b, _ticks, active_view = args[:9]
        generation_click, candidate_click = args[15:17]
        triggered = ctx.triggered_id
        view = active_view or "overview"
        nav_ids = {f"nav-{key}": key for key, _label, _number in VIEWS}
        if triggered in nav_ids:
            view = nav_ids[triggered]

        snapshot = load_workspace(root)
        run_options = _run_options(snapshot)
        available_ids = [option["value"] for option in run_options]
        if selected_run not in available_ids:
            selected_run = snapshot.latest_run_id if snapshot.latest_run_id in available_ids else (available_ids[-1] if available_ids else None)
        run = snapshot.runs.get(selected_run or "")

        compare_options = [{"label": run_id, "value": run_id} for run_id in sorted(snapshot.runs)]
        compare_ids = [option["value"] for option in compare_options]
        default_compare_a = compare_ids[0] if compare_ids else None
        default_compare_b = compare_ids[1] if len(compare_ids) > 1 else default_compare_a
        if compare_a not in compare_ids:
            compare_a = default_compare_a
        if compare_b not in compare_ids:
            compare_b = default_compare_b

        maximum = max(1, run.committed_generation if run else 1)
        generation = maximum if number_generation is None else int(number_generation)
        if triggered == "generation-slider" and slider_generation is not None:
            generation = int(slider_generation)
        elif triggered == "generation-number" and number_generation is not None:
            generation = int(number_generation)
        elif triggered == "generation-click-store" and generation_click:
            generation = int(generation_click["generation"])
        elif triggered == "candidate-click-store" and candidate_click:
            selected_candidate = candidate_click["candidate_id"]
        generation = min(max(1, generation), maximum)

        candidates = run.generations[generation].candidates if run and generation in run.generations else ()
        candidate_ids = [candidate["candidate_id"] for candidate in candidates]
        candidate_options = [{"label": candidate_id, "value": candidate_id} for candidate_id in candidate_ids]
        if selected_candidate not in candidate_ids:
            selected_candidate = run.generations[generation].best_candidate["candidate_id"] if run and generation in run.generations else None
        if compare_candidate not in candidate_ids or compare_candidate == selected_candidate:
            compare_candidate = _other_candidate(candidates, selected_candidate)

        title, content = render_view(view, snapshot, selected_run, generation, selected_candidate, compare_candidate, compare_a, compare_b)
        refresh_disabled = not bool(run and run.status == "running")
        if run:
            workspace_status = f"{run.run_id} · {run.status.replace('_', ' ').upper()} · {run.committed_generation} complete generations"
        elif selected_run in snapshot.errors:
            workspace_status = f"{selected_run} · HISTORY ISSUE"
        else:
            workspace_status = "NO SAVED RUNS"
        nav_classes = ["nav-item active" if view == key else "nav-item" for key, _label, _number in VIEWS]
        return (
            title, content, view, maximum, generation, _marks(maximum), maximum, generation, f"of {maximum}", f"{generation} / {maximum}",
            candidate_options, selected_candidate, candidate_options, compare_candidate, run_options, selected_run, compare_options, compare_a, compare_options, compare_b,
            refresh_disabled, workspace_status, *nav_classes,
        )

    return app
