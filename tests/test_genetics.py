import numpy as np

from velacare.genetics import crossover, evolve, initialize_population, mutate


def deterministic_evaluator(chromosome):
    score = float(chromosome.sum() / chromosome.size)
    return {
        "accuracy": score,
        "balanced_accuracy": score,
        "malignant_sensitivity": score,
        "specificity": score,
        "f1_malignant": score,
        "confusion_matrix": [[1, 0], [0, 1]],
        "confusion_matrix_labels": ["malignant", "benign"],
    }


def test_population_and_operators_keep_valid_nonempty_masks():
    rng = np.random.default_rng(7)
    population = initialize_population(12, rng)
    assert len(population) == 12
    assert all(mask.shape == (30,) and set(mask.tolist()) <= {0, 1} and mask.any() for mask in population)

    first = np.zeros(30, dtype=np.uint8)
    second = np.ones(30, dtype=np.uint8)
    first_before, second_before = first.copy(), second.copy()
    child_a, child_b = crossover(first, second, rng)
    assert set(child_a.tolist()) <= {0, 1}
    assert set(child_b.tolist()) <= {0, 1}
    assert np.array_equal(first, first_before) and np.array_equal(second, second_before)

    mutated, changed = mutate(np.ones(30, dtype=np.uint8), 1.0, rng)
    assert changed and mutated.any()
    repaired, changed = mutate(np.zeros(30, dtype=np.uint8), 0.0, rng)
    assert changed and repaired.any()


def test_evolution_is_seeded_and_elitism_preserves_the_winner():
    def run():
        return evolve(
            population_size=8,
            generations=4,
            seed=42,
            mutation_rate=0.04,
            crossover_rate=0.8,
            evaluator=deterministic_evaluator,
        )

    summaries_a, populations_a, _ = run()
    summaries_b, populations_b, _ = run()
    for generation_a, generation_b in zip(populations_a, populations_b, strict=True):
        assert [item["chromosome"] for item in generation_a] == [item["chromosome"] for item in generation_b]
        assert [item["fitness"] for item in generation_a] == [item["fitness"] for item in generation_b]
    best_by_gen = [summary["best_fitness"] for summary in summaries_a]
    assert best_by_gen == sorted(best_by_gen)
    assert [item["operator"] for item in populations_a[1][:2]] == ["elite", "elite"]
    assert populations_a[1][0]["chromosome"] == summaries_a[0]["best_candidate"]["chromosome"]
    assert all(len(population) == 8 for population in populations_a)


def test_without_crossover_each_offspring_names_only_its_source_parent():
    summaries, populations, _ = evolve(
        population_size=8,
        generations=2,
        seed=23,
        mutation_rate=0.0,
        crossover_rate=0.0,
        evaluator=deterministic_evaluator,
    )
    for candidate in populations[1][2:]:
        assert candidate["operator"] == "selection"
        assert len(candidate["parents"]) == 1
        parent = candidate["parents"][0]
        assert parent["generation"] == 1
        assert any(source["candidate_id"] == parent["candidate_id"] for source in populations[0])
