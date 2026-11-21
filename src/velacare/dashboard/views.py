"""Branded research views built only from persisted run and dataset artifacts."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import plotly.graph_objects as go
from dash import dash_table, dcc, html

from .data import DatasetData, GenerationData, RunData, WorkspaceData


NAVY = "#0b1422"
PANEL = "#122338"
BLUE = "#2f80ff"
TEAL = "#59cbb8"
WHITE = "#f4f8fc"
MUTED = "#8ea2b9"
LINE = "#263d56"
EXCLUDED = "#34465b"

_PLOT_LAYOUT: dict[str, Any] = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"family": "Inter, Arial, sans-serif", "color": WHITE, "size": 12},
    "margin": {"l": 52, "r": 18, "t": 26, "b": 45},
    "xaxis": {"gridcolor": LINE, "linecolor": LINE, "zerolinecolor": LINE, "automargin": True},
    "yaxis": {"gridcolor": LINE, "linecolor": LINE, "zerolinecolor": LINE, "automargin": True},
    "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "font": {"color": "#c4d0df"}},
    "hoverlabel": {"bgcolor": "#172c43", "bordercolor": LINE, "font": {"color": WHITE}},
}


def _graph(figure: go.Figure, *, height: int = 320, class_name: str = "plot", graph_id: Any = None) -> dcc.Graph:
    figure.update_layout(**_PLOT_LAYOUT, height=height, autosize=True)
    props: dict[str, Any] = {"figure": figure, "config": {"displayModeBar": False, "responsive": True},
                             "className": class_name, "style": {"height": f"{height}px"}}
    if graph_id is not None:
        props["id"] = graph_id
    return dcc.Graph(**props)


def _section(title: str, child: Any, subtitle: str | None = None, *, class_name: str = "panel") -> html.Section:
    head: list[Any] = [html.H2(title)]
    if subtitle:
        head.append(html.P(subtitle, className="section-note"))
    return html.Section([html.Div(head, className="panel-heading"), child], className=class_name)


def _metric(label: str, value: str, caption: str = "", color: str | None = None) -> html.Div:
    return html.Div([
        html.Span(label, className="metric-label"),
        html.Strong(value, className="metric-value", style={"color": color} if color else {}),
        html.Span(caption, className="metric-caption") if caption else None,
    ], className="metric-card")


def _metric_grid(items: list[html.Div]) -> html.Div:
    return html.Div(items, className="metric-grid")


def _empty(title: str, detail: str, *, kind: str = "empty-state") -> html.Div:
    return html.Div([html.Div("VC", className="empty-mark"), html.H2(title), html.P(detail)], className=kind)


def _score(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "not available"


def _when(value: Any) -> str:
    if not value:
        return "not available in run artifact"
    return str(value).replace("T", " ").replace("+00:00", " UTC")


def _style_heatmap(figure: go.Figure) -> go.Figure:
    layout = {**_PLOT_LAYOUT, "height": max(390, 130 + 17 * len(figure.data[0].y)),
              "margin": {"l": 115, "r": 16, "t": 22, "b": 120}}
    figure.update_layout(**layout)
    figure.update_xaxes(tickangle=-55, tickfont={"size": 10})
    figure.update_yaxes(autorange="reversed", tickfont={"size": 10})
    return figure


def _fitness_trend(run: RunData, selected_generation: int, *, include_summary: bool = True) -> go.Figure:
    generations = list(run.generations)
    figure = go.Figure()
    if not generations:
        return figure
    summaries = [run.generations[number].summary for number in generations]
    series = [
        ("Best fitness", [float(row["best_fitness"]) for row in summaries], BLUE, 3),
        ("Mean fitness", [float(row["mean_fitness"]) for row in summaries], TEAL, 2),
    ]
    if include_summary:
        series.extend([
            ("Median fitness", [float(row["median_fitness"]) for row in summaries], "#a9bdd2", 1.4),
            ("Minimum fitness", [float(row["min_fitness"]) for row in summaries], "#70859c", 1.4),
        ])
    for name, values, color, width in series:
        figure.add_trace(go.Scatter(
            x=generations, y=values, name=name, mode="lines",
            line={"color": color, "width": width},
            hovertemplate=f"Generation %{{x}}<br>{name}: %{{y:.4f}}<extra></extra>",
        ))
    selected = run.generations.get(selected_generation)
    if selected:
        figure.add_vline(x=selected_generation, line_dash="dash", line_color="#70859c", opacity=0.7)
        for name, color, value in [
            ("Selected best", BLUE, float(selected.summary["best_fitness"])),
            ("Selected mean", TEAL, float(selected.summary["mean_fitness"])),
        ]:
            figure.add_trace(go.Scatter(x=[selected_generation], y=[value], name=name, mode="markers", showlegend=False,
                                        marker={"color": color, "size": 9, "line": {"color": WHITE, "width": 1}}))
    figure.update_layout(xaxis_title="Generation", yaxis_title="Composite fitness score (unitless)", hovermode="x unified")
    return figure


def _diversity_trend(run: RunData, selected_generation: int) -> go.Figure:
    generations = list(run.generations)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=generations, y=[run.generations[g].diversity["unique_chromosome_ratio"] for g in generations],
                             name="Unique chromosome ratio", mode="lines", line={"color": BLUE, "width": 2.5}))
    fig.add_trace(go.Scatter(x=generations, y=[run.generations[g].diversity["mean_pairwise_hamming_fraction"] for g in generations],
                             name="Mean pairwise Hamming fraction", mode="lines", line={"color": TEAL, "width": 2}))
    fig.add_vline(x=selected_generation, line_dash="dash", line_color="#71869c")
    fig.update_layout(xaxis_title="Generation", yaxis_title="Diversity (0–1)", yaxis={"range": [0, 1], **_PLOT_LAYOUT["yaxis"]})
    return fig


def _feature_count_trend(run: RunData, selected_generation: int) -> go.Figure:
    generations = list(run.generations)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=generations, y=[int(run.generations[g].summary["best_feature_count"]) for g in generations],
                             name="Best candidate", mode="lines", line={"color": BLUE, "width": 2.5}))
    fig.add_trace(go.Scatter(x=generations, y=[float(np.mean(run.generations[g].feature_counts)) for g in generations],
                             name="Population mean", mode="lines", line={"color": TEAL, "width": 2}))
    fig.add_vline(x=selected_generation, line_dash="dash", line_color="#71869c")
    fig.update_layout(xaxis_title="Generation", yaxis_title="Selected features (count)", yaxis={"range": [0, 30], **_PLOT_LAYOUT["yaxis"]})
    return fig


def _feature_mask(chromosome: str, names: list[str], candidate_id: str, generation: int, color: str = BLUE) -> html.Div:
    return html.Div([
        html.Span(
            title=f"{name}: {'selected' if bit == '1' else 'excluded'} · {candidate_id} · generation {generation}",
            className="mask-bit is-selected" if bit == "1" else "mask-bit",
            style={"--bit-color": color},
            **{"aria-label": f"{name}: {'selected' if bit == '1' else 'excluded'}"},
        )
        for name, bit in zip(names, chromosome, strict=True)
    ], className="feature-mask", role="img", **{"aria-label": f"{sum(bit == '1' for bit in chromosome)} of {len(names)} features selected"})


def _feature_list(names: list[str]) -> html.Div:
    if not names:
        return html.P("No selected features recorded.", className="muted")
    return html.Div([html.Span(name, className="feature-chip") for name in names], className="feature-chip-list")


def overview_view(run: RunData, generation: GenerationData, selected_candidate: dict[str, Any]) -> list[Any]:
    manifest = run.manifest
    dataset = manifest.get("dataset", {})
    params = manifest.get("parameters", {})
    summary = generation.summary
    best = generation.best_candidate
    best_names = list(best["selected_features"])
    duration = summary.get("generation_seconds")
    completion = "not available in run artifact"  # GA records elapsed duration, not a per-generation timestamp.
    detail = html.Div([
        html.Div([html.Span("Selected generation", className="eyebrow"),
                  html.Div([html.Strong(str(generation.number), className="selected-generation"), html.Span(f"of {run.committed_generation}", className="muted")], className="selected-number"),
                  html.Div([html.Span("Best fitness"), html.Strong(_score(summary["best_fitness"]), className="blue"),
                            html.Span("Mean fitness"), html.Strong(_score(summary["mean_fitness"]), className="teal"),
                            html.Span("Features in best mask"), html.Strong(f"{summary['best_feature_count']} / 30")], className="metric-rows")], className="panel overview-selected"),
        html.Div([html.Span("Best-candidate feature subset", className="eyebrow"), _feature_mask(best["chromosome"], list(manifest["feature_order"]), best["candidate_id"], generation.number),
                  html.P(f"{best['candidate_id']} · candidate snapshot from the saved population", className="section-note")], className="panel mask-panel"),
    ], className="overview-side")
    cards = _metric_grid([
        _metric("Candidate count", str(len(generation.candidates)), "complete population"),
        _metric("Unique masks", f"{generation.diversity['unique_chromosome_ratio']:.1%}", f"{generation.summary['distinct_mask_count']} distinct chromosomes"),
        _metric("Mean pairwise distance", f"{generation.diversity['mean_pairwise_hamming_distance']:.1f} bits", "Hamming distance across all pairs"),
        _metric("Generation duration", f"{float(duration):.2f} s" if duration not in (None, "") else "not available", "saved compute duration"),
    ])
    metadata = html.Div([
        html.Div([html.Span("Dataset"), html.Strong(str(dataset.get("name", "not available"))), html.Small(f"UCI dataset ID {dataset.get('dataset_id', 'not available')} · {dataset.get('sample_count', 'not available')} samples")]),
        html.Div([html.Span("Seed"), html.Strong(str(params.get("seed", "not available in run artifact"))), html.Small("reproducibility input")]),
        html.Div([html.Span("Run status"), html.Strong(run.status.replace("_", " ").title()), html.Small(f"Run started {_when(manifest.get('started_at'))}")]),
        html.Div([html.Span("Generation completion time"), html.Strong(completion), html.Small("The writer stores duration, not generation timestamps.")]),
    ], className="metadata-grid")
    selected_details = html.Div([html.H3("Selected features"), _feature_list(best_names), html.P(f"Composite fitness score: {_score(best['fitness'])}. This is an optimization score, not clinical accuracy or sensitivity.", className="science-note")], className="panel")
    return [
        html.Div([_section("Evolution across generations", _graph(_fitness_trend(run, generation.number, include_summary=False), height=280), "Best and mean composite fitness · the vertical marker follows the shared generation control."), detail], className="overview-top-grid"),
        cards,
        html.Div([selected_details, _section("Reproducibility", metadata, "Captured from the selected run manifest.")], className="two-column-grid"),
        html.Div([html.Span("Reading"), html.Code(str(run.path / "generation_history.csv")), html.Span(f"{len(generation.candidates)} complete candidate records reconstructed for generation {generation.number}.")], className="source-line"),
    ]


def _candidate_table(generation: GenerationData, selected_id: str) -> dash_table.DataTable:
    rows = []
    for candidate in generation.candidates:
        parents = candidate.get("parents") or []
        rows.append({
            "id": candidate["candidate_id"],
            "candidate_id": candidate["candidate_id"],
            "fitness": float(candidate["fitness"]),
            "features": int(candidate["selected_feature_count"]),
            "operator": candidate.get("operator") or "not available in run artifact",
            "parents": ", ".join(str(item.get("candidate_id", "")) for item in parents) or "not available",
            "cache": "yes" if candidate.get("evaluation_cache_hit") else "no",
            "chromosome": candidate["chromosome"],
        })
    return dash_table.DataTable(
        id={"type": "candidate-table", "index": "population"},
        data=rows,
        columns=[{"name": name, "id": key, "type": "numeric" if key == "fitness" else "text"} for name, key in [
            ("Candidate ID", "candidate_id"), ("Fitness score", "fitness"), ("Features", "features"),
            ("Operator / lineage", "operator"), ("Parents", "parents"), ("Cached CV", "cache"), ("Chromosome", "chromosome"),
        ]],
        sort_action="native", filter_action="native", page_action="native", page_size=12,
        row_selectable="single", selected_row_ids=[selected_id],
        style_table={"overflowX": "auto", "minWidth": "100%"},
        style_header={"backgroundColor": "#182d43", "color": "#bdcadd", "border": f"1px solid {LINE}", "fontWeight": 650, "textAlign": "left", "padding": "10px"},
        style_cell={"backgroundColor": "#102136", "color": WHITE, "border": f"1px solid {LINE}", "padding": "9px", "fontFamily": "Inter, Arial", "fontSize": "12px", "minWidth": "85px", "maxWidth": "250px", "whiteSpace": "normal", "height": "auto"},
        style_data_conditional=[{"if": {"state": "selected"}, "backgroundColor": "#173d68", "border": f"1px solid {BLUE}"}],
    )


def _lineage_interpretation(candidate: dict[str, Any]) -> str:
    operator = candidate.get("operator")
    if not operator:
        return "not available in run artifact"
    if operator == "initial":
        return "Initial population candidate; no parent or later-generation operator is recorded."
    if operator == "elite":
        return "Copied from the prior generation by elitism; the saved record identifies the source parent."
    labels = {
        "selection": "parent(s) chosen by tournament selection",
        "crossover": "uniform crossover applied",
        "mutation": "independent per-bit mutation applied",
    }
    parts = [labels.get(token) for token in str(operator).split("+")]
    recognized = [part for part in parts if part]
    return "; ".join(recognized) if recognized else "Stored operator label: " + str(operator)


def evolution_view(run: RunData, generation: GenerationData, selected: dict[str, Any], compare_id: str | None) -> list[Any]:
    fitness = np.asarray(generation.fitness_values)
    histogram = go.Figure()
    histogram.add_trace(go.Histogram(x=fitness, nbinsx=18, marker={"color": BLUE, "line": {"color": "#83b3ff", "width": 0.6}}, name="Candidate fitness"))
    histogram.update_layout(xaxis_title="Composite fitness score (unitless)", yaxis_title="Candidate count", bargap=0.08, showlegend=False)
    selected_cv = selected.get("cv_metrics", {})
    components = selected.get("fitness_components", {})
    parents = selected.get("parents") or []
    candidate_detail = html.Div([
        html.Div([html.Span("Candidate inspector", className="eyebrow"), html.H3(str(selected["candidate_id"])), html.P(f"{sum(bit == '1' for bit in selected['chromosome'])} of 30 features selected · fitness score {_score(selected['fitness'])}", className="muted")]),
        _feature_mask(selected["chromosome"], list(run.manifest["feature_order"]), selected["candidate_id"], generation.number),
        html.Div([html.H4("Selected feature names"), _feature_list(selected["selected_features"])]),
        html.Div([html.H4("Stored fitness components"), html.Pre(json_pretty(components), className="json-block")]),
        html.Div([html.H4("CV metrics stored on candidate"), html.Pre(json_pretty(selected_cv), className="json-block")]),
        html.Div([html.H4("Lineage"), html.P(f"Operator: {selected.get('operator') or 'not available in run artifact'}"),
                  html.P(f"Interpretation: {_lineage_interpretation(selected)}"),
                  html.P("Parents: " + (", ".join(f"g{parent.get('generation', '?')} · {parent.get('candidate_id', '?')}" for parent in parents) if parents else "not available in run artifact")),
                  html.P(f"Evaluation cache hit: {'yes' if selected.get('evaluation_cache_hit') else 'no'}")]),
    ], className="panel candidate-inspector")
    compare_candidates = [candidate for candidate in generation.candidates if candidate["candidate_id"] == compare_id]
    comparison: Any
    if compare_candidates:
        other = compare_candidates[0]
        distance = sum(a != b for a, b in zip(selected["chromosome"], other["chromosome"], strict=True))
        changed = [name for name, a, b in zip(run.manifest["feature_order"], selected["chromosome"], other["chromosome"], strict=True) if a != b]
        comparison = html.Div([
            _metric("Hamming distance", f"{distance} / 30", f"{distance / 30:.1%} of feature positions differ"),
            html.Div([html.H3("Chromosome comparison"), html.P(f"{selected['candidate_id']} compared with {other['candidate_id']}"),
                      html.P("Changed feature positions: " + (", ".join(changed) if changed else "none"), className="section-note"),
                      html.Div([html.Div([html.Span("Selected candidate"), _feature_mask(selected["chromosome"], list(run.manifest["feature_order"]), selected["candidate_id"], generation.number)]),
                                html.Div([html.Span("Comparison candidate"), _feature_mask(other["chromosome"], list(run.manifest["feature_order"]), other["candidate_id"], generation.number, TEAL)])], className="comparison-masks")], className="panel"),
        ], className="two-column-grid")
    else:
        comparison = _empty("Choose a second candidate", "Select another candidate in the comparison control to calculate chromosome distance.")
    return [
        _metric_grid([
            _metric("Best fitness", _score(generation.summary["best_fitness"]), "saved full population", BLUE),
            _metric("Mean fitness", _score(generation.summary["mean_fitness"]), "saved full population", TEAL),
            _metric("Median fitness", _score(generation.summary["median_fitness"]), "saved full population"),
            _metric("Minimum fitness", _score(generation.summary["min_fitness"]), "saved full population"),
        ]),
        html.Div([_section("Fitness distribution", _graph(histogram), f"All {len(generation.candidates)} persisted candidates in generation {generation.number}."),
                  candidate_detail], className="two-column-grid evolution-grid"),
        html.Div([_section("Fitness through time", _graph(_fitness_trend(run, generation.number), height=340), "Best, mean, median and minimum fitness are reconstructed for each committed generation."),
                  _section("Selected-feature count", _graph(_feature_count_trend(run, generation.number), height=340), "Best-candidate and population-mean feature counts for every committed generation."),
                  _section("Population diversity", _graph(_diversity_trend(run, generation.number), height=340), "Unique-mask ratio and mean pairwise Hamming distance ÷ 30, computed from all saved chromosomes.")], className="two-column-grid"),
        _section("Complete candidate population", _candidate_table(generation, selected["candidate_id"]), "Every persisted candidate is shown; table sorting and filtering change presentation only."),
        _section("Compare two candidates", comparison, "Selection uses stored CV fitness, crossover, mutation and elitism only where the saved operator/parent fields describe them."),
    ]


def json_pretty(value: Any) -> str:
    import json
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def _best_matrix(run: RunData) -> go.Figure:
    generations = list(run.generations)
    features = list(run.manifest["feature_order"])
    z = [[int(bit) for bit in run.generations[g].best_candidate["chromosome"]] for g in generations]
    custom = [[[g, feature, "selected" if bit else "excluded"] for feature, bit in zip(features, row, strict=True)]
              for g, row in zip(generations, z, strict=True)]
    fig = go.Figure(go.Heatmap(
        z=z, x=features, y=generations, customdata=custom,
        zmin=0, zmax=1, colorscale=[[0, EXCLUDED], [0.49, EXCLUDED], [0.5, BLUE], [1, BLUE]],
        showscale=False, xgap=2, ygap=2,
        hovertemplate="Generation %{customdata[0]}<br>%{customdata[1]}<br>%{customdata[2]}<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Canonical feature order", yaxis_title="Generation")
    return _style_heatmap(fig)


def _population_matrix(run: RunData, generation: GenerationData, selected_id: str) -> go.Figure:
    features = list(run.manifest["feature_order"])
    candidates = list(generation.candidates)
    z = [[int(bit) for bit in item["chromosome"]] for item in candidates]
    custom = [[[item["candidate_id"], feature, "selected" if bit else "excluded"] for feature, bit in zip(features, row, strict=True)]
              for item, row in zip(candidates, z, strict=True)]
    colorscale = [[0, EXCLUDED], [0.49, EXCLUDED], [0.5, BLUE], [1, BLUE]]
    fig = go.Figure(go.Heatmap(
        z=z, x=features, y=[item["candidate_id"] for item in candidates], customdata=custom,
        zmin=0, zmax=1, colorscale=colorscale, showscale=False, xgap=2, ygap=2,
        hovertemplate="Candidate %{customdata[0]}<br>%{customdata[1]}<br>%{customdata[2]}<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Canonical feature order", yaxis_title=f"All {len(candidates)} candidates")
    selected_index = next((index for index, item in enumerate(candidates) if item["candidate_id"] == selected_id), None)
    if selected_index is not None:
        fig.add_shape(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=selected_index - 0.5, y1=selected_index + 0.5,
                      line={"color": TEAL, "width": 2}, fillcolor="rgba(89,203,184,0.06)", layer="above")
    return _style_heatmap(fig)


def feature_view(run: RunData, generation: GenerationData, selected: dict[str, Any], compare_id: str | None) -> list[Any]:
    features = list(run.manifest["feature_order"])
    generations = list(run.generations)
    freq_matrix = [list(run.generations[g].feature_frequencies) for g in generations]
    freq_custom = [[[g, feature, value] for feature, value in zip(features, row, strict=True)] for g, row in zip(generations, freq_matrix, strict=True)]
    frequency = go.Figure(go.Heatmap(
        z=freq_matrix, x=features, y=generations, customdata=freq_custom, zmin=0, zmax=1,
        colorscale=[[0, "#182d43"], [0.35, "#28557c"], [1, TEAL]], colorbar={"title": "Candidate share", "tickformat": ".0%"},
        hovertemplate="Generation %{customdata[0]}<br>%{customdata[1]}<br>Selected by %{customdata[2]:.1%} of candidates<extra></extra>",
    ))
    frequency.update_layout(xaxis_title="Canonical feature order", yaxis_title="Generation")
    _style_heatmap(frequency)
    selected_frequency = generation.feature_frequencies
    ranked = sorted(zip(features, selected_frequency, strict=True), key=lambda item: (-item[1], item[0]))
    ranking_table = dash_table.DataTable(
        data=[{"feature": feature, "frequency": value} for feature, value in ranked],
        columns=[{"name": "Feature", "id": "feature"}, {"name": f"Selection frequency · generation {generation.number}", "id": "frequency", "type": "numeric", "format": {"specifier": ".1%"}}],
        page_action="native", page_size=10, sort_action="native",
        style_header={"backgroundColor": "#182d43", "color": "#bdcadd", "border": f"1px solid {LINE}", "textAlign": "left", "padding": "9px"},
        style_cell={"backgroundColor": "#102136", "color": WHITE, "border": f"1px solid {LINE}", "padding": "8px", "fontSize": "12px"},
    )
    counts = go.Figure()
    counts.add_trace(go.Histogram(x=generation.feature_counts, xbins={"start": 0, "end": 31, "size": 1}, marker_color=BLUE, name="Candidates"))
    counts.update_layout(xaxis_title="Selected features per candidate", yaxis_title="Candidate count", showlegend=False)
    d = _diversity_trend(run, generation.number)
    comp_candidate = next((item for item in generation.candidates if item["candidate_id"] == compare_id), None)
    if comp_candidate:
        distance = sum(a != b for a, b in zip(selected["chromosome"], comp_candidate["chromosome"], strict=True))
        changed = [name for name, a, b in zip(features, selected["chromosome"], comp_candidate["chromosome"], strict=True) if a != b]
        comparison = html.Div([
            _metric("Hamming distance", f"{distance} / 30", "positions with different bits"),
            html.Div([html.P(f"Selected candidate: {selected['candidate_id']}"), html.P(f"Compared candidate: {comp_candidate['candidate_id']}"),
                      html.P("Changed features: " + (", ".join(changed) if changed else "none"), className="section-note"),
                      _feature_mask(selected["chromosome"], features, selected["candidate_id"], generation.number),
                      _feature_mask(comp_candidate["chromosome"], features, comp_candidate["candidate_id"], generation.number, TEAL)], className="panel")
        ], className="two-column-grid")
    else:
        comparison = _empty("Candidate comparison", "Choose another candidate from this generation using the comparison control.")
    return [
        html.Div([_metric("Feature columns", "30", "canonical UCI WDBC feature order"), _metric("Population snapshots", str(len(generation.candidates)), "all candidates in selected generation"), _metric("Committed generations", str(run.committed_generation), "no sampling")], className="metric-grid"),
        _section("Best candidate · full history", _graph(_best_matrix(run), height=max(410, 150 + 17 * len(generations)), class_name="plot heatmap-plot", graph_id={"type": "history-heatmap", "index": "best"}), "Generation × 30 mask. Select any row to move the shared generation control; hover cells for feature and state."),
        _section(f"Population matrix · generation {generation.number}", _graph(_population_matrix(run, generation, selected["candidate_id"]), height=max(400, 180 + 17 * len(generation.candidates)), class_name="plot heatmap-plot", graph_id={"type": "population-heatmap", "index": "population"}), "Candidate × 30 mask, with all persisted candidates. Click a row to select the candidate and update the inspector."),
        html.Div([_section("Feature-selection frequency", _graph(frequency, height=max(390, 150 + 17 * len(generations)), class_name="plot heatmap-plot"), "Share of candidates selecting each feature in each complete generation."), _section("Feature ranking", ranking_table, "Ranking uses candidate frequency, not diagnostic importance.")], className="two-column-grid"),
        html.Div([_section("Selected-feature count distribution", _graph(counts), "All candidates in the selected generation."), _section("Population diversity", _graph(d, height=320), "Unique chromosome ratio and mean pairwise Hamming distance divided by 30; both are computed from persisted chromosomes.")], className="two-column-grid"),
        _section("Compare candidate masks", comparison, "Algorithmic mask changes describe selection among measured inputs, not biological cancer mutations."),
        html.P("Feature frequencies and masks are algorithmic feature-selection records. They do not describe biological mutations or causal mechanisms.", className="science-note strong-note"),
    ]


def _metric_value(metrics: dict[str, Any], key: str, *, percent: bool = True) -> str:
    value = metrics.get(key) if isinstance(metrics, dict) else None
    if value is None:
        return "not available in run artifact"
    try:
        return f"{float(value):.1%}" if percent else f"{float(value):.3f}"
    except (ValueError, TypeError):
        return "not available in run artifact"


def _evaluation_panel(title: str, metrics: dict[str, Any], samples: str, labels: list[str]) -> html.Div:
    known = bool(metrics)
    metric_cards = _metric_grid([
        _metric("Malignant sensitivity", _metric_value(metrics, "malignant_sensitivity"), "positive class: malignant", BLUE),
        _metric("Specificity", _metric_value(metrics, "specificity"), "negative class: benign", TEAL),
        _metric("Balanced accuracy", _metric_value(metrics, "balanced_accuracy"), "recorded evaluation split"),
        _metric("Accuracy", _metric_value(metrics, "accuracy"), "recorded evaluation split"),
    ])
    cm = metrics.get("confusion_matrix") if known else None
    if isinstance(cm, list) and len(cm) == 2 and all(isinstance(row, list) and len(row) == 2 for row in cm):
        fig = go.Figure(go.Heatmap(
            z=cm, x=labels, y=labels, colorscale=[[0, "#182d43"], [1, BLUE]], showscale=False,
            text=[[str(value) for value in row] for row in cm], texttemplate="%{text}",
            hovertemplate="Actual %{y}<br>Predicted %{x}<br>Samples: %{z}<extra></extra>",
        ))
        fig.update_layout(xaxis_title="Predicted class", yaxis_title="Actual class")
        matrix: Any = _section(f"{title} confusion matrix", _graph(fig, height=280), f"Actual rows and predicted columns · {samples}.")
    else:
        matrix = _section(f"{title} confusion matrix", _empty("not available in run artifact", "Saved confusion-matrix counts are required before this view can be rendered."), samples)
    auc_value = metrics.get("roc_auc") if known else None
    roc = _empty("ROC curve / AUC not available in run artifact", "The run stores summary metrics and confusion counts, but no ROC threshold or prediction scores.") if auc_value is None else html.Div([html.H3("ROC / AUC"), html.P(str(auc_value))], className="panel")
    return html.Div([html.Div([html.H3(title), html.P(samples, className="section-note"), metric_cards], className="evaluation-card"), matrix, roc], className="evaluation-column")


def evaluation_view(run: RunData) -> list[Any]:
    metrics = run.model_metrics
    cv = metrics.get("cv_metrics", {}) if metrics else {}
    test = metrics.get("held_out_test_metrics", {}) if metrics else {}
    labels = (metrics.get("metric_notes", {}).get("confusion_matrix_axis_order", {}).get("actual_rows") if metrics else None) or ["malignant", "benign"]
    if metrics:
        split = metrics.get("test_split", {})
        cv_n = run.manifest.get("cross_validation", {}).get("training_samples")
        test_n = split.get("held_out_samples") if isinstance(split, dict) else None
        cv_text = f"Out-of-fold results within the training split; {cv_n if cv_n is not None else 'not available'} training samples."
        test_text = f"One-time held-out test result; {test_n if test_n is not None else 'not available'} held-out samples."
    else:
        cv_text = "Cross-validation metrics not available in run artifact."
        test_text = "Held-out test metrics not available in run artifact."
    return [
        html.Div([html.Span("Research evaluation"), html.Strong("Research demonstration · not clinically validated")], className="research-banner"),
        html.P("Fitness is a composite optimization score used during feature selection. It is not accuracy, sensitivity, specificity, or a probability of cancer. Held-out test measurements are shown separately and are never plotted across generations.", className="science-note"),
        html.Div([_evaluation_panel("Cross-validation · model selection evidence", cv, cv_text, list(labels)), _evaluation_panel("Held-out test · one-time estimate", test, test_text, list(labels))], className="evaluation-grid"),
        _section("Evaluation provenance", html.Div([
            html.P(f"Positive class: {run.manifest.get('label_mapping', {}).get('malignant', 'not available in run artifact')} (malignant)."),
            html.P(f"Fitness definition: {run.manifest.get('fitness_definition', 'not available in run artifact')}"),
            html.P("Held-out data is used once after feature selection, according to the run's saved holdout policy."),
            html.P(f"Holdout policy: {run.manifest.get('holdout_policy', 'not available in run artifact')}"),
        ], className="provenance-copy")),
    ]


def dataset_view(dataset: DatasetData | None, error: str | None) -> list[Any]:
    if dataset is None:
        return [_empty("Local dataset unavailable", error or "Place breast_cancer.csv and dataset_metadata.json in WORKSPACE/data/.")]
    matrix = dataset.values
    finite_counts = np.isfinite(matrix).sum(axis=0)
    means = np.nanmean(matrix, axis=0)
    medians = np.nanmedian(matrix, axis=0)
    stds = np.nanstd(matrix, axis=0, ddof=1)
    mins = np.nanmin(matrix, axis=0)
    maxs = np.nanmax(matrix, axis=0)
    stats = []
    for i, feature in enumerate(dataset.columns[1:]):
        stats.append({"feature": feature, "unit": "not documented", "count": int(finite_counts[i]),
                      "missing": int(len(matrix) - finite_counts[i]), "mean": float(means[i]), "std": float(stds[i]),
                      "median": float(medians[i]), "min": float(mins[i]), "max": float(maxs[i])})
    numeric_columns = list(dataset.columns[1:])
    correlation = np.corrcoef(matrix, rowvar=False)
    corrfig = go.Figure(go.Heatmap(z=correlation, x=numeric_columns, y=numeric_columns,
                                   colorscale=[[0, "#2f80ff"], [0.5, "#162a40"], [1, TEAL]], zmin=-1, zmax=1,
                                   colorbar={"title": "Pearson r"}, hovertemplate="%{y} × %{x}<br>r = %{z:.3f}<extra></extra>"))
    _style_heatmap(corrfig)
    counts = {label: dataset.labels.count(label) for label in ["malignant", "benign"]}
    records = []
    for index, row in enumerate(dataset.rows, start=1):
        records.append({"sample": index, **row})
    table = dash_table.DataTable(
        data=records, columns=[{"name": "Sample", "id": "sample"}] + [{"name": c, "id": c, "type": "numeric", "format": {"specifier": ".5g"}} for c in dataset.columns],
        page_action="native", page_size=12, filter_action="native", sort_action="native",
        style_table={"overflowX": "auto", "minWidth": "100%"},
        style_header={"backgroundColor": "#182d43", "color": "#bdcadd", "border": f"1px solid {LINE}", "fontWeight": 650, "textAlign": "left", "padding": "9px"},
        style_cell={"backgroundColor": "#102136", "color": WHITE, "border": f"1px solid {LINE}", "padding": "8px", "fontSize": "12px", "minWidth": "100px", "maxWidth": "220px"},
    )
    stats_table = dash_table.DataTable(
        data=stats, columns=[{"name": "Feature", "id": "feature"}, {"name": "Units", "id": "unit"}, {"name": "N", "id": "count"}, {"name": "Missing", "id": "missing"}] + [
            {"name": label, "id": key, "type": "numeric", "format": {"specifier": ".5g"}} for label, key in [("Mean", "mean"), ("SD", "std"), ("Median", "median"), ("Min", "min"), ("Max", "max")]],
        page_action="native", page_size=15, sort_action="native",
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#182d43", "color": "#bdcadd", "border": f"1px solid {LINE}", "padding": "8px", "textAlign": "left"},
        style_cell={"backgroundColor": "#102136", "color": WHITE, "border": f"1px solid {LINE}", "padding": "8px", "fontSize": "12px"},
    )
    meta = dataset.metadata
    return [
        html.Div([_metric("Dataset", str(meta.get("name", "not available")), f"UCI dataset ID {meta.get('dataset_id', 17)}"), _metric("Samples", str(len(dataset.rows)), "local cached CSV"), _metric("Features", "30", "numerical measurements"), _metric("Missing values", "yes" if meta.get("missing_values_found") else "none detected", "inspected from local rows")], className="metric-grid"),
        html.Div([html.H3("Dataset provenance"), html.P("Source: UCI Machine Learning Repository, Breast Cancer Wisconsin (Diagnostic), dataset ID 17."), html.P(f"Attribution: {meta.get('attribution', 'not available in dataset metadata')} · License: {meta.get('license', 'not available in dataset metadata')} · DOI: {meta.get('doi', 'not available in dataset metadata')}"), html.P(f"SHA-256: {meta.get('sha256', 'not available in dataset metadata')}")], className="panel provenance-copy"),
        _section("Class distribution", html.Div([_metric("Malignant", str(counts["malignant"]), "positive class"), _metric("Benign", str(counts["benign"]), "negative class")], className="metric-grid"), "Original diagnostic labels; benign = 0, malignant = 1 in the GA manifest."),
        _section("Feature definitions and descriptive statistics", stats_table, "Feature names follow the canonical dataset order. Units are not documented in the provided dataset metadata."),
        _section("Pairwise correlations", _graph(corrfig, height=860, class_name="plot heatmap-plot"), "Pearson correlation across locally stored numerical measurements."),
        _section("Browse dataset rows", table, "Search, sort and page through the local CSV. Dashboard access never downloads or synchronizes data."),
    ]


def _compatibility(a: RunData, b: RunData) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ma, mb = a.manifest, b.manifest
    checks = [
        (ma.get("dataset", {}).get("sha256"), mb.get("dataset", {}).get("sha256"), "dataset checksum"),
        (ma.get("feature_order"), mb.get("feature_order"), "feature order"),
        (ma.get("fitness_definition"), mb.get("fitness_definition"), "fitness formula"),
        (ma.get("classifier"), mb.get("classifier"), "classifier configuration"),
        (ma.get("cross_validation"), mb.get("cross_validation"), "validation design"),
        (ma.get("holdout_policy"), mb.get("holdout_policy"), "held-out policy"),
    ]
    reasons.extend(label for left, right, label in checks if left != right)
    parameter_keys = ("population", "mutation_rate", "crossover_rate", "elite_count")
    if any(ma.get("parameters", {}).get(key) != mb.get("parameters", {}).get(key) for key in parameter_keys):
        reasons.append("GA search settings")
    seeds = (ma.get("parameters", {}).get("seed"), mb.get("parameters", {}).get("seed"))
    if seeds[0] != seeds[1]:
        reasons.append("random seed")
    return not reasons, reasons


def compare_view(workspace: WorkspaceData, run_a_id: str | None, run_b_id: str | None) -> list[Any]:
    a, b = workspace.runs.get(run_a_id or ""), workspace.runs.get(run_b_id or "")
    if not a or not b:
        return [_empty("Choose two readable runs", "Select any two discovered run directories using the comparison controls above.")]
    generations_a, generations_b = list(a.generations), list(b.generations)
    fig = go.Figure()
    for run, generations, best_color, mean_color in [(a, generations_a, BLUE, TEAL), (b, generations_b, "#a18bff", "#f0b35b")]:
        fig.add_trace(go.Scatter(x=generations, y=[float(run.generations[g].summary["best_fitness"]) for g in generations],
                                 name=f"{run.run_id} · best", mode="lines", line={"color": best_color, "width": 2.6}))
        fig.add_trace(go.Scatter(x=generations, y=[float(run.generations[g].summary["mean_fitness"]) for g in generations],
                                 name=f"{run.run_id} · mean", mode="lines", line={"color": mean_color, "width": 2, "dash": "dot"}))
    fig.update_layout(xaxis_title="Generation", yaxis_title="Composite fitness score (unitless)", hovermode="x unified")
    last_a, last_b = a.generations[max(generations_a)], b.generations[max(generations_b)]
    winner_a, winner_b = last_a.best_candidate, last_b.best_candidate
    mask_a, mask_b = winner_a["chromosome"], winner_b["chromosome"]
    overlap = sum(x == "1" and y == "1" for x, y in zip(mask_a, mask_b, strict=True))
    union = sum(x == "1" or y == "1" for x, y in zip(mask_a, mask_b, strict=True))
    jaccard = overlap / union if union else 1.0
    comparable, reasons = _compatibility(a, b)
    warning = html.Div([
        html.Strong("Comparable setup" if comparable else "Comparability warning"),
        html.P("Both runs match on dataset, feature order, fitness formula, model and validation design; seed differences remain visible." if comparable else "These runs differ in: " + ", ".join(reasons) + ". Last-generation values should not be interpreted as a superiority claim."),
    ], className="research-banner" if comparable else "research-banner warning")
    overlap_feature_names = [name for name, bit_a, bit_b in zip(a.manifest["feature_order"], mask_a, mask_b, strict=True) if bit_a == "1" and bit_b == "1"]
    mask_content = html.Div([
        html.Div([html.H3(f"{a.run_id} · generation {last_a.number}"), _feature_mask(mask_a, a.manifest["feature_order"], winner_a["candidate_id"], last_a.number, BLUE), html.P(f"Fitness {_score(winner_a['fitness'])} · {winner_a['selected_feature_count']} features")]),
        html.Div([html.H3(f"{b.run_id} · generation {last_b.number}"), _feature_mask(mask_b, b.manifest["feature_order"], winner_b["candidate_id"], last_b.number, TEAL), html.P(f"Fitness {_score(winner_b['fitness'])} · {winner_b['selected_feature_count']} features")]),
    ], className="comparison-masks")
    metrics_a = a.model_metrics.get("held_out_test_metrics", {})
    metrics_b = b.model_metrics.get("held_out_test_metrics", {})
    eval_rows = []
    for label, key in [("Malignant sensitivity", "malignant_sensitivity"), ("Specificity", "specificity"), ("Balanced accuracy", "balanced_accuracy"), ("Accuracy", "accuracy")]:
        eval_rows.append({"metric": label, a.run_id: _metric_value(metrics_a, key), b.run_id: _metric_value(metrics_b, key)})
    eval_table = dash_table.DataTable(data=eval_rows, columns=[{"name": name, "id": name} for name in ["metric", a.run_id, b.run_id]],
                                      style_header={"backgroundColor": "#182d43", "color": "#bdcadd", "border": f"1px solid {LINE}", "padding": "8px", "textAlign": "left"},
                                      style_cell={"backgroundColor": "#102136", "color": WHITE, "border": f"1px solid {LINE}", "padding": "9px"})
    time_a = _time_to_best(a)
    time_b = _time_to_best(b)
    return [
        warning,
        _section("Fitness history", _graph(fig, height=370), f"{a.run_id}: {len(generations_a)} committed generations, seed {a.manifest.get('parameters', {}).get('seed', 'not available')}. {b.run_id}: {len(generations_b)} committed generations, seed {b.manifest.get('parameters', {}).get('seed', 'not available')}.") ,
        _metric_grid([
            _metric("Best-mask overlap", f"{overlap} features", "selected in both runs"),
            _metric("Jaccard similarity", f"{jaccard:.1%}", f"intersection ÷ {union} features in either mask"),
            _metric("Time to best", time_a, f"{a.run_id}; first generation reaching final best"),
            _metric("Time to best", time_b, f"{b.run_id}; first generation reaching final best"),
        ]),
        _section("Final committed best masks", html.Div([mask_content, html.P("Shared selected features: " + (", ".join(overlap_feature_names) if overlap_feature_names else "none"), className="section-note")]), "Masks come from each run's final fully committed generation."),
        _section("Held-out evaluation metrics", eval_table, "One-time saved test results are shown only for the held-out split; unsupported metrics display 'not available in run artifact'."),
        html.P("Different random seeds can produce different candidate histories. Dataset, validation and fitness setup are checked above. A higher last-generation fitness alone does not establish superiority.", className="science-note"),
    ]


def _time_to_best(run: RunData) -> str:
    if not run.generations:
        return "not available in run artifact"
    final_best = max(float(generation.summary["best_fitness"]) for generation in run.generations.values())
    for generation in run.generations.values():
        if math.isclose(float(generation.summary["best_fitness"]), final_best, rel_tol=1e-10, abs_tol=1e-12):
            elapsed = generation.summary.get("elapsed_seconds")
            try:
                return f"{float(elapsed):.2f} s" if elapsed not in (None, "") else "not available in run artifact"
            except (TypeError, ValueError):
                return "not available in run artifact"
    return "not available in run artifact"


def render_view(view: str, workspace: WorkspaceData, run_id: str | None, generation_number: int,
                candidate_id: str | None, compare_candidate_id: str | None,
                compare_a: str | None, compare_b: str | None) -> tuple[str, list[Any]]:
    titles = {"overview": "Overview", "evolution": "Evolution", "features": "Feature Selection", "evaluation": "Model Evaluation", "dataset": "Dataset", "compare": "Compare Runs"}
    title = titles.get(view, titles["overview"])
    if view == "dataset":
        return title, dataset_view(workspace.dataset, workspace.dataset_error)
    if view == "compare":
        return title, compare_view(workspace, compare_a, compare_b)
    run = workspace.runs.get(run_id or "")
    if not run:
        error = workspace.errors.get(run_id or "")
        if error:
            return title, [_empty(f"Cannot read {run_id}", error, kind="empty-state error-state")]
        return title, [_empty("No experiment runs found", "Run ./run-demo --workspace ./agentic-space, then return here. The dashboard reads saved files only and never evaluates the model.")]
    if not run.generations:
        return title, [_empty("No complete generation yet", f"Run status is {run.status}. The dashboard waits for the manifest commit boundary before showing candidate history.")]
    generation = run.generations.get(generation_number) or run.generations[run.committed_generation]
    candidates = {candidate["candidate_id"]: candidate for candidate in generation.candidates}
    selected = candidates.get(candidate_id or "", generation.best_candidate)
    if view == "overview":
        content = overview_view(run, generation, selected)
    elif view == "evolution":
        content = evolution_view(run, generation, selected, compare_candidate_id)
    elif view == "features":
        content = feature_view(run, generation, selected, compare_candidate_id)
    elif view == "evaluation":
        content = evaluation_view(run)
    else:
        content = overview_view(run, generation, selected)
    if run.warnings:
        content.insert(0, html.Div([html.Strong("History warning"), html.Ul([html.Li(item) for item in run.warnings])], className="research-banner warning"))
    return title, content
