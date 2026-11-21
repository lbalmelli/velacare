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


def test_dashboard_supports_configured_base_path(tmp_path):
    pytest.importorskip("dash")
    from velacare.dashboard.app import create_app

    app = create_app(tmp_path, base_path="/research/")
    client = app.server.test_client()
    assert client.get("/research/").status_code == 200
    assert client.get("/research/_dash-layout").status_code == 200
    assert client.get("/research/assets/dashboard.css").status_code == 200
