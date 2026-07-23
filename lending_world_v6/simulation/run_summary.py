from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import json
import pandas as pd


CORE_FILES = [
    "conversion_metrics.csv",
    "marketplace_dashboard.csv",
    "bank_offers.csv",
    "consumer_actions.csv",
    "customer_lifecycle_snapshot.csv",
    "invalid_rows.csv",
    "db_loss_analysis.csv",
    "db_recommendations.csv",
]


def _read_csv(run_dir: Path, file_name: str) -> Optional[pd.DataFrame]:
    path = run_dir / file_name
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def _numeric(row: dict, key: str) -> float:
    try:
        return float(row.get(key, 0) or 0)
    except Exception:
        return 0.0


def summarise_run_dir(run_dir: str | Path) -> dict[str, Any]:
    """Summarise a completed/persisted run from CSV files only.

    This deliberately does not depend on a live engine instance, so it works after
    ADK or the Python process restarts.
    """
    run_dir = Path(run_dir)
    summary: dict[str, Any] = {
        "run_dir": str(run_dir),
        "exists": run_dir.exists(),
        "files_found": {file_name: (run_dir / file_name).exists() for file_name in CORE_FILES},
    }

    metadata_path = run_dir / "run_metadata.json"
    if metadata_path.exists():
        try:
            summary["run_metadata"] = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            summary["run_metadata_error"] = str(exc)

    conversion = _read_csv(run_dir, "conversion_metrics.csv")
    if conversion is not None:
        summary["conversion_metric_rows"] = int(len(conversion))
        if not conversion.empty:
            summary["final_conversion_metrics"] = conversion.tail(1).to_dict("records")[0]
            if "timestep" in conversion.columns:
                summary["final_timestep"] = int(pd.to_numeric(conversion["timestep"], errors="coerce").max())

    dashboard = _read_csv(run_dir, "marketplace_dashboard.csv")
    if dashboard is not None:
        summary["marketplace_dashboard_rows"] = int(len(dashboard))
        if not dashboard.empty:
            summary["final_marketplace_dashboard"] = dashboard.tail(1).to_dict("records")[0]

    offers = _read_csv(run_dir, "bank_offers.csv")
    if offers is not None:
        summary["bank_offer_count"] = int(len(offers))
        if "visibility" in offers.columns:
            summary["bank_offers_by_visibility"] = offers["visibility"].fillna("(blank)").astype(str).value_counts().to_dict()
        if "suppressed_by_offer_cap" in offers.columns:
            summary["suppressed_offer_count"] = int(offers["suppressed_by_offer_cap"].astype(str).str.lower().eq("true").sum())

    invalid = _read_csv(run_dir, "invalid_rows.csv")
    if invalid is not None:
        summary["invalid_row_count"] = int(len(invalid))
        if "source_table" in invalid.columns:
            summary["invalid_rows_by_table"] = invalid["source_table"].fillna("(blank)").astype(str).value_counts().to_dict()
        if "error_message" in invalid.columns:
            summary["top_invalid_errors"] = invalid["error_message"].fillna("(blank)").astype(str).value_counts().head(10).to_dict()

    customer_actions = _read_csv(run_dir, "consumer_actions.csv")
    if customer_actions is not None:
        summary["consumer_action_count"] = int(len(customer_actions))
        if "decision_reason" in customer_actions.columns:
            blank = customer_actions["decision_reason"].isna() | customer_actions["decision_reason"].astype(str).str.strip().eq("")
            summary["consumer_actions_missing_decision_reason"] = int(blank.sum())

    lifecycle = _read_csv(run_dir, "customer_lifecycle_snapshot.csv")
    if lifecycle is not None and not lifecycle.empty and "timestep" in lifecycle.columns:
        numeric_timestep = pd.to_numeric(lifecycle["timestep"], errors="coerce")
        max_timestep = numeric_timestep.max()
        final = lifecycle[numeric_timestep.eq(max_timestep)]
        summary["final_lifecycle_timestep"] = int(max_timestep) if pd.notna(max_timestep) else None
        summary["final_customer_count"] = int(len(final))
        if "funnel_stage" in final.columns:
            summary["final_funnel_stage_counts"] = final["funnel_stage"].fillna("(blank)").astype(str).value_counts().to_dict()
        if "selected_bank" in final.columns:
            summary["final_selected_bank_counts"] = final["selected_bank"].fillna("(blank)").astype(str).value_counts().to_dict()

    return summary


def load_latest_run_dir(runs_root_dir: str | Path, scenario_name: str) -> Optional[Path]:
    pointer = Path(runs_root_dir) / scenario_name / "latest_run.json"
    if not pointer.exists():
        return None
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
        run_dir = data.get("run_dir")
        return Path(run_dir) if run_dir else None
    except Exception:
        return None


def summarise_latest_run(runs_root_dir: str | Path = "runs", scenario_name: str = "baseline") -> dict[str, Any]:
    run_dir = load_latest_run_dir(runs_root_dir, scenario_name)
    if run_dir is None:
        return {"scenario_name": scenario_name, "error": "No latest_run.json found for scenario."}
    return summarise_run_dir(run_dir)


def compare_run_dirs(baseline_run_dir: str | Path, improved_run_dir: str | Path) -> dict[str, Any]:
    baseline = summarise_run_dir(baseline_run_dir)
    improved = summarise_run_dir(improved_run_dir)
    b = baseline.get("final_conversion_metrics") or {}
    i = improved.get("final_conversion_metrics") or {}
    metric_keys = [
        "deutsche_bank_wins",
        "deutsche_bank_selected_customers",
        "deutsche_bank_acquired_customers",
        "deutsche_bank_closed_applications",
        "competitor_wins",
        "dropped",
        "recoverable_losses",
        "deutsche_bank_win_rate",
    ]
    return {
        "baseline": baseline,
        "improved": improved,
        "metric_deltas": {key: _numeric(i, key) - _numeric(b, key) for key in metric_keys},
    }


def compare_latest_runs(runs_root_dir: str | Path = "runs", baseline_scenario: str = "baseline", improved_scenario: str = "improved") -> dict[str, Any]:
    baseline_dir = load_latest_run_dir(runs_root_dir, baseline_scenario)
    improved_dir = load_latest_run_dir(runs_root_dir, improved_scenario)
    if baseline_dir is None or improved_dir is None:
        return {
            "status": "missing_run",
            "baseline_found": baseline_dir is not None,
            "improved_found": improved_dir is not None,
        }
    return compare_run_dirs(baseline_dir, improved_dir)
