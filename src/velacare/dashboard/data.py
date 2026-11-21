"""Typed, read-only adapters for VelaCare workspace files.

The GA's manifest commit boundary is authoritative. A generation is visible only
after all of its population records and summary have been committed by the writer.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from .. import SCHEMA_VERSION
from ..dataset import FEATURE_NAMES


class DashboardDataError(RuntimeError):
    """A saved workspace artifact is missing or inconsistent."""


@dataclass(frozen=True)
class GenerationData:
    number: int
    candidates: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    best_candidate: dict[str, Any]
    fitness_values: tuple[float, ...]
    feature_counts: tuple[int, ...]
    feature_frequencies: tuple[float, ...]
    diversity: dict[str, float]


@dataclass(frozen=True)
class RunData:
    run_id: str
    path: Path
    manifest: dict[str, Any]
    generations: dict[int, GenerationData]
    model_metrics: dict[str, Any]
    warnings: tuple[str, ...] = ()

    @property
    def committed_generation(self) -> int:
        return max(self.generations, default=0)

    @property
    def status(self) -> str:
        return str(self.manifest.get("status", "unknown"))


@dataclass(frozen=True)
class DatasetData:
    metadata: dict[str, Any]
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    values: np.ndarray = field(repr=False)
    labels: tuple[str, ...]


@dataclass(frozen=True)
class WorkspaceData:
    root: Path
    runs: dict[str, RunData]
    errors: dict[str, str]
    latest_run_id: str | None
    dataset: DatasetData | None
    dataset_error: str | None = None


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DashboardDataError(f"Missing {label}: {path.name}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardDataError(f"Cannot read {label}: {path.name} ({exc})") from exc
    if not isinstance(value, dict):
        raise DashboardDataError(f"{label} must contain a JSON object.")
    return value


def _stat_signature(paths: tuple[Path, ...]) -> tuple[tuple[int, int] | None, ...]:
    result: list[tuple[int, int] | None] = []
    for path in paths:
        try:
            stat = path.stat()
            result.append((stat.st_mtime_ns, stat.st_size))
        except OSError:
            result.append(None)
    return tuple(result)


def _number(record: dict[str, Any], key: str, generation: int) -> float:
    try:
        value = float(record[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise DashboardDataError(f"Generation {generation} has invalid {key}.") from exc
    if not math.isfinite(value):
        raise DashboardDataError(f"Generation {generation} has non-finite {key}.")
    return value


def _close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12)


def _read_candidates(path: Path, run_id: str, committed: int, population: int) -> tuple[dict[int, list[dict[str, Any]]], list[str]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    uncommitted_records = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        raise DashboardDataError(f"Cannot read {path.name}: {exc}") from exc
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError as exc:
            committed_counts = [len(grouped.get(g, [])) for g in range(1, committed + 1)]
            is_uncommitted_tail = (
                index == len(lines)
                and not line.endswith("\n")
                and all(count == population for count in committed_counts)
            )
            if is_uncommitted_tail:
                warnings.append(f"Ignored malformed, uncommitted JSONL tail at line {index}; no committed generation was affected.")
                break
            raise DashboardDataError(f"Malformed candidate record at {path.name}:{index}: {exc.msg}.") from exc
        if not isinstance(candidate, dict):
            raise DashboardDataError(f"Candidate record at {path.name}:{index} is not a JSON object.")
        try:
            generation = int(candidate["generation"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DashboardDataError(f"Candidate record at {path.name}:{index} has no valid generation.") from exc
        if generation > committed:
            uncommitted_records += 1
            continue
        if generation < 1:
            raise DashboardDataError(f"Candidate record at {path.name}:{index} has an invalid generation.")
        if candidate.get("run_id") != run_id:
            raise DashboardDataError(f"Candidate record at {path.name}:{index} belongs to another run.")
        if candidate.get("schema_version") != SCHEMA_VERSION:
            raise DashboardDataError(f"Candidate record at {path.name}:{index} has an unsupported schema.")
        grouped.setdefault(generation, []).append(candidate)
    if uncommitted_records:
        warnings.append(f"Ignored {uncommitted_records} candidate record(s) beyond the manifest commit boundary.")
    return grouped, warnings


def _read_summaries(path: Path, committed: int) -> dict[int, dict[str, Any]]:
    summaries: dict[int, dict[str, Any]] = {}
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            for line_number, row in enumerate(csv.DictReader(stream), start=2):
                try:
                    generation = int(row["generation"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise DashboardDataError(f"Malformed generation summary at {path.name}:{line_number}.") from exc
                if generation > committed:
                    continue
                if generation < 1 or generation in summaries:
                    raise DashboardDataError(f"Duplicate or invalid summary for generation {generation}.")
                summaries[generation] = row
    except DashboardDataError:
        raise
    except OSError as exc:
        raise DashboardDataError(f"Cannot read {path.name}: {exc}") from exc
    return summaries


def _reconstruct(
    run_id: str,
    generation: int,
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    feature_order: list[str],
    expected_population: int,
) -> GenerationData:
    if len(records) != expected_population:
        raise DashboardDataError(
            f"Generation {generation} contains {len(records)} of {expected_population} expected candidates."
        )
    identifiers: set[str] = set()
    chromosomes: list[str] = []
    fitness: list[float] = []
    counts: list[int] = []
    for record in records:
        candidate_id = str(record.get("candidate_id", ""))
        if not candidate_id or candidate_id in identifiers:
            raise DashboardDataError(f"Generation {generation} has a missing or duplicate candidate ID.")
        identifiers.add(candidate_id)
        if int(record.get("generation", -1)) != generation or record.get("run_id") != run_id:
            raise DashboardDataError(f"Candidate {candidate_id} does not match its run/generation identity.")
        chromosome = str(record.get("chromosome", ""))
        if len(chromosome) != len(feature_order) or set(chromosome) - {"0", "1"} or "1" not in chromosome:
            raise DashboardDataError(f"Candidate {candidate_id} has an invalid chromosome.")
        selected = [name for name, bit in zip(feature_order, chromosome, strict=True) if bit == "1"]
        if selected != record.get("selected_features"):
            raise DashboardDataError(f"Candidate {candidate_id} feature names disagree with its chromosome.")
        count = sum(bit == "1" for bit in chromosome)
        if int(record.get("selected_feature_count", -1)) != count:
            raise DashboardDataError(f"Candidate {candidate_id} has an inconsistent feature count.")
        if not isinstance(record.get("cv_metrics"), dict) or not isinstance(record.get("fitness_components"), dict):
            raise DashboardDataError(f"Candidate {candidate_id} is missing stored fitness evaluation fields.")
        try:
            score = float(record["fitness"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DashboardDataError(f"Candidate {candidate_id} has no valid fitness score.") from exc
        if not math.isfinite(score):
            raise DashboardDataError(f"Candidate {candidate_id} has a non-finite fitness score.")
        chromosomes.append(chromosome)
        fitness.append(score)
        counts.append(count)

    best = min(records, key=lambda row: (-float(row["fitness"]), str(row["candidate_id"])))
    values = np.asarray(fitness, dtype=float)
    masks = np.asarray([[int(bit) for bit in chrom] for chrom in chromosomes], dtype=np.uint8)
    freqs = masks.mean(axis=0)
    unique_count = len(set(chromosomes))
    if len(masks) > 1:
        distances = np.count_nonzero(masks[:, None, :] != masks[None, :, :], axis=2)
        mean_hamming = float(distances[np.triu_indices(len(masks), k=1)].mean())
    else:
        mean_hamming = 0.0
    entropy = float(np.sum([
        -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
        for p in freqs
        if 0 < p < 1
    ]))
    expected = {
        "population_size": len(records),
        "best_candidate_id": best["candidate_id"],
        "best_chromosome": best["chromosome"],
        "best_fitness": float(values.max()),
        "mean_fitness": float(values.mean()),
        "min_fitness": float(values.min()),
        "median_fitness": float(np.median(values)),
        "distinct_mask_count": unique_count,
        "best_feature_count": int(best["selected_feature_count"]),
        "diversity_entropy_bits": entropy,
        "average_hamming_distance": mean_hamming,
    }
    for key, actual in expected.items():
        if key in summary and summary[key] not in (None, ""):
            if key in {"population_size", "distinct_mask_count", "best_feature_count"}:
                valid = int(summary[key]) == int(actual)
            elif key in {"best_candidate_id", "best_chromosome"}:
                valid = str(summary[key]) == str(actual)
            else:
                valid = _close(float(summary[key]), float(actual))
            if not valid:
                raise DashboardDataError(f"Generation {generation} summary field {key} disagrees with candidate history.")
    return GenerationData(
        number=generation,
        candidates=tuple(sorted(records, key=lambda row: str(row["candidate_id"]))),
        summary=summary,
        best_candidate=best,
        fitness_values=tuple(fitness),
        feature_counts=tuple(counts),
        feature_frequencies=tuple(float(value) for value in freqs),
        diversity={
            "unique_chromosome_ratio": unique_count / len(records),
            "mean_pairwise_hamming_distance": mean_hamming,
            "mean_pairwise_hamming_fraction": mean_hamming / len(feature_order),
            "bit_entropy_sum": entropy,
        },
    )


_RUN_CACHE: dict[str, tuple[tuple[tuple[int, int] | None, ...], RunData]] = {}


def load_run(run_dir: Path) -> RunData:
    """Load and validate one run, returning every complete population in memory."""
    paths = (
        run_dir / "run_manifest.json",
        run_dir / "generation_history.csv",
        run_dir / "candidate_history.jsonl",
        run_dir / "model_metrics.json",
        run_dir / "best_candidates.json",
    )
    key = str(run_dir.resolve())
    signature = _stat_signature(paths)
    cached = _RUN_CACHE.get(key)
    if cached and cached[0] == signature:
        return cached[1]

    manifest = _json(paths[0], "run manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise DashboardDataError(f"Unsupported run schema {manifest.get('schema_version')!r}.")
    run_id = str(manifest.get("run_id", ""))
    if run_id != run_dir.name:
        raise DashboardDataError(f"Manifest run ID {run_id!r} does not match directory {run_dir.name!r}.")
    try:
        committed = int(manifest["last_fully_committed_generation"])
        expected_population = int(manifest["parameters"]["population"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DashboardDataError("Run manifest is missing its commit boundary or population size.") from exc
    if committed < 0 or expected_population < 1:
        raise DashboardDataError("Run manifest contains an invalid commit boundary or population size.")
    feature_order = manifest.get("feature_order")
    if not isinstance(feature_order, list) or feature_order != list(FEATURE_NAMES):
        raise DashboardDataError("Run manifest feature order does not match canonical UCI WDBC order.")
    grouped, warnings = _read_candidates(paths[2], run_id, committed, expected_population)
    summaries = _read_summaries(paths[1], committed)
    expected_generations = set(range(1, committed + 1))
    if set(grouped) != expected_generations:
        missing = sorted(expected_generations - set(grouped))
        raise DashboardDataError(f"Candidate history is missing committed generations: {missing}.")
    if set(summaries) != expected_generations:
        missing = sorted(expected_generations - set(summaries))
        raise DashboardDataError(f"Generation history is missing committed summaries: {missing}.")
    generations = {
        number: _reconstruct(run_id, number, grouped[number], summaries[number], feature_order, expected_population)
        for number in sorted(expected_generations)
    }
    metrics = _json(paths[3], "model metrics") if paths[3].exists() else {}
    if metrics and metrics.get("run_id") != run_id:
        raise DashboardDataError("Model metrics belong to another run.")
    data = RunData(run_id, run_dir, manifest, generations, metrics, tuple(warnings))
    # A concurrent writer may have advanced during the read. In that case avoid
    # caching a mixed snapshot; the next refresh will retry against the new files.
    after = _stat_signature(paths)
    if after == signature:
        _RUN_CACHE[key] = (signature, data)
    return data


def _load_dataset(root: Path, expected_features: list[str] | None = None) -> DatasetData:
    csv_path = root / "data" / "breast_cancer.csv"
    metadata_path = root / "data" / "dataset_metadata.json"
    metadata = _json(metadata_path, "dataset metadata")
    try:
        with csv_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            columns = tuple(reader.fieldnames or ())
            if not columns or columns[0] != "diagnosis":
                raise DashboardDataError("Dataset CSV must start with a diagnosis column.")
            records = list(reader)
    except DashboardDataError:
        raise
    except OSError as exc:
        raise DashboardDataError(f"Cannot read local dataset file {csv_path}: {exc}") from exc
    if len(columns) != 31 or len(columns[1:]) != 30:
        raise DashboardDataError("Local dataset must contain the diagnosis label and 30 feature columns.")
    try:
        actual_checksum = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise DashboardDataError(f"Cannot verify local dataset checksum: {exc}") from exc
    recorded_checksum = metadata.get("sha256")
    if recorded_checksum and recorded_checksum != actual_checksum:
        raise DashboardDataError("Local dataset checksum does not match dataset_metadata.json.")
    if expected_features and list(columns[1:]) != expected_features:
        raise DashboardDataError("Local dataset feature order does not match the selected run manifest.")
    numeric_rows: list[list[float]] = []
    labels: list[str] = []
    missing = False
    for row_number, record in enumerate(records, start=2):
        label = record.get("diagnosis", "")
        if label not in {"benign", "malignant"}:
            raise DashboardDataError(f"Unknown diagnosis label at dataset row {row_number}.")
        labels.append(label)
        values: list[float] = []
        for column in columns[1:]:
            raw = record.get(column, "")
            if raw in (None, ""):
                missing = True
                values.append(float("nan"))
                continue
            try:
                value = float(raw)
            except ValueError as exc:
                raise DashboardDataError(f"Non-numeric value in dataset row {row_number}, {column}.") from exc
            if not math.isfinite(value):
                missing = True
            values.append(value)
        numeric_rows.append(values)
    matrix = np.asarray(numeric_rows, dtype=float)
    if len(records) != int(metadata.get("sample_count", len(records))):
        raise DashboardDataError("Local dataset row count does not match its metadata.")
    rows = tuple({"diagnosis": label, **dict(zip(columns[1:], record_values, strict=True))}
                 for label, record_values in zip(labels, numeric_rows, strict=True))
    metadata = dict(metadata)
    metadata["missing_values_found"] = missing
    return DatasetData(metadata, columns, rows, matrix, tuple(labels))


def load_workspace(workspace: Path) -> WorkspaceData:
    """Discover runs and read the local dataset without network access."""
    root = workspace.expanduser().resolve()
    experiments = root / "analysis" / "experiments"
    runs: dict[str, RunData] = {}
    errors: dict[str, str] = {}
    if experiments.is_dir():
        for run_dir in sorted(experiments.glob("run_*")):
            if not run_dir.is_dir() or not re.fullmatch(r"run_\d+", run_dir.name):
                continue
            try:
                runs[run_dir.name] = load_run(run_dir)
            except DashboardDataError as exc:
                errors[run_dir.name] = str(exc)
    latest_id: str | None = None
    latest_path = experiments / "latest.json"
    if latest_path.exists():
        try:
            pointer = _json(latest_path, "latest run pointer")
            candidate_id = str(pointer.get("run_id", ""))
            if candidate_id in runs or candidate_id in errors:
                latest_id = candidate_id
        except DashboardDataError:
            pass
    if latest_id is None and runs:
        latest_id = sorted(runs)[-1]
    reference = runs.get(latest_id or "")
    try:
        dataset = _load_dataset(root, reference.manifest.get("feature_order") if reference else None)
        dataset_error = None
    except DashboardDataError as exc:
        dataset, dataset_error = None, str(exc)
    return WorkspaceData(root, runs, errors, latest_id, dataset, dataset_error)


def clear_cache() -> None:
    """Clear cached snapshots; exposed for deterministic tests."""
    _RUN_CACHE.clear()
