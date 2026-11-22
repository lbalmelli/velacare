import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-chromeos-launcher.sh"
LAUNCHER = ROOT / "scripts" / "launch-chromeos-dashboard.sh"
LINUX_TOOLS = all(shutil.which(name) for name in ("python3", "uv", "flock", "setsid"))


def _make_server(payloads):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            value = payloads.get(self.path)
            if value is None:
                body = json.dumps({"other": "service"}).encode()
                self.send_response(200)
            else:
                code, response = value
                body = json.dumps(response).encode()
                self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, server.server_address[1]


def _ready_server(port):
    live = {"service": "velacare-dashboard", "status": "live"}
    ready = {
        "service": "velacare-dashboard",
        "status": "ready",
        "dashboard": {"status": "ready"},
        "local_workspace": {"status": "available", "experiments": "empty", "dataset": "missing"},
        "activation": {"status": "unknown", "enabled": False, "simulated": False},
    }
    return _make_server({"/health/live": (200, live), "/health/ready": (200, ready)})


def _run(command, env, cwd):
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=15)


@pytest.mark.skipif(not LINUX_TOOLS, reason="Requires the standard Crostini launcher tools")
def test_linux_desktop_installer_is_idempotent_escaped_and_scoped(tmp_path):
    repo = tmp_path / "Vela Care Research"
    scripts = repo / "scripts"
    brand = repo / "brand"
    scripts.mkdir(parents=True)
    brand.mkdir()
    shutil.copy2(INSTALLER, scripts / INSTALLER.name)
    shutil.copy2(LAUNCHER, scripts / LAUNCHER.name)
    shutil.copy2(ROOT / "brand" / "velacare_icon.png", brand / "velacare_icon.png")
    run_dashboard = repo / "run-dashboard"
    run_dashboard.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    run_dashboard.chmod(0o755)

    home = tmp_path / "User Home"
    data_home = home / ".local" / "share data"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "XDG_DATA_HOME": str(data_home)}
    first = _run([str(scripts / INSTALLER.name)], env, tmp_path)
    second = _run([str(scripts / INSTALLER.name)], env, tmp_path)
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr

    desktop = data_home / "applications" / "velacare-data-explorer.desktop"
    icon = data_home / "icons" / "hicolor" / "512x512" / "apps" / "velacare-data-explorer.png"
    content = desktop.read_text(encoding="utf-8")
    assert content.count("[Desktop Entry]") == 1
    assert 'Name=VelaCare Data Explorer' in content
    assert 'Type=Application' in content
    assert 'Exec="' in content
    assert str(scripts / LAUNCHER.name) in content
    assert "Icon=" + str(icon).replace(" ", "\\s") in content
    assert icon.is_file()

    sentinel = data_home / "applications" / "other.desktop"
    sentinel.write_text("keep", encoding="utf-8")
    removed = _run([str(scripts / INSTALLER.name), "--uninstall"], env, tmp_path)
    assert removed.returncode == 0, removed.stderr
    assert not desktop.exists()
    assert not icon.exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"


