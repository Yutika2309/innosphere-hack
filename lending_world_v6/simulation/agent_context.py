from __future__ import annotations

"""Context-building helpers for the Lending World simulation.

The intent is to keep LLM prompts compact, canonical and privacy-safe:
- world-news receives only exogenous scenario/market information
- banks receive public summary + own private state/history only
- customers receive public summary + committed marketplace dashboard/offers + own private state only
- marketplace receives committed public data only; never same-timestep pending outputs
"""

from typing import Any, Dict, Iterable, List, Optional


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _latest_row(rows: Iterable[Dict[str, Any]] | None) -> Dict[str, Any]:
    rows = list(rows or [])
    return dict(rows[-1]) if rows else {}


def _visibility_public(row: Dict[str, Any]) -> bool:
    return str(row.get("visibility", "")).lower() == "public"


def _take_recent(
    rows: Iterable[Dict[str, Any]] | None, limit: int = 50
) -> List[Dict[str, Any]]:
    return [dict(r) for r in list(rows or [])[-limit:] if isinstance(r, dict)]


def latest_public_summary(sim: Any) -> Dict[str, Any]:
    rows = getattr(sim, "public_information_summary_rows", []) or []
    latest = _latest_row(rows)
    if not latest:
        return {
            "public_information_summary": "No public summary available.",
            "summary_from_timestep": None,
            "summary_to_timestep": None,
            "window_size": getattr(
                getattr(sim, "cfg", object()), "public_summary_window_timesteps", 10
            ),
        }
    return {
        "public_information_summary": latest.get(
            "public_information_summary", "No public summary available."
        ),
        "summary_from_timestep": latest.get("summary_from_timestep"),
        "summary_to_timestep": latest.get("summary_to_timestep"),
        "window_size": latest.get("window_size"),
    }


def latest_marketplace_dashboard(sim: Any) -> Dict[str, Any]:
    if hasattr(sim, "get_latest_marketplace_dashboard"):
        try:
            return dict(sim.get_latest_marketplace_dashboard())
        except Exception:
            pass
    latest = _latest_row(getattr(sim, "marketplace_dashboard_rows", []) or [])
    if latest:
        return latest
    return {
        "dashboard_timestep": getattr(sim, "current_timestep", 0),
        "public_offer_count": 0,
        "public_bank_count": 0,
        "dashboard_summary": "No marketplace dashboard available yet.",
    }


def committed_public_rows(
    sim: Any, table_name: str, limit: int = 100
) -> List[Dict[str, Any]]:
    rows = getattr(sim, f"{table_name}_rows", []) or []
    return _take_recent(
        [r for r in rows if isinstance(r, dict) and _visibility_public(r)], limit
    )


