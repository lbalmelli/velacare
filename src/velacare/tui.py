"""Compact Rich dashboard styled after the supplied VelaCare reference."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text


class EvolutionTUI:
    def __init__(
        self,
        *,
        no_color: bool = False,
        total_generations: int = 1,
        population: int = 1,
        seed: int = 42,
        download_only: bool = False,
    ):
        self.no_color = no_color
        self.console = Console(
            force_terminal=not no_color and sys.stdout.isatty(),
            color_system=None if no_color else "standard",
            highlight=False,
            soft_wrap=True,
        )
        self.total_generations = total_generations
        self.population = population
        self.seed = seed
        self.download_only = download_only
        self.started = time.monotonic()
        self.status = "RUNNING"
        self.phases = {
            "data": ["[01] DATA", "Loading UCI dataset 17", "pending"],
            "setup": ["[02] SETUP", "Stratified train / holdout + CV", "pending"],
            "init": ["[03] INIT", f"{population} candidate feature subsets", "pending"],
            "evolve": ["[04] EVOLVE", "Selection • crossover • mutation", "pending"],
        }
        self.samples = 0
        self.feature_count = 30
        self.generation = 0
        self.completed_candidates = 0
        self.partial_candidates: list[dict] = []
        self.partial_elapsed = 0.0
        self.rows: dict[int, dict] = {}
        self.final_metrics: dict | None = None
        self.saved_files: list[str] = []
        self.run_id = ""
        self.progress = Progress(
            BarColumn(bar_width=14, style="blue", complete_style="bright_blue", finished_style="bright_cyan"),
            TextColumn("{task.percentage:>3.0f}%"),
            expand=False,
            console=self.console,
            auto_refresh=False,
        )
        self.progress_task = self.progress.add_task("evolution", total=total_generations, completed=0)
        self.live: Live | None = None

    def start(self) -> None:
        self.live = Live(self._render(), console=self.console, refresh_per_second=8, transient=False, auto_refresh=False)
        self.live.start(refresh=True)

    def stop(self) -> None:
        if self.live is not None:
            self.live.stop()
            self.live = None

    def set_phase(self, phase: str, state: str, detail: str | None = None) -> None:
        current = self.phases[phase]
        current[2] = state
        if detail is not None:
            current[1] = detail
        self._refresh()

    def set_dataset(self, samples: int, features: int) -> None:
        self.samples, self.feature_count = samples, features
        self.phases["data"][1] = f"{samples} samples • {features} numeric features"
        self._refresh()

    def set_run_id(self, run_id: str) -> None:
        self.run_id = run_id
        self._refresh()

    def on_progress(self, generation: int, total: int, completed: int, candidates: list[dict], elapsed: float) -> None:
        self.generation = generation
        self.completed_candidates = completed
        self.partial_candidates = candidates
        self.partial_elapsed = elapsed
        fraction = (generation - 1 + completed / total) / self.total_generations
        self.progress.update(self.progress_task, completed=min(self.total_generations, fraction * self.total_generations))
        self._refresh()

    def on_generation(self, summary: dict, _candidates: list[dict]) -> None:
        self.rows[int(summary["generation"])] = summary
        self.generation = int(summary["generation"])
        self.completed_candidates = self.population
        self.partial_elapsed = float(summary["elapsed_seconds"])
        self.progress.update(self.progress_task, completed=self.generation)
        self._refresh()

    def complete(self, metrics: dict, files: list[Path]) -> None:
        self.status = "COMPLETE"
        self.final_metrics = metrics
        self.saved_files = [path.name for path in files]
        self.progress.update(self.progress_task, completed=self.total_generations)
        self._refresh()

    def download_complete(self, files: list[Path]) -> None:
        self.status = "COMPLETE"
        self.saved_files = [path.name for path in files]
        self.phases["init"] = ["[03] INIT", "Skipped (--download-only)", "skipped"]
        self.phases["evolve"] = ["[04] EVOLVE", "No generations evaluated", "skipped"]
        self._refresh()

    def fail(self, status: str, message: str | None = None) -> None:
        self.status = status.upper()
        if message:
            self.phases["evolve"][1] = message
        self.phases["evolve"][2] = "failed"
        self._refresh()

    def _refresh(self) -> None:
        if self.live is not None:
            self.live.update(self._render(), refresh=True)

    def _style(self, status: str) -> str:
        if self.no_color:
            return ""
        if status == "complete":
            return "bold bright_cyan"
        if status == "active":
            return "bold yellow"
        if status == "failed":
            return "bold red"
        if status == "skipped":
            return "dim"
        if status == "pending":
            return "dim"
        return "bright_cyan"

    def _phase_table(self) -> Table:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(width=15, no_wrap=True)
        table.add_column(ratio=1)
        for phase, (name, detail, state) in self.phases.items():
            icon = {"complete": "✓", "active": "●", "pending": "○", "failed": "!", "skipped": "–"}[state]
            table.add_row(Text(f"{name}  {icon}", style=self._style(state)), Text(detail, style="white" if not self.no_color else ""))
        return table

    def _checkpoint_generations(self) -> list[int]:
        if self.total_generations <= 5:
            return list(range(1, self.total_generations + 1))
        return sorted({1, round(self.total_generations * 0.25), round(self.total_generations * 0.5),
                       round(self.total_generations * 0.75), self.total_generations})

    def _history_table(self) -> Table:
        table = Table(expand=True, box=box.SIMPLE, padding=(0, 1), show_edge=False)
        table.add_column("GENERATION", justify="right", no_wrap=True)
        table.add_column("BEST FITNESS", justify="right")
        table.add_column("FEATURES", justify="right")
        table.add_column("PROGRESS", ratio=1)
        checkpoints = self._checkpoint_generations()
        for generation in checkpoints:
            row = self.rows.get(generation)
            if row is None:
                if self.generation == generation and self.partial_candidates:
                    best = max(self.partial_candidates, key=lambda item: item["fitness"])
                    row = {
                        "best_fitness": best["fitness"],
                        "best_feature_count": best["selected_feature_count"],
                        "generation": generation,
                    }
                else:
                    continue
            fraction = generation / self.total_generations
            width = 12
            filled = int(round(width * fraction))
            bar = Text("━" * filled, style="bright_blue" if not self.no_color else "")
            bar.append("─" * (width - filled), style="dim" if not self.no_color else "")
            is_current = generation == self.generation
            fit_text = f"{row['best_fitness']:.3f}"
            feature_text = f"{row['best_feature_count']} / {self.feature_count}"
            style = "bold bright_cyan" if is_current and self.status == "COMPLETE" else "bold white" if is_current and not self.no_color else ""
            table.add_row(f"{generation:02d}", Text(fit_text, style=style), Text(feature_text, style=style), bar)
        return table

    def _evolution_panel(self) -> Panel:
        if self.download_only:
            return Panel(
                Text("Dataset download and validation only; no generations were evaluated."),
                title="DATASET CHECK",
                border_style="cyan" if not self.no_color else "",
                box=box.ROUNDED,
            )
        if self.partial_candidates:
            best = max(self.partial_candidates, key=lambda item: item["fitness"])
            average = sum(item["fitness"] for item in self.partial_candidates) / len(self.partial_candidates)
            best_fitness = float(best["fitness"])
            feature_count = int(best["selected_feature_count"])
            gen_line = f"Generation {self.generation:02d} / {self.total_generations:02d}"
            detail_line = (
                f"Best fitness {best_fitness:.4f}    Selected features {feature_count:02d} / {self.feature_count}"
            )
        elif self.final_metrics:
            best_fitness = float(self.final_metrics["cv_fitness"])
            feature_count = int(self.final_metrics["selected_feature_count"])
            average = self.rows.get(self.generation, {}).get("mean_fitness", best_fitness)
            gen_line = f"Generation {self.generation:02d} / {self.total_generations:02d}"
            detail_line = f"Best fitness {best_fitness:.4f}    Selected features {feature_count:02d} / {self.feature_count}"
        else:
            average = 0.0
            gen_line = f"Generation {self.generation:02d} / {self.total_generations:02d}"
            detail_line = "Waiting for candidate evaluations"

        stats = Table.grid(expand=True, padding=(0, 1))
        stats.add_column(ratio=1)
        stats.add_column(justify="right")
        stats.add_row(Text(gen_line, style="bold white"), self.progress)
        stats.add_row(Text(detail_line, style="bright_cyan" if not self.no_color else ""), "")
        stats.add_row(Text(f"Mean fitness {average:.4f}    Elapsed {self.partial_elapsed:.1f}s", style="dim"), "")
        history = self._history_table()
        return Panel(Group(stats, history), title="EVOLUTION", border_style="cyan" if not self.no_color else "", box=box.ROUNDED)

    def _render(self):
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(ratio=1)
        grid.add_column(justify="right")
        title = Text("VELACARE  /  EVOLUTION ENGINE", style="bold white" if not self.no_color else "")
        status_style = "bold bright_cyan" if self.status == "COMPLETE" and not self.no_color else "bold red" if self.status in {"FAILED", "INTERRUPTED"} and not self.no_color else "bold yellow" if not self.no_color else ""
        grid.add_row(title, Text(f"● {self.status}", style=status_style))
        command = Text("$ ./run-demo", style="bright_cyan" if not self.no_color else "")
        if self.download_only:
            command.append("  --download-only", style="yellow" if not self.no_color else "")
        elif self.total_generations:
            if self.console.width < 74:
                command.append(
                    f"\n  --generations {self.total_generations}\n  --population {self.population} --seed {self.seed}",
                    style="yellow" if not self.no_color else "",
                )
            else:
                command.append(
                    f"  --generations {self.total_generations} --population {self.population} --seed {self.seed}",
                    style="yellow" if not self.no_color else "",
                )
        body = Group(
            grid,
            Text(""),
            command,
            Text(""),
            self._phase_table(),
            Text(""),
            self._evolution_panel(),
            self._footer(),
        )
        return Panel(body, border_style="cyan" if not self.no_color else "", box=box.ROUNDED, padding=(0, 1))

    def _footer(self) -> Panel | Text:
        if self.status == "COMPLETE":
            if self.final_metrics is None:
                result = Text(f"Validated UCI cache: {self.samples} samples • {self.feature_count} features\n")
                result.append("Saved: " + "  ·  ".join(self.saved_files))
                return Panel(result, border_style="cyan" if not self.no_color else "", box=box.ROUNDED, title="DATA CACHE")
            test = self.final_metrics["held_out_test_metrics"] if self.final_metrics else {}
            cv = self.final_metrics["cv_metrics"] if self.final_metrics else {}
            result = Text(
                f"CV sensitivity: {cv.get('malignant_sensitivity', 0):.3f}\n"
                f"Hold-out accuracy: {test.get('accuracy', 0):.3f}\n"
                f"Hold-out malignant sensitivity: {test.get('malignant_sensitivity', 0):.3f}\n",
                style="white" if not self.no_color else "",
            )
            result.append("Saved files:\n", style="bright_cyan" if not self.no_color else "")
            result.append(
                "run_manifest.json\n"
                "generation_history.csv\n"
                "candidate_history.jsonl\n"
                "best_candidates.json\n"
                "model_metrics.json",
                style="bright_cyan" if not self.no_color else "",
            )
            return Panel(result, border_style="cyan" if not self.no_color else "", box=box.ROUNDED, title=self.run_id)
        if self.status in {"FAILED", "INTERRUPTED"}:
            if self.run_id:
                message = f"\nRun {self.status.lower()}; completed generations are retained in {self.run_id}."
            else:
                message = f"\n{self.status.capitalize()} before an experiment directory was created."
            return Text(message, style="red" if not self.no_color else "")
        return Text(f"\nRun {self.run_id}  •  elapsed {time.monotonic() - self.started:.1f}s", style="dim" if not self.no_color else "")
