from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Lending Simulation Output Dashboard",
    page_icon="🏦",
    layout="wide",
)

OUTPUT_DIR = Path("output")
EXPECTED_FILES = {
    "conversion_metrics": "conversion_metrics.csv",
    "customer_lifecycle": "customer_lifecycle.csv",
    "funnel_events": "funnel_events.csv",
    "db_loss_analysis": "db_loss_analysis.csv",
    "db_recommendations": "db_recommendations.csv",
    "retention_metrics": "retention_metrics.csv",
    "acquisition_metrics": "acquisition_metrics.csv",
    "customer_feedback": "customer_feedback.csv",
    "scenario_comparison": "scenario_comparison.csv",
    "bank_offers": "bank_offers.csv",
}

IMPROVEMENT_LABELS = {
    "targeted_relationship_discount": "Targeted relationship discount",
    "faster_preapproval_or_reduced_approval_sla": "Faster pre-approval SLA",
    "guided_document_upload_and_instant_validation": "Guided document upload + instant validation",
    "simplify_digital_application_journey": "Simplify digital application journey",
    "strengthen_product_specific_proposition": "Product-specific proposition",
    "advisor_callback_or_relationship_manager_support": "Advisor callback / relationship support",
    "review_borderline_schufa_and_affordability_policy": "Borderline SCHUFA / affordability review",
}

IMPROVEMENT_EFFECTS = {
    "targeted_relationship_discount": {"db_win_lift": 1.4, "competitor_loss_reduction": 1.1, "dropoff_reduction": 0.1},
    "faster_preapproval_or_reduced_approval_sla": {"db_win_lift": 1.5, "competitor_loss_reduction": 1.0, "dropoff_reduction": 0.2},
    "guided_document_upload_and_instant_validation": {"db_win_lift": 0.8, "competitor_loss_reduction": 0.3, "dropoff_reduction": 1.1},
    "simplify_digital_application_journey": {"db_win_lift": 1.0, "competitor_loss_reduction": 0.6, "dropoff_reduction": 0.8},
    "strengthen_product_specific_proposition": {"db_win_lift": 0.8, "competitor_loss_reduction": 0.7, "dropoff_reduction": 0.1},
    "advisor_callback_or_relationship_manager_support": {"db_win_lift": 0.6, "competitor_loss_reduction": 0.3, "dropoff_reduction": 0.5},
    "review_borderline_schufa_and_affordability_policy": {"db_win_lift": 0.5, "competitor_loss_reduction": 0.2, "dropoff_reduction": 0.4},
}

