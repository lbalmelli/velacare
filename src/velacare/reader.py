"""File-only reconstruction helpers for the Data Explorer contract."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from . import SCHEMA_VERSION


class HistoryError(RuntimeError):
    """Saved experiment history is incomplete or inconsistent."""


def _read_manifest(run_dir: Path) -> dict:
    try:
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoryError(f"Cannot read run manifest at {run_dir}.") from exc
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise HistoryError(f"Unsupported run schema {manifest.get('schema_version')!r}.")
    return manifest


def _index_history(run_dir: Path) -> tuple[dict, dict[int, list[dict]], dict[int, dict]]:
    manifest = _read_manifest(run_dir)
    committed = int(manifest["last_fully_committed_generation"])
    candidates_by_generation: dict[int, list[dict]] = {}
    candidate_path = run_dir / "candidate_history.jsonl"
    try:
        content = candidate_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        for line_number, line in enumerate(lines, start=1):
            if line.strip():
                try:
                    candidate = json.loads(line)
                except json.JSONDecodeError as exc:
                    expected = int(manifest["parameters"]["population"])
                    committed_counts = [len(candidates_by_generation.get(gen, [])) for gen in range(1, committed + 1)]
                    is_uncommitted_tail = (
                        line_number == len(lines)
                        and not line.endswith("\n")
                        and all(count == expected for count in committed_counts)
                    )
                    if is_uncommitted_tail:
                        break
                    raise HistoryError(f"Invalid JSONL record at line {line_number}.") from exc
                generation = int(candidate["generation"])
                candidates_by_generation.setdefault(generation, []).append(candidate)
    except OSError as exc:
        raise HistoryError(f"Cannot read candidate history in {run_dir}.") from exc

    summaries: dict[int, dict] = {}
    try:
        with (run_dir / "generation_history.csv").open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                try:
                    generation = int(row["generation"])
                except (KeyError, ValueError):
                    if manifest["status"] != "completed":
                        break
                    raise HistoryError("Completed run has an incomplete generation summary row.")
                if generation in summaries:
                    raise HistoryError(f"Generation {generation} has duplicate summary rows.")
                summaries[generation] = row
    except OSError as exc:
        raise HistoryError(f"Cannot parse generation summaries in {run_dir}.") from exc
    return manifest, candidates_by_generation, summaries


def _validate_population(manifest: dict, generation: int, candidates: list[dict]) -> dict:
    expected_count = int(manifest["parameters"]["population"])
    if len(candidates) != expected_count:
        raise HistoryError(
            f"Generation {generation} reconstructs {len(candidates)} candidates; expected {expected_count}."
        )
    expected_order = manifest["feature_order"]
    if len(expected_order) != 30:
        raise HistoryError("Run manifest feature order must contain 30 names.")
    ids = set()
    for candidate in candidates:
        if int(candidate.get("generation", -1)) != generation:
            raise HistoryError(f"Generation {generation} contains a candidate with a mismatched generation field.")
        if candidate.get("run_id") != manifest["run_id"] or candidate.get("schema_version") != SCHEMA_VERSION:
            raise HistoryError(f"Generation {generation} contains a record from another run or schema.")
        candidate_id = candidate.get("candidate_id")
        if candidate_id in ids:
            raise HistoryError(f"Generation {generation} repeats candidate ID {candidate_id!r}.")
        ids.add(candidate_id)
        chromosome = candidate.get("chromosome", "")
        if len(chromosome) != len(expected_order) or set(chromosome) - {"0", "1"} or "1" not in chromosome:
            raise HistoryError(f"Candidate {candidate_id!r} has an invalid chromosome.")
        selected = [name for name, bit in zip(expected_order, chromosome, strict=True) if bit == "1"]
        if selected != candidate.get("selected_features"):
            raise HistoryError(f"Candidate {candidate_id!r} chromosome and selected feature names disagree.")
        if int(candidate.get("selected_feature_count", -1)) != len(selected):
            raise HistoryError(f"Candidate {candidate_id!r} feature count is inconsistent.")
        if not isinstance(candidate.get("cv_metrics"), dict) or not isinstance(candidate.get("fitness_components"), dict):
            raise HistoryError(f"Candidate {candidate_id!r} is missing CV metrics or fitness components.")
    fitness = np.asarray([float(candidate["fitness"]) for candidate in candidates], dtype=float)
    best = min(candidates, key=lambda candidate: (-float(candidate["fitness"]), candidate["candidate_id"]))
    return {
        "generation": generation,
        "population_size": len(candidates),
        "candidates": candidates,
        "fitness_values": fitness.tolist(),
        "best_candidate": best,
        "best_fitness": float(fitness.max()),
        "mean_fitness": float(fitness.mean()),
        "min_fitness": float(fitness.min()),
        "median_fitness": float(np.median(fitness)),
        "distinct_mask_count": len({candidate["chromosome"] for candidate in candidates}),
        "selected_feature_counts": [int(candidate["selected_feature_count"]) for candidate in candidates],
        "chromosomes": [candidate["chromosome"] for candidate in candidates],
    }


def reconstruct_generation(run_dir: Path, generation: int) -> dict:
    """Rebuild a full generation from saved files only (no GA/model imports)."""
    manifest, by_generation, summaries = _index_history(run_dir)
    committed = int(manifest["last_fully_committed_generation"])
    if generation < 1 or generation > committed:
        raise HistoryError(f"Generation {generation} is not committed; committed range is 1..{committed}.")
    if generation not in by_generation or generation not in summaries:
        raise HistoryError(f"Generation {generation} is missing candidate or summary records.")
    reconstructed = _validate_population(manifest, generation, by_generation[generation])
    summary = summaries[generation]
    if summary["best_candidate_id"] != reconstructed["best_candidate"]["candidate_id"]:
        raise HistoryError(f"Generation {generation} best candidate ID does not match its population.")
    if not np.isclose(float(summary["best_fitness"]), reconstructed["best_fitness"], atol=1e-12):
        raise HistoryError(f"Generation {generation} best fitness does not match its population.")
    if not np.isclose(float(summary["mean_fitness"]), reconstructed["mean_fitness"], atol=1e-12):
        raise HistoryError(f"Generation {generation} mean fitness does not match its population.")
    if not np.isclose(float(summary["min_fitness"]), reconstructed["min_fitness"], atol=1e-12):
        raise HistoryError(f"Generation {generation} minimum fitness does not match its population.")
    if not np.isclose(float(summary["median_fitness"]), reconstructed["median_fitness"], atol=1e-12):
        raise HistoryError(f"Generation {generation} median fitness does not match its population.")
    if int(summary["population_size"]) != reconstructed["population_size"]:
        raise HistoryError(f"Generation {generation} summary population size is inconsistent.")
    if int(summary["distinct_mask_count"]) != reconstructed["distinct_mask_count"]:
        raise HistoryError(f"Generation {generation} distinct-mask count is inconsistent.")
    if summary["best_chromosome"] != reconstructed["best_candidate"]["chromosome"]:
        raise HistoryError(f"Generation {generation} best chromosome does not match its population.")
    if json.loads(summary["best_selected_features"]) != reconstructed["best_candidate"]["selected_features"]:
        raise HistoryError(f"Generation {generation} best feature names do not match its population.")
    reconstructed["summary"] = summary
    return reconstructed


def validate_run_history(run_dir: Path) -> dict:
    """Reconstruct and validate every committed generation from disk."""
    manifest, by_generation, summaries = _index_history(run_dir)
    committed = int(manifest["last_fully_committed_generation"])
    expected_generations = set(range(1, committed + 1))
    visible_summaries = {generation for generation in summaries if generation <= committed}
    if visible_summaries != expected_generations:
        raise HistoryError(f"Summary generations differ from committed range 1..{committed}.")
    if set(generation for generation in by_generation if generation <= committed) != expected_generations:
        raise HistoryError(f"Candidate generations differ from committed range 1..{committed}.")
    total_candidates = 0
    for generation in sorted(expected_generations):
        reconstructed = reconstruct_generation(run_dir, generation)
        total_candidates += reconstructed["population_size"]

    if manifest["status"] == "completed":
        expected_total = committed * int(manifest["parameters"]["population"])
        actual_total = sum(len(records) for records in by_generation.values())
        if actual_total != expected_total:
            raise HistoryError(f"Completed run contains {actual_total} candidate lines; expected {expected_total}.")
        if set(summaries) != expected_generations:
            raise HistoryError("Completed run has summary rows beyond its committed generation boundary.")
        best_doc = json.loads((run_dir / "best_candidates.json").read_text(encoding="utf-8"))
        if len(best_doc.get("generations", [])) != committed:
            raise HistoryError("Best-candidate history does not contain one snapshot per completed generation.")
    return {
        "run_id": manifest["run_id"],
        "status": manifest["status"],
        "completed_generations": committed,
        "candidate_records": total_candidates,
        "reconstructed_generations": sorted(expected_generations),
    }
