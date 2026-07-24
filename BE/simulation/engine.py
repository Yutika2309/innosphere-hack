from __future__ import annotations

"""Simulation engine for the Lending World agentic simulation.

This version adds the missing deterministic layer between agent outputs and CSV
files:
- validates/normalises rows before commit
- quarantines invalid rows into invalid_rows.csv
- fills timestep and committed_timestep
- writes canonical CSV schemas
- splits customer lifecycle events and snapshots
- builds deterministic public summaries/marketplace dashboard fallbacks
- creates basic loss-analysis/recommendation rows for dropouts
"""

import csv
import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from .row_validation import (
        collect_invalid_rows,
        flatten_validated_results,
        json_safe,
        validate_and_normalise_tables,
        validation_summary,
    )
except Exception:  # pragma: no cover - supports flat/script use
    from row_validation import (  # type: ignore
        collect_invalid_rows,
        flatten_validated_results,
        json_safe,
        validate_and_normalise_tables,
        validation_summary,
    )

try:
    from .csv_schemas import CSV_SCHEMAS, get_schema, ordered_row
except Exception:  # pragma: no cover
    from csv_schemas import CSV_SCHEMAS, get_schema, ordered_row  # type: ignore


class LendingWorldSimulation:
    def __init__(self, cfg: Any):
        self.cfg = cfg
        self.current_timestep = 0
        self.completed = False
        self.rng = random.Random(getattr(cfg, "seed", 42))
        self.output_dir = Path(getattr(cfg, "output_dir", "output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir = Path(getattr(cfg, "log_dir", "logs"))
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("simulation.engine")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        if not self.logger.handlers:
            fh = logging.FileHandler(self.log_dir / "engine.log", encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
            self.logger.addHandler(fh)

        self.banks = self._seed_banks(int(getattr(cfg, "num_banks", 8)))
        self.consumers = self._seed_consumers(int(getattr(cfg, "num_consumers", 14)))
        self.private_summaries: Dict[str, str] = {}

        # In-memory mirrors of output tables.
        for table_name in CSV_SCHEMAS:
            setattr(self, f"{table_name}_rows", [])
        self.public_information_summary_rows: List[Dict[str, Any]] = []
        self.marketplace_dashboard_rows: List[Dict[str, Any]] = []
        self.scenario_comparison_rows: List[Dict[str, Any]] = []

        self._initialise_output_files()

    # ------------------------------------------------------------------
    # Initial data
    # ------------------------------------------------------------------

    def _seed_banks(self, n: int) -> List[Dict[str, Any]]:
        names = [
            "Deutsche Bank", "Commerzbank", "ING", "DKB", "Sparkasse",
            "Volksbanken Raiffeisenbanken", "Targobank", "Santander",
        ]
        banks = []
        for i in range(1, n + 1):
            bank_id = f"B{i:03d}"
            banks.append({
                "bank_id": bank_id,
                "actor_id": bank_id,
                "bank_name": names[i - 1] if i <= len(names) else f"Bank {i}",
                "market": "Germany",
            })
        return banks

    def _seed_consumers(self, n: int) -> List[Dict[str, Any]]:
        names = [
            "Anna Müller", "Lukas Schneider", "Sophie Weber", "Max Fischer",
            "Elena García", "Thomas Becker", "Mia Hoffmann", "Jonas Wagner",
            "Laura Schmidt", "Nico Bauer", "Hannah Krause", "Omar Yilmaz",
            "Klara Neumann", "Felix Richter",
        ]
        purposes = [
            "home_modernisation", "used_electric_vehicle_purchase", "family_home_renovation",
            "business_cash_flow_bridge", "relocation_and_home_setup", "used_car_loan",
            "consumer_electronics_and_training", "debt_consolidation", "equipment_and_working_capital",
        ]
        consumers = []
        for i in range(1, n + 1):
            cid = f"C{i:03d}"
            consumers.append({
                "consumer_id": cid,
                "actor_id": cid,
                "name": names[i - 1] if i <= len(names) else f"Dynamic Consumer {cid}",
                "funnel_stage": "lead",
                "active": True,
                "selected_bank": None,
                "selected_bank_name": None,
                "loan_purpose": purposes[(i - 1) % len(purposes)],
                "expected_loan_amount": [3500, 10500, 12000, 16000, 18000, 22000, 24000, 26000, 28000][(i - 1) % 9],
                "preferred_term_months": [24, 36, 48, 60, 72][(i - 1) % 5],
            })
        return consumers

    def _initialise_output_files(self) -> None:
        for table_name, columns in CSV_SCHEMAS.items():
            path = self.output_dir / f"{table_name}.csv"
            if not path.exists():
                self._write_rows(table_name, [], columns=columns, initialise=True)

    # ------------------------------------------------------------------
    # CSV writing
    # ------------------------------------------------------------------

    def _write_rows(self, table_name: str, rows: List[Dict[str, Any]], *, columns: Optional[List[str]] = None, initialise: bool = False) -> int:
        columns = columns or get_schema(table_name)
        path = self.output_dir / f"{table_name}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = initialise or not path.exists() or path.stat().st_size == 0
        normalised_rows = [ordered_row(json_safe(row), table_name) for row in rows]
        if not columns and normalised_rows:
            columns = list(normalised_rows[0].keys())
        with path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            for row in normalised_rows:
                writer.writerow(row)
        return len(rows)

    def _append_table_rows(self, table_name: str, rows: List[Dict[str, Any]]) -> int:
        if not rows:
            return 0
        attr = f"{table_name}_rows"
        if not hasattr(self, attr):
            setattr(self, attr, [])
        getattr(self, attr).extend(rows)
        return self._write_rows(table_name, rows)

    # ------------------------------------------------------------------
    # Context builders used by agent.py
    # ------------------------------------------------------------------

    def build_world_news_agent_context(self) -> Dict[str, Any]:
        return {
            "timestep": self.current_timestep + 1,
            "agent_name": "world_news_agent",
            "actor_type": "world",
            "actor_id": "world_news",
            "market": "Germany",
            "news_min_rows": getattr(self.cfg, "world_news_min_rows_per_timestep", 1),
            "scenario_name": getattr(self.cfg, "scenario_name", "baseline_current_db"),
        }

    def build_bank_agent_contexts(self) -> List[Dict[str, Any]]:
        contexts = []
        public_summary = self.get_latest_public_summary_text()
        marketplace_dashboard = self.get_latest_marketplace_dashboard()
        for bank in self.banks:
            bank_id = bank["bank_id"]
            contexts.append({
                "timestep": self.current_timestep + 1,
                "agent_name": "bank_agent",
                "actor_type": "bank",
                "actor_id": bank_id,
                "bank_id": bank_id,
                "bank_name": bank.get("bank_name"),
                "bank_state": bank,
                "bank_private_summary": self.private_summaries.get(bank_id, ""),
                "public_information_summary": public_summary,
                "marketplace_dashboard": marketplace_dashboard,
                "previous_bank_offers": [r for r in getattr(self, "bank_offers_rows", []) if r.get("bank_id") == bank_id][-20:],
                "previous_bank_actions": [r for r in getattr(self, "bank_actions_rows", []) if r.get("bank_id") == bank_id][-20:],
            })
        return contexts

    def build_customer_agent_contexts(self) -> List[Dict[str, Any]]:
        public_summary = self.get_latest_public_summary_text()
        marketplace_dashboard = self.get_latest_marketplace_dashboard()
        public_offers = [r for r in getattr(self, "bank_offers_rows", []) if r.get("visibility") == "public"][-50:]
        contexts = []
        for consumer in self.consumers:
            if not consumer.get("active", True):
                continue
            cid = consumer["consumer_id"]
            contexts.append({
                "timestep": self.current_timestep + 1,
                "agent_name": "customer_agent",
                "actor_type": "consumer",
                "actor_id": cid,
                "consumer_id": cid,
                "customer_state": consumer,
                "current_funnel_stage": consumer.get("funnel_stage", "lead"),
                "own_private_summary": self.private_summaries.get(cid, ""),
                "public_information_summary": public_summary,
                "marketplace_dashboard": marketplace_dashboard,
                "eligible_public_offers": public_offers,
                "decision_thresholds": {
                    "marketplace_reliance": getattr(self.cfg, "default_marketplace_reliance", 0.5),
                    "public_news_reliance": getattr(self.cfg, "default_public_news_reliance", 0.3),
                    "relationship_bank_reliance": getattr(self.cfg, "default_relationship_bank_reliance", 0.4),
                    "digital_comparison_preference": getattr(self.cfg, "default_digital_comparison_preference", 0.5),
                },
            })
        return contexts

    def build_marketplace_agent_context(self) -> Dict[str, Any]:
        return {
            "timestep": self.current_timestep + 1,
            "agent_name": "marketplace_agent",
            "actor_type": "marketplace",
            "actor_id": "loan_marketplace",
            "public_information_summary": self.get_latest_public_summary_text(),
            "committed_public_bank_offers": [r for r in getattr(self, "bank_offers_rows", []) if r.get("visibility") == "public"][-100:],
            "committed_public_marketing_actions": [r for r in getattr(self, "marketing_actions_rows", []) if r.get("visibility") == "public"][-100:],
            "committed_public_bank_actions": [r for r in getattr(self, "bank_actions_rows", []) if r.get("visibility") == "public"][-100:],
            "previous_marketplace_dashboard": self.get_latest_marketplace_dashboard(),
        }

    def build_post_processing_agent_context(self) -> Dict[str, Any]:
        public_rows = self._public_rows_for_summary(self.current_timestep)
        return {
            "timestep": self.current_timestep,
            "agent_name": "post_processing_agent",
            "actor_type": "system",
            "actor_id": "post_processing",
            "public_rows": public_rows[-100:],
            "public_row_count": len(public_rows),
        }

    # ------------------------------------------------------------------
    # Core timestep commit
    # ------------------------------------------------------------------

    def run_timestep(self, agent_outputs: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> Dict[str, Any]:
        if self.completed:
            return {"status": "done", "completed": True, "timestep": self.current_timestep}

        timestep = self.current_timestep + 1
        self.logger.info("=== TIMESTEP %s START ===", timestep)
        agent_outputs = dict(agent_outputs or {})

        validation_results = validate_and_normalise_tables(
            {k: v for k, v in agent_outputs.items() if k != "invalid_rows"},
            timestep,
            strict=bool(getattr(self.cfg, "strict_schema_validation_enabled", True)),
        )
        validated_outputs = flatten_validated_results(validation_results)
        invalid_rows = collect_invalid_rows(validation_results)
        if agent_outputs.get("invalid_rows"):
            invalid_rows.extend(agent_outputs.get("invalid_rows") or [])

        rows_written: Dict[str, int] = {}
        for table_name in [
            "world_news",
            "consumer_actions",
            "bank_actions",
            "marketing_actions",
            "marketplace_rankings",
            "marketplace_recommendations",
            "marketplace_visibility_events",
            "funnel_events",
            "bank_offers",
            "customer_feedback",
        ]:
            rows_written[table_name] = self._append_table_rows(table_name, validated_outputs.get(table_name, []))

        if invalid_rows:
            rows_written["invalid_rows"] = self._append_table_rows("invalid_rows", invalid_rows[: int(getattr(self.cfg, "max_invalid_rows_logged_per_timestep", 100))])
        else:
            rows_written["invalid_rows"] = 0

        self._apply_funnel_events(validated_outputs.get("funnel_events", []), timestep)
        self._apply_consumer_actions(validated_outputs.get("consumer_actions", []), timestep)
        self._stochastic_customer_lifecycle(timestep)
        lifecycle_writes = self._write_lifecycle_outputs(timestep)
        rows_written.update(lifecycle_writes)

        marketplace_dashboard = self._build_marketplace_dashboard(timestep)
        rows_written["marketplace_dashboard"] = self._append_table_rows("marketplace_dashboard", [marketplace_dashboard])
        self.marketplace_dashboard_rows.append(marketplace_dashboard)

        public_summary = self._build_public_summary(timestep)
        self.public_information_summary_rows.append(public_summary)
        rows_written["public_information_summary"] = self._append_table_rows("public_information_summary", [public_summary])

        diagnostic_writes = self._generate_diagnostics(timestep)
        rows_written.update(diagnostic_writes)

        metrics = self._build_conversion_metrics(timestep)
        rows_written["conversion_metrics"] = self._append_table_rows("conversion_metrics", [metrics])

        self.current_timestep = timestep
        if self.current_timestep >= int(getattr(self.cfg, "timesteps", 1)):
            self.completed = True

        self.logger.info("VALIDATION_SUMMARY timestep=%s summary=%s", timestep, validation_summary(validation_results))
        self.logger.info("=== TIMESTEP %s DONE rows_written=%s completed=%s ===", timestep, rows_written, self.completed)
        return {
            "status": "ok",
            "timestep": timestep,
            "completed": self.completed,
            "rows_written": rows_written,
            "validation_summary": validation_summary(validation_results),
            "post_processing": {
                "public_summary_created": True,
                "marketplace_dashboard_created": True,
                "invalid_rows": len(invalid_rows),
            },
        }

    # ------------------------------------------------------------------
    # State transitions / lifecycle
    # ------------------------------------------------------------------

    def _consumer_by_id(self, consumer_id: str) -> Optional[Dict[str, Any]]:
        for consumer in self.consumers:
            if consumer.get("consumer_id") == consumer_id:
                return consumer
        return None

    def _apply_funnel_events(self, events: List[Dict[str, Any]], timestep: int) -> None:
        for event in events:
            cid = event.get("consumer_id")
            consumer = self._consumer_by_id(cid)
            if not consumer:
                continue
            after = event.get("funnel_stage_after")
            if after:
                consumer["funnel_stage"] = after
            if after == "dropped":
                consumer["active"] = False
                consumer["drop_reason"] = event.get("event_detail") or "customer_drop"
                consumer["left_timestep"] = timestep
            if event.get("selected_bank"):
                consumer["selected_bank"] = event.get("selected_bank")
                consumer["selected_bank_name"] = event.get("selected_bank_name")

    def _apply_consumer_actions(self, actions: List[Dict[str, Any]], timestep: int) -> None:
        for action in actions:
            cid = action.get("consumer_id")
            consumer = self._consumer_by_id(cid)
            if not consumer:
                continue
            after = action.get("funnel_stage_after")
            if after:
                consumer["funnel_stage"] = after
            if action.get("selected_bank_id"):
                consumer["selected_bank"] = action.get("selected_bank_id")
                consumer["selected_bank_name"] = action.get("selected_bank_name")

    def _stochastic_customer_lifecycle(self, timestep: int) -> None:
        # Keep this conservative; customer-agent decisions should drive most movement.
        active = [c for c in self.consumers if c.get("active", True)]
        if active and self.rng.random() < 0.15:
            consumer = self.rng.choice(active)
            consumer["active"] = False
            consumer["funnel_stage"] = "dropped"
            consumer["drop_reason"] = "stochastic_dropout"
            consumer["left_timestep"] = timestep
        if self.rng.random() < 0.35:
            next_id = len(self.consumers) + 1
            cid = f"C{next_id:03d}"
            self.consumers.append({
                "consumer_id": cid,
                "actor_id": cid,
                "name": f"Dynamic Consumer {cid}",
                "funnel_stage": "lead",
                "active": True,
                "selected_bank": None,
                "selected_bank_name": None,
                "loan_purpose": "dynamic_loan_need",
                "expected_loan_amount": 10000,
                "preferred_term_months": 48,
                "joined_timestep": timestep,
            })

    def _write_lifecycle_outputs(self, timestep: int) -> Dict[str, int]:
        snapshots = []
        events = []
        for c in self.consumers:
            snapshots.append({
                "timestep": timestep,
                "consumer_id": c.get("consumer_id"),
                "name": c.get("name"),
                "row_type": "snapshot",
                "funnel_stage": c.get("funnel_stage"),
                "active": c.get("active"),
                "selected_bank": c.get("selected_bank"),
                "selected_bank_name": c.get("selected_bank_name"),
                "offered_rate": c.get("offered_rate"),
                "approved_amount": c.get("approved_amount"),
                "drop_reason": c.get("drop_reason"),
                "loan_episode": c.get("loan_episode"),
                "joined_timestep": c.get("joined_timestep"),
                "left_timestep": c.get("left_timestep"),
                "successful_loans": c.get("successful_loans", 0),
                "reentry_reason": c.get("reentry_reason"),
            })
            if c.get("joined_timestep") == timestep:
                events.append({
                    "timestep": timestep,
                    "consumer_id": c.get("consumer_id"),
                    "name": c.get("name"),
                    "row_type": "event",
                    "event_type": "joined",
                    "funnel_stage_before": "none",
                    "funnel_stage_after": c.get("funnel_stage", "lead"),
                    "active_before": False,
                    "active_after": True,
                    "reason": "dynamic_spawn",
                    "joined_timestep": timestep,
                })
            if c.get("left_timestep") == timestep:
                events.append({
                    "timestep": timestep,
                    "consumer_id": c.get("consumer_id"),
                    "name": c.get("name"),
                    "row_type": "event",
                    "event_type": "left",
                    "funnel_stage_before": "lead",
                    "funnel_stage_after": "dropped",
                    "active_before": True,
                    "active_after": False,
                    "drop_reason": c.get("drop_reason"),
                    "reason": c.get("drop_reason"),
                    "left_timestep": timestep,
                })
        self.customer_lifecycle_snapshot_rows.extend(snapshots)
        self.customer_lifecycle_events_rows.extend(events)
        return {
            "customer_lifecycle_snapshot": self._write_rows("customer_lifecycle_snapshot", snapshots),
            "customer_lifecycle_events": self._write_rows("customer_lifecycle_events", events),
        }

    # ------------------------------------------------------------------
    # Summaries, dashboard, diagnostics
    # ------------------------------------------------------------------

    def _public_rows_for_summary(self, timestep: int) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for table_name in ["world_news", "bank_offers", "bank_actions", "marketing_actions", "marketplace_rankings", "marketplace_recommendations", "marketplace_visibility_events", "customer_feedback", "funnel_events"]:
            for row in getattr(self, f"{table_name}_rows", []) or []:
                if row.get("visibility") == "public" and int(row.get("timestep") or 0) <= timestep:
                    clean = dict(row)
                    clean["source_table"] = table_name
                    rows.append(clean)
        return rows

    def _build_public_summary(self, timestep: int) -> Dict[str, Any]:
        window = int(getattr(self.cfg, "public_summary_window_timesteps", 10))
        from_ts = max(1, timestep - window + 1)
        rows = [r for r in self._public_rows_for_summary(timestep) if int(r.get("timestep") or 0) >= from_ts]
        if not rows:
            summary = "No public activity was recorded in this window."
        else:
            snippets = []
            for row in rows[:40]:
                text = row.get("headline") or row.get("event_detail") or row.get("offer_description") or row.get("action_detail") or row.get("campaign_detail") or row.get("ranking_reason") or row.get("recommendation_reason")
                if text:
                    snippets.append(f"- {row.get('source_table')}: {str(text)[:220]}")
            summary = "\n".join(snippets) if snippets else f"{len(rows)} public rows were recorded."
        return {
            "run_id": None,
            "timestep": timestep,
            "summary_from_timestep": from_ts,
            "summary_to_timestep": timestep,
            "window_size": window,
            "public_information_summary": summary,
            "created_by": "engine_fallback",
        }

    def _build_marketplace_dashboard(self, timestep: int) -> Dict[str, Any]:
        public_offers = [r for r in getattr(self, "bank_offers_rows", []) if r.get("visibility") == "public"]
        bank_ids = sorted({str(r.get("bank_id")) for r in public_offers if r.get("bank_id")})
        product_ids = sorted({str(r.get("product_id")) for r in public_offers if r.get("product_id")})
        rankings = getattr(self, "marketplace_rankings_rows", [])
        recommendations = getattr(self, "marketplace_recommendations_rows", [])
        visibility_events = getattr(self, "marketplace_visibility_events_rows", [])
        return {
            "timestep": timestep,
            "dashboard_timestep": timestep,
            "public_offer_count": len(public_offers),
            "public_bank_count": len(bank_ids),
            "ranked_offer_count": len(rankings),
            "recommendation_count": len(recommendations),
            "visibility_event_count": len(visibility_events),
            "top_bank_ids": ",".join(bank_ids[:10]),
            "top_product_ids": ",".join(product_ids[:10]),
            "dashboard_summary": f"{len(public_offers)} public offers from {len(bank_ids)} banks are available for marketplace/customer comparison.",
            "created_by": "engine_fallback",
        }

    def _generate_diagnostics(self, timestep: int) -> Dict[str, int]:
        losses = []
        recs = []
        dropped_now = [c for c in self.consumers if c.get("left_timestep") == timestep and c.get("drop_reason")]
        for c in dropped_now:
            loss = {
                "timestep": timestep,
                "consumer_id": c.get("consumer_id"),
                "customer_segment": c.get("customer_segment"),
                "loan_purpose": c.get("loan_purpose"),
                "lost_at_stage": c.get("funnel_stage", "dropped"),
                "loss_type": "funnel_abandonment",
                "winning_bank_name": c.get("selected_bank_name"),
                "primary_loss_reason": c.get("drop_reason"),
                "secondary_loss_reason": None,
                "rate_gap_bps": None,
                "approval_gap_days": None,
                "recoverable_loss": True,
                "recommended_improvement": "advisor_callback_or_follow_up",
            }
            losses.append(loss)
            recs.append({
                "timestep": timestep,
                "consumer_id": c.get("consumer_id"),
                "recommendation_id": f"REC_{timestep}_{c.get('consumer_id')}",
                "target_issue": c.get("drop_reason"),
                "recommended_change": "Trigger advisor callback / abandoned journey follow-up",
                "implementation_complexity": "low",
                "expected_impact": "recover some abandoned funnel customers",
                "affected_stage": c.get("funnel_stage", "dropped"),
                "competitor_bank_name": c.get("selected_bank_name"),
            })
        self.db_loss_analysis_rows.extend(losses)
        self.db_recommendations_rows.extend(recs)
        return {
            "db_loss_analysis": self._write_rows("db_loss_analysis", losses),
            "db_recommendations": self._write_rows("db_recommendations", recs),
        }

    def _build_conversion_metrics(self, timestep: int) -> Dict[str, Any]:
        total = len(self.consumers)
        active = len([c for c in self.consumers if c.get("active", True)])
        dropped = len([c for c in self.consumers if not c.get("active", True)])
        db_wins = len([c for c in self.consumers if c.get("selected_bank") == "B001"])
        competitor_wins = len([c for c in self.consumers if c.get("selected_bank") and c.get("selected_bank") != "B001"])
        lost_to_competitor = competitor_wins
        recoverable_losses = len([r for r in self.db_loss_analysis_rows if r.get("recoverable_loss")])
        return {
            "timestep": timestep,
            "total_customers": total,
            "active_customers": active,
            "deutsche_bank_wins": db_wins,
            "competitor_wins": competitor_wins,
            "dropped": dropped,
            "lost_to_competitor": lost_to_competitor,
            "funnel_abandonments": dropped,
            "recoverable_losses": recoverable_losses,
            "deutsche_bank_win_rate": round(db_wins / max(1, db_wins + competitor_wins), 4),
        }

    # ------------------------------------------------------------------
    # Public query helpers
    # ------------------------------------------------------------------

    def get_latest_public_summary_text(self) -> str:
        if self.public_information_summary_rows:
            return str(self.public_information_summary_rows[-1].get("public_information_summary") or "")
        return "No public summary available."

    def get_latest_marketplace_dashboard(self) -> Dict[str, Any]:
        if self.marketplace_dashboard_rows:
            return dict(self.marketplace_dashboard_rows[-1])
        return {"dashboard_timestep": self.current_timestep, "dashboard_summary": "No marketplace dashboard available yet.", "public_offer_count": 0}

    def add_consumer(self, consumer: Dict[str, Any]) -> Dict[str, Any]:
        cid = consumer.get("consumer_id") or f"C{len(self.consumers) + 1:03d}"
        row = {**consumer, "consumer_id": cid, "actor_id": cid, "active": True, "funnel_stage": consumer.get("funnel_stage", "lead"), "joined_timestep": self.current_timestep}
        self.consumers.append(row)
        return {"status": "ok", "consumer_id": cid}

    def drop_consumer(self, consumer_id: str, reason: str = "manual_drop") -> Dict[str, Any]:
        consumer = self._consumer_by_id(consumer_id)
        if not consumer:
            return {"status": "error", "message": f"Consumer not found: {consumer_id}"}
        consumer["active"] = False
        consumer["funnel_stage"] = "dropped"
        consumer["drop_reason"] = reason
        consumer["left_timestep"] = self.current_timestep
        return {"status": "ok", "consumer_id": consumer_id, "reason": reason}

    def get_active_consumers(self) -> Dict[str, Any]:
        rows = [c for c in self.consumers if c.get("active", True)]
        return {"status": "ok", "count": len(rows), "consumers": rows}

    def get_funnel_metrics(self) -> Dict[str, Any]:
        stages: Dict[str, int] = {}
        for c in self.consumers:
            stages[c.get("funnel_stage", "unknown")] = stages.get(c.get("funnel_stage", "unknown"), 0) + 1
        return {"status": "ok", "timestep": self.current_timestep, "stages": stages}

    def get_customer_lifecycle(self) -> Dict[str, Any]:
        return {"status": "ok", "snapshot_rows": getattr(self, "customer_lifecycle_snapshot_rows", []), "event_rows": getattr(self, "customer_lifecycle_events_rows", [])}

    def get_marketing_campaigns(self) -> Dict[str, Any]:
        return {"status": "ok", "rows": getattr(self, "marketing_actions_rows", [])}

    def get_db_loss_analysis(self) -> Dict[str, Any]:
        return {"status": "ok", "rows": getattr(self, "db_loss_analysis_rows", [])}

    def get_db_recommendations(self) -> Dict[str, Any]:
        return {"status": "ok", "rows": getattr(self, "db_recommendations_rows", [])}

    def build_scenario_summary_row(self, scenario_name: Optional[str] = None) -> Dict[str, Any]:
        row = {
            "scenario_name": scenario_name or getattr(self.cfg, "scenario_name", "scenario"),
            "timestep": self.current_timestep,
            "total_customers": len(self.consumers),
            "active_customers": len([c for c in self.consumers if c.get("active", True)]),
            "db_loss_rows": len(getattr(self, "db_loss_analysis_rows", [])),
            "db_recommendation_rows": len(getattr(self, "db_recommendations_rows", [])),
        }
        self.scenario_comparison_rows.append(row)
        return row

    def get_scenario_comparison(self) -> Dict[str, Any]:
        return {"status": "ok", "rows": self.scenario_comparison_rows}


def _is_offer_active_for_timestep(offer: dict, timestep: int) -> bool:
    try:
        start = int(offer.get("valid_from_timestep") or offer.get("timestep") or timestep)
    except Exception:
        start = timestep
    raw_end = offer.get("valid_to_timestep")
    if raw_end in (None, "", "None"):
        return start <= timestep
    try:
        end = int(raw_end)
    except Exception:
        return start <= timestep
    return start <= timestep <= end

def _active_rows_for_timestep(rows: list, timestep: int) -> list:
    return [row for row in (rows or []) if isinstance(row, dict) and _is_offer_active_for_timestep(row, timestep)]


# -----------------------------------------------------------------------------
# Active offers, Deutsche Bank closures, and bank reputation helpers
# -----------------------------------------------------------------------------
def _is_offer_active_for_timestep(offer: dict, timestep: int) -> bool:
    try: start = int(offer.get("valid_from_timestep") or offer.get("timestep") or timestep)
    except Exception: start = timestep
    raw_end = offer.get("valid_to_timestep")
    if raw_end in (None, "", "None"): return start <= timestep
    try: end = int(raw_end)
    except Exception: return start <= timestep
    return start <= timestep <= end
def _active_rows_for_timestep(rows: list, timestep: int) -> list:
    return [row for row in (rows or []) if isinstance(row, dict) and _is_offer_active_for_timestep(row, timestep)]
def _deutsche_bank_closed_application_metrics(lifecycle_rows: list, timestep: int, config: dict, previous_count: int = 0) -> dict:
    db_id = config.get("deutsche_bank_id", "B001"); closed_stages = set(config.get("closed_application_stages") or ["completed", "finished", "closed", "loan_closed"])
    current_rows = [r for r in (lifecycle_rows or []) if int(r.get("timestep", timestep)) == int(timestep)]; closed = []
    for row in current_rows:
        if str(row.get("selected_bank") or row.get("closed_by_bank_id") or "") == db_id and str(row.get("funnel_stage") or "") in closed_stages:
            cid = row.get("consumer_id")
            if cid: closed.append(str(cid))
    closed = sorted(set(closed))
    return {"deutsche_bank_closed_applications": len(closed), "deutsche_bank_closed_applications_delta": len(closed) - int(previous_count or 0), "deutsche_bank_closed_application_consumer_ids": ",".join(closed)}
def _apply_bank_reputation_defaults(row: dict, config: dict) -> dict:
    reps = config.get("bank_reputation_scores") or {}; bank_id = row.get("bank_id") or row.get("actor_id")
    if bank_id in reps:
        rep = reps[bank_id]; row.setdefault("base_reputation_score", rep.get("base_reputation_score")); row.setdefault("current_reputation_score", rep.get("current_reputation_score", rep.get("base_reputation_score"))); row.setdefault("reputation_source", rep.get("source")); row.setdefault("reputation_notes", rep.get("source_type"))
    return row

# ACTIVE_OFFER_FILTERING_REQUIRED: use _active_rows_for_timestep(bank_offers, timestep) for marketplace dashboard and customer/marketplace context.
# DB_CLOSED_METRICS_REQUIRED: merge _deutsche_bank_closed_application_metrics(...) into conversion_metrics at each timestep.
# BANK_REPUTATION_REQUIRED: call _apply_bank_reputation_defaults(...) for bank action/offer/marketing rows before writing.
