# ChromeOS launcher and VelaCare PWA

This guide covers the local Crostini launcher and the browser-installable VelaCare Data Explorer. The Linux shortcut starts the local dashboard process after ChromeOS starts the Linux environment. Installing the PWA only installs a browser app; it cannot start Crostini or a stopped dashboard backend.

## Install the ChromeOS Linux app shortcut

From the repository root in the Crostini terminal, install the user-scoped Linux launcher:

```bash
./scripts/install-chromeos-launcher.sh
```

It creates `~/.local/share/applications/velacare-data-explorer.desktop` and installs the VelaCare icon under `~/.local/share/icons/`. It uses the existing `./run-dashboard` command and needs `uv` and Python 3. No root access is required. Find **VelaCare Data Explorer** in ChromeOS Launcher > Linux apps. Right-click it and choose **Pin to shelf** if you want a shelf shortcut. Some ChromeOS versions refresh Linux app entries after a short delay or after reopening the Launcher.

To remove only the files installed by this script:

```bash
./scripts/install-chromeos-launcher.sh --uninstall
```

The shortcut starts or reuses the dashboard on port 8050, waits up to 90 seconds for `/health/ready`, then opens `http://localhost:8050/` through `xdg-open`. Use `--check` to start/reuse and check readiness without opening a browser:

```bash
./scripts/launch-chromeos-dashboard.sh --check
```

The launcher stores its PID, lock and log under `${XDG_STATE_HOME:-~/.local/state}/velacare/`. Inspect startup output with:

```bash
tail -n 100 "${XDG_STATE_HOME:-$HOME/.local/state}/velacare/dashboard-8050.log"
```

Configure the local run with environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VELACARE_WORKSPACE` | `<repo>/agentic-space` | Shared data and experiment workspace |
| `VELACARE_BIND_HOST` | `0.0.0.0` | Dashboard listen address |
| `VELACARE_PORT` | `8050` | Dashboard port |
| `VELACARE_BASE_PATH` | `/` | Optional reverse-proxy path prefix |
| `VELACARE_URL` | `http://localhost:<port><base-path>` | URL opened in ChromeOS |
| `VELACARE_STARTUP_TIMEOUT` | `90` | Readiness timeout in seconds |
| `VELACARE_STATE_DIR` | `${XDG_STATE_HOME:-~/.local/state}/velacare` | PID, lock and log location |

For example, start the shortcut with another workspace and port:

```bash
VELACARE_WORKSPACE=/agentic-space VELACARE_PORT=8051 ./scripts/launch-chromeos-dashboard.sh
```

When reusing an existing server, its health endpoint must identify itself as `velacare-dashboard`; an unrelated service on the chosen port is reported and left untouched. The launcher serializes quick successive starts and does not kill a process it did not start.

### ChromeOS networking and cold starts

For same-device local development, the launcher opens the dashboard through `localhost`. To access the server from another device, configure Linux port forwarding in ChromeOS under **Settings > Developers > Linux > Port forwarding** and use the Chromebook's network address and forwarded port. The exact settings labels may vary by ChromeOS release; see [ChromeOS port forwarding](https://chromeos.dev/en/web-environment/port-forwarding) and [Chromebook Help](https://support.google.com/chromebook/answer/10057656?hl=en-EN).

The Linux launcher is the local cold-start path: selecting the Linux app can start the Linux environment, after which the script starts the dashboard and opens a browser tab. A Chrome-installed PWA icon does not start Crostini. The Linux launcher does not promise to open the PWA in its standalone window.

## Install and use the PWA

The dashboard serves its manifest at `/manifest.webmanifest`, with relative URLs and a scoped service worker so a configured base path can be used behind a reverse proxy. It provides branded 192px and 512px icons, including a maskable 512px icon. In Chrome, first start the dashboard and open its URL; use the browser's **Install VelaCare Data Explorer** or **Install app** action. The browser controls the installation prompt. The PWA's scientific views still require a live backend and workspace.

