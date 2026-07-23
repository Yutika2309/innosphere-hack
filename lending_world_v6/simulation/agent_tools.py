"""Tool functions for the Germany lending simulation agents.

This module keeps the ADK agent declarations lightweight by holding the
simulation heuristics, offer-generation tools, funnel-decision tools, and shared
scoring helpers separately from ``simulation.agents``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


FUNNEL_STAGES = [
    "lead",
    "aware",
    "interested",
    "prequalified",
    "application_started",
    "application_submitted",
    "kyc_pending",
    "under_review",
    "approved",
    "offer_received",
    "accepted",
    "disbursed",
    "dropped",
    "rejected",
]

TERMINAL_STAGES = {"disbursed", "dropped", "rejected"}

DROP_REASONS = [
    "rate_too_high",
    "competitor_offer_better",
    "documentation_too_complex",
    "approval_too_slow",
    "loan_amount_insufficient",
    "monthly_emi_too_high",
    "kyc_or_schufa_issue",
    "poor_digital_experience",
    "branch_visit_required",
    "changed_mind",
]


# -----------------------------------------------------------------------------
# Small parsing/scoring helpers
# -----------------------------------------------------------------------------
def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _level_score(value: Any, default: float = 0.5) -> float:
    mapping = {
        "low": 0.25,
        "medium": 0.5,
        "high": 0.8,
    }
    if isinstance(value, str):
        return mapping.get(value.strip().lower(), default)
    return default


def _monthly_emi(principal: float, annual_rate_pct: float, tenure_months: int) -> float:
    if principal <= 0 or tenure_months <= 0:
        return 0.0
    monthly_rate = annual_rate_pct / 100.0 / 12.0
    if monthly_rate <= 0:
        return principal / tenure_months
    return (
        principal
        * monthly_rate
        * ((1 + monthly_rate) ** tenure_months)
        / (((1 + monthly_rate) ** tenure_months) - 1)
    )


def _campaigns_for_bank(
    campaigns: List[Dict[str, Any]], bank_id: str
) -> List[Dict[str, Any]]:
    return [c for c in campaigns if c.get("bank_id") == bank_id]


def _apply_db_scenario_state(
    bank: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    """Return a bank persona with the correct DB scenario state applied.

    Competitor banks are returned unchanged. For Deutsche Bank, baseline runs use
    current-state operating assumptions, while improved runs use future-state
    assumptions. Config-level DB state overrides take precedence over persona-level
    current_state/improved_state values so chat/CLI scenario overrides can adjust
    the simulation without editing bank_personas.json.
    """
    resolved_bank = dict(bank or {})
    deutsche_bank_id = str(context.get("deutsche_bank_id") or "B001")
    bank_id = str(resolved_bank.get("bank_id") or "")

    if bank_id != deutsche_bank_id:
        return resolved_bank

    scenario_mode = str(context.get("scenario_mode") or "baseline").strip().lower()
    enable_db_improvements = bool(
        context.get("enable_db_improvements", scenario_mode == "improved")
    )
    use_improved_state = scenario_mode == "improved" or enable_db_improvements

    persona_state_key = "improved_state" if use_improved_state else "current_state"
    config_state_key = "db_improved_state" if use_improved_state else "db_current_state"

    persona_state = resolved_bank.get(persona_state_key) or {}
    config_state = context.get(config_state_key) or {}

    if isinstance(persona_state, dict):
        resolved_bank.update(persona_state)
    if isinstance(config_state, dict):
        resolved_bank.update(config_state)

    resolved_bank["scenario_mode"] = scenario_mode
    resolved_bank["scenario_state"] = (
        "improved_state" if use_improved_state else "current_state"
    )
    resolved_bank["enable_db_improvements"] = use_improved_state
    return resolved_bank


def _feedback_contains(feedback: List[Dict[str, Any]], text: str) -> bool:
    needle = text.lower()
    for item in feedback:
        msg = str(item.get("message", "")).lower()
        if needle in msg:
            return True
    return False


# -----------------------------------------------------------------------------
# Existing compatibility tools
# -----------------------------------------------------------------------------
def consumer_decision_tool(context: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic fallback for legacy consumer actions.

    This remains backward-compatible with the original engine. The richer
    funnel-aware logic is implemented in consumer_funnel_decision_tool().
    """
    persona = context.get("persona", {})
    public = context.get("public_information", {})
    prev_summary = context.get("previous_summary", "")

    income = _as_float(persona.get("monthly_income"), 0.0)
    expense = _as_float(persona.get("monthly_expense"), 0.0)
    credit = _as_int(persona.get("credit_score"), 650)
    schufa = _as_float(persona.get("schufa_score_pct"), 90.0)
    loan_need = _as_float(persona.get("loan_need_probability"), 0.5)
    expected_amount = _as_float(persona.get("expected_loan_amount"), 0.0)

    actions: List[Dict[str, Any]] = []
    disposable = income - expense

    if disposable < 500 or credit < 640 or schufa < 82:
        actions.append({"action": "no_action", "reason": "budget_or_schufa_constraint"})
    elif loan_need > 0.6:
        amount = int(expected_amount or max(3000, min(50000, disposable * 12)))
        actions.append(
            {
                "action": "apply_loan",
                "amount": amount,
                "currency": "EUR",
                "target_bank": persona.get("preferred_bank")
                or public.get("top_public_bank", "B001"),
            }
        )
        actions.append(
            {
                "action": "compare_bank_offers",
                "count": public.get("visible_offer_count", 1),
            }
        )
    else:
        actions.append({"action": "no_action", "reason": "low_current_need"})

    summary_update = (
        f"Prev: {prev_summary[:120]} | NewActions: {_safe_json(actions)[:240]}"
    )
    return {
        "actions": actions,
        "new_summary": summary_update,
    }


