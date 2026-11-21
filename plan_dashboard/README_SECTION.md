<!-- VELACARE_DASHBOARD_DOCS_START -->

## VelaCare Data Explorer and OpenCode reporting

The genetic Evolution Engine runs through `./run-demo`, using data in `./agentic-space/`.

- **Dashboard:** [setup and run instructions](docs/DASHBOARD_SETUP.md). After the dashboard is implemented, use `./run-dashboard --workspace ./agentic-space --host 127.0.0.1 --port 8050`.
- **OpenCode Report Agent:** [install, configure, and generate VelaCare PowerPoint reports](docs/OPENCODE_SETUP.md).
- **Implementation goal for Codex:** [VelaCare Data Explorer](CODEX_DASHBOARD_GOAL.md).

The Coding Agent, Data Explorer and Report Agent share the **same `./agentic-space/` filesystem**. No file export or synchronization between them is required.

<!-- VELACARE_DASHBOARD_DOCS_END -->