For the supported local development URL, use `http://localhost:8050/`. Service workers are available on HTTPS and the localhost development exception; production installation should use HTTPS on the deployed origin. See [Chrome's service worker guidance](https://developer.chrome.com/docs/workbox/service-worker-lifecycle) and [PWA installation guide](https://developer.chrome.com/docs/modern-web-guidance/guides/pwa/install-web-app).

The versioned service worker caches only the branded startup shell, its CSS/JavaScript and icons. It never caches health responses, dashboard callbacks, research files, results, credentials or authenticated responses. If a shell was already cached, it can show a reconnection screen with Retry while the dashboard is down. First use while the dashboard is stopped cannot fetch the app or its shell, and the cached shell cannot analyze data offline.

## Verify the PWA

This check verifies installation metadata, online startup, the cached offline shell, and recovery after the dashboard returns. Use `localhost` so Chrome treats the local site as a secure context for service workers.

1. Start the dashboard and leave it running:

   ```bash
   cd ~/velacare
   ./run-dashboard --workspace ./agentic-space --host 127.0.0.1 --port 8050
   ```

2. In Chrome, open `http://localhost:8050/`. Wait for the research dashboard to appear. In DevTools > **Application**, confirm that the manifest loads and the service worker is active. Under **Cache Storage**, confirm `velacare-public-startup-v1` contains only the offline shell, startup CSS/JavaScript, and two icons.

3. Install VelaCare from Chrome's **Install app** option. Open the installed app and confirm it reaches the dashboard while the server is running.

4. Stop the dashboard with **Ctrl+C** in its terminal, then reload the installed app. The cached startup screen should show **VelaCare is unavailable** and a **Retry** button. This requires the app to have been opened online at least once so the service worker has cached the shell.

5. Restart the dashboard with the command from step 1, then select **Retry**. The dashboard should load again. The health routes can also be checked from a terminal:

   ```bash
   curl -fsS http://localhost:8050/health/live
   curl -i http://localhost:8050/health/ready
   ```

The cached screen is only a reconnection surface; experiment views require the running dashboard and workspace. For Chromebook-specific Linux app cold-start verification, follow the manual check at the end of this guide.

For a production cold-start experience, a separately reachable bootstrap origin or gateway must remain available while the workspace is stopped. It can host the shell and, once a real activation service exists, mediate status and start requests. This repository does not provision that always-on service.

## Health and workspace activation

The local launcher and startup screen use:

- `GET /health/live`: minimal process liveness response.
- `GET /health/ready`: dashboard initialization and configured local workspace access. An empty experiment history is a valid ready state. Health payloads include a stable VelaCare service marker and do not include local paths or experiment contents.

The routes are anonymous in this local app so a local launcher and startup screen can probe them. A production gateway should decide whether health checks are internal-only or protected, while exposing only the minimum safe status required by its probes.

The Python `ActivationProvider` contract separates external workspace state (`unknown`, `unavailable`, `stopped`, `starting`, `running`, `ready`, `auth_required`, `error`) from the dashboard's own readiness. `DisabledActivationProvider` is the default and performs no remote request. The opt-in `MockActivationProvider` simulates success, timeout, error and authorization-required outcomes without network access:

```bash
./run-dashboard --workspace ./agentic-space --activation-mode mock
```

The mock mode is for local UI demonstrations and automated tests only. It does not sign in, contact SecurSpaces or start infrastructure. **No external SecurSpaces status or activation API is assumed to exist or called.**

When a genuine, documented endpoint becomes available, a future provider can map its documented inputs and outputs onto the status/start contract. Keep endpoint configuration and credentials out of JavaScript, browser storage and the manifest. A privileged start operation belongs behind an always-available, authenticated server or gateway that enforces authorization, CSRF protection where relevant, allowed origins, audit logging, idempotency and rate limits. The dashboard process cannot activate its own stopped workspace because it is not running while that workspace is stopped.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Launcher does not appear under Linux apps | Rerun the installer from the repository; confirm `run-dashboard`, `uv`, and Python 3 are available. Reopen the ChromeOS Launcher after a short wait. |
| Startup times out | Read `dashboard-8050.log`; run the launcher with `--check`; confirm the workspace exists and is readable. Increase `VELACARE_STARTUP_TIMEOUT` if first startup needs longer. |
| Port already occupied | Check whether a dashboard is already using that port. Choose a different `VELACARE_PORT` if another app owns it; the launcher will not stop an unrelated service. |
| Local browser cannot reach the dashboard | Confirm `GET http://localhost:8050/health/ready` returns ready. For another device, configure ChromeOS Linux port forwarding and use the Chromebook host address. |
| Install action is missing | Open the app directly from a secure HTTPS origin or `localhost`, check the manifest and icons in Chrome DevTools' Application panel, and ensure the server is running. Browser install availability depends on the browser and origin. |
| Cached app shows unavailable | Start the Linux app or restore the backend/network, then select **Retry**. A cached shell is a recovery screen only; it cannot start Crostini or operate on saved runs. |
| Authentication required | Complete sign-in through the hosting environment's approved flow. The local mock only demonstrates this message and does not implement authentication. |

The complete click-through cold-start flow must be checked on the target Chromebook: shut down Linux, select **VelaCare Data Explorer** in Linux apps, and confirm Crostini starts, readiness passes, and Chrome opens the dashboard. This host is not ChromeOS, so that device-specific check remains manual verification pending.
