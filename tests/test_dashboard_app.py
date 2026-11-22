import json
import struct

import pytest


def test_dashboard_serves_layout_dependencies_and_brand_assets(tmp_path):
    pytest.importorskip("dash")
    from velacare.dashboard.app import create_app

    app = create_app(tmp_path)
    client = app.server.test_client()
    assert client.get("/").status_code == 200
    layout = client.get("/_dash-layout")
    assert layout.status_code == 200
    assert b"generation-slider" in layout.data
    assert b"run-selector" in layout.data
    dependencies = client.get("/_dash-dependencies")
    assert dependencies.status_code == 200
    assert b"history-heatmap" in dependencies.data
    assert client.get("/assets/dashboard.css").status_code == 200
    assert client.get("/assets/velacare_icon.png").status_code == 200
    assert client.get("/assets/velacare_logo.png").status_code == 200
    assert b'link rel="manifest" href="/manifest.webmanifest"' in client.get("/").data
    assert b"startup-screen" in layout.data


def test_dashboard_health_routes_report_ready_empty_workspace(tmp_path):
    pytest.importorskip("dash")
    from velacare.dashboard.app import create_app

    app = create_app(tmp_path)
    client = app.server.test_client()
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json == {"service": "velacare-dashboard", "status": "live"}

    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json["dashboard"]["status"] == "ready"
    assert ready.json["local_workspace"] == {"status": "available", "experiments": "empty", "dataset": "missing"}
    assert ready.json["activation"]["status"] == "unknown"
    assert ready.json["activation"]["enabled"] is False


def test_dashboard_readiness_reports_initializing_and_workspace_errors(tmp_path):
    pytest.importorskip("dash")
    from velacare.dashboard.app import create_app

    initializing = create_app(tmp_path / "initializing")
    initializing.server.extensions["velacare_readiness"]["initialized"] = False
    response = initializing.server.test_client().get("/health/ready")
    assert response.status_code == 503
    assert response.json["status"] == "initializing"

    invalid_root = tmp_path / "workspace-file"
    invalid_root.write_text("not a directory", encoding="utf-8")
    unavailable = create_app(invalid_root)
    response = unavailable.server.test_client().get("/health/ready")
    assert response.status_code == 503
    assert response.json["status"] == "unavailable"


def test_pwa_routes_serve_manifest_icons_worker_and_scoped_shell(tmp_path):
    pytest.importorskip("dash")
    from velacare.dashboard.app import create_app

    app = create_app(tmp_path, base_path="/research/")
    client = app.server.test_client()
    manifest_response = client.get("/research/manifest.webmanifest")
    assert manifest_response.status_code == 200
    assert manifest_response.mimetype == "application/manifest+json"
    manifest = json.loads(manifest_response.data)
    assert manifest["name"] == "VelaCare Data Explorer"
    assert manifest["start_url"] == "./"
    assert manifest["scope"] == "./"
    assert manifest["display"] == "standalone"
    assert {entry["sizes"] for entry in manifest["icons"]} >= {"192x192", "512x512"}

    for icon in manifest["icons"]:
        response = client.get(f"/research/{icon['src']}")
        assert response.status_code == 200
        size = struct.unpack(">II", response.data[16:24])
        expected = int(icon["sizes"].split("x")[0])
        assert size == (expected, expected)

    worker = client.get("/research/service-worker.js")
    assert worker.status_code == 200
    assert worker.mimetype == "application/javascript"
    assert worker.headers["Service-Worker-Allowed"] == "/research/"
    assert b"candidate_history" not in worker.data
    assert b"latest.json" not in worker.data

    shell = client.get("/research/offline-shell.html")
    assert shell.status_code == 200
    assert b'content="/research/"' in shell.data
    assert b"__VELACARE_BASE_PATH__" not in shell.data


def test_health_routes_honor_configured_base_path(tmp_path):
    pytest.importorskip("dash")
    from velacare.dashboard.app import create_app

    app = create_app(tmp_path, base_path="/research/")
    client = app.server.test_client()
    assert client.get("/research/health/live").status_code == 200
    assert client.get("/research/health/ready").status_code == 200
    assert client.get("/health/live").status_code == 404


def test_mock_activation_routes_are_opt_in_and_idempotent(tmp_path):
    pytest.importorskip("dash")
    from velacare.dashboard.app import create_app

    disabled = create_app(tmp_path / "disabled")
    disabled_client = disabled.server.test_client()
    assert disabled_client.post("/activation/start", headers={"Idempotency-Key": "disabled"}).status_code == 404

    demo = create_app(tmp_path / "demo", activation_mode="mock")
    client = demo.server.test_client()
    before = client.get("/health/ready").json["activation"]
    assert before["status"] == "stopped"
    assert before["simulated"] is True
    headers = {"Idempotency-Key": "demo-start-001"}
    first = client.post("/activation/start", headers=headers)
    second = client.post("/activation/start", headers=headers)
    assert first.status_code == 202
    assert first.json == second.json
    assert first.json["status"] == "starting"


def test_dashboard_supports_configured_base_path(tmp_path):
    pytest.importorskip("dash")
    from velacare.dashboard.app import create_app

    app = create_app(tmp_path, base_path="/research/")
    client = app.server.test_client()
    assert client.get("/research/").status_code == 200
    assert client.get("/research/_dash-layout").status_code == 200
    assert client.get("/research/assets/dashboard.css").status_code == 200


def test_dashboard_graphs_have_zoom_and_full_data_reset_controls():
    pytest.importorskip("dash")
    import plotly.graph_objects as go

    from velacare.dashboard.views import _graph, _section

    graph = _graph(go.Figure(), zoomable=True)
    config = graph.to_plotly_json()["props"]["config"]
    assert config["displayModeBar"] is True
    assert config["modeBarButtons"] == [["zoomIn2d", "zoomOut2d", "autoScale2d"]]
    assert "zoomable-plot" in graph.to_plotly_json()["props"]["className"]
    assert "has-zoom-controls" in _section("Zoomable", graph).className


def test_non_zoomable_dashboard_graphs_hide_the_modebar():
    pytest.importorskip("dash")
    import plotly.graph_objects as go

    from velacare.dashboard.views import _graph, _section

    graph = _graph(go.Figure())
    props = graph.to_plotly_json()["props"]
    assert props["config"]["displayModeBar"] is False
    assert "zoomable-plot" not in props["className"]
    assert "has-zoom-controls" not in _section("Static", graph).className
