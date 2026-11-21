"""Seeded binary genetic algorithm for feature subset selection."""

from __future__ import annotations

import math
import time
from collections.abc import Callable

import numpy as np

from .dataset import FEATURE_NAMES
from .evaluation import fitness_from_cv

Evaluator = Callable[[np.ndarray], dict]
ProgressCallback = Callable[[int, int, int, list[dict], float], None]
GenerationCallback = Callable[[dict, list[dict]], None]


def repair_chromosome(chromosome: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Return a copied 30-bit mask with at least one selected feature."""
    result = np.asarray(chromosome, dtype=np.uint8).copy()
    if result.shape != (len(FEATURE_NAMES),) or np.any((result != 0) & (result != 1)):
        raise ValueError("Chromosomes must be 30-element binary arrays.")
    if not result.any():
        result[int(rng.integers(0, result.size))] = 1
    return result


def initialize_population(size: int, rng: np.random.Generator) -> list[np.ndarray]:
    if size < 4:
        raise ValueError("Population size must be at least 4.")
    population = [repair_chromosome(rng.integers(0, 2, size=30, dtype=np.uint8), rng) for _ in range(size)]
    return population


def tournament_select(population: list[dict], rng: np.random.Generator, tournament_size: int = 3) -> dict:
    if len(population) < tournament_size:
        raise ValueError("Population is smaller than the tournament.")
    contenders = rng.choice(len(population), size=tournament_size, replace=False)
    return max((population[int(index)] for index in contenders), key=lambda item: item["fitness"])


def crossover(
    first: np.ndarray,
    second: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Uniform crossover, preserving the input masks."""
    choose_first = rng.integers(0, 2, size=first.size).astype(bool)
    child_one = np.where(choose_first, first, second).astype(np.uint8)
    child_two = np.where(choose_first, second, first).astype(np.uint8)
    return child_one, child_two


def mutate(chromosome: np.ndarray, rate: float, rng: np.random.Generator) -> tuple[np.ndarray, bool]:
    result = chromosome.copy()
    flips = rng.random(result.size) < rate
    result[flips] = 1 - result[flips]
    changed = bool(flips.any())
    if not result.any():
        result[int(rng.integers(0, result.size))] = 1
        changed = True
    return result, changed


def _candidate(
    chromosome: np.ndarray,
    generation: int,
    position: int,
    parents: list[dict],
    operator: str,
    evaluator: Evaluator,
    cache: dict[tuple[int, ...], dict],
) -> dict:
    key = tuple(int(bit) for bit in chromosome)
    cache_hit = key in cache
    if not cache_hit:
        metrics = evaluator(chromosome.copy())
        fitness, components = fitness_from_cv(metrics, int(chromosome.sum()), len(FEATURE_NAMES))
        cache[key] = {
            "cv_metrics": metrics,
            "fitness": fitness,
            "fitness_components": components,
        }
    evaluated = cache[key]
    selected = [name for name, bit in zip(FEATURE_NAMES, chromosome, strict=True) if bit]
    return {
        "generation": generation,
        "candidate_id": f"g{generation:03d}_c{position:03d}",
        "chromosome": "".join(str(int(bit)) for bit in chromosome),
        "selected_features": selected,
        "selected_feature_count": len(selected),
        "fitness": evaluated["fitness"],
        "fitness_components": evaluated["fitness_components"],
        "cv_metrics": evaluated["cv_metrics"],
        "parents": parents,
        "operator": operator,
        "evaluation_cache_hit": cache_hit,
    }


def _population_statistics(candidates: list[dict], generation: int, started: float, generation_seconds: float) -> dict:
    fitness = np.asarray([candidate["fitness"] for candidate in candidates], dtype=np.float64)
    masks = np.asarray([[int(bit) for bit in candidate["chromosome"]] for candidate in candidates], dtype=np.uint8)
    unique_masks = len({candidate["chromosome"] for candidate in candidates})
    probabilities = masks.mean(axis=0)
    entropy = 0.0
    for probability in probabilities:
        if 0 < probability < 1:
            entropy -= probability * math.log2(probability) + (1 - probability) * math.log2(1 - probability)
    if len(masks) > 1:
        pair_distances = [
            float(np.count_nonzero(masks[left] != masks[right]))
            for left in range(len(masks))
            for right in range(left + 1, len(masks))
        ]
        mean_hamming = float(np.mean(pair_distances))
    else:
        mean_hamming = 0.0
    best = min(candidates, key=lambda candidate: (-candidate["fitness"], candidate["candidate_id"]))
    return {
        "generation": generation,
        "population_size": len(candidates),
        "best_candidate_id": best["candidate_id"],
        "best_fitness": float(fitness.max()),
        "mean_fitness": float(fitness.mean()),
        "min_fitness": float(fitness.min()),
        "median_fitness": float(np.median(fitness)),
        "best_feature_count": best["selected_feature_count"],
        "best_chromosome": best["chromosome"],
        "best_selected_features": best["selected_features"],
        "distinct_mask_count": unique_masks,
        "diversity_entropy_bits": float(entropy),
        "average_hamming_distance": mean_hamming,
        "elapsed_seconds": float(time.monotonic() - started),
        "generation_seconds": float(generation_seconds),
        "best_candidate": best,
    }


def evolve(
    *,
    population_size: int,
    generations: int,
    seed: int,
    mutation_rate: float,
    crossover_rate: float,
    evaluator: Evaluator,
    on_progress: ProgressCallback | None = None,
    on_generation: GenerationCallback | None = None,
    elite_count: int = 2,
) -> tuple[list[dict], list[list[dict]], int]:
    """Run the GA and return all per-generation records plus cache misses.

    Every generation is evaluated as a full population. Elites and repeated
    chromosomes still receive candidate records; evaluation cache hits only
    avoid repeating an identical CV fit.
    """
    if generations < 1:
        raise ValueError("Generations must be positive.")
    if population_size < 4:
        raise ValueError("Population size must be at least 4.")
    if not 0 <= mutation_rate <= 1 or not 0 <= crossover_rate <= 1:
        raise ValueError("Mutation and crossover rates must be in [0, 1].")
    if not 1 <= elite_count < population_size:
        raise ValueError("Elite count must be at least 1 and smaller than population size.")

    rng = np.random.default_rng(seed)
    started = time.monotonic()
    cache: dict[tuple[int, ...], dict] = {}
    initial_masks = initialize_population(population_size, rng)
    population: list[dict] = []
    generation_summaries: list[dict] = []
    generation_populations: list[list[dict]] = []

    for generation in range(1, generations + 1):
        generation_started = time.monotonic()
        if generation == 1:
            plans = [(mask, [], "initial") for mask in initial_masks]
        else:
            ranked = sorted(population, key=lambda item: (-item["fitness"], item["candidate_id"]))
            plans = []
            for elite in ranked[:elite_count]:
                plans.append((np.fromiter((int(bit) for bit in elite["chromosome"]), dtype=np.uint8),
                              [{"generation": generation - 1, "candidate_id": elite["candidate_id"]}],
                              "elite"))
            while len(plans) < population_size:
                parent_a = tournament_select(population, rng)
                parent_b = tournament_select(population, rng)
                first = np.fromiter((int(bit) for bit in parent_a["chromosome"]), dtype=np.uint8)
                second = np.fromiter((int(bit) for bit in parent_b["chromosome"]), dtype=np.uint8)
                did_crossover = rng.random() < crossover_rate
                if did_crossover:
                    children = crossover(first, second, rng)
                else:
                    children = (first.copy(), second.copy())
                for child_index, child in enumerate(children):
                    if len(plans) >= population_size:
                        break
                    child, did_mutate = mutate(child, mutation_rate, rng)
                    operations = ["selection"]
                    if did_crossover:
                        operations.append("crossover")
                    if did_mutate:
                        operations.append("mutation")
                    if did_crossover:
                        parents = [
                            {"generation": generation - 1, "candidate_id": parent_a["candidate_id"]},
                            {"generation": generation - 1, "candidate_id": parent_b["candidate_id"]},
                        ]
                    else:
                        source_parent = parent_a if child_index == 0 else parent_b
                        parents = [{"generation": generation - 1, "candidate_id": source_parent["candidate_id"]}]
                    plans.append((child, parents, "+".join(operations)))

        population = []
        for position, (chromosome, parents, operator) in enumerate(plans, start=1):
            candidate = _candidate(
                chromosome,
                generation,
                position,
                parents,
                operator,
                evaluator,
                cache,
            )
            population.append(candidate)
            if on_progress:
                on_progress(generation, population_size, position, population.copy(), time.monotonic() - started)

        generation_seconds = time.monotonic() - generation_started
        summary = _population_statistics(population, generation, started, generation_seconds)
        generation_summaries.append(summary)
        generation_populations.append(population.copy())
        if on_generation:
            on_generation(summary, population.copy())

    return generation_summaries, generation_populations, len(cache)
