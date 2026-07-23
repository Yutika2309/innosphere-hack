from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import json


@dataclass(frozen=True)
class RunPaths:
    runs_root_dir: Path
    scenario_name: str
    run_id: str
    scenario_dir: Path
    run_dir: Path
    latest_pointer_path: Path
    metadata_path: Path


def make_run_id() -> str:
    """Create a stable, sortable run identifier."""
    return "run_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def resolve_run_paths(cfg: Any) -> RunPaths:
    """Resolve scenario-specific run paths from config.

    Baseline and improved simulations are kept in separate scenario folders:
    runs/<scenario_name>/<run_id>/.
    """
    runs_root = Path(getattr(cfg, "runs_root_dir", "runs") or "runs")
    scenario_name = str(
        getattr(cfg, "current_scenario_name", None)
        or getattr(cfg, "scenario_mode", None)
        or getattr(cfg, "scenario_name", None)
        or "baseline"
    )
    run_id = str(getattr(cfg, "run_id", None) or make_run_id())
    scenario_dir = runs_root / scenario_name
    run_dir = scenario_dir / run_id
    return RunPaths(
        runs_root_dir=runs_root,
        scenario_name=scenario_name,
        run_id=run_id,
        scenario_dir=scenario_dir,
        run_dir=run_dir,
        latest_pointer_path=scenario_dir / "latest_run.json",
        metadata_path=run_dir / "run_metadata.json",
    )


def write_latest_pointer(paths: RunPaths) -> None:
    paths.latest_pointer_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scenario_name": paths.scenario_name,
        "run_id": paths.run_id,
        "run_dir": str(paths.run_dir),
        "metadata_path": str(paths.metadata_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    paths.latest_pointer_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_latest_pointer(runs_root_dir: str | Path, scenario_name: str) -> Optional[dict]:
    path = Path(runs_root_dir) / scenario_name / "latest_run.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def latest_run_dir(runs_root_dir: str | Path, scenario_name: str) -> Optional[Path]:
    pointer = load_latest_pointer(runs_root_dir, scenario_name)
    if not pointer:
        return None
    run_dir = pointer.get("run_dir")
    return Path(run_dir) if run_dir else None
