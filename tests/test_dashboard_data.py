import csv
import json
from pathlib import Path

import pytest

from velacare.dashboard.data import DashboardDataError, load_run
from velacare.dataset import FEATURE_NAMES
from velacare.persistence import CSV_FIELDS


def _write_run(root: Path, *, committed=1, include_uncommitted=False, drop_last=False) -> Path:
    run_dir = root / "run_001"
    run_dir.mkdir(parents=True)
    chromosomes = [
        "1" + "0" * 29,
        "01" + "0" * 28,
        "001" + "0" * 27,
        "110" + "0" * 27,
    ]
    scores = [0.6, 0.7, 0.8, 0.5]
    candidates = []
    for position, (chromosome, score) in enumerate(zip(chromosomes, scores, strict=True), start=1):
        candidates.append({
            "schema_version": "1.0.0",
            "run_id": "run_001",
            "generation": 1,
            "candidate_id": f"g001_c{position:03d}",
            "chromosome": chromosome,
            "selected_features": [name for name, bit in zip(FEATURE_NAMES, chromosome, strict=True) if bit == "1"],
            "selected_feature_count": chromosome.count("1"),
            "fitness": score,
            "fitness_components": {"cv": score},
            "cv_metrics": {"malignant_sensitivity": score},
            "parents": [],
            "operator": "initial",
            "evaluation_cache_hit": False,
        })
    if include_uncommitted:
        for position, item in enumerate(list(candidates), start=1):
            pending = dict(item)
            pending["generation"] = 2
            pending["candidate_id"] = f"g002_c{position:03d}"
            candidates.append(pending)
    if drop_last:
        candidates = candidates[:-1]
    (run_dir / "candidate_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in candidates), encoding="utf-8")
    summary = {
        "run_id": "run_001",
        "generation": 1,
        "population_size": 4,
        "best_candidate_id": "g001_c003",
        "best_fitness": 0.8,
        "mean_fitness": 0.65,
        "min_fitness": 0.5,
        "median_fitness": 0.65,
        "best_feature_count": 1,
        "best_chromosome": chromosomes[2],
        "best_selected_features": json.dumps(FEATURE_NAMES[2:3]),
        "distinct_mask_count": 4,
        "diversity_entropy_bits": 2.811278124459133,
        "average_hamming_distance": 11 / 6,
        "elapsed_seconds": 1.0,
        "generation_seconds": 0.1,
    }
    with (run_dir / "generation_history.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerow(summary)
        if committed > 1 or include_uncommitted:
            second_summary = dict(summary, generation=2, best_candidate_id="g002_c003")
            writer.writerow(second_summary)
    manifest = {
        "schema_version": "1.0.0",
        "run_id": "run_001",
        "status": "running",
        "last_fully_committed_generation": committed,
        "parameters": {"population": 4, "generations": 2, "seed": 7},
        "feature_order": list(FEATURE_NAMES),
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def test_load_run_reconstructs_full_population_and_diversity(tmp_path):
    run = load_run(_write_run(tmp_path))
    generation = run.generations[1]
    assert run.committed_generation == 1
    assert len(generation.candidates) == 4
    assert generation.best_candidate["candidate_id"] == "g001_c003"
    assert generation.feature_frequencies[:3] == (0.5, 0.5, 0.25)
    assert generation.diversity["unique_chromosome_ratio"] == 1.0
    assert generation.diversity["mean_pairwise_hamming_distance"] == pytest.approx(11 / 6)


def test_uncommitted_population_is_not_exposed(tmp_path):
    run = load_run(_write_run(tmp_path, include_uncommitted=True))
    assert list(run.generations) == [1]
    assert len(run.generations[1].candidates) == 4
    assert any("Ignored 4 candidate" in warning for warning in run.warnings)


def test_new_commit_boundary_exposes_generation_on_next_read(tmp_path):
    run_dir = _write_run(tmp_path, committed=1, include_uncommitted=True)
    first = load_run(run_dir)
    assert first.committed_generation == 1
    (run_dir / "run_manifest.json").write_text(json.dumps({
        **first.manifest,
        "last_fully_committed_generation": 2,
    }), encoding="utf-8")
    second = load_run(run_dir)
    assert second.committed_generation == 2
    assert len(second.generations[2].candidates) == 4


def test_committed_population_with_missing_candidate_is_reported(tmp_path):
    run_dir = _write_run(tmp_path, drop_last=True)
    with pytest.raises(DashboardDataError, match="contains 3 of 4 expected candidates"):
        load_run(run_dir)
