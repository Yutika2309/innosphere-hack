from __future__ import annotations

"""ADK entry points and utility functions for Lending World."""


# -----------------------------------------------------------------------------
# Restart-safe run summary helpers
# -----------------------------------------------------------------------------

try:
    from .config import load_default_config, resolve_config
    from .engine import LendingWorldSimulation
    from .run_summary import summarise_latest_run, compare_latest_runs
except Exception:  # pragma: no cover
    from .simulation.config import load_default_config, resolve_config  # type: ignore
    from .simulation.engine import LendingWorldSimulation  # type: ignore
    from .simulation.run_summary import summarise_latest_run, compare_latest_runs  # type: ignore


def _run_with_overrides(overrides: dict) -> dict:
    cfg = resolve_config(load_default_config(), chat_overrides=overrides)
    sim = LendingWorldSimulation(cfg)
    # This helper creates a persistent run directory and metadata. Actual agentic
    # timestep execution can continue to call sim.run_timestep(...) externally.
    return {
        "status": "initialised",
        "scenario_name": getattr(cfg, "current_scenario_name", None),
        "run_dir": str(sim.output_dir),
        "metadata": sim.summarise_persisted_run(),
    }


def run_baseline_simulation() -> dict:
    return _run_with_overrides({
        "current_scenario_name": "baseline",
        "scenario_mode": "baseline",
        "enable_db_improvements": False,
    })


def run_improved_simulation() -> dict:
    return _run_with_overrides({
        "current_scenario_name": "improved",
        "scenario_mode": "improved",
        "enable_db_improvements": True,
    })


def summarize_latest_baseline_run() -> dict:
    return summarise_latest_run("runs", "baseline")


def summarize_latest_improved_run() -> dict:
    return summarise_latest_run("runs", "improved")


def compare_latest_baseline_and_improved_runs() -> dict:
    return compare_latest_runs("runs", "baseline", "improved")


try:
    from google.adk import Agent
except Exception:  # pragma: no cover
    Agent = None  # type: ignore

if Agent is not None:
    root_agent = Agent(
        name="lending_world_run_manager",
        model="gemini-2.5-pro",
        instruction=(
            "Manage Lending World simulation runs. Use separate baseline and improved "
            "run directories, and summarise persisted CSV outputs even after restarts."
        ),
        tools=[
            run_baseline_simulation,
            run_improved_simulation,
            summarize_latest_baseline_run,
            summarize_latest_improved_run,
            compare_latest_baseline_and_improved_runs,
        ],
    )
else:
    root_agent = None
