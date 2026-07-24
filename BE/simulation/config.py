from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

@dataclass
class SimulationConfig:
    scenario_name: str = "baseline_current_db"
    scenario_mode: str = "baseline"
    enable_db_improvements: bool = False
    num_consumers: int = 14
    num_banks: int = 8
    timesteps: int = 12
    seed: int = 42
    output_dir: str = "output"
    log_dir: str = "logs"
    step_mode: str = "agentic"
    agentic_mode: bool = True
    enable_world_news_agent: bool = True
    enable_customer_agent: bool = True
    enable_bank_agent: bool = True
    enable_marketplace_agent: bool = True
    enable_post_processing_agent: bool = True
    customer_agent_batch_size: int = 10
    parallel_agent_start_jitter_seconds: float = 1.5
    parallel_agent_semaphore_limit: int = 8
    public_summary_window_timesteps: int = 10
    max_actions_per_agent_per_timestep: int = 5
    strict_schema_validation_enabled: bool = True
    invalid_row_policy: str = "quarantine"
    auto_repair_missing_timestep: bool = True
    auto_repair_customer_id_from_actor_id: bool = True
    auto_repair_bank_id_from_actor_id: bool = True
    reject_unrepairable_actor_identity: bool = True
    canonicalise_bank_offer_schema: bool = True
    split_lifecycle_events_and_snapshots: bool = True
    bank_require_identity_fields: bool = True
    max_invalid_rows_logged_per_timestep: int = 100
    customer_min_actions_per_active_customer: int = 1
    customer_allow_empty_batch_output: bool = False
    world_news_min_rows_per_timestep: int = 1
    marketplace_require_output_if_public_offers_exist: bool = True
    default_marketplace_reliance: float = 0.5
    default_public_news_reliance: float = 0.3
    default_relationship_bank_reliance: float = 0.4
    default_branch_advice_preference: float = 0.2
    default_digital_comparison_preference: float = 0.5

def load_default_config(path: str | Path = "default_configs.json") -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)

def _coerce_value(field_name: str, value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(default, bool):
        return _as_bool(value)
    if isinstance(default, int) and not isinstance(default, bool):
        try: return int(value)
        except Exception: return default
    if isinstance(default, float):
        try: return float(value)
        except Exception: return default
    return value

def _validate_config_values(values: Dict[str, Any]) -> Dict[str, Any]:
    values = dict(values)
    if values.get("invalid_row_policy") not in {"quarantine", "reject", "warn"}:
        values["invalid_row_policy"] = "quarantine"
    int_min_fields = {
        "num_consumers": 1, "num_banks": 1, "timesteps": 1,
        "customer_agent_batch_size": 1, "parallel_agent_semaphore_limit": 1,
        "public_summary_window_timesteps": 1, "max_actions_per_agent_per_timestep": 1,
        "customer_min_actions_per_active_customer": 0,
        "world_news_min_rows_per_timestep": 0,
        "max_invalid_rows_logged_per_timestep": 0,
    }
    for field, minimum in int_min_fields.items():
        try: values[field] = max(minimum, int(values.get(field, minimum)))
        except Exception: values[field] = minimum
    try: values["parallel_agent_start_jitter_seconds"] = max(0.0, float(values.get("parallel_agent_start_jitter_seconds", 1.5)))
    except Exception: values["parallel_agent_start_jitter_seconds"] = 1.5
    for field in ["default_marketplace_reliance", "default_public_news_reliance", "default_relationship_bank_reliance", "default_branch_advice_preference", "default_digital_comparison_preference"]:
        try: values[field] = min(1.0, max(0.0, float(values.get(field, 0.5))))
        except Exception: values[field] = 0.5
    return values

def resolve_config(defaults: Optional[Dict[str, Any]] = None, args: Optional[argparse.Namespace] = None, chat_overrides: Optional[Dict[str, Any]] = None) -> SimulationConfig:
    base = SimulationConfig()
    values = dict(base.__dict__)
    sources = [defaults or {}, vars(args) if args is not None and hasattr(args, "__dict__") else {}, chat_overrides or {}]
    for source in sources:
        for key, value in source.items():
            if key in values and value is not None:
                values[key] = _coerce_value(key, value, values[key])
    values = _validate_config_values(values)
    return SimulationConfig(**values)

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Lending World simulation")
    parser.add_argument("--num-consumers", type=int, default=None)
    parser.add_argument("--num-banks", type=int, default=None)
    parser.add_argument("--timesteps", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--log-dir", type=str, default=None)
    parser.add_argument("--scenario-name", type=str, default=None)
    parser.add_argument("--scenario-mode", type=str, default=None)
    parser.add_argument("--agentic-mode", type=_as_bool, default=None)
    parser.add_argument("--strict-schema-validation-enabled", type=_as_bool, default=None)
    parser.add_argument("--invalid-row-policy", type=str, choices=["quarantine", "reject", "warn"], default=None)
    return parser

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Backwards-compatible CLI parser expected by existing imports.

    Some modules import parse_args directly from simulation.config. The previous
    config rewrite kept build_arg_parser() but accidentally removed parse_args(),
    causing ImportError during module load.
    """
    return build_arg_parser().parse_args(argv)

