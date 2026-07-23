from __future__ import annotations

"""Strict agent output schemas for the Lending World simulation.

This module is intentionally independent from ADK runtime objects.  The LLM
agents should produce payloads that can be parsed into these Pydantic models;
then deterministic Python code can validate, normalise, quarantine invalid rows,
and commit only clean rows to CSV.

Design goals:
- one canonical schema per output table
- required actor identity for bank/customer rows
- canonical bank-offer fields only
- no arbitrary alternate APR/amount/term columns
- simple JSON-serialisable values only
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


Visibility = Literal["public", "private"]
ActorType = Literal["world", "bank", "consumer", "marketplace", "system"]


class StrictBaseModel(BaseModel):
    """Base model that rejects accidental/uncontrolled fields."""

    class Config:
        extra = "forbid"
        validate_assignment = True
        allow_mutation = True


class BaseSimulationRow(StrictBaseModel):
    timestep: Optional[int] = None
    agent_name: str
    actor_type: ActorType
    actor_id: str
    visibility: Visibility = "private"
    reasoning_summary: Optional[str] = None
    action_sequence: int = 1
    intra_timestep_sequence: int = 1
    action_id: Optional[str] = None
    depends_on_action_id: Optional[str] = None
    source_snapshot_timestep: Optional[int] = None
    committed_timestep: Optional[int] = None


class WorldNewsRow(BaseSimulationRow):
    agent_name: Literal["world_news_agent"] = "world_news_agent"
    actor_type: Literal["world"] = "world"
    actor_id: Literal["world_news"] = "world_news"
    visibility: Literal["public"] = "public"
    news_type: str = "market_news"
    headline: str
    event_detail: str
    market: str = "Germany"
    affected_segments: Optional[str] = None
    affected_products: Optional[str] = None
    severity: Optional[str] = None


class CustomerActionRow(BaseSimulationRow):
    agent_name: Literal["customer_agent"] = "customer_agent"
    actor_type: Literal["consumer"] = "consumer"
    consumer_id: str
    consumer_name: Optional[str] = None
    action_type: str
    action_detail: Optional[str] = None
    funnel_stage_before: Optional[str] = None
    funnel_stage_after: Optional[str] = None
    search_parameters: Optional[Dict[str, Any]] = None
    selected_offer_id: Optional[str] = None
    selected_bank_id: Optional[str] = None
    selected_bank_name: Optional[str] = None


class FunnelEventRow(BaseSimulationRow):
    agent_name: Literal["customer_agent"] = "customer_agent"
    actor_type: Literal["consumer"] = "consumer"
    consumer_id: str
    event_type: str = "funnel_transition"
    event_detail: Optional[str] = None
    funnel_stage_before: str
    funnel_stage_after: str
    selected_bank: Optional[str] = None
    selected_bank_name: Optional[str] = None


class CustomerFeedbackRow(BaseSimulationRow):
    agent_name: Literal["customer_agent"] = "customer_agent"
    actor_type: Literal["consumer"] = "consumer"
    consumer_id: str
    feedback_type: str
    message: str
    market: str = "Germany"


class BankActionRow(BaseSimulationRow):
    agent_name: Literal["bank_agent"] = "bank_agent"
    actor_type: Literal["bank"] = "bank"
    bank_id: str
    bank_name: Optional[str] = None
    action_type: str
    action_detail: Optional[str] = None
    advisor_callback_enabled: Optional[bool] = None
    preapproved_offer_enabled: Optional[bool] = None
    documentation_friction_score: Optional[float] = None
    counter_offer_enabled: Optional[bool] = None
    average_approval_time_days: Optional[float] = None
    relationship_discount_bps: Optional[float] = None
    digital_friction_score: Optional[float] = None
    comparison_portal_optimised: Optional[bool] = None
    instant_document_validation_enabled: Optional[bool] = None
    abandoned_application_followup_enabled: Optional[bool] = None
    parameters: Optional[Dict[str, Any]] = None


class BankOfferRow(BaseSimulationRow):
    agent_name: Literal["bank_agent"] = "bank_agent"
    actor_type: Literal["bank"] = "bank"
    bank_id: str
    bank_name: Optional[str] = None
    offer_id: str
    product_id: str
    product_name: str
    offer_type: str = "standard_offer"
    base_interest_rate_apr: Optional[float] = None
    effective_interest_rate_apr: Optional[float] = None
    processing_fee_pct: Optional[float] = None
    relationship_discount_bps: Optional[float] = None
    min_credit_score: Optional[float] = None
    min_schufa_score_pct: Optional[float] = None
    min_loan_amount_eur: Optional[float] = None
    max_loan_amount_eur: Optional[float] = None
    min_term_months: Optional[int] = None
    max_term_months: Optional[int] = None
    target_customer_segment: Optional[str] = None
    offer_description: Optional[str] = None
    valid_from_timestep: Optional[int] = None
    valid_to_timestep: Optional[int] = None


class MarketingActionRow(BaseSimulationRow):
    agent_name: Literal["bank_agent"] = "bank_agent"
    actor_type: Literal["bank"] = "bank"
    bank_id: str
    bank_name: Optional[str] = None
    campaign_name: str
    campaign_type: Optional[str] = None
    campaign_detail: Optional[str] = None
    target_segment: Optional[str] = None
    marketing_channel: Optional[str] = None
    marketing_spend_eur: Optional[float] = None
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    source_function: str = "bank_owned_marketing"
    start_timestep: Optional[int] = None
    end_timestep: Optional[int] = None


class MarketplaceRankingRow(BaseSimulationRow):
    agent_name: Literal["marketplace_agent"] = "marketplace_agent"
    actor_type: Literal["marketplace"] = "marketplace"
    actor_id: Literal["loan_marketplace"] = "loan_marketplace"
    visibility: Literal["public"] = "public"
    ranking_id: str
    offer_id: str
    bank_id: str
    product_id: str
    rank: int
    ranking_score: Optional[float] = None
    ranking_reason: Optional[str] = None


class MarketplaceRecommendationRow(BaseSimulationRow):
    agent_name: Literal["marketplace_agent"] = "marketplace_agent"
    actor_type: Literal["marketplace"] = "marketplace"
    actor_id: Literal["loan_marketplace"] = "loan_marketplace"
    visibility: Literal["public"] = "public"
    recommendation_id: str
    consumer_id: Optional[str] = None
    offer_id: str
    bank_id: str
    product_id: str
    recommendation_reason: Optional[str] = None


class MarketplaceVisibilityEventRow(BaseSimulationRow):
    agent_name: Literal["marketplace_agent"] = "marketplace_agent"
    actor_type: Literal["marketplace"] = "marketplace"
    actor_id: Literal["loan_marketplace"] = "loan_marketplace"
    visibility: Literal["public"] = "public"
    event_type: str
    event_detail: str
    offer_id: Optional[str] = None
    bank_id: Optional[str] = None
    product_id: Optional[str] = None


class PublicInformationSummaryRow(StrictBaseModel):
    run_id: Optional[str] = None
    timestep: int
    summary_from_timestep: int
    summary_to_timestep: int
    window_size: int
    public_information_summary: str
    created_by: str = "post_processing_agent"


class MarketplaceDashboardRow(StrictBaseModel):
    timestep: int
    dashboard_timestep: int
    public_offer_count: int = 0
    public_bank_count: int = 0
    ranked_offer_count: int = 0
    recommendation_count: int = 0
    visibility_event_count: int = 0
    top_bank_ids: Optional[str] = None
    top_product_ids: Optional[str] = None
    dashboard_summary: str = ""
    created_by: str = "post_processing"


class InvalidRow(StrictBaseModel):
    timestep: Optional[int] = None
    source_table: str
    agent_name: Optional[str] = None
    actor_type: Optional[str] = None
    actor_id: Optional[str] = None
    error_type: str
    error_message: str
    raw_row_json: str
    created_at: Optional[str] = None


class WorldNewsAgentOutput(StrictBaseModel):
    world_news: List[WorldNewsRow] = Field(default_factory=list)


class CustomerAgentOutput(StrictBaseModel):
    consumer_actions: List[CustomerActionRow] = Field(default_factory=list)
    funnel_events: List[FunnelEventRow] = Field(default_factory=list)
    customer_feedback: List[CustomerFeedbackRow] = Field(default_factory=list)


class BankAgentOutput(StrictBaseModel):
    bank_actions: List[BankActionRow] = Field(default_factory=list)
    bank_offers: List[BankOfferRow] = Field(default_factory=list)
    marketing_actions: List[MarketingActionRow] = Field(default_factory=list)


class MarketplaceAgentOutput(StrictBaseModel):
    marketplace_rankings: List[MarketplaceRankingRow] = Field(default_factory=list)
    marketplace_recommendations: List[MarketplaceRecommendationRow] = Field(default_factory=list)
    marketplace_visibility_events: List[MarketplaceVisibilityEventRow] = Field(default_factory=list)
    no_output_reason: Optional[str] = None


class PostProcessingOutput(StrictBaseModel):
    public_information_summary: Optional[str] = None
    marketplace_dashboard: Optional[MarketplaceDashboardRow] = None
    notes: Optional[str] = None


class TimestepAgentOutputs(StrictBaseModel):
    world_news: List[WorldNewsRow] = Field(default_factory=list)
    consumer_actions: List[CustomerActionRow] = Field(default_factory=list)
    bank_actions: List[BankActionRow] = Field(default_factory=list)
    marketing_actions: List[MarketingActionRow] = Field(default_factory=list)
    funnel_events: List[FunnelEventRow] = Field(default_factory=list)
    bank_offers: List[BankOfferRow] = Field(default_factory=list)
    customer_feedback: List[CustomerFeedbackRow] = Field(default_factory=list)
    marketplace_rankings: List[MarketplaceRankingRow] = Field(default_factory=list)
    marketplace_recommendations: List[MarketplaceRecommendationRow] = Field(default_factory=list)
    marketplace_visibility_events: List[MarketplaceVisibilityEventRow] = Field(default_factory=list)


class ValidationResult(StrictBaseModel):
    table_name: str
    valid_rows: List[Dict[str, Any]] = Field(default_factory=list)
    invalid_rows: List[InvalidRow] = Field(default_factory=list)
    repaired_count: int = 0
    rejected_count: int = 0


TABLE_TO_SCHEMA = {
    "world_news": WorldNewsRow,
    "consumer_actions": CustomerActionRow,
    "funnel_events": FunnelEventRow,
    "customer_feedback": CustomerFeedbackRow,
    "bank_actions": BankActionRow,
    "bank_offers": BankOfferRow,
    "marketing_actions": MarketingActionRow,
    "marketplace_rankings": MarketplaceRankingRow,
    "marketplace_recommendations": MarketplaceRecommendationRow,
    "marketplace_visibility_events": MarketplaceVisibilityEventRow,
    "public_information_summary": PublicInformationSummaryRow,
    "marketplace_dashboard": MarketplaceDashboardRow,
}


REQUIRED_COLUMNS_BY_TABLE = {
    "world_news": ["timestep", "agent_name", "actor_type", "actor_id", "headline", "event_detail", "visibility", "action_sequence", "action_id"],
    "consumer_actions": ["timestep", "agent_name", "actor_type", "actor_id", "consumer_id", "action_type", "visibility", "action_sequence", "action_id"],
    "funnel_events": ["timestep", "agent_name", "actor_type", "actor_id", "consumer_id", "event_type", "funnel_stage_before", "funnel_stage_after", "visibility", "action_sequence", "action_id"],
    "customer_feedback": ["timestep", "agent_name", "actor_type", "actor_id", "consumer_id", "feedback_type", "message", "visibility", "action_sequence", "action_id"],
    "bank_actions": ["timestep", "agent_name", "actor_type", "actor_id", "bank_id", "action_type", "visibility", "action_sequence", "action_id"],
    "bank_offers": ["timestep", "agent_name", "actor_type", "actor_id", "bank_id", "offer_id", "product_id", "product_name", "visibility", "action_sequence", "action_id"],
    "marketing_actions": ["timestep", "agent_name", "actor_type", "actor_id", "bank_id", "campaign_name", "visibility", "action_sequence", "action_id"],
    "marketplace_rankings": ["timestep", "agent_name", "actor_type", "actor_id", "ranking_id", "offer_id", "bank_id", "product_id", "rank", "visibility", "action_sequence", "action_id"],
    "marketplace_recommendations": ["timestep", "agent_name", "actor_type", "actor_id", "recommendation_id", "offer_id", "bank_id", "product_id", "visibility", "action_sequence", "action_id"],
    "marketplace_visibility_events": ["timestep", "agent_name", "actor_type", "actor_id", "event_type", "event_detail", "visibility", "action_sequence", "action_id"],
}


CANONICAL_BANK_OFFER_FIELDS = [
    "timestep",
    "agent_name",
    "actor_type",
    "actor_id",
    "bank_id",
    "bank_name",
    "offer_id",
    "product_id",
    "product_name",
    "offer_type",
    "visibility",
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
    "reasoning_summary",
    "action_sequence",
    "intra_timestep_sequence",
    "action_id",
    "depends_on_action_id",
    "source_snapshot_timestep",
    "committed_timestep",
]


class ActiveOfferBrief(StrictBaseModel):
    offer_id: str
    bank_id: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    effective_interest_rate_apr: Optional[float] = None
    valid_to_timestep: Optional[int] = None
    rank: Optional[int] = None

class CustomerStateBrief(StrictBaseModel):
    consumer_id: str
    name: Optional[str] = None
    funnel_stage: str
    active: bool = True
    selected_bank: Optional[str] = None
    loan_purpose: Optional[str] = None
    expected_loan_amount: Optional[float] = None
    preferred_term_months: Optional[int] = None

class CustomerBatchInput(StrictBaseModel):
    timestep: int
    source_snapshot_timestep: int
    public_market_summary: str = ""
    active_offers: List[ActiveOfferBrief] = Field(default_factory=list)
    customers: List[CustomerStateBrief] = Field(default_factory=list)
    max_actions_per_customer: int = 2

class CustomerBatchOutput(StrictBaseModel):
    consumer_actions: List[CustomerActionRow] = Field(default_factory=list)
    funnel_events: List[FunnelEventRow] = Field(default_factory=list)
    customer_feedback: List[CustomerFeedbackRow] = Field(default_factory=list)

class MarketplaceInput(StrictBaseModel):
    timestep: int
    public_market_summary: str = ""
    active_offers: List[ActiveOfferBrief] = Field(default_factory=list)

class MarketplaceOutput(StrictBaseModel):
    marketplace_rankings: List[MarketplaceRankingRow] = Field(default_factory=list)
    marketplace_recommendations: List[MarketplaceRecommendationRow] = Field(default_factory=list)
    marketplace_visibility_events: List[MarketplaceVisibilityEventRow] = Field(default_factory=list)

class BankInput(StrictBaseModel):
    timestep: int
    bank_id: str
    bank_name: Optional[str] = None
    public_market_summary: str = ""
    own_active_offers: List[ActiveOfferBrief] = Field(default_factory=list)
    competitor_active_offers: List[ActiveOfferBrief] = Field(default_factory=list)
    max_new_public_offers: int = 2

class BankOutput(StrictBaseModel):
    bank_actions: List[BankActionRow] = Field(default_factory=list)
    bank_offers: List[BankOfferRow] = Field(default_factory=list, max_length=2)
    marketing_actions: List[MarketingActionRow] = Field(default_factory=list)
