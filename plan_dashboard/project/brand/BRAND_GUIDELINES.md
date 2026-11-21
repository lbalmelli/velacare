# VelaCare Research: demo brand system

**Fictional company.** The name, logo, presentations and research context are illustrative. Do not represent it as an operating healthcare provider or imply medical certification.

## Voice and presentation style

Use clear, restrained scientific language. Credible rather than promotional. Explain evidence, reproducibility, uncertainty and limitations. Prefer short declarative slide titles (e.g. 'Evolution of feature selection') with one claim per visual. Avoid claims of patient benefit without clinical evidence.

## Colors

| Role | Hex |
| --- | --- |
| Navy background | `#0B1422` |
| Deep panel | `#122338` |
| Primary blue | `#2F80FF` |
| Teal highlight | `#59CBB8` |
| Near-white | `#F4F8FC` |
| Dark text | `#1B3048` |
| Muted slate text | `#7C90A8` |
| Cool gray line | `#DCE5EF` |

Typography: Public Sans if available; fallback Aptos/Arial. Use 16:9 landscape. Large clear titles, generous whitespace, short callouts, explicit data labels. Use blue for best-candidate series and teal for mean-fitness series throughout dashboard and reports.

## Asset paths

- `brand/velacare_logo.png` — horizontal generated company identity for light-background slides, footers and documents.
- `brand/velacare_icon.png` — V emblem for dark sidebars or compact app chrome.
- `brand/VelaCare_Research_Reporting_Template.pptx` — editable 16:9 branded deck skeleton with named placeholders.

At runtime, these are provisioned into the persistent Agentic Space once by its template, e.g. `/agentic-space/brand/`. All agents and applications open those same files directly. Do not implement a separate file-sync mechanism.

## Clinical content policy

Always carry the footer 'Research demonstration • Not clinically validated'. Distinguish fitness (objective score) from accuracy, malignant sensitivity, specificity and other model evaluation measures. Cite UCI dataset provenance and captured run metadata in reports.