SAMPLE_DATA: Dict[str, pd.DataFrame] = {
    "conversion_metrics": pd.DataFrame([
        {"timestep": 1, "total_customers": 14, "active_customers": 14, "deutsche_bank_wins": 0, "competitor_wins": 0, "dropped": 0, "lost_to_competitor": 0, "funnel_abandonments": 0, "recoverable_losses": 0, "deutsche_bank_win_rate": 0.0},
        {"timestep": 2, "total_customers": 15, "active_customers": 15, "deutsche_bank_wins": 0, "competitor_wins": 0, "dropped": 1, "lost_to_competitor": 0, "funnel_abandonments": 1, "recoverable_losses": 1, "deutsche_bank_win_rate": 0.0},
        {"timestep": 3, "total_customers": 16, "active_customers": 14, "deutsche_bank_wins": 0, "competitor_wins": 1, "dropped": 2, "lost_to_competitor": 1, "funnel_abandonments": 2, "recoverable_losses": 2, "deutsche_bank_win_rate": 0.0},
        {"timestep": 4, "total_customers": 17, "active_customers": 11, "deutsche_bank_wins": 1, "competitor_wins": 2, "dropped": 3, "lost_to_competitor": 2, "funnel_abandonments": 3, "recoverable_losses": 4, "deutsche_bank_win_rate": 0.33},
        {"timestep": 5, "total_customers": 18, "active_customers": 8, "deutsche_bank_wins": 3, "competitor_wins": 4, "dropped": 4, "lost_to_competitor": 4, "funnel_abandonments": 4, "recoverable_losses": 5, "deutsche_bank_win_rate": 0.43},
        {"timestep": 6, "total_customers": 19, "active_customers": 5, "deutsche_bank_wins": 5, "competitor_wins": 6, "dropped": 5, "lost_to_competitor": 6, "funnel_abandonments": 5, "recoverable_losses": 6, "deutsche_bank_win_rate": 0.45},
    ]),
    "customer_lifecycle": pd.DataFrame([
        {"timestep": 4, "consumer_id": "C002", "name": "Lukas Schneider", "funnel_stage": "accepted", "selected_bank": "B003", "offered_rate": 6.8, "approved_amount": 32000},
        {"timestep": 4, "consumer_id": "C004", "name": "Max Fischer", "funnel_stage": "dropped", "selected_bank": "", "offered_rate": None, "approved_amount": None},
        {"timestep": 5, "consumer_id": "C008", "name": "Jonas Wagner", "funnel_stage": "accepted", "selected_bank": "B008", "offered_rate": 8.1, "approved_amount": 28000},
        {"timestep": 5, "consumer_id": "C009", "name": "Laura Schmidt", "funnel_stage": "accepted", "selected_bank": "B004", "offered_rate": 7.0, "approved_amount": 16000},
        {"timestep": 6, "consumer_id": "C001", "name": "Anna Müller", "funnel_stage": "disbursed", "selected_bank": "B001", "offered_rate": 6.75, "approved_amount": 25000},
        {"timestep": 6, "consumer_id": "C003", "name": "Sophie Weber", "funnel_stage": "accepted", "selected_bank": "B001", "offered_rate": 6.85, "approved_amount": 40000},
    ]),
    "db_loss_analysis": pd.DataFrame([
        {"timestep": 3, "consumer_id": "C002", "customer_segment": "digital_affluent", "loan_purpose": "electric_vehicle_purchase", "lost_at_stage": "offer_received", "loss_type": "competitor_loss", "winning_bank_name": "ING Germany", "primary_loss_reason": "competitor_rate_better", "secondary_loss_reason": "approval_too_slow", "rate_gap_bps": 45, "approval_gap_days": 1, "recoverable_loss": True, "recommended_improvement": "targeted_relationship_discount"},
        {"timestep": 4, "consumer_id": "C004", "customer_segment": "self_employed_professional", "loan_purpose": "business_cash_flow_bridge", "lost_at_stage": "application_started", "loss_type": "funnel_abandonment", "winning_bank_name": "", "primary_loss_reason": "documentation_too_complex", "secondary_loss_reason": "poor_digital_experience", "rate_gap_bps": 0, "approval_gap_days": 0, "recoverable_loss": True, "recommended_improvement": "guided_document_upload_and_instant_validation"},
        {"timestep": 5, "consumer_id": "C008", "customer_segment": "prime_auto_borrower", "loan_purpose": "car_loan", "lost_at_stage": "offer_received", "loss_type": "competitor_loss", "winning_bank_name": "Santander Consumer Bank Germany", "primary_loss_reason": "competitor_product_fit_better", "secondary_loss_reason": "approval_too_slow", "rate_gap_bps": 35, "approval_gap_days": 1, "recoverable_loss": True, "recommended_improvement": "strengthen_product_specific_proposition"},
        {"timestep": 5, "consumer_id": "C009", "customer_segment": "core_salaried", "loan_purpose": "debt_consolidation", "lost_at_stage": "offer_received", "loss_type": "competitor_loss", "winning_bank_name": "DKB", "primary_loss_reason": "competitor_rate_better", "secondary_loss_reason": "poor_digital_experience", "rate_gap_bps": 55, "approval_gap_days": 0, "recoverable_loss": True, "recommended_improvement": "targeted_relationship_discount"},
        {"timestep": 6, "consumer_id": "C012", "customer_segment": "new_to_country_banking", "loan_purpose": "relocation_and_family_support", "lost_at_stage": "under_review", "loss_type": "funnel_abandonment", "winning_bank_name": "", "primary_loss_reason": "db_rejected_customer", "secondary_loss_reason": "kyc_or_schufa_issue", "rate_gap_bps": 0, "approval_gap_days": 0, "recoverable_loss": False, "recommended_improvement": "review_borderline_schufa_and_affordability_policy"},
    ]),
    "db_recommendations": pd.DataFrame([
        {"timestep": 3, "consumer_id": "C002", "recommendation_id": "R_RATE_001", "target_issue": "competitor_rate_better", "recommended_change": "targeted_relationship_discount", "implementation_complexity": "low", "expected_impact": "high", "affected_stage": "offer_received", "competitor_bank_name": "ING Germany"},
        {"timestep": 4, "consumer_id": "C004", "recommendation_id": "R_DOCS_001", "target_issue": "documentation_too_complex", "recommended_change": "guided_document_upload_and_instant_validation", "implementation_complexity": "medium", "expected_impact": "medium", "affected_stage": "application_started", "competitor_bank_name": ""},
        {"timestep": 5, "consumer_id": "C008", "recommendation_id": "R_PRODUCT_001", "target_issue": "competitor_product_fit_better", "recommended_change": "strengthen_product_specific_proposition", "implementation_complexity": "medium", "expected_impact": "medium", "affected_stage": "offer_received", "competitor_bank_name": "Santander Consumer Bank Germany"},
    ]),
    "customer_feedback": pd.DataFrame([
        {"timestep": 1, "message": "Need lower rates and transparent instalments", "market": "Germany"},
        {"timestep": 2, "message": "Faster approval desired for online Ratenkredit", "market": "Germany"},
        {"timestep": 3, "message": "Document upload process feels heavy", "market": "Germany"},
        {"timestep": 4, "message": "Customers compare offers on digital channels", "market": "Germany"},
        {"timestep": 5, "message": "Some borrowers prefer advisor support for larger loans", "market": "Germany"},
    ]),
    "scenario_comparison": pd.DataFrame([
        {"scenario_name": "baseline_current_db", "scenario_mode": "baseline", "db_wins": 5, "competitor_wins": 6, "dropoffs": 5, "db_win_rate": 0.45, "lost_to_competitor": 6, "funnel_abandonments": 5, "recoverable_losses": 6},
        {"scenario_name": "improved_combined_strategy", "scenario_mode": "improved", "db_wins": 8, "competitor_wins": 4, "dropoffs": 3, "db_win_rate": 0.67, "lost_to_competitor": 3, "funnel_abandonments": 3, "recoverable_losses": 2},
    ]),
}


