import hashlib

import numpy as np
import pytest
from sklearn.datasets import make_classification

from velacare.evaluation import evaluate_cross_validation, evaluate_holdout, split_dataset
from velacare.genetics import evolve
from velacare.persistence import commit_generation, create_run, save_final_metrics, update_manifest
from velacare.reader import HistoryError, reconstruct_generation, validate_run_history


def synthetic_data():
    X, y = make_classification(
        n_samples=180,
        n_features=30,
        n_informative=8,
        n_redundant=3,
        n_repeated=0,
        n_classes=2,
        class_sep=1.1,
        random_state=41,
    )
    return X.astype(float), y.astype(np.int8)


def create_test_run(tmp_path, *, generations=3, population=8, fail_after_first=False):
    X, y = synthetic_data()
    X_train, X_test, y_train, y_test = split_dataset(X, y, seed=9)
    metadata = {
        "dataset_id": 17,
        "name": "synthetic test input",
        "sha256": hashlib.sha256(X.tobytes() + y.tobytes()).hexdigest(),
        "sample_count": len(y),
        "feature_count": 30,
        "source_url": "test fixture",
        "doi": "test",
    }
    run_dir, manifest = create_run(
        tmp_path,
        dataset_metadata=metadata,
        parameters={"generations": generations, "population": population, "seed": 9},
        cv_config={"method": "StratifiedKFold", "folds": 3, "data_scope": "training split only"},
    )
    evaluator = lambda mask: evaluate_cross_validation(mask, X_train, y_train, seed=9, folds=3)

    def save_generation(summary, candidates):
        nonlocal manifest
        manifest = commit_generation(run_dir, manifest, summary, candidates)

    def progress(generation, _total, _completed, _records, _elapsed):
        if fail_after_first and generation == 2:
            raise RuntimeError("simulated interruption during generation 2")

    if fail_after_first:
        return run_dir, manifest, X_train, X_test, y_train, y_test, evaluator, save_generation, progress

    summaries, populations, cache_misses = evolve(
        population_size=population,
        generations=generations,
        seed=9,
        mutation_rate=0.04,
        crossover_rate=0.8,
        evaluator=evaluator,
        on_generation=save_generation,
    )
    best = summaries[-1]["best_candidate"]
    mask = np.fromiter((int(bit) for bit in best["chromosome"]), dtype=np.uint8)
    metrics = {
        "candidate_id": best["candidate_id"],
        "selected_feature_count": best["selected_feature_count"],
        "selected_features": best["selected_features"],
        "chromosome": best["chromosome"],
        "cv_fitness": best["fitness"],
        "cv_metrics": best["cv_metrics"],
        "held_out_test_metrics": evaluate_holdout(mask, X_train, y_train, X_test, y_test, seed=9),
        "test_split": {"training_samples": len(y_train), "held_out_samples": len(y_test)},
    }
    save_final_metrics(run_dir, run_dir.name, metrics)
    manifest = update_manifest(
        run_dir,
        manifest,
        status="completed",
        last_fully_committed_generation=generations,
        cache_unique_chromosomes_evaluated=cache_misses,
    )
    return run_dir, manifest, summaries, populations, metrics


def test_end_to_end_history_reconstructs_every_candidate_from_files(tmp_path):
    run_dir, _manifest, summaries, _populations, metrics = create_test_run(tmp_path)
    report = validate_run_history(run_dir)
    assert report == {
        "run_id": "run_001",
        "status": "completed",
        "completed_generations": 3,
        "candidate_records": 24,
        "reconstructed_generations": [1, 2, 3],
    }
    assert set(metrics["cv_metrics"]) == set(metrics["held_out_test_metrics"])
    assert "confusion_matrix" in metrics["cv_metrics"]
    assert "confusion_matrix" in metrics["held_out_test_metrics"]
    for generation in range(1, 4):
        restored = reconstruct_generation(run_dir, generation)
        assert len(restored["candidates"]) == 8
        assert len(restored["fitness_values"]) == 8
        assert restored["best_candidate"]["candidate_id"] == summaries[generation - 1]["best_candidate_id"]
        for candidate in restored["candidates"]:
            selected = [name for name, bit in zip(
                __import__("json").loads((run_dir / "run_manifest.json").read_text())["feature_order"],
                candidate["chromosome"],
                strict=True,
            ) if bit == "1"]
            assert selected == candidate["selected_features"]


def test_interruption_retains_only_committed_generations(tmp_path):
    run_dir, manifest, X_train, X_test, y_train, y_test, evaluator, save_generation, progress = create_test_run(
        tmp_path, generations=3, population=8, fail_after_first=True
    )
    with pytest.raises(RuntimeError, match="generation 2"):
        evolve(
            population_size=8,
            generations=3,
            seed=9,
            mutation_rate=0.04,
            crossover_rate=0.8,
            evaluator=evaluator,
            on_generation=save_generation,
            on_progress=progress,
        )
    manifest = update_manifest(run_dir, manifest, status="failed", last_fully_committed_generation=1)
    report = validate_run_history(run_dir)
    assert report["status"] == "failed"
    assert report["completed_generations"] == 1
    assert report["candidate_records"] == 8
    with pytest.raises(HistoryError, match="not committed"):
        reconstruct_generation(run_dir, 2)


def test_truncated_uncommitted_jsonl_tail_does_not_hide_committed_history(tmp_path):
    run_dir, _manifest, _summaries, _populations, _metrics = create_test_run(
        tmp_path, generations=1, population=8
    )
    with (run_dir / "candidate_history.jsonl").open("a", encoding="utf-8") as stream:
        stream.write('{"schema_version":"1.0.0","generation":2,"candidate_id":"g002_c001"')
    report = validate_run_history(run_dir)
    assert report["completed_generations"] == 1
    assert report["candidate_records"] == 8


def test_run_directories_are_never_overwritten(tmp_path):
    metadata = {"dataset_id": 17, "name": "x", "sha256": "a", "sample_count": 1,
                "feature_count": 30, "source_url": "x", "doi": "x"}
    args = {"dataset_metadata": metadata, "parameters": {"generations": 1, "population": 4}, "cv_config": {}}
    first, _ = create_run(tmp_path, **args)
    second, _ = create_run(tmp_path, **args)
    assert first.name == "run_001"
    assert second.name == "run_002"