def bank_decision_tool(context: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic fallback for bank strategy actions under constraints."""
    persona = context.get("persona", {})
    public = context.get("public_information", {})
    feedback = context.get("customer_feedback", [])
    prev_summary = context.get("previous_summary", "")

    rate = _as_float(persona.get("base_interest_rate"), 7.5)
    strictness = persona.get("approval_strictness", "medium")
    max_disbursal = _as_float(persona.get("max_monthly_disbursal"), 1000000.0)
    demand_index = _as_float(public.get("loan_demand_index"), 0.5)

    actions: List[Dict[str, Any]] = []
    if demand_index > 0.65:
        adj = -0.15 if strictness != "high" else 0.05
        actions.append(
            {"action": "adjust_interest_rate", "new_rate": round(rate + adj, 2)}
        )
        actions.append(
            {"action": "publish_offer", "segment": "prime_and_near_prime_germany"}
        )
    elif demand_index < 0.35:
        actions.append(
            {"action": "tighten_underwriting", "reason": "weak_market_signal"}
        )
    else:
        actions.append({"action": "no_action", "reason": "stable_signal"})

    if _feedback_contains(feedback, "Faster approval") or _feedback_contains(
        feedback, "approval"
    ):
        actions.append(
            {"action": "improve_approval_speed", "reason": "customer_feedback"}
        )
    if max_disbursal < 1000000:
        actions.append({"action": "cap_disbursal", "cap": int(max_disbursal)})

    summary_update = (
        f"Prev: {prev_summary[:120]} | NewActions: {_safe_json(actions)[:240]}"
    )
    return {
        "actions": actions,
        "new_summary": summary_update,
    }


# -----------------------------------------------------------------------------
# Germany market / funnel-aware tools
# -----------------------------------------------------------------------------
def marketing_decision_tool(context: Dict[str, Any]) -> Dict[str, Any]:
    """Create Germany-market loan marketing campaigns for a bank.

    Campaigns model public bank actions such as advertising lower Ratenkredit
    rates, faster online approval, relationship pricing for salary-account
    customers, or debt-consolidation offers.
    """
    bank = context.get("persona") or context.get("bank") or {}
    public = context.get("public_information", {})
    feedback = context.get("customer_feedback", [])
    timestep = _as_int(context.get("timestep"), 0)
    max_actions = _as_int(context.get("max_marketing_actions"), 2)

    bank_id = bank.get("bank_id", "B001")
    bank_name = bank.get("name", "Deutsche Bank")
    demand_index = _as_float(public.get("loan_demand_index"), 0.5)
    digital_friction = _as_float(bank.get("digital_friction_score"), 0.3)
    approval_days = _as_int(bank.get("average_approval_time_days"), 3)
    base_budget = _as_float(bank.get("marketing_budget"), 500000)
    relationship_discount = _as_int(bank.get("relationship_discount_bps"), 20)

    campaigns: List[Dict[str, Any]] = []

    if bank_id == "B001":
        campaigns.append(
            {
                "timestep": timestep,
                "bank_id": bank_id,
                "bank_name": bank_name,
                "campaign_type": "salary_account_relationship_ratenkredit",
                "target_segment": "salary_account_and_affluent_salaried",
                "message": "Relationship-priced Deutsche Bank Ratenkredit for salary-account customers in Germany.",
                "rate_discount_bps": max(relationship_discount, 35),
                "processing_fee_discount_pct": 0,
                "promised_approval_time_days": min(approval_days, 2),
                "digital_push": True,
                "budget_spend": int(base_budget * 0.18),
                "expected_lead_lift": 0.16,
            }
        )
    elif digital_friction < 0.2:
        campaigns.append(
            {
                "timestep": timestep,
                "bank_id": bank_id,
                "bank_name": bank_name,
                "campaign_type": "fast_online_ratenkredit",
                "target_segment": "digital_first_prime_customers",
                "message": "Fast online Ratenkredit with low-friction digital application.",
                "rate_discount_bps": 20,
                "processing_fee_discount_pct": 0,
                "promised_approval_time_days": max(1, min(approval_days, 2)),
                "digital_push": True,
                "budget_spend": int(base_budget * 0.16),
                "expected_lead_lift": 0.14,
            }
        )
    else:
        campaigns.append(
            {
                "timestep": timestep,
                "bank_id": bank_id,
                "bank_name": bank_name,
                "campaign_type": "trusted_branch_personal_loan",
                "target_segment": "relationship_and_branch_customers",
                "message": "Trusted personal loan consultation with local German banking relationship.",
                "rate_discount_bps": relationship_discount,
                "processing_fee_discount_pct": 0,
                "promised_approval_time_days": approval_days,
                "digital_push": False,
                "budget_spend": int(base_budget * 0.12),
                "expected_lead_lift": 0.1,
            }
        )

    if _feedback_contains(feedback, "lower rates") or demand_index < 0.45:
        campaigns.append(
            {
                "timestep": timestep,
                "bank_id": bank_id,
                "bank_name": bank_name,
                "campaign_type": "rate_discount_ratenkredit",
                "target_segment": "price_sensitive_borrowers",
                "message": "Limited-period rate discount for eligible German consumer-loan applicants.",
                "rate_discount_bps": 30,
                "processing_fee_discount_pct": 0,
                "promised_approval_time_days": approval_days,
                "digital_push": digital_friction < 0.35,
                "budget_spend": int(base_budget * 0.1),
                "expected_lead_lift": 0.12,
            }
        )
    elif _feedback_contains(feedback, "approval") or approval_days > 3:
        campaigns.append(
            {
                "timestep": timestep,
                "bank_id": bank_id,
                "bank_name": bank_name,
                "campaign_type": "faster_approval_journey",
                "target_segment": "urgent_borrowers",
                "message": "Improved approval journey with clearer document guidance and faster decisioning.",
                "rate_discount_bps": 10,
                "processing_fee_discount_pct": 0,
                "promised_approval_time_days": max(1, approval_days - 1),
                "digital_push": True,
                "budget_spend": int(base_budget * 0.1),
                "expected_lead_lift": 0.1,
            }
        )

    campaigns = campaigns[:max_actions]
    return {"campaigns": campaigns, "actions": campaigns}


def generate_bank_offer_tool(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a bank offer for one German consumer-loan applicant."""
    consumer = context.get("consumer") or context.get("persona") or {}
    raw_bank = context.get("bank") or {}
    bank = _apply_db_scenario_state(raw_bank, context)
    campaigns = context.get("marketing_campaigns", [])
    tenure_months = _as_int(context.get("tenure_months"), 48)

    deutsche_bank_id = str(context.get("deutsche_bank_id") or "B001")
    scenario_name = str(context.get("scenario_name") or "baseline_current_db")
    scenario_mode = str(
        bank.get("scenario_mode") or context.get("scenario_mode") or "baseline"
    )
    scenario_state = str(bank.get("scenario_state") or "competitor_state")

    bank_id = bank.get("bank_id", "B001")
    bank_name = bank.get("name", "Deutsche Bank")
    requested_amount = _as_float(consumer.get("expected_loan_amount"), 10000.0)
    income = _as_float(consumer.get("monthly_income"), 0.0)
    expense = _as_float(consumer.get("monthly_expense"), 0.0)
    disposable = max(0.0, income - expense)
    credit = _as_int(consumer.get("credit_score"), 650)
    schufa = _as_float(consumer.get("schufa_score_pct"), 88.0)

    min_credit = _as_int(bank.get("min_credit_score"), 680)
    min_schufa = _as_float(bank.get("min_schufa_score_pct"), 88.0)
    strictness = str(bank.get("approval_strictness", "medium")).lower()

    # Improved DB scenario should have visibly better approval capability.
    is_db_offer = str(bank_id) == deutsche_bank_id
    db_improved_mode = is_db_offer and bool(
        context.get("enable_db_improvements", scenario_mode == "improved")
    )
    effective_min_credit = min_credit - 10 if db_improved_mode else min_credit
    effective_min_schufa = min_schufa - 1.0 if db_improved_mode else min_schufa
    base_rate = _as_float(bank.get("base_interest_rate"), 7.5)
    processing_fee_pct = _as_float(bank.get("processing_fee_pct"), 0.0)

    bank_campaigns = _campaigns_for_bank(campaigns, bank_id)
    campaign_discount_bps = max(
        [_as_float(c.get("rate_discount_bps"), 0.0) for c in bank_campaigns] or [0.0]
    )
    relationship_discount_bps = _as_float(bank.get("relationship_discount_bps"), 0.0)
    relationship_discount = (
        relationship_discount_bps if consumer.get("preferred_bank") == bank_id else 0.0
    )

    credit_gap = max(0, effective_min_credit - credit)
    schufa_gap = max(0.0, effective_min_schufa - schufa)
    risk_adjustment = (credit_gap / 100.0) + (schufa_gap * 0.08)
    if strictness == "low":
        risk_adjustment *= 0.75
    elif strictness == "high":
        risk_adjustment *= 1.25

    interest_rate = round(
        max(
            3.0,
            base_rate
            + risk_adjustment
            - (campaign_discount_bps + relationship_discount) / 100.0,
        ),
        2,
    )
    estimated_emi = _monthly_emi(requested_amount, interest_rate, tenure_months)
    max_affordable_emi = disposable * 0.45

    approved = True
    rejection_reason: Optional[str] = None
    if credit < effective_min_credit - (40 if strictness == "low" else 20):
        approved = False
        rejection_reason = "credit_score_too_low"
    if schufa < effective_min_schufa - (4.0 if strictness == "low" else 2.0):
        approved = False
        rejection_reason = "schufa_score_too_low"
    if estimated_emi > max_affordable_emi and disposable > 0:
        approved = False
        rejection_reason = "debt_to_income_too_high"
    if disposable <= 0:
        approved = False
        rejection_reason = "insufficient_disposable_income"

    affordability_cap = max(0.0, max_affordable_emi * tenure_months * 0.9)
    approved_amount = (
        requested_amount if approved else min(requested_amount, affordability_cap)
    )
    if approved and approved_amount < requested_amount * 0.75:
        approved = False
        rejection_reason = "loan_amount_insufficient"

    offer = {
        "bank_id": bank_id,
        "bank_name": bank_name,
        "consumer_id": consumer.get("consumer_id"),
        "scenario_name": scenario_name,
        "scenario_mode": scenario_mode,
        "scenario_state": scenario_state,
        "is_deutsche_bank_offer": str(bank_id) == deutsche_bank_id,
        "approved": approved,
        "interest_rate": interest_rate,
        "approved_amount": round(approved_amount, 2) if approved else 0,
        "requested_amount": requested_amount,
        "currency": bank.get("currency", "EUR"),
        "processing_fee": round(requested_amount * processing_fee_pct / 100.0, 2),
        "tenure_months": tenure_months,
        "estimated_emi": round(estimated_emi, 2),
        "approval_time_days": min(
            [
                _as_int(
                    c.get("promised_approval_time_days"),
                    _as_int(bank.get("average_approval_time_days"), 3),
                )
                for c in bank_campaigns
            ]
            or [_as_int(bank.get("average_approval_time_days"), 3)]
        ),
        "documentation_friction_score": _as_float(
            bank.get("documentation_friction_score"), 0.3
        ),
        "digital_friction_score": _as_float(bank.get("digital_friction_score"), 0.3),
        "brand_trust_score": _as_float(bank.get("brand_trust_score"), 0.75),
        "relationship_discount_bps": relationship_discount_bps,
        "campaign_discount_bps": campaign_discount_bps,
        "preapproved_offer_enabled": bool(bank.get("preapproved_offer_enabled", False)),
        "abandoned_application_followup_enabled": bool(
            bank.get("abandoned_application_followup_enabled", False)
        ),
        "instant_document_validation_enabled": bool(
            bank.get("instant_document_validation_enabled", False)
        ),
        "counter_offer_enabled": bool(bank.get("counter_offer_enabled", False)),
        "advisor_callback_enabled": bool(bank.get("advisor_callback_enabled", False)),
        "comparison_portal_optimised": bool(
            bank.get("comparison_portal_optimised", False)
        ),
        "rejection_reason": rejection_reason,
    }

    # Higher is better. Used by the consumer funnel decision tool.
    relationship_bonus = 0.03 if consumer.get("preferred_bank") == bank_id else 0.0
    db_improved_bonus = (
        0.04
        if str(bank_id) == deutsche_bank_id
        and bool(context.get("enable_db_improvements", scenario_mode == "improved"))
        else 0.0
    )
    offer["offer_score"] = round(
        _clamp(
            (1.0 if approved else 0.0)
            + (0.2 * offer["brand_trust_score"])
            + relationship_bonus
            + db_improved_bonus
            - (interest_rate / 100.0)
            - (offer["digital_friction_score"] * 0.08)
            - (offer["documentation_friction_score"] * 0.08)
            - (offer["approval_time_days"] * 0.015),
            0.0,
            1.2,
        ),
        4,
    )
    offer["relationship_bonus"] = relationship_bonus
    offer["db_improved_bonus"] = db_improved_bonus
    return {"offer": offer}


def consumer_funnel_decision_tool(context: Dict[str, Any]) -> Dict[str, Any]:
    """Advance one consumer through a realistic German lending funnel."""
    consumer = context.get("consumer") or context.get("persona") or {}
    offers = context.get("bank_offers", [])
    campaigns = context.get("marketing_campaigns", [])
    prev_summary = context.get("previous_summary", "")
    base_dropout_probability = _as_float(context.get("base_dropout_probability"), 0.08)

    cid = consumer.get("consumer_id")
    current_stage = consumer.get("funnel_stage", "lead")
    loan_need = _as_float(consumer.get("loan_need_probability"), 0.5)
    price_sensitivity = _level_score(consumer.get("price_sensitivity"), 0.5)
    documentation_tolerance = _level_score(consumer.get("documentation_tolerance"), 0.5)
    digital_comfort = _level_score(consumer.get("digital_comfort"), 0.5)
    urgency = _level_score(consumer.get("urgency"), 0.5)
    brand_loyalty = _level_score(consumer.get("brand_loyalty"), 0.5)
    preferred_bank = consumer.get("preferred_bank")

    approved_offers = [o for o in offers if o.get("approved")]
    best_offer = max(
        approved_offers,
        key=lambda o: _as_float(o.get("offer_score"), 0.0),
        default=None,
    )
    preferred_offer = next(
        (o for o in approved_offers if o.get("bank_id") == preferred_bank), None
    )

    actions: List[Dict[str, Any]] = []
    drop = False
    drop_reason: Optional[str] = None
    selected_bank: Optional[str] = consumer.get("selected_bank")
    next_stage = current_stage

    if current_stage in TERMINAL_STAGES:
        actions.append(
            {"action": "no_action", "reason": f"terminal_stage_{current_stage}"}
        )
    elif current_stage == "lead":
        campaign_lift = sum(
            _as_float(c.get("expected_lead_lift"), 0.0)
            for c in campaigns
            if c.get("bank_id") == preferred_bank
        )
        if loan_need + campaign_lift >= 0.55:
            next_stage = "aware"
            actions.append(
                {"action": "notice_loan_offer", "source": "marketing_or_existing_need"}
            )
        else:
            next_stage = "dropped"
            drop = True
            drop_reason = "changed_mind"
            actions.append({"action": "drop_from_funnel", "reason": drop_reason})
    elif current_stage == "aware":
        next_stage = "interested"
        actions.append({"action": "view_product_details", "product": "ratenkredit"})
    elif current_stage == "interested":
        if not offers:
            next_stage = "prequalified"
            actions.append(
                {"action": "request_prequalification", "credit_bureau": "SCHUFA"}
            )
        elif approved_offers:
            next_stage = "prequalified"
            actions.append(
                {
                    "action": "compare_prequalified_offers",
                    "offer_count": len(approved_offers),
                }
            )
        else:
            next_stage = "rejected"
            drop = True
            drop_reason = "kyc_or_schufa_issue"
            actions.append({"action": "reject_or_drop", "reason": drop_reason})
    elif current_stage == "prequalified":
        if best_offer is None:
            next_stage = "rejected"
            drop = True
            drop_reason = "kyc_or_schufa_issue"
            actions.append({"action": "reject_or_drop", "reason": drop_reason})
        else:
            next_stage = "application_started"
            selected_bank = best_offer.get("bank_id")
            actions.append(
                {"action": "start_application", "target_bank": selected_bank}
            )
    elif current_stage == "application_started":
        friction = _as_float(
            (best_offer or {}).get("documentation_friction_score"), 0.3
        )
        if friction > 0.45 and documentation_tolerance < 0.5:
            next_stage = "dropped"
            drop = True
            drop_reason = "documentation_too_complex"
            actions.append({"action": "drop_from_funnel", "reason": drop_reason})
        else:
            next_stage = "application_submitted"
            actions.append(
                {
                    "action": "submit_application",
                    "target_bank": selected_bank or (best_offer or {}).get("bank_id"),
                }
            )
    elif current_stage == "application_submitted":
        next_stage = "kyc_pending"
        actions.append({"action": "upload_documents_and_consent_schufa_check"})
    elif current_stage == "kyc_pending":
        if best_offer is None:
            next_stage = "rejected"
            drop = True
            drop_reason = "kyc_or_schufa_issue"
            actions.append({"action": "reject_or_drop", "reason": drop_reason})
        else:
            next_stage = "under_review"
            actions.append({"action": "await_underwriting_decision"})
    elif current_stage == "under_review":
        approval_days = _as_int((best_offer or {}).get("approval_time_days"), 3)
        if approval_days > 3 and urgency > 0.65:
            next_stage = "dropped"
            drop = True
            drop_reason = "approval_too_slow"
            actions.append({"action": "drop_from_funnel", "reason": drop_reason})
        else:
            next_stage = "approved"
            actions.append(
                {
                    "action": "receive_credit_approval",
                    "bank_id": (best_offer or {}).get("bank_id"),
                }
            )
    elif current_stage == "approved":
        next_stage = "offer_received"
        actions.append(
            {
                "action": "receive_final_offer",
                "bank_id": (best_offer or {}).get("bank_id"),
            }
        )
    elif current_stage == "offer_received":
        if best_offer is None:
            next_stage = "rejected"
            drop = True
            drop_reason = "kyc_or_schufa_issue"
            actions.append({"action": "reject_or_drop", "reason": drop_reason})
        else:
            selected = (
                preferred_offer
                if preferred_offer and brand_loyalty >= 0.75
                else best_offer
            )
            best_rate = _as_float(best_offer.get("interest_rate"), 99.0)
            selected_rate = _as_float(selected.get("interest_rate"), 99.0)
            selected_bank = selected.get("bank_id")
            if (
                preferred_offer
                and best_offer.get("bank_id") != preferred_bank
                and price_sensitivity > 0.65
                and selected_rate - best_rate > 0.25
            ):
                next_stage = "dropped"
                drop = True
                drop_reason = "competitor_offer_better"
                selected_bank = best_offer.get("bank_id")
                actions.append(
                    {
                        "action": "drop_from_funnel",
                        "reason": drop_reason,
                        "winner_bank": selected_bank,
                    }
                )
            elif (
                _as_float(selected.get("estimated_emi"), 0.0)
                > (
                    _as_float(consumer.get("monthly_income"), 0.0)
                    - _as_float(consumer.get("monthly_expense"), 0.0)
                )
                * 0.5
            ):
                next_stage = "dropped"
                drop = True
                drop_reason = "monthly_emi_too_high"
                actions.append({"action": "drop_from_funnel", "reason": drop_reason})
            else:
                next_stage = "accepted"
                actions.append({"action": "accept_offer", "bank_id": selected_bank})
    elif current_stage == "accepted":
        next_stage = "disbursed"
        actions.append(
            {
                "action": "sign_agreement_and_disburse",
                "bank_id": selected_bank or (best_offer or {}).get("bank_id"),
            }
        )

    # Deterministic friction-based dropout overlay for non-terminal stages.
    if not drop and next_stage not in TERMINAL_STAGES:
        friction_signal = base_dropout_probability
        if best_offer:
            friction_signal += (
                _as_float(best_offer.get("digital_friction_score"), 0.0)
                * (1.0 - digital_comfort)
                * 0.08
            )
            friction_signal += (
                _as_float(best_offer.get("documentation_friction_score"), 0.0)
                * (1.0 - documentation_tolerance)
                * 0.08
            )
            friction_signal += (
                max(0.0, _as_float(best_offer.get("interest_rate"), 0.0) - 8.0)
                * price_sensitivity
                * 0.01
            )
        # Use a stable customer-specific threshold instead of random numbers.
        threshold = (_as_int(str(cid or "0")[-2:].replace("C", ""), 0) % 10) / 100.0
        if friction_signal > 0.18 and threshold < friction_signal - 0.18:
            next_stage = "dropped"
            drop = True
            if (
                best_offer
                and _as_float(best_offer.get("interest_rate"), 0.0) > 8.0
                and price_sensitivity > 0.65
            ):
                drop_reason = "rate_too_high"
            elif (
                best_offer
                and _as_float(best_offer.get("digital_friction_score"), 0.0) > 0.4
            ):
                drop_reason = "poor_digital_experience"
            else:
                drop_reason = "changed_mind"
            actions.append({"action": "drop_from_funnel", "reason": drop_reason})

    selected_offer = None
    if selected_bank:
        selected_offer = next(
            (o for o in offers if o.get("bank_id") == selected_bank), None
        )

    decision_factors = {
        "current_stage": current_stage,
        "next_stage": next_stage,
        "price_sensitivity": consumer.get("price_sensitivity"),
        "documentation_tolerance": consumer.get("documentation_tolerance"),
        "digital_comfort": consumer.get("digital_comfort"),
        "urgency": consumer.get("urgency"),
        "brand_loyalty": consumer.get("brand_loyalty"),
        "preferred_bank": preferred_bank,
        "best_offer_bank": (best_offer or {}).get("bank_id"),
        "selected_bank": selected_bank,
    }

    summary_update = (
        f"Prev: {prev_summary[:120]} | Funnel: {current_stage}->{next_stage} | "
        f"Drop: {drop_reason or 'no'} | Actions: {_safe_json(actions)[:240]}"
    )
    return {
        "next_stage": next_stage,
        "actions": actions,
        "drop": drop,
        "drop_reason": drop_reason,
        "selected_bank": selected_bank,
        "approved_amount": (selected_offer or {}).get("approved_amount"),
        "offered_rate": (selected_offer or {}).get("interest_rate"),
        "decision_factors": decision_factors,
        "new_summary": summary_update,
    }


# -----------------------------------------------------------------------------
# Context/news/summary tools
# -----------------------------------------------------------------------------
def world_news_tool(context: Dict[str, Any]) -> Dict[str, Any]:
    timestep = _as_int(context.get("timestep"), 0)
    count = _as_int(context.get("count"), 1)
    themes = [
        "ECB rate expectations influence German consumer credit pricing",
        "SCHUFA data transparency remains a topic for borrowers",
        "German employment market shows stable salaried income trends",
        "Energy and living costs affect household disposable income",
        "Digital identity and eID adoption improve online loan journeys",
    ]
    items = []
    for i in range(count):
        theme = themes[(timestep + i) % len(themes)]
        items.append(
            {
                "headline": f"T{timestep}: {theme}",
                "impact": "mixed" if i % 2 == 0 else "consumer_positive",
                "market": "Germany",
            }
        )
    return {"news": items}


def timestep_summary_tool(context: Dict[str, Any]) -> Dict[str, Any]:
    ts = context.get("timestep")
    consumer_actions = context.get("consumer_actions", 0)
    bank_actions = context.get("bank_actions", 0)
    news_count = context.get("news_count", 0)
    feedback_count = context.get("feedback_count", 0)
    new_leads_count = _as_int(context.get("new_leads_count"), 0)
    metrics = context.get("funnel_metrics") or {}

    if metrics:
        submitted = metrics.get(
            "cumulative_applications_submitted",
            metrics.get("applications_submitted", 0),
        )
        approvals = metrics.get("approved", 0)
        summary = (
            f"Timestep {ts}: {new_leads_count} new leads, "
            f"{metrics.get('active_customers', 0)} active customers, "
            f"{submitted} submitted applications, "
            f"{approvals} approvals, {metrics.get('deutsche_bank_wins', 0)} Deutsche Bank wins, "
            f"{metrics.get('dropped', 0)} drop-offs."
        )
    else:
        summary = (
            f"Timestep {ts}: {new_leads_count} new leads, consumers took {consumer_actions} actions, "
            f"banks took {bank_actions} actions, generated {news_count} news items, "
            f"and collected {feedback_count} customer feedback entries."
        )
    return {"summary": summary}
