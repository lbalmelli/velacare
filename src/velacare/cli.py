"""Command-line interface and run orchestration."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from . import __version__
from .dataset import CSV_NAME, METADATA_NAME, DatasetError, load_dataset
from .evaluation import evaluate_cross_validation, evaluate_holdout, split_dataset
from .genetics import evolve
from .persistence import (
    commit_generation,
    create_run,
    save_final_metrics,
    update_manifest,
)
from .reader import reconstruct_generation, validate_run_history
from .tui import EvolutionTUI


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def population_int(value: str) -> int:
    number = positive_int(value)
    if number < 4:
        raise argparse.ArgumentTypeError("must be at least 4")
    return number


def probability(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number in [0, 1]") from exc
    if not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("must be a number in [0, 1]")
    return number


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="run-demo",
        description="Evolve feature subsets for the UCI Breast Cancer Wisconsin (Diagnostic) research dataset.",
        epilog=(
            "Example: ./run-demo --generations 40 --population 60 --seed 42\n"
            "Data and experiment records go to /agentic-space when writable, otherwise ./agentic-space."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    result.add_argument("--generations", type=positive_int, default=40, help="positive number of generations (default: 40)")
    result.add_argument("--population", type=population_int, default=60, help="population size, at least 4 (default: 60)")
    result.add_argument("--seed", type=int, default=42, help="seed for reproducible GA and model evaluation (default: 42)")
    result.add_argument("--mutation-rate", type=probability, default=0.03, help="per-feature mutation probability (default: 0.03)")
    result.add_argument("--crossover-rate", type=probability, default=0.8, help="probability of uniform crossover (default: 0.8)")
    result.add_argument("--workspace", type=Path, help="shared filesystem root (default: /agentic-space or ./agentic-space)")
    result.add_argument("--download-only", action="store_true", help="download and validate dataset 17, then exit")
    result.add_argument("--no-color", action="store_true", help="disable terminal color output")
    result.add_argument("--version", action="version", version=f"VelaCare Evolution Engine {__version__}")
    return result


def resolve_workspace(override: Path | None, repository_root: Path | None = None) -> Path:
    if override is not None:
        return override.expanduser().resolve()
    shared = Path("/agentic-space")
    if shared.is_dir() and os.access(shared, os.W_OK | os.X_OK):
        return shared
    return ((repository_root or Path.cwd()) / "agentic-space").resolve()


def _print_run_result(run_dir: Path, report: dict, generations: list[int]) -> None:
    print(f"\nRun completed: {run_dir}")
    print(
        "History reconstructed from saved files: "
        f"{report['completed_generations']} generations, {report['candidate_records']} candidate records."
    )
    if generations:
        requested_historical = 17 if 17 in generations else generations[len(generations) // 2]
        selected = sorted(set([generations[0], requested_historical, generations[-1]]))
    else:
        selected = []
    for generation in selected:
        reconstructed = reconstruct_generation(run_dir, generation)
        best = reconstructed["best_candidate"]
        print(
            f"  generation {generation:02d}: {reconstructed['population_size']} candidates; "
            f"best={reconstructed['best_fitness']:.4f}; features={best['selected_feature_count']}/30"
        )
    print("Saved files:")
    for name in (
        "run_manifest.json",
        "generation_history.csv",
        "candidate_history.jsonl",
        "best_candidates.json",
        "model_metrics.json",
    ):
        print(f"  {run_dir / name}")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    workspace = resolve_workspace(args.workspace, Path(__file__).resolve().parents[2])
    tui = EvolutionTUI(
        no_color=args.no_color,
        total_generations=args.generations,
        population=args.population,
        seed=args.seed,
        download_only=args.download_only,
    )
    run_dir: Path | None = None
    manifest: dict | None = None
    started = time.monotonic()
    tui.start()
    try:
        tui.set_phase("data", "active", "Connecting to UCI dataset 17")
        dataset, dataset_metadata = load_dataset(workspace)
        tui.set_dataset(*dataset.X.shape)
        tui.set_phase("data", "complete")

        if args.download_only:
            tui.set_phase("setup", "complete", "Dataset validation passed")
            tui.download_complete([workspace / "data" / CSV_NAME, workspace / "data" / METADATA_NAME])
            return 0

        tui.set_phase("setup", "active")
        X_train, X_test, y_train, y_test = split_dataset(dataset.X, dataset.y, args.seed)
        cv_folds = 3
        cv_config = {
            "method": "StratifiedKFold",
            "folds": cv_folds,
            "shuffle": True,
            "random_state": args.seed,
            "data_scope": "training split only",
            "training_samples": int(len(y_train)),
            "held_out_samples": int(len(y_test)),
        }
        tui.set_phase("setup", "complete", f"Stratified train {len(y_train)} / holdout {len(y_test)}; {cv_folds}-fold CV")

        parameters = {
            "generations": args.generations,
            "population": args.population,
            "seed": args.seed,
            "mutation_rate": args.mutation_rate,
            "crossover_rate": args.crossover_rate,
            "elite_count": 2,
        }
        run_dir, manifest = create_run(
            workspace,
            dataset_metadata=dataset_metadata,
            parameters=parameters,
            cv_config=cv_config,
        )
        tui.set_run_id(run_dir.name)
        tui.set_phase("init", "active")
        tui.set_phase("init", "complete")
        tui.set_phase("evolve", "active")

        def evaluate(mask):
            return evaluate_cross_validation(mask, X_train, y_train, seed=args.seed, folds=cv_folds)

        def save_generation(summary, candidates):
            nonlocal manifest
            manifest = commit_generation(run_dir, manifest, summary, candidates)
            tui.on_generation(summary, candidates)

        summaries, _populations, unique_evaluations = evolve(
            population_size=args.population,
            generations=args.generations,
            seed=args.seed,
            mutation_rate=args.mutation_rate,
            crossover_rate=args.crossover_rate,
            evaluator=evaluate,
            on_progress=tui.on_progress,
            on_generation=save_generation,
        )

        final_candidate = summaries[-1]["best_candidate"]
        held_out = evaluate_holdout(
            np_from_chromosome(final_candidate["chromosome"]),
            X_train,
            y_train,
            X_test,
            y_test,
            seed=args.seed,
        )
        final_metrics = {
            "candidate_id": final_candidate["candidate_id"],
            "selected_feature_count": final_candidate["selected_feature_count"],
            "selected_features": final_candidate["selected_features"],
            "chromosome": final_candidate["chromosome"],
            "cv_fitness": final_candidate["fitness"],
            "cv_metrics": final_candidate["cv_metrics"],
            "held_out_test_metrics": held_out,
            "test_split": {
                "training_samples": int(len(y_train)),
                "held_out_samples": int(len(y_test)),
                "stratified": True,
            },
        }
        save_final_metrics(run_dir, run_dir.name, final_metrics)
        manifest = update_manifest(
            run_dir,
            manifest,
            status="completed",
            finished_at=utc_now(),
            last_fully_committed_generation=args.generations,
            cache_unique_chromosomes_evaluated=unique_evaluations,
            duration_seconds=time.monotonic() - started,
            final_candidate_id=final_candidate["candidate_id"],
            output_files=[
                "generation_history.csv",
                "candidate_history.jsonl",
                "best_candidates.json",
                "model_metrics.json",
            ],
        )

        # This audit reads and reconstructs every generation from files only.
        report = validate_run_history(run_dir)
        tui.set_phase("evolve", "complete")
        files = [run_dir / name for name in (
            "run_manifest.json",
            "generation_history.csv",
            "candidate_history.jsonl",
            "best_candidates.json",
            "model_metrics.json",
        )]
        tui.complete(final_metrics, files)
        tui.stop()
        _print_run_result(run_dir, report, report["reconstructed_generations"])
        return 0
    except KeyboardInterrupt:
        tui.fail("interrupted")
        if run_dir is not None and manifest is not None:
            manifest = update_manifest(
                run_dir,
                manifest,
                status="interrupted",
                finished_at=utc_now(),
                duration_seconds=time.monotonic() - started,
            )
        print("\nRun interrupted. Completed generations remain available in the run directory.", file=sys.stderr)
        return 130
    except Exception as exc:
        tui.fail("failed", str(exc))
        if run_dir is not None and manifest is not None:
            try:
                manifest = update_manifest(
                    run_dir,
                    manifest,
                    status="failed",
                    finished_at=utc_now(),
                    duration_seconds=time.monotonic() - started,
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
            except Exception:
                pass
        print(f"VelaCare run failed: {exc}", file=sys.stderr)
        if isinstance(exc, DatasetError):
            print("Recovery: check internet access to UCI, or restore the workspace data/ cache.", file=sys.stderr)
        return 1
    finally:
        tui.stop()


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def np_from_chromosome(chromosome: str):
    import numpy as np

    return np.fromiter((int(bit) for bit in chromosome), dtype=np.uint8)


if __name__ == "__main__":
    raise SystemExit(main())
