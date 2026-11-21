from velacare.tui import EvolutionTUI


def test_no_color_render_has_required_panels_without_ansi():
    tui = EvolutionTUI(no_color=True, total_generations=3, population=8, seed=17)
    tui.set_dataset(569, 30)
    tui.set_phase("data", "complete")
    tui.set_phase("setup", "complete", "Stratified train / holdout + CV")
    metrics = {
        "cv_fitness": 0.9,
        "selected_feature_count": 8,
        "cv_metrics": {"malignant_sensitivity": 0.9},
        "held_out_test_metrics": {"accuracy": 0.9, "malignant_sensitivity": 0.8},
    }
    tui.set_run_id("run_001")
    tui.on_generation(
        {
            "generation": 3,
            "best_fitness": 0.9,
            "best_feature_count": 8,
            "mean_fitness": 0.8,
            "elapsed_seconds": 1.0,
        },
        [],
    )
    tui.complete(metrics, [])
    tui.console.width = 50
    with tui.console.capture() as capture:
        tui.console.print(tui._render())
    rendered = capture.get()
    assert "VELACARE" in rendered
    assert "[01] DATA" in rendered
    assert "[02] SETUP" in rendered
    assert "[03] INIT" in rendered
    assert "[04] EVOLVE" in rendered
    assert "--seed 17" in rendered
    assert "COMPLETE" in rendered
    assert "Hold-out malignant sensitivity: 0.800" in rendered
    assert "Hold-out accuracy: 0.900" in rendered
    assert "candidate_history.jsonl" in rendered
    assert "generation_history.csv" in rendered
    assert "best_candidates.json" in rendered
    assert "\x1b[" not in rendered