def canonical_public_offer_view(offer: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the offer fields customers/marketplace should see."""
    keys = [
        "timestep",
        "bank_id",
        "bank_name",
        "offer_id",
        "product_id",
        "product_name",
        "offer_type",
        "base_interest_rate_apr",
        "effective_interest_rate_apr",
        "processing_fee_pct",
        "relationship_discount_bps",
        "min_credit_score",
        "min_schufa_score_pct",
        "min_loan_amount_eur",
        "max_loan_amount_eur",
        "min_term_months",
        "max_term_months",
        "target_customer_segment",
        "offer_description",
        "valid_from_timestep",
        "valid_to_timestep",
    ]
    return {k: offer.get(k) for k in keys if k in offer}


def build_world_news_context(sim: Any) -> Dict[str, Any]:
    cfg = getattr(sim, "cfg", object())
    return {
        "timestep": getattr(sim, "current_timestep", 0) + 1,
        "agent_name": "world_news_agent",
        "actor_type": "world",
        "actor_id": "world_news",
        "market": "Germany",
        "scenario_name": getattr(cfg, "scenario_name", "baseline_current_db"),
        "scenario_mode": getattr(cfg, "scenario_mode", "baseline"),
        "news_min_rows": getattr(cfg, "world_news_min_rows_per_timestep", 1),
        "exogenous": True,
        "context_contract": "Generate external news only. Do not use public summaries, bank outputs, customer outputs or marketplace outputs.",
    }


def build_bank_contexts(sim: Any) -> List[Dict[str, Any]]:
    public_summary = latest_public_summary(sim)
    dashboard = latest_marketplace_dashboard(sim)
    contexts: List[Dict[str, Any]] = []
    banks = getattr(sim, "banks", []) or []
    for bank in banks:
        bank_id = bank.get("bank_id") or bank.get("actor_id")
        if not bank_id:
            continue
        contexts.append(
            {
                "timestep": getattr(sim, "current_timestep", 0) + 1,
                "agent_name": "bank_agent",
                "actor_type": "bank",
                "actor_id": bank_id,
                "bank_id": bank_id,
                "bank_name": bank.get("bank_name"),
                "bank_state": dict(bank),
                "bank_private_summary": getattr(sim, "private_summaries", {}).get(
                    bank_id, ""
                ),
                "public_information_summary": public_summary[
                    "public_information_summary"
                ],
                "public_summary_from_timestep": public_summary.get(
                    "summary_from_timestep"
                ),
                "public_summary_to_timestep": public_summary.get("summary_to_timestep"),
                "marketplace_dashboard": dashboard,
                "own_previous_bank_actions": _take_recent(
                    [
                        r
                        for r in getattr(sim, "bank_actions_rows", [])
                        if r.get("bank_id") == bank_id
                    ],
                    25,
                ),
                "own_previous_bank_offers": _take_recent(
                    [
                        r
                        for r in getattr(sim, "bank_offers_rows", [])
                        if r.get("bank_id") == bank_id
                    ],
                    25,
                ),
                "own_previous_marketing_actions": _take_recent(
                    [
                        r
                        for r in getattr(sim, "marketing_actions_rows", [])
                        if r.get("bank_id") == bank_id
                    ],
                    25,
                ),
                "context_contract": "Use only this bank's private state/history plus public summary/dashboard. Never use another bank's private data.",
            }
        )
    return contexts


def build_customer_contexts(sim: Any) -> List[Dict[str, Any]]:
    cfg = getattr(sim, "cfg", object())
    public_summary = latest_public_summary(sim)
    dashboard = latest_marketplace_dashboard(sim)
    public_offers = [
        canonical_public_offer_view(r)
        for r in committed_public_rows(sim, "bank_offers", 80)
    ]
    contexts: List[Dict[str, Any]] = []
    for consumer in getattr(sim, "consumers", []) or []:
        if not consumer.get("active", True):
            continue
        cid = consumer.get("consumer_id") or consumer.get("actor_id")
        if not cid:
            continue
        contexts.append(
            {
                "timestep": getattr(sim, "current_timestep", 0) + 1,
                "agent_name": "customer_agent",
                "actor_type": "consumer",
                "actor_id": cid,
                "consumer_id": cid,
                "customer_state": dict(consumer),
                "current_funnel_stage": consumer.get("funnel_stage", "lead"),
                "own_private_summary": getattr(sim, "private_summaries", {}).get(
                    cid, ""
                ),
                "public_information_summary": public_summary[
                    "public_information_summary"
                ],
                "public_summary_from_timestep": public_summary.get(
                    "summary_from_timestep"
                ),
                "public_summary_to_timestep": public_summary.get("summary_to_timestep"),
                "marketplace_dashboard": dashboard,
                "eligible_public_offers": public_offers,
                "source_preferences": {
                    "marketplace_reliance": getattr(
                        cfg, "default_marketplace_reliance", 0.5
                    ),
                    "public_news_reliance": getattr(
                        cfg, "default_public_news_reliance", 0.3
                    ),
                    "relationship_bank_reliance": getattr(
                        cfg, "default_relationship_bank_reliance", 0.4
                    ),
                    "branch_advice_preference": getattr(
                        cfg, "default_branch_advice_preference", 0.2
                    ),
                    "digital_comparison_preference": getattr(
                        cfg, "default_digital_comparison_preference", 0.5
                    ),
                },
                "decision_contract": "Emit at least one valid consumer_action for this active customer. Emit funnel_event when stage changes.",
            }
        )
    return contexts


def build_marketplace_context(sim: Any) -> Dict[str, Any]:
    public_summary = latest_public_summary(sim)
    return {
        "timestep": getattr(sim, "current_timestep", 0) + 1,
        "agent_name": "marketplace_agent",
        "actor_type": "marketplace",
        "actor_id": "loan_marketplace",
        "public_information_summary": public_summary["public_information_summary"],
        "public_summary_from_timestep": public_summary.get("summary_from_timestep"),
        "public_summary_to_timestep": public_summary.get("summary_to_timestep"),
        "committed_public_bank_offers": [
            canonical_public_offer_view(r)
            for r in committed_public_rows(sim, "bank_offers", 120)
        ],
        "committed_public_bank_actions": committed_public_rows(sim, "bank_actions", 80),
        "committed_public_marketing_actions": committed_public_rows(
            sim, "marketing_actions", 80
        ),
        "previous_marketplace_dashboard": latest_marketplace_dashboard(sim),
        "reads_committed_state_only": True,
        "source_snapshot_timestep": getattr(sim, "current_timestep", 0),
        "context_contract": "Use committed public data only. Do not use same-timestep pending bank outputs or private data.",
    }


def build_post_processing_context(sim: Any) -> Dict[str, Any]:
    public_rows: List[Dict[str, Any]] = []
    for table in [
        "world_news",
        "bank_offers",
        "bank_actions",
        "marketing_actions",
        "marketplace_rankings",
        "marketplace_recommendations",
        "marketplace_visibility_events",
        "customer_feedback",
        "funnel_events",
    ]:
        public_rows.extend(committed_public_rows(sim, table, 100))
    return {
        "timestep": getattr(sim, "current_timestep", 0),
        "agent_name": "post_processing_agent",
        "actor_type": "system",
        "actor_id": "post_processing",
        "public_rows": public_rows[-150:],
        "public_row_count": len(public_rows),
        "marketplace_dashboard": latest_marketplace_dashboard(sim),
        "context_contract": "Summarise public rows only. Never include private rows or invalid rows.",
    }


class AgentContextMixin:
    """Optional mixin for engines that prefer method-based context builders."""

    def build_world_news_agent_context(self) -> Dict[str, Any]:
        return build_world_news_context(self)

    def build_bank_agent_contexts(self) -> List[Dict[str, Any]]:
        return build_bank_contexts(self)

    def build_customer_agent_contexts(self) -> List[Dict[str, Any]]:
        return build_customer_contexts(self)

    def build_marketplace_agent_context(self) -> Dict[str, Any]:
        return build_marketplace_context(self)

    def build_post_processing_agent_context(self) -> Dict[str, Any]:
        return build_post_processing_context(self)
