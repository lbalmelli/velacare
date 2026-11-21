#!/usr/bin/env python3
"""Create a VelaCare research report from existing on-disk GA run artifacts.

This helper is intentionally conservative: if a result is absent it says 'Not available',
never substitutes the illustrative screenshot metrics. It does not run a classifier or GA.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pptx import Presentation
from velacare.reader import validate_run_history

NAVY = '#0B1422'
BLUE = '#2F80FF'
TEAL = '#59CBB8'
WHITE = '#F4F8FC'
SLATE = '#9CB3C9'


def read_json(path: Path, required: bool = False) -> Any:
    if not path.exists():
        if required:
            raise FileNotFoundError(f'Required source file missing: {path}')
        return {}
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f'Cannot make a sourced report without generation history: {path}')
    with path.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError('generation_history.csv has no completed generations')
    return rows


def pick(row: dict, *names: str, fallback: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ''):
            return value
    return fallback


def number(v: Any) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def safe_label(v: Any, fallback: str = 'Not available') -> str:
    return str(v) if v not in (None, '') else fallback


def fmt_float(v: Any) -> str:
    n = number(v)
    return 'Not available' if n is None else f'{n:.3f}'


def normalized_history(rows: list[dict]) -> tuple[list[int], list[float | None], list[float | None]]:
    gens, best, mean = [], [], []
    for i, row in enumerate(rows, 1):
        g = number(pick(row, 'generation', 'generation_number', 'gen', fallback=i))
        gens.append(int(g if g is not None else i))
        best.append(number(pick(row, 'best_fitness', 'fitness_best', 'best_score')))
        mean.append(number(pick(row, 'mean_fitness', 'average_fitness', 'avg_fitness', 'fitness_mean')))
    if any(a >= b for a, b in zip(gens, gens[1:])):
        raise ValueError('Non-monotonic or duplicate generation numbers in history')
    return gens, best, mean


def get_best_candidates(path: Path) -> Any:
    return read_json(path)


def get_winner(best_data: Any, last_gen: int) -> dict:
    if isinstance(best_data, dict):
        for key in ('per_generation', 'generations', 'candidates', 'best_candidates'):
            if isinstance(best_data.get(key), (list, dict)):
                return get_winner(best_data[key], last_gen)
        for key in ('final_best', 'best_final', 'best_candidate'):
            if isinstance(best_data.get(key), dict):
                return best_data[key]
        for key in (str(last_gen), f'G{last_gen:02d}'):
            if isinstance(best_data.get(key), dict):
                return best_data[key]
        return best_data
    if isinstance(best_data, list):
        matching = [row for row in best_data if isinstance(row, dict) and str(pick(row, 'generation', 'generation_number', 'gen', fallback='')) == str(last_gen)]
        return matching[-1] if matching else (best_data[-1] if best_data else {})
    return {}


def metrics_summary(section: Any) -> str:
    if not isinstance(section, dict) or not section:
        return 'Not available in run artifacts'
    aliases = {
        'balanced_accuracy': 'Balanced accuracy',
        'accuracy': 'Accuracy',
        'sensitivity_malignant': 'Malignant sensitivity',
        'malignant_sensitivity': 'Malignant sensitivity',
        'sensitivity': 'Sensitivity',
        'specificity': 'Specificity',
        'roc_auc': 'ROC AUC',
    }
    lines=[]
    for key, label in aliases.items():
        val=number(section.get(key))
        if val is not None and label not in [x.split(':')[0] for x in lines]:
            lines.append(f'{label}: {100*val:.1f}%' if 0 <= val <= 1 else f'{label}: {val:.3f}')
    return '\n'.join(lines[:5]) or 'Metrics are not available in a recognized schema'


def text_replace(prs: Presentation, mapping: dict[str, str]) -> None:
    """Replace template tokens inside text runs to preserve typography and text colors."""
    for sl in prs.slides:
        for shape in sl.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    current = run.text
                    updated = current
                    for key, value in mapping.items():
                        updated = updated.replace('{{'+key+'}}', value)
                    if updated != current:
                        run.text = updated


def chart_evolution(gens, best, mean) -> io.BytesIO | None:
    if all(v is None for v in best) and all(v is None for v in mean):
        return None
    fig, ax=plt.subplots(figsize=(10.8,3.2),dpi=170)
    fig.patch.set_facecolor(NAVY); ax.set_facecolor('#122338')
    if any(v is not None for v in best):
        ax.plot(gens, [float('nan') if v is None else v for v in best], color=BLUE, linewidth=3, label='Best fitness')
    if any(v is not None for v in mean):
        ax.plot(gens, [float('nan') if v is None else v for v in mean], color=TEAL, linewidth=2.5, label='Mean fitness')
    ax.grid(alpha=.18,color='white'); ax.tick_params(colors=SLATE,labelsize=9)
    for s in ax.spines.values(): s.set_color('#35516F')
    ax.set_xlabel('Generation',color=WHITE); ax.set_ylabel('Fitness (optimization score)',color=WHITE)
    lg=ax.legend(frameon=False,loc='lower right')
    if lg:
        for t in lg.get_texts(): t.set_color(WHITE)
    fig.subplots_adjust(left=.08,right=.93,top=.98,bottom=.32,hspace=.45)
    bio=io.BytesIO(); fig.savefig(bio,format='png',dpi=170,transparent=False,facecolor=fig.get_facecolor());plt.close(fig);bio.seek(0)
    return bio


def chart_mask(winner: dict, feature_order: list[str]) -> io.BytesIO | None:
    chrom=pick(winner,'chromosome','mask','feature_mask','bits')
    if isinstance(chrom,str):
        bits=[int(ch) for ch in chrom if ch in '01']
    elif isinstance(chrom,list) and all(v in (0,1,True,False) for v in chrom):
        bits=list(map(int,chrom))
    else:
        return None
    if len(bits)!=30: return None
    fig,ax=plt.subplots(figsize=(10.7,2.2),dpi=170)
    fig.patch.set_facecolor('#F4F8FC'); ax.set_facecolor('#F4F8FC')
    for i,b in enumerate(bits):
        ax.add_patch(plt.Rectangle((i,0),.85,1,facecolor=TEAL if b else '#C3D1E1',edgecolor='white',linewidth=1))
    ax.set_xlim(-.05,30);ax.set_ylim(0,1.1);ax.set_yticks([])
    ax.set_xticks(range(0,30,5));ax.set_xticklabels([str(i+1) for i in range(0,30,5)],color='#1B3048')
    ax.set_xlabel('Measurement position (canonical dataset order)',color='#1B3048')
    for side in ax.spines.values():side.set_visible(False)
    fig.tight_layout();bio=io.BytesIO();fig.savefig(bio,format='png',dpi=170,facecolor=fig.get_facecolor());plt.close(fig);bio.seek(0)
    return bio


def chart_feature_evolution(run_dir: Path, manifest: dict) -> io.BytesIO | None:
    """Render the final best mask and every persisted generation's selection frequency."""
    try:
        from velacare.dashboard.data import load_run
        run = load_run(run_dir)
    except Exception as exc:
        raise ValueError(f'Cannot validate feature-selection history for report: {exc}') from exc
    generations = list(run.generations)
    features = manifest.get('feature_order', [])
    if not generations or len(features) != 30:
        return None
    winner = run.generations[generations[-1]].best_candidate
    frequencies = np.asarray([run.generations[g].feature_frequencies for g in generations], dtype=float)
    bits = np.asarray([int(bit) for bit in winner['chromosome']], dtype=int)[None, :]
    from matplotlib.colors import ListedColormap
    fig, (mask_ax, frequency_ax) = plt.subplots(2, 1, figsize=(10.7, 2.8), dpi=170,
                                                gridspec_kw={'height_ratios': [0.32, 1.0], 'hspace': 0.55})
    fig.patch.set_facecolor('#F4F8FC')
    mask_ax.set_facecolor('#F4F8FC')
    mask_ax.imshow(bits, aspect='auto', interpolation='nearest', cmap=ListedColormap(['#C3D1E1', TEAL]), vmin=0, vmax=1)
    mask_ax.set_yticks([0], ['Final best'])
    mask_ax.tick_params(axis='x', bottom=False, labelbottom=False)
    mask_ax.tick_params(axis='y', colors='#1B3048', labelsize=8, length=0)
    mask_ax.set_xticks(np.arange(-.5, 30, 1), minor=True)
    mask_ax.grid(which='minor', color='white', linewidth=1)
    mask_ax.set_xlim(-.5, 29.5)
    frequency_ax.set_facecolor('#F4F8FC')
    mesh = frequency_ax.imshow(frequencies, aspect='auto', interpolation='nearest', cmap='GnBu', vmin=0, vmax=1, origin='upper')
    frequency_ax.set_ylabel('Generation', color='#1B3048', fontsize=8)
    frequency_ax.set_xlabel('Feature (canonical dataset order)', color='#1B3048', fontsize=8)
    frequency_ax.set_yticks(np.unique(np.linspace(0, len(generations) - 1, min(5, len(generations))).astype(int)),
                            [str(generations[index]) for index in np.unique(np.linspace(0, len(generations) - 1, min(5, len(generations))).astype(int))])
    frequency_ax.set_xticks(range(30), features, rotation=60, ha='right', fontsize=6)
    frequency_ax.tick_params(axis='both', colors='#1B3048', labelsize=7, length=0)
    cbar = fig.colorbar(mesh, ax=frequency_ax, fraction=.02, pad=.01)
    cbar.set_label('Candidate share', color='#1B3048', fontsize=7)
    cbar.ax.tick_params(colors='#1B3048', labelsize=6)
    for ax in (mask_ax, frequency_ax):
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.subplots_adjust(left=.08,right=.90,top=.98,bottom=.28,hspace=.55)
    bio = io.BytesIO()
    fig.savefig(bio, format='png', dpi=170, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close(fig)
    bio.seek(0)
    return bio


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description='Generate a sourced VelaCare-branded PPTX from persisted experiment files.')
    parser.add_argument('--run',required=True,help='Path to run_NNN directory')
    parser.add_argument('--output',required=True,help='Destination .pptx (typically WORKSPACE/presentations/)')
    parser.add_argument('--brand-dir',default=str(Path(__file__).resolve().parents[1]/'brand'))
    args=parser.parse_args(argv)
    run=Path(args.run).expanduser().resolve(); brand=Path(args.brand_dir).expanduser().resolve()
    if not run.is_dir(): parser.error(f'Run directory not found: {run}')
    manifest=read_json(run/'run_manifest.json',required=True)
    if manifest.get('schema_version') is None:
        raise ValueError('run_manifest.json does not record a schema version')
    history_report=validate_run_history(run)
    history=load_history(run/'generation_history.csv')
    gens,best,mean=normalized_history(history)
    cutoff=int(manifest.get('last_fully_committed_generation', manifest.get('last_completed_generation', 0)))
    vals=[(g,b,m,r) for g,b,m,r in zip(gens,best,mean,history) if g<=cutoff]
    if not vals: raise ValueError('No fully committed generations according to run manifest')
    gens,best,mean,history=map(list,zip(*vals))
    if history_report['completed_generations'] != cutoff:
        raise ValueError('Validated history and manifest commit boundary disagree')
    best_data=get_best_candidates(run/'best_candidates.json')
    winner=get_winner(best_data,gens[-1]); metrics=read_json(run/'model_metrics.json')
    params=manifest.get('parameters',{}) if isinstance(manifest.get('parameters'),dict) else {}
    def param(k): return pick(params,k,f'--{k}',fallback=manifest.get(k))
    feature_count=pick(winner,'selected_feature_count','n_features','feature_count',fallback=pick(history[-1],'best_feature_count','features_selected','best_features'))
    # Correctly handle absent metrics, no assumed result percentages.
    cv=pick(metrics,'cross_validation','cv_metrics','cv',fallback={}) if isinstance(metrics,dict) else {}
    held=pick(metrics,'held_out_test_metrics','held_out_test','test_metrics','held_out','test',fallback={}) if isinstance(metrics,dict) else {}
    if not isinstance(cv,dict): cv={}
    if not isinstance(held,dict): held={}
    r_id=safe_label(manifest.get('run_id',run.name))
    now=datetime.now(timezone.utc).strftime('%Y-%m-%d')
    status=safe_label(manifest.get('status'),'unknown')
    seed=safe_label(param('seed'))
    fitness=safe_label(manifest.get('fitness_definition'), 'Fitness definition not recorded')
    featu_names=pick(winner,'selected_features','selected_feature_names',fallback=[])
    if not isinstance(featu_names,list): featu_names=[]
    if feature_count is None and featu_names:feature_count=len(featu_names)
    dataset_info=manifest.get('dataset',{}) if isinstance(manifest.get('dataset'),dict) else {}
    cv_info=manifest.get('cross_validation',{}) if isinstance(manifest.get('cross_validation'),dict) else {}
    evolution=chart_evolution(gens,best,mean)
    feature_evolution=chart_feature_evolution(run,manifest)
    classifier=manifest.get('classifier',{})
    if isinstance(classifier,dict):
        pipeline=' + '.join(classifier.get('pipeline',[])) or 'not available in run artifact'
        classifier_summary=f"{pipeline} (solver={safe_label(classifier.get('solver'))}, class_weight={safe_label(classifier.get('class_weight'))}, C={safe_label(classifier.get('C'))})"
    else:
        classifier_summary=safe_label(classifier,'Classifier not recorded')
    mapping={
        'STUDY_TITLE':'Genetic feature selection\nResearch report',
        'RUN_ID':r_id,'REPORT_DATE':now,'SEED':seed,
        'N_GENERATIONS':str(len(gens)),
        'BEST_FITNESS':fmt_float(best[-1]),
        'FEATURE_COUNT':safe_label(feature_count),
        'SUMMARY_TEXT':f'{len(gens)} fully committed generations are available in the {status} run {r_id}. The best recorded fitness score was {fmt_float(best[-1])}. Selected feature count: {safe_label(feature_count)}. This is exploratory optimization, not a clinical diagnosis.',
        'DATASET':safe_label(dataset_info.get('name'),'UCI Wisconsin Diagnostic dataset (ID 17)'),
        'ALGORITHM':'Genetic algorithm  /  '+classifier_summary,
        'POPULATION':safe_label(param('population')),
        'VALIDATION':f"{safe_label(cv_info.get('method'), 'not available')} · {safe_label(cv_info.get('folds'), 'not available')} folds; {safe_label(cv_info.get('data_scope'), 'data scope not documented')}",
        'METHOD_DETAIL':f'Fitness: {fitness}. Selection operates on 30-feature masks with held-out testing reserved for final evaluation. Dataset checksum: {safe_label(dataset_info.get("sha256"))}.',
        'EVOLUTION_CHART':'' if evolution else 'not available in run artifact',
        'FEATURE_CHART':'' if feature_evolution else 'not available in run artifact',
        'FEATURE_EXPLANATION':'Final best candidate selected: '+(', '.join(featu_names[:8])+(f' (+{len(featu_names)-8} more)' if len(featu_names)>8 else '') if featu_names else 'Feature names not available'),
        'CV_METRICS':metrics_summary(cv),
        'TEST_METRICS':metrics_summary(held),
        'EVALUATION_CAVEAT':'CV guides model selection; held-out results are distinct and do not establish clinical generalizability. Never equate fitness with accuracy.',
        'LIMITATIONS':'Historical public dataset; possible selection bias and distribution shift; unknown prospective clinical performance; no external cohort or prospective validation. The results are research-only.',
        'REPRODUCIBILITY':f'Run {r_id} • seed {seed} • manifest status {status} • {len(gens)} committed generations • schema {manifest.get("schema_version")}. Dataset and software provenance in run_manifest.json.'
    }
    template=brand/'VelaCare_Research_Reporting_Template.pptx'
    if not template.exists(): raise FileNotFoundError(f'Brand template missing: {template}')
    prs=Presentation(str(template));text_replace(prs,mapping)
    if evolution:
        from pptx.util import Inches
        prs.slides[3].shapes.add_picture(evolution, Inches(1.04), Inches(2.49), width=Inches(11.18), height=Inches(3.16))
    feat_order=manifest.get('feature_order',[]) if isinstance(manifest.get('feature_order'),list) else []
    mask_img=feature_evolution
    if mask_img:
        from pptx.util import Inches
        prs.slides[4].shapes.add_picture(mask_img, Inches(1.07), Inches(2.82), width=Inches(11.05), height=Inches(2.75))
    output=Path(args.output).expanduser();output.parent.mkdir(parents=True,exist_ok=True)
    prs.save(str(output))
    print(f'Wrote: {output}')
    print(f'Source: {run} / {len(gens)} complete generations / run {r_id}')
    return 0


if __name__=='__main__':
    sys.exit(main())
