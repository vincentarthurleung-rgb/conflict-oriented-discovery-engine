#!/usr/bin/env python3
"""Bounded replay of authentic SEEN Builder V4 inputs; never dispatch a request."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
sys.dont_write_bytecode = True
OUT = ROOT / "runs/20261013_code_first_full_pipeline_seen_development_offline"
MARKER = "code_first_full_pipeline_seen_development_sha256"
DISPATCH_VIOLATIONS: list[str] = []


def deny_network(*args, **kwargs):
    DISPATCH_VIOLATIONS.append("NETWORK_ATTEMPT_DENIED")
    raise RuntimeError("OFFLINE_ONLY_NETWORK_DENIED")


socket.socket.connect = deny_network
socket.socket.connect_ex = deny_network
socket.create_connection = deny_network
socket.getaddrinfo = deny_network

from scripts import search_plan_v24_alpha318a1_source_contracts as construction
from scripts import search_plan_v24_alpha318b_post_builder_prechecks as prechecks
from scripts import search_plan_v24_alpha317d_preregister_quality_v2_offline as quality
from scripts import search_plan_v24_alpha320a_v4_localizer as localizer
from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id
from scripts.search_plan_v24_alpha317a_safety_audits import leakage_failed
from scripts.run_search_plan_v24_alpha320d_deterministic_variant_evaluation_offline import structural_result
from scripts.run_code_post_pilot_handoff_to_construction_adapter_offline import CONFIG
from scripts.run_code_pilot_bound_quality_v2_development_execution import quality_state
from code_engine.construction import handoff_adapter
from code_engine.normalization.resolver import ResolverCascade
from code_engine.normalization.formal_relations import normalize_formal_relation


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def obj(path):
    return json.loads(path.read_bytes())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def ref(path):
    assert path.is_file() and not path.is_symlink(), str(path)
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())}


def run(name):
    return ROOT / "runs" / name


def put(name, value):
    path = OUT / name
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600)


def root_record(directory):
    markers = [p for p in directory.glob("*_sha256") if p.is_file()
               and (p.name.startswith("search_plan_v24") or p.name.startswith("code_"))]
    assert len(markers) == 1, (directory.name, [p.name for p in markers])
    marker = markers[0]
    actual = handoff_adapter.root_hash(directory, marker.name)
    assert actual == marker.read_text().strip(), directory.name
    return {"path": str(directory.relative_to(ROOT)), "marker": marker.name, "sha256": actual}


def main():
    started = time.perf_counter()
    assert not OUT.exists() or {p.name for p in OUT.iterdir()} == {"selection_manifest.json"}, "NO_OVERWRITE_EXISTING_RESULT"
    d = run("20261002_search_plan_v24_dev_alpha3_19d_pmc_oa_jats_construction_eligibility")
    d1 = run("20261002_search_plan_v24_dev_alpha3_19d1_updateof_resolution_offline")
    e = run("20261002_search_plan_v24_dev_alpha3_19e_construction_document_anchor_builder_freeze_offline")
    b = run("20261002_search_plan_v24_dev_alpha3_20b_proposition_abstraction_prompt_freeze_offline")
    c = run("20261002_search_plan_v24_dev_alpha3_20c_builder_v4_development_execution")
    f = run("20261004_search_plan_v24_dev_alpha3_20f_final_builder_v4_contract_freeze_offline")
    adapter_dir = run("20261012_code_minimal_immutable_handoff_to_construction_adapter_offline")
    bf = run("20261012_code_pilot_bound_builder_v4_request_freeze_offline")
    be = run("20261012_code_first_pilot_bound_builder_v4_development_execution")
    qf = run("20261012_code_pilot_bound_quality_v2_request_freeze_offline")
    qe = run("20261013_code_pilot_bound_quality_v2_development_execution")
    qp = run("20260927_search_plan_v24_dev_alpha3_17d_independent_quality_adjudication_v2_preregistration_offline")
    seen_path = run("20261002_search_plan_v24_dev_alpha3_20_post_alpha3_19_development_master_preregistration_offline") / "alpha3_20_combined_seen_source_registry.jsonl"
    sample_path = run("20261002_search_plan_v24_dev_alpha3_19b_dedup_seen_source_sampling_offline") / "sampled_source_manifest.jsonl"
    protected = [root_record(p) for p in (d, d1, e, b, c, f, adapter_dir, bf, be, qf, qe, qp)]
    assert protected[4]["sha256"] == "51a78a802f8fdab234f2e0b962e69067ca0f9db53ee11822a195cffe523713f0"
    assert protected[6]["sha256"] == "d8a05a63f48f0fa71c319c25d4f0cf622127cbcee866465e01b7228181f709ea"
    assert protected[8]["sha256"] == "bebb5b6be579bd39a99f463e7f7f9d71e00001a05b7047ba9c60930f0a60c44f"
    assert protected[10]["sha256"] == "5a9b46ce730cbae2b4b757766343b63c198467e4d0c7745643b8c0a9b0696e7d"
    contract = obj(f / "search_plan_builder_v4_final_contract.json")
    for component in contract["components"]:
        assert ref(ROOT / component["artifact_path"])["sha256"] == component["sha256"]
    qbinding = obj(qf / "quality_contract_binding.json")
    for component in qbinding["contract_components"].values():
        assert ref(ROOT / component["artifact_path"])["sha256"] == component["sha256"]
    docs = {r["source_token"]: r for r in rows(e / "construction_document_manifest.jsonl")}
    sources = [s for s in rows(d1 / "final_construction_source_manifest.jsonl") if s["opaque_source_token"] in docs]
    samples = {r["pmid"]: r for r in rows(sample_path)}
    seen = {r["pmid"]: r for r in rows(seen_path)}
    source_manifest = obj(adapter_dir / "source_manifest.json")
    token_authority = source_manifest["opaque_source_token_authority"]
    pilot = token_authority["binding"]
    exposure_path = ROOT / CONFIG.pilot_directory / "contamination_registry/0002_actual_exposure.json"
    exposure = obj(exposure_path)
    assert exposure["future_independent_fresh_primary_excluded"] is True
    assert exposure["recognized_literature_identities"]["pmid"] == pilot["pmid"]
    inventory = [{"pmid": s["pmid"], "pmcid": s["pmcid"], "kind": "HISTORICAL_V4",
                  "stratum": samples[s["pmid"]]["owner_stratum"]} for s in sources]
    inventory.append({"pmid": pilot["pmid"], "pmcid": pilot["pmcid"], "kind": "PILOT_V4", "stratum": "pilot_MuSC_AR"})
    counts = Counter(x["stratum"] for x in inventory)
    assert max(counts.values()) < 6, "REVISIT_TOPIC_SELECTION_BEFORE_OUTCOMES"
    selected = sorted(inventory, key=lambda x: (-int(x["pmid"]), x["pmcid"]))[:8]
    assert len(selected) == len({x["pmid"] for x in selected}) == 8
    selection = {
        "classification": "SEEN_DATA_DEVELOPMENT_NOT_FRESH_PRIMARY",
        "rule_fixed_before_candidate_and_quality_replay": True,
        "universe": "All 14 source-bound alpha3.20B V4 construction requests plus the completed Pilot V4 source; not selected by scientific outcomes.",
        "coherent_topic_preference": "No existing source stratum in this exact V4 replay universe reaches six sources; use heterogeneous engineering cohort and do not claim a coherent-topic conflict test.",
        "stratum_counts": dict(counts), "stable_sort": "PMID numeric descending; PMCID lexical ascending tie break; first eight",
        "inventory": inventory, "selected": selected,
        "registry_references": [ref(seen_path), ref(exposure_path), ref(sample_path)],
    }
    if OUT.exists():
        assert obj(OUT / "selection_manifest.json") == selection, "FROZEN_SELECTION_CHANGED"
    else:
        OUT.mkdir(mode=0o700)
        put("selection_manifest.json", selection)
    # Selection is now durably fixed; no subsequent outcome may replace a source.
    selected_shas = ref(OUT / "selection_manifest.json")
    requests = {r["private_source_token"]: r for r in rows(b / "alpha3_20c_combined_request_manifest.jsonl") if r["variant_index"] == 1}
    responses = {r["execution_ordinal"]: r for r in rows(c / "alpha3_20c_raw_provider_responses.jsonl")}
    transports = {r["execution_ordinal"]: r for r in rows(c / "alpha3_20c_transport_provenance.jsonl")}
    schema = obj(b / "builder_output_schema_v4.json")["schema"]
    user_template = (run("20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline") / "proposition_builder_v2_1_user_prompt_template.txt").read_text()
    system_prompt = (f / "final_selected_builder_v4_prompt.txt").read_text()
    expected_template_hash = (f / "final_selected_builder_v4_prompt_sha256").read_text().strip()
    # Final prompt is the frozen SYSTEM + USER template, not just the system message.
    historical_quality_manifests = [
        run("20261001_search_plan_v24_dev_alpha3_18b_builder_execution") / "proposition_quality_v2_request_manifest.jsonl",
        run("20261001_search_plan_v24_dev_alpha3_18b2_builder_v3_execution") / "proposition_quality_v2_request_manifest_v3.jsonl",
    ]
    cache_request_hashes = set()
    for path in historical_quality_manifests:
        for record in rows(path):
            cache_request_hashes.add(record.get("request_sha256"))
    pilot_q = obj(qf / "quality_request_manifest.json")
    cache_request_hashes.add(pilot_q["request_sha256"])
    source_by_pmid = {s["pmid"]: s for s in sources}
    source_results, candidate_results, pending, historical_usage = [], [], [], []
    accepted = []
    for item in selected:
        tick = time.perf_counter()
        is_pilot = item["kind"] == "PILOT_V4"
        if is_pilot:
            bundle = handoff_adapter.load_verified_evidence_bundle(CONFIG)
            envelope = handoff_adapter.adapt_evidence_bundle(bundle, token_authority, ROOT)
            document = envelope["construction_document"]
            assert document == source_manifest["verified_construction_input"]["construction_document"]
            token = token_authority["opaque_source_token"]
            req_row = obj(bf / "builder_request_manifest.json")
            req = req_row["request"]
            execution = obj(be / "execution_manifest.json")
            raw_path = be / "provider_response.json"
            assert ref(raw_path)["sha256"] == execution["provider_response"]["sha256"]
            response = obj(raw_path)
            jats_ref = source_manifest["verified_construction_input"]["controller_private_provenance"]["normalized_jats_reference"]
            jats_path = Path(jats_ref["artifact_path"])
            assert ref(jats_path)["sha256"] == jats_ref["sha256"]
            private = prechecks.private_identity_from_jats(jats_path.read_bytes(), pilot["pmid"], pilot["pmcid"], pilot["doi"])
            doc_ref = {"path": str((adapter_dir / "source_manifest.json").relative_to(ROOT)), "json_pointer": "/verified_construction_input/construction_document", "canonical_document_sha256": sha(canonical(document))}
            assert doc_ref["canonical_document_sha256"] == req_row["construction_document_sha256"]
            historical_usage.append({"stage": "Builder V4", "pmid": item["pmid"], "usage": response["usage"], "elapsed_seconds": execution["elapsed_seconds"], "provider_cost": execution["provider_cost"], "ref": ref(raw_path)})
            admission = "VERIFIED_COMMITTED_PILOT_HANDOFF"
        else:
            s = source_by_pmid[item["pmid"]]
            assert s["pmid"] in seen and seen[s["pmid"]]["future_primary_fresh_heldout_reuse_prohibited"] is True
            assert s["construction_eligibility_state"] == "CONSTRUCTION_SOURCE_ELIGIBLE"
            token = s["opaque_source_token"]
            jats_path = d / s["normalized_jats_path"]
            assert ref(jats_path)["sha256"] == s["normalized_jats_sha256"]
            assert ref(d / s["raw_jats_path"])["sha256"] == s["raw_jats_sha256"]
            doc_row = docs[token]
            doc_path = e / doc_row["document_path"]
            assert ref(doc_path)["sha256"] == doc_row["document_sha256"]
            document = construction.build_construction_document(jats_path.read_bytes(), token)
            assert document == obj(doc_path)
            handoff_adapter.validate_construction_document(document, token)
            doc_ref = ref(doc_path)
            req_row = requests[token]
            req = req_row["request"]
            assert req_row["construction_document_sha256"] == doc_row["document_sha256"]
            ordinal = req_row["execution_ordinal"]
            transport = transports[ordinal]
            assert transport["request_sha256"] == req_row["request_sha256"]
            raw_path = c / transport["raw_response_path"]
            assert ref(raw_path)["sha256"] == transport["raw_response_sha256"]
            response = obj(raw_path)
            assert response["choices"][0]["message"]["content"] == responses[ordinal]["model_content_raw"]
            private = prechecks.private_identity_from_jats(jats_path.read_bytes(), s["pmid"], s["pmcid"], s.get("doi"))
            historical_usage.append({"stage": "Builder V4", "pmid": item["pmid"], "usage": response["usage"], "elapsed_seconds": transport["elapsed_seconds"], "provider_cost": response.get("cost"), "ref": ref(raw_path)})
            admission = "VERIFIED_ORIGINAL_HISTORICAL_ELIGIBILITY_NOT_PROSPECTIVE_TRANSPORT_REPLAY"
        assert sha(canonical(req)) == req_row["request_sha256"]
        assert sha(canonical({"abstract_text": document["abstract_text"], "body_text": document["body_text"]})) == req_row["scientific_source_input_sha256"]
        assert req["model"] == response["model"] == "deepseek-flash"
        assert req["thinking"] == {"type": "enabled"} and req["reasoning_effort"] == "high"
        assert "temperature" not in req and "top_p" not in req
        assert req["messages"][1]["content"] == user_template.format(source_record_token=token, frozen_abstract=document["abstract_text"], frozen_body=document["body_text"], output_schema_json=canonical(schema).decode())
        # Preserve the two actual frozen serializers. The Pilot splits on
        # \nUSER:\n and therefore omits the historical system's final LF.
        separator = "\nUSER:\n" if is_pilot else "USER:\n"
        assert sha(("SYSTEM:\n" + req["messages"][0]["content"] + separator + user_template).encode()) == expected_template_hash
        parsed = prechecks.validate_builder_response(response["choices"][0]["message"]["content"].encode(), token, schema)
        survivors = []
        records = []
        seen_candidates = set()
        for position, candidate in enumerate(parsed["candidates"]):
            cid = candidate_id(token, candidate)
            localized = localizer.localize_exact_body_quote(candidate["construction_evidence_span"]["exact_text"], document["body_text"], document["paragraphs"])
            structure = structural_result(candidate, schema)
            record = {"pmid": item["pmid"], "candidate_id": cid, "original_array_position": position, "candidate_payload_sha256": sha(canonical(candidate)), "proposition_verbatim": candidate["neutral_proposition"], "candidate": candidate, "localization": localized, "structure": structure, "quality_state": "NOT_EVALUATED"}
            duplicate = cid in seen_candidates
            seen_candidates.add(cid)
            record["exact_duplicate"] = duplicate
            if localized["development_v4_localization_state"] == localizer.SUCCESS and structure["structural_state"] == "STRUCTURALLY_COMPLETE":
                start, end = localized["body_document_start_offset"], localized["body_document_end_offset"]
                sentence = prechecks.evidence_sentence(document["body_text"], start, end)
                failed = leakage_failed(candidate["neutral_proposition"], private["title_1"], sentence)
                record["leakage_state"] = "FAILED" if failed else "PASSED"
                if not failed and not duplicate:
                    enriched = copy.deepcopy(candidate)
                    enriched["construction_evidence_span"] = {"source_field": "body", "start_offset": start, "end_offset": end, "exact_text": candidate["construction_evidence_span"]["exact_text"]}
                    survivors.append({"candidate_id": cid, "candidate_payload_sha256": record["candidate_payload_sha256"], "candidate": enriched, "original_array_positions": [position]})
            else:
                record["leakage_state"] = "NOT_EXECUTED"
            records.append(record)
        survivors.sort(key=lambda r: (r["candidate_payload_sha256"], r["candidate_id"]))
        qstate, qsha = "NO_ELIGIBLE_OUTPUT", None
        if survivors:
            payload = prechecks.build_quality_payload(token, survivors, document, private)
            qrequest = prechecks.build_quality_request(payload, pilot_q["expected_response_schema"], (qp / "quality_adjudicator_system_prompt.txt").read_text(), (qp / "quality_adjudicator_user_prompt_template.txt").read_text(), obj(qp / "quality_machine_output_contract.json")["appendix_utf8"])
            qrequest["model"] = qbinding["provider_projection"]["frozen_operational_model"]
            qsha = sha(canonical(qrequest))
            if is_pilot:
                assert qrequest == pilot_q["request"] and qsha == pilot_q["request_sha256"]
                qexecution = obj(qe / "execution_manifest.json")
                qraw = qe / qexecution["provider_response"]["artifact_path"]
                assert ref(qraw)["sha256"] == qexecution["provider_response"]["sha256"]
                qresponse = obj(qraw)
                assert qresponse["model"] == qrequest["model"] == qexecution["actual_provider_model"]
                judgments = quality.validate_response(json.loads(qresponse["choices"][0]["message"]["content"]), payload["source_group_id"], {p["candidate_id"] for p in payload["candidate_packets"]}, {p["candidate_id"]: p["evidence"]["exact_evidence_span"] + "\n" + p["evidence"]["bounded_local_context"] for p in payload["candidate_packets"]}, pilot_q["expected_response_schema"])
                jmap = {j["candidate_id"]: j for j in judgments}
                frozen_judgments = {j["candidate_id"]: j for j in obj(qe / "candidate_quality_results.json")["candidate_records"]}
                for record in records:
                    if record["candidate_id"] in jmap:
                        judgment = jmap[record["candidate_id"]]
                        state = quality_state(judgment["criteria"])
                        assert state == frozen_judgments[record["candidate_id"]]["quality_state"]
                        record["quality_state"] = state
                        record["quality_judgment"] = judgment
                        if state == "QUALITY_PASS":
                            accepted.append(record)
                historical_usage.append({"stage": "Quality V2", "pmid": item["pmid"], "usage": qresponse["usage"], "elapsed_seconds": qexecution["elapsed_seconds"], "provider_cost": qexecution["provider_cost"], "ref": ref(qraw)})
                qstate = "VERIFIED_CACHE_REPLAY"
            else:
                assert qsha not in cache_request_hashes, "MATCHED_CACHE_REQUIRES_RESPONSE_VALIDATION_BEFORE_STOPPING"
                pending.append({"pmid": item["pmid"], "source_group_id": payload["source_group_id"], "candidate_count": len(survivors), "candidate_ids": [r["candidate_id"] for r in survivors], "request_sha256": qsha, "request": qrequest, "execution_authorized": False, "planned_inference_attempts": 1, "automatic_retry": False})
                qstate = "BLOCKED"
        candidate_results.extend(records)
        source_results.append({**item, "seen_verified": True, "admission": admission, "jats": {**ref(jats_path), "status": "VERIFIED_CACHE_REPLAY"}, "construction": {"status": "EXECUTED", "exact_frozen_document_reproduced": True, "reference": doc_ref, "body_character_count": len(document["body_text"])}, "builder": {"status": "VERIFIED_CACHE_REPLAY", "request_sha256": req_row["request_sha256"], "response": ref(raw_path), "schema_valid_candidates": len(records)}, "deterministic_survivor_count": len(survivors), "quality": {"status": qstate, "request_sha256": qsha, "accepted_candidate_count": sum(r["quality_state"] == "QUALITY_PASS" for r in records)}, "offline_elapsed_seconds": round(time.perf_counter()-tick, 6)})
    # Existing resolver is exercised without any guessed entity type, cleaning,
    # intervention stripping, causal sign inversion, or external lookup.
    cache_path = ROOT / "data/index/entity_cache/accepted_mappings.jsonl"
    cache_before = ref(cache_path)
    resolver = ResolverCascade(execute=False, network_enabled=False, api_enabled=False, entity_network_lookup=False, entity_llm_proposer=False, entity_llm_cleaner=False, external_clients={})
    normalized = []
    for record in accepted:
        candidate = record["candidate"]
        for field, role in (("actor_or_intervention", "subject"), ("response_or_endpoint", "object")):
            decision = resolver.resolve_entity(candidate[field], {"species": candidate["species"], "paper_id": record["pmid"], "claim_id": record["candidate_id"], "mention_role": role, "context_text": candidate["construction_evidence_span"]["exact_text"]})
            normalized.append({"candidate_id": record["candidate_id"], "source_pmid": record["pmid"], "input_field": field, "component_probe_only_not_authoritative_observation_projection": True, "decision": decision.model_dump(mode="json")})
        record["formal_relation_direct_native_input_result"] = None if normalize_formal_relation(candidate) is None else "UNEXPECTED_NATIVE_RELATION_AVAILABLE"
    assert ref(cache_path) == cache_before
    # No guessed adapter/observations are injected into the downstream pipeline.
    downstream = [
        {"stage": "entity normalization", "status": "EXECUTED", "scope": "six raw role-surface component probes on Quality-accepted Pilot candidates; not a complete observation adapter", "input_candidates": len(accepted), "resolved_role_surfaces": sum(x["decision"]["normalization_status"] == "resolved" for x in normalized), "role_surface_count": len(normalized)},
        {"stage": "relation normalization and authoritative observation handoff", "status": "BLOCKED", "reason": "Builder V4 native fields do not supply relation_raw/relation_family/direction expected by normalize_formal_relation; no activated Builder/Quality-to-L2 observation projection was found. Do not infer actor, intervention semantics, endpoint decomposition, or validated entity types.", "input_candidates": len(accepted), "normalized_relations": 0},
        {"stage": "cross-paper comparability", "status": "NO_ELIGIBLE_OUTPUT", "reason": "Only one source has exact verified Quality cache; no authoritative normalized relation records; no admissible cross-paper pair.", "comparable_pairs": 0},
        {"stage": "conflict detection and classification", "status": "BLOCKED", "reason": "No admissible normalized cross-paper observations; module exists but was not executed on fabricated or empty substitute inputs.", "confirmed_conflicts": 0},
        {"stage": "context attribution", "status": "NO_ELIGIBLE_OUTPUT", "reason": "No validated conflict candidate/comparability input; existing pending-policy contracts cannot be replaced with explanations.", "context_explanations": 0},
        {"stage": "hypothesis generation", "status": "NO_ELIGIBLE_OUTPUT", "reason": "Implemented artifact-based generator has no admissible conflict/mechanism inputs in this run; not called with fabricated inputs.", "falsifiable_hypotheses": 0},
        {"stage": "final evidence-linked output", "status": "EXECUTED", "scope": "Development report plus authentic proposition/source/offset bindings, not a discovery result."},
    ]
    for previous in protected:
        assert root_record(ROOT / previous["path"]) == previous
    assert ref(OUT / "selection_manifest.json") == selected_shas
    assert not DISPATCH_VIOLATIONS
    put("source_stage_results.json", source_results)
    put("evidence_linked_outputs_private.json", {"role": "SEEN_DATA_DEVELOPMENT", "candidates": candidate_results, "normalization_component_probes": normalized, "conflicts": [], "hypotheses": [], "quality_is_not_independent_scientific_accuracy": True})
    put("pending_quality_requests_private.json", {"authorization": "NOT_AUTHORIZED_DO_NOT_DISPATCH", "source_group_count": len(pending), "planned_new_quality_calls": len(pending), "new_builder_calls": 0, "requests": pending, "extra_downstream_calls_not_budgetable_until_interfaces_and_eligible_inputs_exist": True})
    tokens = {k: sum(u["usage"].get(k, 0) for u in historical_usage) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    put("provenance_and_execution.json", {"protected_roots_before_after": protected, "seen_registry": ref(seen_path), "pilot_actual_exposure_registry": ref(exposure_path), "normalization_cache_before_after": cache_before, "runner": ref(Path(__file__)), "historical_usage_replayed_not_new_usage": historical_usage, "new_network_calls": 0, "new_llm_calls": 0, "denied_dispatch_attempts": DISPATCH_VIOLATIONS, "historical_assets_unchanged": True, "no_journal_reconstruction": True})
    summary = {"status": "PARTIAL_DEVELOPMENT_EXECUTION_BLOCKED_NOT_END_TO_END", "seen_source_count": len(selected), "construction_valid_documents": len(source_results), "generated_propositions_from_verified_cache": len(candidate_results), "deterministic_survivors": sum(r["deterministic_survivor_count"] for r in source_results), "quality_cache_replayed_source_groups": sum(r["quality"]["status"] == "VERIFIED_CACHE_REPLAY" for r in source_results), "quality_accepted_propositions": len(accepted), "quality_not_evaluated_propositions": sum(r["quality_state"] == "NOT_EVALUATED" for r in candidate_results), "normalized_relations": 0, "comparable_cross_paper_pairs": 0, "confirmed_conflict_candidates": 0, "context_explanations": 0, "falsifiable_hypotheses": 0, "source_results": source_results, "downstream_stage_results": downstream, "new_call_budget_pending_separate_authorization": {"builder": 0, "quality": len(pending), "literature": 0, "downstream_adjudication": "UNDETERMINED_NOT_AUTHORIZED"}, "historical_token_usage_of_replayed_inferences": tokens, "historical_provider_elapsed_seconds_sum_not_replay_wall_time": sum(u["elapsed_seconds"] for u in historical_usage), "actual_new_token_usage": 0, "actual_new_provider_cost": 0, "historical_reported_cost": None, "historical_cost_unavailable_no_pricing_inference": True, "offline_execution_seconds": round(time.perf_counter()-started, 6), "scientific_policy_changed": False, "runtime_source_modified": False, "fresh_primary_started": False, "network_calls": 0, "llm_calls": 0, "independently_verified_scientific_accuracy": "NOT_EVALUATED", "limitations": ["Mixed-topic replay cohort is not a conflict-enriched coherent biomedical cohort.", "Seven source groups may require new Quality adjudication; no automatic calls authorized.", "Builder/Quality to authoritative normalized observation wiring is missing, not fixed by relabeling schemas.", "Pilot mechanistic claim has previously identified evidence-window insufficiency and potential overstatement; cached Quality PASS is not independent scientific validation.", "Historical eligible JATS is verified as archived evidence, not upgraded to a durable prospective HTTP journal."]}
    put("summary.json", summary)
    final_root = handoff_adapter.root_hash(OUT, MARKER)
    with (OUT / MARKER).open("x") as handle:
        handle.write(final_root + "\n")
    assert handoff_adapter.root_hash(OUT, MARKER) == final_root
    print(json.dumps({k: v for k, v in summary.items() if k not in ("source_results", "downstream_stage_results")}, ensure_ascii=False, indent=2))
    print("result_root_sha256=" + final_root)


if __name__ == "__main__":
    main()
