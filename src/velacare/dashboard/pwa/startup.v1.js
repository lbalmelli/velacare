(() => {
  "use strict";

  const delays = [1000, 2000, 4000, 8000, 15000, 30000, 30000];
  let startup = null;
  let inFlight = false;
  let attempts = 0;
  let timer = null;
  let activationInfo = null;
  let demoIdempotencyKey = null;

  function basePath() {
    const meta = document.querySelector('meta[name="velacare-base-path"]');
    let value = (meta && meta.content) || new URL("./", window.location.href).pathname;
    if (!value.startsWith("/")) value = `/${value}`;
    return value.endsWith("/") ? value : `${value}/`;
  }

  function offlineShell() {
    return document.documentElement.dataset.startupShell === "offline";
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
    const scope = new URL(basePath(), window.location.origin).href;
    navigator.serviceWorker.register(new URL("service-worker.js", scope), {
      scope,
      updateViaCache: "none",
    }).catch(() => {
      // PWA registration is optional on insecure origins; online dashboard use still works.
    });
  }

  function updateScreen(state, heading, detail, options = {}) {
    if (!startup) return;
    startup.dataset.state = state;
    const headingNode = document.getElementById("startup-heading");
    const detailNode = document.getElementById("startup-detail");
    const simulatedNode = document.getElementById("startup-simulated");
    const spinner = document.getElementById("startup-spinner");
    const retry = document.getElementById("startup-retry");
    const demo = document.getElementById("startup-demo-start");
    if (headingNode) headingNode.textContent = heading;
    if (detailNode) detailNode.textContent = detail;
    if (simulatedNode) simulatedNode.textContent = options.simulated ? "SIMULATED DEMO · NO EXTERNAL WORKSPACE REQUESTS" : "";
    if (spinner) spinner.hidden = !["connecting", "starting"].includes(state);
    if (retry) retry.hidden = !options.retry;
    if (demo) demo.hidden = !options.demo;
  }

  function hideScreen() {
    if (!startup || offlineShell()) return;
    startup.classList.add("is-hidden");
    startup.setAttribute("aria-hidden", "true");
  }

  function showReady() {
    updateScreen("ready", "VelaCare is ready", "Opening the research dashboard…");
    if (offlineShell()) {
      window.setTimeout(() => window.location.replace(basePath()), 250);
    } else {
      window.setTimeout(hideScreen, 300);
    }
  }

  function scheduleNext() {
    if (timer) window.clearTimeout(timer);
    if (attempts >= delays.length) {
      const simulated = Boolean(activationInfo && activationInfo.simulated);
      updateScreen("failed", "VelaCare could not connect", "The dashboard did not become ready after several checks. Check the Linux app or network, then retry.", {
        retry: true,
        demo: Boolean(activationInfo && activationInfo.simulated && activationInfo.status === "stopped"),
        simulated,
      });
      timer = window.setTimeout(checkReady, 60000);
      return;
    }
    const requested = Number(activationInfo && activationInfo.retry_after) * 1000;
    const fallback = delays[attempts];
    const wait = Number.isFinite(requested) && requested > 0 ? Math.max(1000, Math.min(30000, requested)) : fallback;
    timer = window.setTimeout(checkReady, wait);
  }

  function showUnavailable(detail) {
    const simulated = Boolean(activationInfo && activationInfo.simulated);
    updateScreen("unavailable", "VelaCare is unavailable", detail || "The dashboard server is not reachable yet. Start the Linux app or check the network, then retry.", {
      retry: true,
      demo: Boolean(activationInfo && activationInfo.simulated && activationInfo.status === "stopped"),
      simulated,
    });
    attempts += 1;
    scheduleNext();
  }

  async function checkReady() {
    if (inFlight || !startup) return;
    inFlight = true;
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
    try {
      const response = await fetch(`${basePath()}health/ready`, {
        cache: "no-store",
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      let payload = {};
      try { payload = await response.json(); } catch (_) { /* Auth gateways may return a non-JSON page. */ }
      activationInfo = payload.activation || null;
      const activationStatus = activationInfo && activationInfo.status;
      const simulated = Boolean(activationInfo && activationInfo.simulated);

      if (response.status === 401 || activationStatus === "auth_required") {
        updateScreen("auth_required", "Authentication required", "Complete authentication using the hosting environment’s approved sign-in flow, then retry.", { retry: true, simulated });
        attempts += 1;
        scheduleNext();
      } else if (activationStatus === "starting") {
        updateScreen("starting", "Starting workspace", activationInfo.detail || "The workspace provider reports that startup is in progress.", { retry: true, simulated });
        attempts += 1;
        scheduleNext();
      } else if (activationStatus === "error") {
        showUnavailable(activationInfo && activationInfo.detail);
      } else if (response.ok && (payload.dashboard && payload.dashboard.status) === "ready") {
        if (activationInfo && activationInfo.enabled && ["stopped", "unavailable"].includes(activationStatus)) {
          showUnavailable(activationInfo.detail);
        } else {
          attempts = 0;
          showReady();
        }
      } else if (payload.status === "initializing") {
        updateScreen("connecting", "Connecting to VelaCare", "The dashboard is initializing. Checking again shortly…", { retry: true, simulated });
        attempts += 1;
        scheduleNext();
      } else {
        const localWorkspaceUnavailable = payload.local_workspace && payload.local_workspace.status === "unavailable";
        const externalWorkspaceUnavailable = activationInfo && activationInfo.enabled && activationStatus === "unavailable";
        showUnavailable(localWorkspaceUnavailable
          ? "The dashboard can’t access its configured workspace directory. Check the local workspace mount and retry."
          : externalWorkspaceUnavailable && activationInfo.detail
            ? activationInfo.detail
            : undefined);
      }
    } catch (_) {
      activationInfo = null;
      showUnavailable("The dashboard server could not be reached. Start the VelaCare Linux app or check network connectivity, then retry.");
    } finally {
      inFlight = false;
    }
  }

  async function startMockWorkspace() {
    if (!activationInfo || !activationInfo.simulated || activationInfo.status !== "stopped") return;
    const button = document.getElementById("startup-demo-start");
    if (button) button.disabled = true;
    if (!demoIdempotencyKey) {
      demoIdempotencyKey = window.crypto && crypto.randomUUID
        ? crypto.randomUUID()
        : `mock-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }
    updateScreen("starting", "Starting workspace", "Requesting the opt-in simulated workspace transition…", { retry: true, simulated: true });
    try {
      const response = await fetch(`${basePath()}activation/start`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "Idempotency-Key": demoIdempotencyKey },
        body: "{}",
      });
      const result = await response.json();
      if (!response.ok && result.status === "auth_required") {
        activationInfo = { ...activationInfo, status: "auth_required", simulated: true };
        updateScreen("auth_required", "Authentication required", result.detail, { retry: true, simulated: true });
        scheduleNext();
      } else if (!response.ok) {
        activationInfo = { ...activationInfo, status: "error", detail: result.detail, simulated: true };
        updateScreen("failed", "Simulated startup failed", result.detail || "The mock provider reported an error.", { retry: true, simulated: true });
      } else {
        activationInfo = { ...activationInfo, status: result.status, detail: result.detail, simulated: true };
        attempts = 0;
        if (timer) window.clearTimeout(timer);
        timer = window.setTimeout(checkReady, 100);
      }
    } catch (_) {
      updateScreen("failed", "Simulated startup failed", "The mock activation route could not be reached. Retry the demo.", { retry: true, simulated: true });
    } finally {
      if (button) button.disabled = false;
    }
  }

  function initialize() {
    if (startup) return;
    startup = document.getElementById("startup-screen");
    if (!startup) return;
    const retry = document.getElementById("startup-retry");
    const demo = document.getElementById("startup-demo-start");
    if (retry) retry.addEventListener("click", () => {
      attempts = 0;
      checkReady();
    });
    if (demo) demo.addEventListener("click", startMockWorkspace);
    registerServiceWorker();
    checkReady();
  }

  document.addEventListener("DOMContentLoaded", initialize, { once: true });
  new MutationObserver(initialize).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("online", () => {
    attempts = 0;
    checkReady();
  });
})();