@pytest.mark.skipif(not LINUX_TOOLS, reason="Requires the standard Crostini launcher tools")
def test_launcher_reuses_ready_dashboard_and_clears_stale_pid(tmp_path):
    server, thread, port = _ready_server(0)
    try:
        state = tmp_path / "state"
        state.mkdir()
        (state / f"dashboard-{port}.pid").write_text("999999999\n", encoding="utf-8")
        env = {
            **os.environ,
            "VELACARE_PORT": str(port),
            "VELACARE_STATE_DIR": str(state),
            "VELACARE_STARTUP_TIMEOUT": "3",
            "VELACARE_WORKSPACE": str(tmp_path / "workspace"),
        }
        result = _run([str(LAUNCHER), "--check"], env, tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Reusing existing VelaCare dashboard" in result.stdout
        assert "no browser was opened" in result.stdout
        assert not (state / f"dashboard-{port}.pid").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.skipif(not LINUX_TOOLS, reason="Requires the standard Crostini launcher tools")
def test_launcher_rejects_unrelated_service_without_stopping_it(tmp_path):
    server, thread, port = _make_server({})
    try:
        env = {
            **os.environ,
            "VELACARE_PORT": str(port),
            "VELACARE_STATE_DIR": str(tmp_path / "state"),
            "VELACARE_STARTUP_TIMEOUT": "2",
        }
        result = _run([str(LAUNCHER), "--check"], env, tmp_path)
        assert result.returncode != 0
        assert "unrelated application" in result.stderr
        assert server.fileno() >= 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.skipif(not LINUX_TOOLS, reason="Requires the standard Crostini launcher tools")
def test_launcher_timeout_stops_only_its_own_startup_process_group(tmp_path):
    repo = tmp_path / "timeout repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(LAUNCHER, scripts / LAUNCHER.name)
    runner = repo / "run-dashboard"
    runner.write_text("#!/usr/bin/env bash\nsleep 120\n", encoding="utf-8")
    runner.chmod(0o755)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    state = tmp_path / "timeout-state"
    env = {
        **os.environ,
        "VELACARE_PORT": str(port),
        "VELACARE_STATE_DIR": str(state),
        "VELACARE_STARTUP_TIMEOUT": "2",
    }
    result = _run([str(scripts / LAUNCHER.name), "--check"], env, tmp_path)
    assert result.returncode != 0
    assert "timed out" in result.stderr
    assert "Startup log:" in result.stderr
    pid_file = state / f"dashboard-{port}.pid"
    assert not pid_file.exists()


@pytest.mark.skipif(not LINUX_TOOLS, reason="Requires the standard Crostini launcher tools")
def test_two_rapid_launches_start_one_server_and_share_readiness_lock(tmp_path):
    repo = tmp_path / "test repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(LAUNCHER, scripts / LAUNCHER.name)
    fake_server = repo / "fake_server.py"
    fake_server.write_text(
        """import argparse, json, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
parser = argparse.ArgumentParser()
parser.add_argument('--host'); parser.add_argument('--port', type=int); parser.add_argument('--base-path')
args = parser.parse_args()
time.sleep(0.7)
prefix = args.base_path.rstrip('/')
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == prefix + '/health/live':
            code, payload = 200, {'service':'velacare-dashboard','status':'live'}
        elif self.path == prefix + '/health/ready':
            code, payload = 200, {'service':'velacare-dashboard','status':'ready','dashboard':{'status':'ready'}}
        else:
            code, payload = 404, {}
        body = json.dumps(payload).encode()
        self.send_response(code); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_args): pass
ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
""",
        encoding="utf-8",
    )
    runner = repo / "run-dashboard"
    runner.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'start\\n' >> "$VELACARE_TEST_START_MARKER"
exec python3 "$REPO_ROOT/fake_server.py" --host "$HOST" --port "$PORT" --base-path "$BASE"
""",
        encoding="utf-8",
    )
    runner.chmod(0o755)

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    state = tmp_path / "race-state"
    marker = tmp_path / "start-count.txt"
    env = {
        **os.environ,
        "VELACARE_PORT": str(port),
        "VELACARE_STATE_DIR": str(state),
        "VELACARE_STARTUP_TIMEOUT": "8",
        "VELACARE_TEST_START_MARKER": str(marker),
        "REPO_ROOT": str(repo),
        "HOST": "0.0.0.0",
        "PORT": str(port),
        "BASE": "/",
    }
    commands = [[str(scripts / LAUNCHER.name), "--check"] for _ in range(2)]
    processes = [subprocess.Popen(cmd, cwd=tmp_path, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for cmd in commands]
    try:
        results = [process.communicate(timeout=15) + (process.returncode,) for process in processes]
        assert all(returncode == 0 for _stdout, _stderr, returncode in results), results
        assert marker.read_text(encoding="utf-8").splitlines() == ["start"]
        pid = int((state / f"dashboard-{port}.pid").read_text(encoding="utf-8"))
        assert os.getpgid(pid) == pid
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        pid_file = state / f"dashboard-{port}.pid"
        if pid_file.exists():
            pid = int(pid_file.read_text(encoding="utf-8"))
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            for _ in range(30):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
