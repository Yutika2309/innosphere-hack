
from __future__ import annotations
from pathlib import Path
import json, re

ROOT = Path.cwd()
SIM = ROOT / "simulation"
FILES = {
    "agent": ROOT / "agent.py",
    "row_validation": SIM / "row_validation.py" if (SIM / "row_validation.py").exists() else ROOT / "row_validation.py",
    "csv_schemas": SIM / "csv_schemas.py" if (SIM / "csv_schemas.py").exists() else ROOT / "csv_schemas.py",
    "engine": SIM / "engine.py" if (SIM / "engine.py").exists() else ROOT / "engine.py",
    "post_processing": SIM / "post_processing.py" if (SIM / "post_processing.py").exists() else ROOT / "post_processing.py",
    "private_summaries": SIM / "private_summaries.py" if (SIM / "private_summaries.py").exists() else ROOT / "private_summaries.py",
    "default_config": ROOT / "default_configs.json",
    "bank_personas": ROOT / "bank_personas.json",
    "consumer_personas": ROOT / "consumer_personas.json",
    "readme": ROOT / "README.md",
}

REPUTATION = {
    "B001": {"bank_name":"Deutsche Bank","base_reputation_score":49.0,"source":"Investors Marketing CCI 2025","source_type":"customer_centricity_index"},
    "B002": {"bank_name":"Commerzbank","base_reputation_score":62.84,"source":"Argus Data Insights Reputationsstudie Banken 2025","source_type":"media_reputation"},
    "B003": {"bank_name":"ING-DiBa","base_reputation_score":67.44,"source":"Argus Data Insights Reputationsstudie Banken 2025","source_type":"media_reputation"},
    "B004": {"bank_name":"DKB","base_reputation_score":68.0,"source":"Configured proxy: GlobalData says Deutsche Kreditbank follows ING-DiBa in NPS; exact score unavailable in accessible snippet","source_type":"proxy_from_nps_order"},
    "B005": {"bank_name":"Sparkasse","base_reputation_score":54.74,"source":"Argus Data Insights Reputationsstudie Banken 2025, Hamburger Sparkasse proxy","source_type":"media_reputation_proxy"},
    "B006": {"bank_name":"Volksbanken","base_reputation_score":41.0,"source":"Investors Marketing CCI 2025, Genossenschaftsbanken proxy","source_type":"customer_centricity_index_proxy"},
    "B007": {"bank_name":"Targobank","base_reputation_score":80.77,"source":"Argus Data Insights Reputationsstudie Banken 2025","source_type":"media_reputation"},
    "B008": {"bank_name":"Santander Consumer Bank","base_reputation_score":63.01,"source":"Argus Data Insights Reputationsstudie Banken 2025","source_type":"media_reputation"},
}

def backup(path: Path) -> None:
    if path.exists():
        b = path.with_suffix(path.suffix + ".bak_no_retry_reasoning_reputation")
        if not b.exists():
            b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

def replace_function(text: str, name: str, new_source: str) -> str:
    start = text.find("def " + name + "(")
    if start == -1:
        return text
    m = re.search(r"\ndef [A-Za-z_][A-Za-z0-9_]*\(|\nasync def [A-Za-z_][A-Za-z0-9_]*\(|\n# -{5,}", text[start + 1:])
    end = len(text) if not m else start + 1 + m.start()
    return text[:start] + new_source.rstrip() + "\n" + text[end:]

def patch_default_config():
    path = FILES["default_config"]
    cfg = {}
    if path.exists():
        backup(path)
        cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["row_validation_mode"] = "repair_insert"
    cfg["enable_row_retry"] = False
    cfg["max_row_retry_attempts"] = 0
    cfg["always_insert_unrepaired_rows"] = True
    cfg["write_unrepaired_rows_to_target_csv"] = True
    cfg["invalid_rows_file_is_audit_only"] = True
    cfg.setdefault("default_offer_validity_timesteps", 3)
    cfg["active_offers_only_for_marketplace"] = True
    cfg.setdefault("deutsche_bank_id", "B001")
    cfg.setdefault("closed_application_stages", ["completed", "finished", "closed", "loan_closed"])
    cfg["customer_reasoning_field"] = "decision_reason"
    cfg["feedback_is_experience_only"] = True
    cfg["use_bank_reputation_score"] = True
    cfg["bank_reputation_scores"] = REPUTATION
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print("patched", path)

