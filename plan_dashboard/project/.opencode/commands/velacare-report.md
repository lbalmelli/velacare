---
description: Generate a VelaCare-branded PowerPoint research report from a saved experiment
agent: velacare-report
---

Generate the VelaCare branded medical research PowerPoint requested by the user. Use the exact experiment run specified in these arguments (or ask for a run if ambiguous): $ARGUMENTS

Load the `interpret-medical-research` and `create-report-slide` skills. Read saved run artifacts from the shared Agentic Space, verify provenance and real metrics, produce PPTX using the bundled company logo and template, save to the workspace `presentations/` folder, render and inspect it, and explain limitations. Do not invent results or clinical claims.