def safe_read_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception as exc:
            st.warning(f"Could not read {path.name}: {exc}")
    return pd.DataFrame()


def load_from_output_dir(output_dir: Path) -> Dict[str, pd.DataFrame]:
    return {key: safe_read_csv(output_dir / filename) for key, filename in EXPECTED_FILES.items()}


def load_uploaded_files(uploaded_files) -> Dict[str, pd.DataFrame]:
    loaded: Dict[str, pd.DataFrame] = {}
    reverse = {v: k for k, v in EXPECTED_FILES.items()}
    for uploaded_file in uploaded_files or []:
        key = reverse.get(uploaded_file.name)
        if key:
            loaded[key] = pd.read_csv(uploaded_file)
    return loaded


def ensure_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in df.columns:
            df[column] = None
    return df


def numeric(series, default=0):
    return pd.to_numeric(series, errors="coerce").fillna(default)


def latest_lifecycle_at_timestep(lifecycle: pd.DataFrame, timestep: int) -> pd.DataFrame:
    if lifecycle.empty or "timestep" not in lifecycle.columns:
        return pd.DataFrame()
    df = lifecycle.copy()
    df["timestep"] = numeric(df["timestep"])
    df = df[df["timestep"] <= timestep]
    if df.empty:
        return df
    identity_col = "consumer_id" if "consumer_id" in df.columns else df.columns[0]
    return df.sort_values("timestep").groupby(identity_col, as_index=False).tail(1)