def patch_personas(path: Path, bank: bool):
    if not path.exists():
        print("missing", path); return
    backup(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    def patch_obj(o, key=None):
        if not isinstance(o, dict): return o
        if bank:
            bid = o.get("bank_id") or o.get("id") or o.get("actor_id") or key
            if bid in REPUTATION:
                r = REPUTATION[bid]
                o.setdefault("bank_id", bid)
                o.setdefault("base_reputation_score", r["base_reputation_score"])
                o.setdefault("current_reputation_score", r["base_reputation_score"])
                o.setdefault("reputation_source", r["source"])
                o.setdefault("reputation_source_type", r["source_type"])
                o.setdefault("reputation_notes", "Initial score loaded from default_configs.bank_reputation_scores")
        else:
            o.setdefault("reputation_sensitivity", 0.5)
            o.setdefault("price_sensitivity", o.get("price_sensitivity", 0.7))
            o.setdefault("speed_sensitivity", o.get("speed_sensitivity", 0.5))
            o.setdefault("green_preference", o.get("green_preference", 0.3))
            o.setdefault("trust_threshold", 40.0)
        return o
    if isinstance(data, list):
        data = [patch_obj(x) for x in data]
    elif isinstance(data, dict):
        lk = "banks" if bank else "consumers"
        if isinstance(data.get(lk), list):
            data[lk] = [patch_obj(x) for x in data[lk]]
        else:
            for k, v in list(data.items()): data[k] = patch_obj(v, k)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("patched", path)

def patch_csv_schemas():
    path = FILES["csv_schemas"]
    if not path.exists(): print("missing", path); return
    backup(path)
    text = path.read_text(encoding="utf-8")
    for col in ["retry_attempted", "retry_success", "retry_attempt"]:
        text = re.sub(r"\n\s*['\"]" + col + r"['\"],?", "", text)
    if "validation_status" not in text:
        text = text.replace('"committed_timestep",', '"committed_timestep",\n    "validation_status",\n    "validation_errors",\n    "repair_notes",\n    "raw_row_json",')
        text = text.replace("'committed_timestep',", "'committed_timestep',\n    'validation_status',\n    'validation_errors',\n    'repair_notes',\n    'raw_row_json',")
    if "decision_reason" not in text:
        text = text.replace('"action_detail",', '"action_detail",\n    "decision_reason",\n    "reasoning_inputs",\n    "considered_offer_ids",', 1)
        text = text.replace("'action_detail',", "'action_detail',\n    'decision_reason',\n    'reasoning_inputs',\n    'considered_offer_ids',", 1)
    if "deutsche_bank_closed_applications" not in text:
        text = text.replace('"deutsche_bank_wins",', '"deutsche_bank_wins",\n    "deutsche_bank_closed_applications",\n    "deutsche_bank_closed_applications_delta",\n    "deutsche_bank_closed_application_consumer_ids",')
        text = text.replace("'deutsche_bank_wins',", "'deutsche_bank_wins',\n    'deutsche_bank_closed_applications',\n    'deutsche_bank_closed_applications_delta',\n    'deutsche_bank_closed_application_consumer_ids',")
    if "base_reputation_score" not in text:
        text = text.replace('"bank_name",', '"bank_name",\n    "base_reputation_score",\n    "current_reputation_score",\n    "reputation_source",\n    "reputation_notes",')
        text = text.replace("'bank_name',", "'bank_name',\n    'base_reputation_score',\n    'current_reputation_score',\n    'reputation_source',\n    'reputation_notes',")
    if "valid_from_timestep" not in text:
        text = text.replace('"offer_description",', '"offer_description",\n    "valid_from_timestep",\n    "valid_to_timestep",')
        text = text.replace("'offer_description',", "'offer_description',\n    'valid_from_timestep',\n    'valid_to_timestep',")
    path.write_text(text, encoding="utf-8")
    print("patched", path)

ROW_VALIDATION_HELPER = r'''

# -----------------------------------------------------------------------------
# Final row policy: validation -> repair -> insert, no retry
# -----------------------------------------------------------------------------
def _ri_json_dumps(value):
    import json
    try: return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception: return str(value)
def _ri_is_blank(value): return value is None or value == "" or value == [] or value == {}
def _ri_join(value):
    if isinstance(value, list): return ",".join(str(x) for x in value)
    if isinstance(value, dict): return _ri_json_dumps(value)
    return value
def _ri_meta(row, raw, status, errors, notes):
    row["validation_status"] = status; row["validation_errors"] = "; ".join(errors or []); row["repair_notes"] = "; ".join(notes or []); row["raw_row_json"] = _ri_json_dumps(raw)
    row.pop("retry_attempted", None); row.pop("retry_success", None); row.pop("retry_attempt", None)
    return row
def validate_repair_insert_row(table_name, row, timestep, context=None):
    context = context or {}; raw = dict(row or {}); row = dict(row or {}); errors, notes = [], []
    if "action_details" in row and _ri_is_blank(row.get("action_detail")): row["action_detail"] = _ri_json_dumps(row.get("action_details")); notes.append("action_details -> action_detail")
    if isinstance(row.get("action_detail"), (dict, list)): row["action_detail"] = _ri_json_dumps(row.get("action_detail")); notes.append("action_detail serialised")
    if "type" in row and _ri_is_blank(row.get("action_type")): row["action_type"] = row.get("type"); notes.append("type -> action_type")
    if "action_name" in row and _ri_is_blank(row.get("action_type")): row["action_type"] = row.get("action_name"); notes.append("action_name -> action_type")
    if table_name == "consumer_actions":
        if _ri_is_blank(row.get("decision_reason")): row["decision_reason"] = row.get("reasoning_summary") or row.get("action_detail") or "Customer action recorded; explicit decision reason was not provided."; notes.append("decision_reason generated")
        if _ri_is_blank(row.get("reasoning_summary")): row["reasoning_summary"] = row.get("decision_reason"); notes.append("reasoning_summary mirrored")
        if isinstance(row.get("considered_offer_ids"), list): row["considered_offer_ids"] = _ri_join(row.get("considered_offer_ids"))
    if table_name == "customer_feedback":
        if _ri_is_blank(row.get("experience_type")): row["experience_type"] = row.get("feedback_type") or "experience"; notes.append("experience_type defaulted")
        if _ri_is_blank(row.get("message")): row["message"] = "Customer experience feedback recorded."; notes.append("message defaulted")
    if table_name == "marketing_actions":
        if "target_audience" in row and _ri_is_blank(row.get("target_segment")): row["target_segment"] = _ri_join(row.get("target_audience")); notes.append("target_audience -> target_segment")
        if isinstance(row.get("target_segment"), (list, dict)): row["target_segment"] = _ri_join(row.get("target_segment")); notes.append("target_segment serialised")
        if "channels" in row and _ri_is_blank(row.get("marketing_channel")): row["marketing_channel"] = _ri_join(row.get("channels")); notes.append("channels -> marketing_channel")
        if "budget_eur" in row and _ri_is_blank(row.get("marketing_spend_eur")): row["marketing_spend_eur"] = row.get("budget_eur"); notes.append("budget_eur -> marketing_spend_eur")
    if table_name in {"marketplace_rankings", "marketplace_recommendations"}:
        if _ri_is_blank(row.get("product_id")) and not _ri_is_blank(row.get("product_name")): row["product_id"] = str(row.get("product_name")).lower().replace(" ", "_"); notes.append("product_id from product_name")
        if _ri_is_blank(row.get("product_id")) and not _ri_is_blank(row.get("offer_id")): row["product_id"] = str(row.get("offer_id")); notes.append("product_id from offer_id")
        if _ri_is_blank(row.get("bank_id")) and str(row.get("actor_id", "")).startswith("B"): row["bank_id"] = row.get("actor_id"); notes.append("bank_id from actor_id")
        if table_name == "marketplace_rankings" and _ri_is_blank(row.get("rank")): row["rank"] = row.get("action_sequence") or row.get("intra_timestep_sequence") or 999; notes.append("rank defaulted")
        if table_name == "marketplace_recommendations" and _ri_is_blank(row.get("recommendation_reason")): row["recommendation_reason"] = row.get("recommendation_text") or row.get("recommendation_details") or row.get("recommendation_narrative") or "Marketplace recommendation recorded."; notes.append("recommendation_reason generated")
    if table_name == "marketplace_visibility_events":
        if _ri_is_blank(row.get("event_type")): row["event_type"] = row.get("visibility_type") or row.get("category") or "marketplace_event"; notes.append("event_type defaulted")
        if _ri_is_blank(row.get("event_detail")): row["event_detail"] = row.get("reasoning_summary") or row.get("headline") or row.get("message") or row.get("event_type") or "Marketplace visibility event recorded."; notes.append("event_detail generated")
        if _ri_is_blank(row.get("bank_id")) and str(row.get("actor_id", "")).startswith("B"): row["bank_id"] = row.get("actor_id"); notes.append("bank_id from actor_id")
    if table_name == "bank_offers":
        if _ri_is_blank(row.get("valid_from_timestep")): row["valid_from_timestep"] = timestep; notes.append("valid_from_timestep defaulted")
        if _ri_is_blank(row.get("valid_to_timestep")): validity = int(context.get("default_offer_validity_timesteps", 3) or 3); row["valid_to_timestep"] = int(timestep) + max(1, validity) - 1; notes.append("valid_to_timestep defaulted")
    reps = context.get("bank_reputation_scores") or {}; bank_id = row.get("bank_id") or row.get("actor_id")
    if bank_id in reps and table_name in {"bank_actions", "bank_offers", "marketing_actions"}:
        rep = reps[bank_id]; row.setdefault("base_reputation_score", rep.get("base_reputation_score")); row.setdefault("current_reputation_score", rep.get("current_reputation_score", rep.get("base_reputation_score"))); row.setdefault("reputation_source", rep.get("source")); row.setdefault("reputation_notes", rep.get("source_type"))
    row.setdefault("timestep", timestep)
    if _ri_is_blank(row.get("actor_id")): row["actor_id"] = context.get("actor_id") or context.get("bank_id") or context.get("consumer_id") or "unknown"; notes.append("actor_id defaulted")
    if _ri_is_blank(row.get("action_id")): row["action_id"] = f"{table_name}-{timestep}-{row.get('actor_id')}-{abs(hash(_ri_json_dumps(raw))) % 100000}"; notes.append("action_id generated")
    required = {"bank_actions":["action_type"], "bank_offers":["offer_id","bank_id","product_id"], "consumer_actions":["consumer_id","action_type","decision_reason"], "customer_feedback":["consumer_id","message"], "marketplace_rankings":["offer_id","bank_id","product_id","rank"], "marketplace_recommendations":["offer_id","bank_id","product_id"], "marketplace_visibility_events":["event_type","event_detail"]}
    for field in required.get(table_name, []):
        if _ri_is_blank(row.get(field)): errors.append(f"missing required field after repair: {field}")
    status = "unrepaired" if errors else "repaired" if notes else "valid"
    return _ri_meta(row, raw, status, errors, notes)
def expand_nested_rows_for_repair_insert(table_name, rows):
    expanded = []
    for row in rows or []:
        row = dict(row or {})
        if table_name == "marketplace_rankings" and isinstance(row.get("ranks"), list):
            for item in row.get("ranks") or []:
                if isinstance(item, dict): child = dict(row); child.pop("ranks", None); child.update(item); child.setdefault("ranking_id", row.get("ranking_id") or row.get("ranking_category")); expanded.append(child)
            continue
        if table_name == "marketplace_recommendations" and isinstance(row.get("recommended_offers"), list):
            for item in row.get("recommended_offers") or []:
                if isinstance(item, dict): child = dict(row); child.pop("recommended_offers", None); child.update(item); child.setdefault("recommendation_reason", row.get("recommendation_narrative") or row.get("recommendation_text") or row.get("recommendation_details")); expanded.append(child)
            continue
        if table_name == "marketplace_recommendations" and isinstance(row.get("recommended_offer_ids"), list):
            for offer_id in row.get("recommended_offer_ids") or []: child = dict(row); child.pop("recommended_offer_ids", None); child["offer_id"] = offer_id; expanded.append(child)
            continue
        expanded.append(row)
    return expanded
'''

def patch_row_validation():
    path = FILES["row_validation"]
    if not path.exists(): print("missing", path); return
    backup(path); text = path.read_text(encoding="utf-8")
    if "validate_repair_insert_row" not in text: text += ROW_VALIDATION_HELPER
    path.write_text(text, encoding="utf-8"); print("patched", path)

AGENT_VALIDATE = r'''
def _validate_rows_for_table(table_name: str, rows: List[Dict[str, Any]], *, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    context = dict(context or {})
    context.setdefault("default_offer_validity_timesteps", _cfg_value("default_offer_validity_timesteps", 3))
    context.setdefault("bank_reputation_scores", _cfg_value("bank_reputation_scores", {}))
    expanded_rows = expand_nested_rows_for_repair_insert(table_name, rows or [])
    repaired_rows: List[Dict[str, Any]] = []
    status_counts: Dict[str, int] = {}
    for row in expanded_rows:
        if not isinstance(row, dict): row = {"raw_value": str(row)}
        repaired = validate_repair_insert_row(table_name, row, _pending_timestep(), context=context)
        status = str(repaired.get("validation_status") or "unknown"); status_counts[status] = status_counts.get(status, 0) + 1
        repaired_rows.append(repaired)
    agent_logger.info("ROWS_VALIDATE_REPAIR_INSERT run_id=%s table=%s input=%s output=%s statuses=%s", _SESSION.get("run_id"), table_name, len(rows or []), len(repaired_rows), status_counts)
    return repaired_rows
'''

def patch_agent():
    path = FILES["agent"]
    if not path.exists(): print("missing", path); return
    backup(path); text = path.read_text(encoding="utf-8")
    if "validate_repair_insert_row" not in text:
        text = text.replace("from .simulation.row_validation import json_safe, validate_and_normalise_rows", "from .simulation.row_validation import json_safe, validate_and_normalise_rows, validate_repair_insert_row, expand_nested_rows_for_repair_insert")
        text = text.replace("from simulation.row_validation import json_safe, validate_and_normalise_rows", "from simulation.row_validation import json_safe, validate_and_normalise_rows, validate_repair_insert_row, expand_nested_rows_for_repair_insert")
    text = re.sub(r"\n\s*['\"]row_retry_requests['\"]\s*:\s*\[\],?", "", text)
    text = replace_function(text, "_validate_rows_for_table", AGENT_VALIDATE)
    text = text.replace('"row_retry_requests": _SESSION.get("row_retry_requests", []), ', '')
    text = text.replace("row_retry_requests", "row_repair_metadata")
    text = text.replace("retry corrected rows once only", "do not retry rows").replace("retry corrected rows once", "do not retry rows")
    text = text.replace("call record_customer_rows once more with corrected rows only", "do not retry rows").replace("call record_bank_rows once more with corrected rows only", "do not retry rows").replace("call record_marketplace_rows once more with corrected rows only", "do not retry rows")
    if "customer_feedback is only for customer experience" not in text:
        text += "\n# Customer reasoning rule: include decision_reason in consumer_actions for every meaningful customer move. customer_feedback is only for customer experience, satisfaction, friction, complaints or praise; never use it for decision reasoning.\n"
    if "base_reputation_score/current_reputation_score" not in text:
        text += "\n# Bank reputation rule: bank agents receive base_reputation_score/current_reputation_score from default_configs.bank_reputation_scores and should consider reputation in pricing, service and marketing decisions.\n"
    path.write_text(text, encoding="utf-8"); print("patched", path)

ENGINE_HELPER = r'''

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
'''

def patch_engine():
    path = FILES["engine"]
    if not path.exists(): print("missing", path); return
    backup(path); text = path.read_text(encoding="utf-8")
    if "def _deutsche_bank_closed_application_metrics" not in text: text += ENGINE_HELPER
    if "ACTIVE_OFFER_FILTERING_REQUIRED" not in text:
        text += "\n# ACTIVE_OFFER_FILTERING_REQUIRED: use _active_rows_for_timestep(bank_offers, timestep) for marketplace dashboard and customer/marketplace context.\n"
        text += "# DB_CLOSED_METRICS_REQUIRED: merge _deutsche_bank_closed_application_metrics(...) into conversion_metrics at each timestep.\n"
        text += "# BANK_REPUTATION_REQUIRED: call _apply_bank_reputation_defaults(...) for bank action/offer/marketing rows before writing.\n"
    path.write_text(text, encoding="utf-8"); print("patched", path)

def append_note(path: Path, title: str, body: str):
    if not path.exists(): print("missing", path); return
    backup(path); text = path.read_text(encoding="utf-8")
    if title not in text: text += f"\n\n# {title}\n{body}\n"
    path.write_text(text, encoding="utf-8"); print("patched", path)

def patch_docs():
    append_note(FILES["post_processing"], "Repair Insert Policy Notes", "Use active offers only in public summaries. Include Deutsche Bank closed applications and bank reputation changes where available. Do not present expired offers as current offers.")
    append_note(FILES["private_summaries"], "Reasoning And Reputation Notes", "Customer private summaries should include consumer_actions.decision_reason. Bank private summaries should include current_reputation_score, active offer performance, closed applications and lost customers.")
    append_note(FILES["readme"], "Validation, customer reasoning, closed applications, and reputation", "Validation policy is validation -> repair -> insert. There is no retry-to-agent layer. Customer reasoning belongs in consumer_actions.decision_reason. customer_feedback is experience only. Offers are limited-time and marketplace/customer context should use active offers. conversion_metrics should include Deutsche Bank closed application counts and consumer ids. Banks have base/current reputation scores.")

def main():
    patch_default_config(); patch_personas(FILES["bank_personas"], True); patch_personas(FILES["consumer_personas"], False); patch_csv_schemas(); patch_row_validation(); patch_agent(); patch_engine(); patch_docs()
    print("Done: no retry, repair-insert policy, customer decision_reason, DB closed metrics helpers, active offer helpers, and reputation config applied.")
if __name__ == "__main__": main()
