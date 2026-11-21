"""Versioned, incremental experiment persistence for downstream readers."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy
import sklearn

from . import SCHEMA_VERSION, __version__
from .dataset import FEATURE_NAMES


CSV_FIELDS = (
    "run_id",
    "generation",
    "population_size",
    "best_candidate_id",
    "best_fitness",
    "mean_fitness",
    "min_fitness",
    "median_fitness",
    "best_feature_count",
    "best_chromosome",
    "best_selected_features",
    "distinct_mask_count",
    "diversity_entropy_bits",
    "average_hamming_distance",
    "elapsed_seconds",
    "generation_seconds",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _software_versions() -> dict:
    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scikit_learn": sklearn.__version__,
        "rich": importlib.metadata.version("rich"),
        "velacare_evolution_engine": __version__,
    }


def create_run(workspace: Path, *, dataset_metadata: dict, parameters: dict, cv_config: dict) -> tuple[Path, dict]:
    experiments = workspace / "analysis" / "experiments"
    experiments.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        run_id = f"run_{index:03d}"
        run_dir = experiments / run_id
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            index += 1

    (run_dir / "candidate_history.jsonl").write_text("", encoding="utf-8")
    with (run_dir / "generation_history.csv").open("w", encoding="utf-8", newline="") as stream:
        csv.DictWriter(stream, fieldnames=CSV_FIELDS).writeheader()
        stream.flush()
        os.fsync(stream.fileno())
    atomic_json(
        run_dir / "best_candidates.json",
        {"schema_version": SCHEMA_VERSION, "run_id": run_id, "generations": [], "final_best": None},
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": utc_now(),
        "started_at": utc_now(),
        "finished_at": None,
        "status": "running",
        "last_fully_committed_generation": 0,
        "dataset": {
            "dataset_id": dataset_metadata["dataset_id"],
            "name": dataset_metadata["name"],
            "sha256": dataset_metadata["sha256"],
            "sample_count": dataset_metadata["sample_count"],
            "feature_count": dataset_metadata["feature_count"],
            "source_url": dataset_metadata["source_url"],
            "doi": dataset_metadata["doi"],
        },
        "feature_order": list(FEATURE_NAMES),
        "label_mapping": {"benign": 0, "malignant": 1},
        "chromosome_encoding": "30-character string, one UCI feature-order bit per character",
        "parameters": parameters,
        "fitness_definition": (
            "0.60 * CV malignant sensitivity + 0.40 * CV balanced accuracy "
            "- 0.02 * selected_feature_count / 30"
        ),
        "classifier": {
            "pipeline": ["StandardScaler", "LogisticRegression"],
            "solver": "liblinear",
            "class_weight": "balanced",
            "C": 1.0,
            "max_iter": 500,
            "preprocessing_fit_scope": "training fold only; final model fit on training split only",
        },
        "cross_validation": cv_config,
        "holdout_policy": "stratified 20% split; held-out data is used only once after feature selection",
        "software_versions": _software_versions(),
        "cache_unique_chromosomes_evaluated": 0,
        "history_contract": {
            "candidate_history.jsonl": "one full record per (run_id, generation, candidate_id)",
            "generation_history.csv": "one row per committed generation",
            "generation_commit_boundary": "manifest last_fully_committed_generation advances only after candidate, summary, and best snapshot writes are fsynced",
        },
    }
    atomic_json(run_dir / "run_manifest.json", manifest)
    atomic_json(
        experiments / "latest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "manifest": f"{run_id}/run_manifest.json",
            "updated_at": utc_now(),
        },
    )
    return run_dir, manifest


def _serialize_candidate(run_id: str, candidate: dict) -> dict:
    return {"schema_version": SCHEMA_VERSION, "run_id": run_id, **candidate}


def commit_generation(run_dir: Path, manifest: dict, summary: dict, candidates: list[dict]) -> dict:
    """Persist every candidate, then advance the manifest's visibility boundary."""
    run_id = manifest["run_id"]
    generation = int(summary["generation"])
    expected_population = int(manifest["parameters"]["population"])
    if len(candidates) != expected_population:
        raise ValueError(f"Generation {generation} has {len(candidates)} candidates; expected {expected_population}.")
    if any(candidate["generation"] != generation for candidate in candidates):
        raise ValueError("A generation commit cannot mix candidate generations.")

    candidate_path = run_dir / "candidate_history.jsonl"
    with candidate_path.open("a", encoding="utf-8") as stream:
        for candidate in candidates:
            stream.write(json.dumps(_serialize_candidate(run_id, candidate), separators=(",", ":"), allow_nan=False))
            stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())

    row = {key: summary[key] for key in CSV_FIELDS if key in summary}
    row["run_id"] = run_id
    row["best_selected_features"] = json.dumps(summary["best_selected_features"], separators=(",", ":"))
    with (run_dir / "generation_history.csv").open("a", encoding="utf-8", newline="") as stream:
        csv.DictWriter(stream, fieldnames=CSV_FIELDS).writerow(row)
        stream.flush()
        os.fsync(stream.fileno())

    best_path = run_dir / "best_candidates.json"
    best_doc = json.loads(best_path.read_text(encoding="utf-8"))
    best_doc["generations"].append(_serialize_candidate(run_id, summary["best_candidate"]))
    best_doc["final_best"] = _serialize_candidate(run_id, summary["best_candidate"])
    atomic_json(best_path, best_doc)

    committed = dict(manifest)
    committed["last_fully_committed_generation"] = generation
    committed["cache_unique_chromosomes_evaluated"] = int(manifest.get("cache_unique_chromosomes_evaluated", 0))
    atomic_json(run_dir / "run_manifest.json", committed)
    return committed


def update_manifest(run_dir: Path, manifest: dict, **updates) -> dict:
    result = dict(manifest)
    result.update(updates)
    atomic_json(run_dir / "run_manifest.json", result)
    return result


def save_final_metrics(run_dir: Path, run_id: str, metrics: dict) -> None:
    atomic_json(
        run_dir / "model_metrics.json",
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "fitness_selected_candidate_id": metrics["candidate_id"],
            "selected_feature_count": metrics["selected_feature_count"],
            "selected_features": metrics["selected_features"],
            "chromosome": metrics["chromosome"],
            "cv_metrics": metrics["cv_metrics"],
            "held_out_test_metrics": metrics["held_out_test_metrics"],
            "test_split": metrics["test_split"],
            "metric_notes": {
                "cv_metrics": "Out-of-fold predictions within the stratified training split; used for fitness.",
                "held_out_test_metrics": "One final evaluation on the untouched stratified 20% test split.",
                "confusion_matrix_axis_order": {
                    "actual_rows": ["malignant", "benign"],
                    "predicted_columns": ["malignant", "benign"],
                },
            },
        },
    )


def dataset_checksum(csv_path: Path) -> str:
    return hashlib.sha256(csv_path.read_bytes()).hexdigest()