def project_selected_improvements(base_row: pd.Series, selected: List[str]) -> dict:
    base_db_wins = int(base_row.get("deutsche_bank_wins", base_row.get("db_wins", 0)) or 0)
    base_competitor_wins = int(base_row.get("competitor_wins", 0) or 0)
    base_dropoffs = int(base_row.get("dropped", base_row.get("dropoffs", 0)) or 0)

    db_lift = sum(IMPROVEMENT_EFFECTS.get(item, {}).get("db_win_lift", 0) for item in selected)
    competitor_reduction = sum(IMPROVEMENT_EFFECTS.get(item, {}).get("competitor_loss_reduction", 0) for item in selected)
    dropoff_reduction = sum(IMPROVEMENT_EFFECTS.get(item, {}).get("dropoff_reduction", 0) for item in selected)

    projected_db_wins = round(base_db_wins + db_lift)
    projected_competitor_wins = max(0, round(base_competitor_wins - competitor_reduction))
    projected_dropoffs = max(0, round(base_dropoffs - dropoff_reduction))
    denominator = max(projected_db_wins + projected_competitor_wins, 1)

    return {
        "projected_db_wins": projected_db_wins,
        "projected_competitor_wins": projected_competitor_wins,
        "projected_dropoffs": projected_dropoffs,
        "projected_db_win_rate": projected_db_wins / denominator,
    }


def format_pct(value) -> str:
    try:
        value = float(value)
        if value <= 1:
            value *= 100
        return f"{value:.1f}%"
    except Exception:
        return "0.0%"


st.title("🏦 Lending Simulation Output Dashboard")
st.caption("Standalone Streamlit UI. It reads generated CSV files from the output directory and does not import simulation runtime code.")

with st.sidebar:
    st.header("Data source")
    output_dir_text = st.text_input("Output directory", value=str(OUTPUT_DIR))
    output_dir = Path(output_dir_text)
    uploaded_files = st.file_uploader(
        "Or upload output CSV files",
        type=["csv"],
        accept_multiple_files=True,
        help="Upload conversion_metrics.csv, customer_lifecycle.csv, db_loss_analysis.csv, db_recommendations.csv, customer_feedback.csv and scenario_comparison.csv.",
    )
    use_sample = st.checkbox("Use sample data if files are missing", value=True)

loaded_data = load_from_output_dir(output_dir)
uploaded_data = load_uploaded_files(uploaded_files)
loaded_data.update(uploaded_data)

if use_sample:
    for key, sample_df in SAMPLE_DATA.items():
        if loaded_data.get(key, pd.DataFrame()).empty:
            loaded_data[key] = sample_df.copy()

conversion = ensure_columns(loaded_data.get("conversion_metrics", pd.DataFrame()), ["timestep"])
lifecycle = ensure_columns(loaded_data.get("customer_lifecycle", pd.DataFrame()), ["timestep", "consumer_id", "funnel_stage"])
losses = ensure_columns(loaded_data.get("db_loss_analysis", pd.DataFrame()), ["timestep", "consumer_id", "lost_at_stage", "loss_type", "winning_bank_name", "primary_loss_reason", "recommended_improvement"])
recommendations = ensure_columns(loaded_data.get("db_recommendations", pd.DataFrame()), ["recommended_change", "target_issue", "expected_impact", "implementation_complexity"])
feedback = ensure_columns(loaded_data.get("customer_feedback", pd.DataFrame()), ["timestep", "message"])
scenario = ensure_columns(loaded_data.get("scenario_comparison", pd.DataFrame()), ["scenario_name", "scenario_mode"])

if conversion.empty:
    st.error("No conversion_metrics.csv found. Upload output CSVs or enable sample data.")
    st.stop()

conversion["timestep"] = numeric(conversion["timestep"])
max_timestep = int(conversion["timestep"].max()) if not conversion.empty else 1
selected_timestep = st.slider("Replay simulation by timestep", min_value=1, max_value=max_timestep, value=max_timestep)

metric_rows = conversion[conversion["timestep"] <= selected_timestep].sort_values("timestep")
current_metric = metric_rows.iloc[-1] if not metric_rows.empty else conversion.iloc[-1]

st.subheader(f"Simulation state at timestep {selected_timestep}")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("DB wins", int(current_metric.get("deutsche_bank_wins", current_metric.get("db_wins", 0)) or 0))
col2.metric("Competitor wins", int(current_metric.get("competitor_wins", 0) or 0))
col3.metric("Drop-offs", int(current_metric.get("dropped", current_metric.get("dropoffs", 0)) or 0))
col4.metric("Recoverable losses", int(current_metric.get("recoverable_losses", 0) or 0))
col5.metric("DB win rate", format_pct(current_metric.get("deutsche_bank_win_rate", current_metric.get("db_win_rate", 0))))

tab_progression, tab_pivots, tab_improvements, tab_feedback, tab_raw = st.tabs([
    "Simulation progression",
    "Customer pivot points",
    "Improvement checkboxes",
    "Reviews / feedback",
    "Raw CSV preview",
])

with tab_progression:
    left, right = st.columns(2)
    with left:
        st.markdown("### Funnel over time")
        chart_cols = [col for col in ["deutsche_bank_wins", "competitor_wins", "dropped", "recoverable_losses"] if col in conversion.columns]
        if chart_cols:
            chart_df = conversion.set_index("timestep")[chart_cols]
            st.line_chart(chart_df)
        else:
            st.info("No standard progression columns found in conversion_metrics.csv.")

    with right:
        st.markdown("### Stage distribution at selected timestep")
        latest_lifecycle = latest_lifecycle_at_timestep(lifecycle, selected_timestep)
        if not latest_lifecycle.empty and "funnel_stage" in latest_lifecycle.columns:
            stage_counts = latest_lifecycle["funnel_stage"].fillna("Unknown").value_counts()
            st.bar_chart(stage_counts)
        else:
            st.info("customer_lifecycle.csv is missing or does not contain funnel_stage data.")

with tab_pivots:
    st.markdown("### Customer pivot points up to selected timestep")
    losses_t = losses.copy()
    if "timestep" in losses_t.columns:
        losses_t["timestep"] = numeric(losses_t["timestep"])
        losses_t = losses_t[losses_t["timestep"] <= selected_timestep]

    pivot_col, reason_col = st.columns(2)
    with pivot_col:
        st.markdown("#### Competitor destinations")
        competitor_losses = losses_t[losses_t.get("loss_type", "") == "competitor_loss"] if "loss_type" in losses_t.columns else pd.DataFrame()
        if not competitor_losses.empty and "winning_bank_name" in competitor_losses.columns:
            st.bar_chart(competitor_losses["winning_bank_name"].replace("", "Unknown").value_counts())
        else:
            st.info("No competitor losses recorded up to this timestep.")
    with reason_col:
        st.markdown("#### Primary loss reasons")
        if not losses_t.empty and "primary_loss_reason" in losses_t.columns:
            st.bar_chart(losses_t["primary_loss_reason"].fillna("Unknown").value_counts())
        else:
            st.info("No DB loss rows recorded up to this timestep.")

    display_cols = [
        "timestep",
        "consumer_id",
        "customer_segment",
        "loan_purpose",
        "lost_at_stage",
        "loss_type",
        "winning_bank_name",
        "primary_loss_reason",
        "secondary_loss_reason",
        "rate_gap_bps",
        "approval_gap_days",
        "recoverable_loss",
        "recommended_improvement",
    ]
    available_cols = [col for col in display_cols if col in losses_t.columns]
    st.dataframe(losses_t[available_cols], use_container_width=True, hide_index=True)

with tab_improvements:
    st.markdown("### Tick improvements and see projected effect")
    st.caption("This projection is UI-side only. For authoritative results, use scenario_comparison.csv generated by running baseline and improved scenarios.")

    selected: List[str] = []
    option_cols = st.columns(2)
    keys = list(IMPROVEMENT_LABELS.keys())
    for idx, key in enumerate(keys):
        with option_cols[idx % 2]:
            if st.checkbox(IMPROVEMENT_LABELS[key], value=key in ["targeted_relationship_discount", "faster_preapproval_or_reduced_approval_sla"], key=f"improvement_{key}"):
                selected.append(key)

    projection = project_selected_improvements(current_metric, selected)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Projected DB wins", projection["projected_db_wins"])
    p2.metric("Projected competitor wins", projection["projected_competitor_wins"])
    p3.metric("Projected drop-offs", projection["projected_dropoffs"])
    p4.metric("Projected DB win rate", format_pct(projection["projected_db_win_rate"]))

    comparison_rows = [
        {
            "scenario": "Current selected timestep",
            "db_wins": int(current_metric.get("deutsche_bank_wins", current_metric.get("db_wins", 0)) or 0),
            "competitor_wins": int(current_metric.get("competitor_wins", 0) or 0),
            "dropoffs": int(current_metric.get("dropped", current_metric.get("dropoffs", 0)) or 0),
        },
        {
            "scenario": "Checkbox projection",
            "db_wins": projection["projected_db_wins"],
            "competitor_wins": projection["projected_competitor_wins"],
            "dropoffs": projection["projected_dropoffs"],
        },
    ]
    if not scenario.empty:
        for _, row in scenario.iterrows():
            comparison_rows.append({
                "scenario": row.get("scenario_name", row.get("scenario_mode", "scenario")),
                "db_wins": int(float(row.get("db_wins", 0) or 0)),
                "competitor_wins": int(float(row.get("competitor_wins", 0) or 0)),
                "dropoffs": int(float(row.get("dropoffs", row.get("dropped", 0)) or 0)),
            })

    comparison_df = pd.DataFrame(comparison_rows).set_index("scenario")
    st.bar_chart(comparison_df)

    if not recommendations.empty:
        matched = recommendations[recommendations["recommended_change"].isin(selected)] if "recommended_change" in recommendations.columns else pd.DataFrame()
        st.markdown("### Recommendations matched by selected improvements")
        st.dataframe(matched, use_container_width=True, hide_index=True)

with tab_feedback:
    st.markdown("### Customer reviews / feedback up to selected timestep")
    feedback_t = feedback.copy()
    if "timestep" in feedback_t.columns:
        feedback_t["timestep"] = numeric(feedback_t["timestep"])
        feedback_t = feedback_t[feedback_t["timestep"] <= selected_timestep]

    if not feedback_t.empty:
        for _, row in feedback_t.iterrows():
            st.info(f"T{int(row.get('timestep', 0))}: {row.get('message', '')}")
    else:
        st.info("No feedback rows available.")

    st.markdown("### Improvement-to-feedback mapping")
    mapping_rows = []
    selected_for_mapping = [key for key in IMPROVEMENT_LABELS if key in st.session_state and st.session_state.get(key)]
    for key in selected:
        label = IMPROVEMENT_LABELS[key]
        keywords = []
        if "discount" in key:
            keywords = ["rate", "instalment", "price"]
        elif "approval" in key:
            keywords = ["approval", "fast", "faster"]
        elif "document" in key:
            keywords = ["document", "upload"]
        elif "digital" in key:
            keywords = ["digital", "online"]
        elif "advisor" in key:
            keywords = ["advisor", "support"]
        count = 0
        if not feedback_t.empty and "message" in feedback_t.columns:
            count = feedback_t["message"].astype(str).str.lower().apply(lambda msg: any(k in msg for k in keywords)).sum()
        mapping_rows.append({"improvement": label, "matched_feedback_items": int(count), "keywords": ", ".join(keywords)})
    st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True, hide_index=True)

with tab_raw:
    st.markdown("### Loaded files")
    loaded_summary = []
    for key, filename in EXPECTED_FILES.items():
        df = loaded_data.get(key, pd.DataFrame())
        loaded_summary.append({"file": filename, "rows": len(df), "loaded": not df.empty})
    st.dataframe(pd.DataFrame(loaded_summary), use_container_width=True, hide_index=True)

    selected_file_key = st.selectbox("Preview file", list(EXPECTED_FILES.keys()), format_func=lambda k: EXPECTED_FILES[k])
    st.dataframe(loaded_data.get(selected_file_key, pd.DataFrame()), use_container_width=True)
