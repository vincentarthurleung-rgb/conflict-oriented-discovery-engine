#!/usr/bin/env python3
"""Execute only the frozen alpha3.19A NCBI source and JATS acquisition."""
from __future__ import annotations

import json
import re
import secrets
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg
from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as historical_transport
from scripts import search_plan_v24_alpha318a4_esearch_response_validity as esearch
from scripts import search_plan_v24_alpha318a5_primary_identity as primary
from scripts import search_plan_v24_alpha318a3_correction_reference as correction
from scripts import search_plan_v24_alpha318a1_source_contracts as source_policy


ROOT = master.ROOT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19a_ncbi_only_source_acquisition"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19a_sha256"
EXPECTED_PREREG = "d65e7b2ed58e855201e12fc31cf100f14d9e37bc91a0dafeb21183418f7cd132"
EXPECTED_QUERY_SET = "45536e1b734d1eeb54e0d111d6878c1b6dee58d1a762ad934d66b7d40089885e"
EXPECTED_MANIFEST = "103199b656d10fbd850d3e0ebbdf3329685ec8438f4c5df0752afc1748733899"
NEXT_PASS = "PREREGISTER_ALPHA3_19B_SOURCE_CONSTRUCTION_AND_BUILDER_FREEZE"
NEXT_FAIL = "AUDIT_ALPHA3_19A_RUNTIME_FAILURE_OFFLINE"
DEFERRED_UPDATEOF = "UPDATEOF_PENDING_19B_STRUCTURAL_RESOLUTION"


class PhaseFailure(RuntimeError):
    pass


def require(ok: bool, code: str):
    if not ok:
        raise PhaseFailure(code)


def write_json(name: str, value: Any):
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(master.canonical(value) + b"\n")


def write_jsonl(name: str, rows: list[dict]):
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(b"".join(master.canonical(row) + b"\n" for row in rows))


def write_bytes(name: str, raw: bytes):
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(raw)


def marker(name: str, value: str):
    write_bytes(name, (value + "\n").encode())


def root_hash() -> str:
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != ROOT_MARKER)
    require(not any(p.is_symlink() for p in OUT.rglob("*")), "SYMLINK_IN_RUN")
    return master.sha(master.canonical([[str(p.relative_to(OUT)), master.digest(p)] for p in files]))


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA3_19A_RUN_DIRECTORY_ALREADY_EXISTS")
    require(prereg.frozen_root(master.OUT, "search_plan_v24_dev_alpha3_19_master_prereg_sha256") ==
            prereg.MASTER_SHA and
            (master.OUT / "search_plan_v24_dev_alpha3_19_master_prereg_sha256").read_text().strip() ==
            prereg.MASTER_SHA,
            "MASTER_ROOT_MISMATCH")
    require(prereg.frozen_root(prereg.OUT, "search_plan_v24_dev_alpha3_19a_prereg_sha256") ==
            EXPECTED_PREREG and
            (prereg.OUT / "search_plan_v24_dev_alpha3_19a_prereg_sha256").read_text().strip() ==
            EXPECTED_PREREG,
            "ALPHA3_19A_PREREG_ROOT_MISMATCH")
    query_path = prereg.OUT / "alpha3_19_source_query_set.jsonl"
    manifest_path = prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json"
    require(master.digest(query_path) == EXPECTED_QUERY_SET and
            (prereg.OUT / "alpha3_19_source_query_set_sha256").read_text().strip() ==
            EXPECTED_QUERY_SET,
            "FROZEN_QUERY_SET_MISMATCH")
    require(master.digest(manifest_path) == EXPECTED_MANIFEST and
            (prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest_sha256").read_text().strip() ==
            EXPECTED_MANIFEST,
            "FROZEN_EXECUTION_MANIFEST_MISMATCH")
    plan = prereg.load(manifest_path)
    queries = master.rows(query_path)
    master_queries = master.rows(master.OUT / "alpha3_19_source_query_templates.jsonl")
    require(plan["query_count"] == len(queries) == len(master_queries) == 6 and
            plan["query_hashes"] == [q["query_sha256"] for q in queries] and
            all(a["query_utf8"] == b["term"] and
                a["query_sha256"] == master.sha(a["query_utf8"].encode()) and
                a["stratum_id"] == b["stratum_id"] and
                a["query_utf8"].count('"pubmed pmc"[sb]') == 1
                for a, b in zip(queries, master_queries)) and
            plan["material_runtime_policy_unresolved_count"] == 0,
            "FROZEN_QUERY_OR_RUNTIME_POLICY_MISMATCH")
    require(plan["network_scope"]["allowed_host"] == "eutils.ncbi.nlm.nih.gov" and
            set(plan["network_scope"]["allowed_endpoints"]) == {prereg.ES, prereg.EF} and
            plan["model_calls"] == 0,
            "NETWORK_OR_MODEL_SCOPE_MISMATCH")
    def walk(value):
        if isinstance(value, dict):
            if "path" in value and "sha256" in value:
                prereg.check_ref(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(plan)
    seed = prereg.load(master.OUT / "alpha3_19_sampling_seed_contract.json")
    require(seed["seed"] == master.sha(seed["seed_input"].encode()) and
            plan["sampling_seed"]["sha256"] == master.digest(master.OUT / "alpha3_19_sampling_seed_contract.json"),
            "FROZEN_SAMPLING_SEED_MISMATCH")
    seen_path = master.OUT / "alpha3_18_seen_source_registry.jsonl"
    seen = master.rows(seen_path)
    require(len(seen) == len({row["pmid"] for row in seen}) == 1041 and
            master.digest(seen_path) == plan["historical_contamination_registry"]["sha256"],
            "HISTORICAL_SOURCE_REGISTRY_MISMATCH")
    return {"manifest": plan, "queries": queries, "seed": seed["seed"],
            "seen_pmids": {row["pmid"] for row in seen},
            "seen_registry_sha256": master.digest(seen_path)}


def frozen_date_year(raw: bytes, expected_pmid: str) -> tuple[int | None, str]:
    """Only the publication window changes; keep the frozen stable-year parsing."""
    root = ET.fromstring(raw)
    matches = []
    for article in root.iter():
        if source_policy.local(article.tag) != "PubmedArticle":
            continue
        citations = primary._children(article, "MedlineCitation")
        if len(citations) == 1 and [source_policy.node_text(p)
                                     for p in primary._children(citations[0], "PMID")] == [expected_pmid]:
            matches.append(citations[0])
    if len(matches) != 1:
        return None, "UNRESOLVED"
    articles = primary._children(matches[0], "Article")
    if len(articles) != 1:
        return None, "UNRESOLVED"
    years: set[int] = set()
    for node in articles[0].iter():
        if source_policy.local(node.tag) not in {"PubDate", "ArticleDate"}:
            continue
        for part in node.iter():
            text = (part.text or "").strip()
            if source_policy.local(part.tag) == "Year" and re.fullmatch(r"[0-9]{4}", text):
                years.add(int(text))
            elif source_policy.local(part.tag) == "MedlineDate":
                years.update(int(y) for y in re.findall(r"\b(?:19|20)[0-9]{2}\b", text))
    if len(years) != 1:
        return None, "UNRESOLVED"
    year = next(iter(years))
    return year, "ELIGIBLE" if year in {2024, 2025} else "INELIGIBLE"


def bind_metadata(raw: bytes, expected_pmid: str) -> dict:
    identity = primary.bind_primary_citation(raw, expected_pmid)
    year, date_state = frozen_date_year(raw, expected_pmid)
    # The historical identity parser owns direct article IDs, but its old
    # 2018-2023 date check is deliberately superseded by this frozen cohort.
    identity_reasons = [r for r in identity["metadata_unresolved_reasons"]
                        if r != "PUBLICATION_DATE_YEAR_AMBIGUOUS_OR_OUT_OF_WINDOW"]
    require(identity["matched_medlinecitation_pmid"] == expected_pmid and
            identity["matching_pubmed_article_count"] == 1,
            "PRIMARY_CITATION_IDENTITY_REGRESSION")
    # The parser may preserve ReferenceList IDs for audit, never for identity.
    direct = identity["direct_primary_article_ids"]
    require(identity["pmcid"] is None or any(r["id_type"] == "pmc" and
            r["value"] == identity["pmcid"] for r in direct),
            "PRIMARY_CITATION_IDENTITY_REGRESSION")
    require(identity["doi"] is None or any(r["id_type"] == "doi" and
            r["value"] == identity["doi"] for r in direct),
            "PRIMARY_CITATION_IDENTITY_REGRESSION")
    identity["publication_year"] = year
    identity["date_state"] = date_state
    identity["metadata_unresolved_reasons"] = identity_reasons
    identity["metadata_state"] = "RESOLVED" if not identity_reasons else "UNRESOLVED"
    return identity


def publication_type_state(types: list[str], accepted: dict, excluded: dict) -> dict:
    found = set(types)
    if not found:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "PUBLICATION_TYPES_MISSING"}
    bad = sorted(found & set(excluded["exact_strings"]))
    if bad:
        return {"state": "SOURCE_TYPE_INELIGIBLE", "reason": "EXCLUDED_PUBLICATION_TYPE", "matched": bad}
    known = set(accepted["exact_strings"]) | set(accepted["neutral_exact_strings"]) | set(excluded["exact_strings"])
    unknown = sorted(found - known)
    if unknown:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "UNRECOGNIZED_PUBLICATION_TYPE", "matched": unknown}
    if not found & set(accepted["exact_strings"]):
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "POSITIVE_PUBLICATION_TYPE_ABSENT"}
    return {"state": "PRELIMINARY_TYPE_ACCEPTED", "reason": "POSITIVE_TYPE_NO_EXCLUSION"}


def canonical_jats(raw: bytes, pmcid: str) -> bytes:
    root = ET.fromstring(raw)
    articles = [node for node in root.iter() if source_policy.local(node.tag) == "article"]
    if len(articles) != 1:
        raise ValueError("JATS_ARTICLE_COUNT_INVALID")
    article = articles[0]
    fronts = primary._children(article, "front")
    metadata = [item for front in fronts for item in primary._children(front, "article-meta")]
    ids = [(node.get("pub-id-type", "").casefold(), source_policy.node_text(node))
           for meta in metadata for node in primary._children(meta, "article-id")]
    current_pmcids = {value if value.startswith("PMC") else "PMC" + value
                      for kind, value in ids if kind in {"pmc", "pmcid"}}
    if current_pmcids != {pmcid}:
        raise ValueError("JATS_CURRENT_ARTICLE_PMCID_MISMATCH")
    return ET.tostring(article, encoding="utf-8")


def run(state: dict, transport: historical_transport.Transport, counts: dict):
    queries = state["queries"]
    source_requests = [{"request_ordinal": i, "stratum_id": q["stratum_id"],
        "query_sha256": q["query_sha256"], "query_utf8": q["query_utf8"],
        "page_retstart": offset, "endpoint": prereg.ES,
        "parameters": {"db": "pubmed", "retmode": "json", "sort": "relevance",
                       "retmax": "50", "retstart": str(offset), "term": q["query_utf8"]}}
        for i, (q, offset) in enumerate(((q, offset) for q in queries
                                          for offset in (0, 50, 100, 150)), 1)]
    write_jsonl("source_query_request_manifest.jsonl", source_requests)
    frames: list[dict] = []
    page_results: list[dict] = []
    for query in queries:
        raw_order: list[str] = []
        pages: list[dict] = []
        for offset in (0, 50, 100, 150):
            parameters = {"db": "pubmed", "retmode": "json", "sort": "relevance",
                          "retmax": "50", "retstart": str(offset), "term": query["query_utf8"]}
            key = f"{query['ordinal']:02d}_{offset:03d}"
            raw, attempts = transport.get("SOURCE_FRAME", key, prereg.ES, parameters,
                                          "source_query_raw_responses")
            verdict = esearch.validate_response(attempts[-1]["status"] if raw is not None else None,
                                                raw or b"", offset, 50)
            page = {"request_ordinal": len(page_results) + 1,
                    "stratum_id": query["stratum_id"], "query_sha256": query["query_sha256"],
                    "retstart": offset, "attempts": attempts,
                    "raw_response_sha256": master.sha(raw) if raw is not None else None,
                    "validity": verdict, "querytranslation": verdict["querytranslation"]}
            page_results.append(page)
            if verdict["state"] not in esearch.VALID_STATES:
                write_jsonl("source_query_execution_results.jsonl", page_results)
                raise PhaseFailure("ALPHA3_19A_SOURCE_FRAME_FAILED_CLOSED:" + verdict["state"])
            ids = verdict["idlist"]
            count = verdict["count"]
            require(ids is not None and count is not None,
                    "ALPHA3_19A_SOURCE_FRAME_FAILED_CLOSED:VALIDITY_MISSING_DATA")
            raw_order.extend(ids)
            pages.append({"retstart": offset, "count": count, "pmids": ids,
                          "raw_response_sha256": master.sha(raw), "validity": verdict})
            if len(ids) < 50 or offset + len(ids) >= count:
                break
        ordered_unique = list(dict.fromkeys(raw_order))
        frame = {"stratum_id": query["stratum_id"], "query_sha256": query["query_sha256"],
                 "raw_pmid_order": raw_order, "ordered_unique_pmids": ordered_unique,
                 "page_records": pages, "terminal": "COMPLETE_VALID"}
        write_json(f"six_source_frame_manifests/{query['ordinal']:02d}_{query['stratum_id']}.json", frame)
        frames.append(frame)
        counts["source_frames_completed"] += 1
        counts["raw_source_records"] += len(raw_order)
        print(json.dumps({"stage": "source_frame", "completed": counts["source_frames_completed"],
                          "stratum": query["stratum_id"], "raw": len(raw_order)}, sort_keys=True), flush=True)
    write_jsonl("source_query_execution_results.jsonl", page_results)
    frame_files = sorted((OUT / "six_source_frame_manifests").glob("*.json"))
    require(len(frame_files) == 6, "SIX_FRAME_BARRIER_NOT_CROSSED")
    marker("six_source_frames_sha256", master.sha(master.canonical(
        [[p.name, master.digest(p)] for p in frame_files])))
    counts["six_source_frames_frozen"] = True

    membership: dict[str, list[str]] = {}
    for frame in frames:
        for pmid in frame["ordered_unique_pmids"]:
            membership.setdefault(pmid, []).append(frame["stratum_id"])
    universe = []
    for frame in frames:
        stratum = frame["stratum_id"]
        for pos, pmid in enumerate(frame["ordered_unique_pmids"]):
            if membership[pmid][0] == stratum:
                universe.append({"pmid": pmid, "owner_stratum": stratum,
                                 "owner_frame_position": pos,
                                 "all_strata": membership[pmid]})
    write_json("cross_stratum_duplicate_audit.json", {
        "raw_records": counts["raw_source_records"],
        "deduplicated_pmids": len(universe),
        "cross_stratum_duplicate_pmids": sum(len(s) > 1 for s in membership.values()),
        "earliest_stratum_ownership": True,
        "all_stratum_memberships_preserved_privately": True})
    write_jsonl("alpha3_19_sampling_universe.jsonl", universe)
    marker("alpha3_19_sampling_universe_sha256",
           master.digest(OUT / "alpha3_19_sampling_universe.jsonl"))
    counts["deduplicated_source_records"] = len(universe)
    sampled = []
    for stratum in [q["stratum_id"] for q in queries]:
        owned = [row for row in universe if row["owner_stratum"] == stratum]
        keyed = [(master.sha(f"{state['seed']}:{stratum}:{row['pmid']}".encode()), row)
                 for row in owned]
        selected = sorted(keyed, key=lambda x: (bytes.fromhex(x[0]), int(x[1]["pmid"])))[:12]
        sampled.extend({**row, "sample_key_sha256": key,
                        "sample_rank_in_stratum": rank}
                       for rank, (key, row) in enumerate(selected, 1))
    write_jsonl("deterministic_source_sampling_results.jsonl", sampled)
    counts["sampled_source_count"] = len(sampled)
    write_json("source_sampling_summary.json", {
        "sampled_source_count": len(sampled),
        "per_stratum": {q["stratum_id"]: sum(r["owner_stratum"] == q["stratum_id"]
                      for r in sampled) for q in queries},
        "seed": state["seed"], "universe_frozen_before_sampling": True,
        "historical_registry_not_prefiltered": True,
        "no_replacement_or_topup": True})
    contamination = [{"pmid": row["pmid"],
                      "state": "ALPHA3_18_SEEN_SOURCE_MATCH" if row["pmid"] in state["seen_pmids"]
                               else "NO_ALPHA3_18_SOURCE_MATCH",
                      "unexpected_temporal_overlap": row["pmid"] in state["seen_pmids"],
                      "registry_sha256": state["seen_registry_sha256"]}
                     for row in sampled]
    write_jsonl("historical_source_contamination_results.jsonl", contamination)
    seen_by_pmid = {r["pmid"]: r["state"] for r in contamination}
    counts["alpha3_18_seen_source_matches"] = sum(r["unexpected_temporal_overlap"]
                                                  for r in contamination)
    print(json.dumps({"stage": "sampling", "universe": len(universe), "sampled": len(sampled),
                      "historical_matches": counts["alpha3_18_seen_source_matches"]},
                     sort_keys=True), flush=True)

    metadata_manifest = [{"pmid": row["pmid"], "ordinal": i, "endpoint": prereg.EF,
                          "parameters": {"db": "pubmed", "retmode": "xml", "id": row["pmid"]}}
                         for i, row in enumerate(sampled, 1)]
    write_jsonl("sampled_source_metadata_manifest.jsonl", metadata_manifest)
    accepted = prereg.load(master.A1 / "publication_type_acceptance_set.json")
    excluded = prereg.load(master.A1 / "publication_type_exclusion_set.json")
    metadata_records = []
    identities = []
    dates = []
    types = []
    corrections = []
    pre_oa = []
    for row in metadata_manifest:
        pmid = row["pmid"]
        key = f"{row['ordinal']:03d}_{pmid}"
        raw, attempts = transport.get("SAMPLED_METADATA", key, prereg.EF,
                                      row["parameters"], "sampled_source_metadata_raw_responses")
        identity = None
        error = None
        if raw is not None:
            try:
                identity = bind_metadata(raw, pmid)
            except (ValueError, ET.ParseError, PhaseFailure) as exc:
                error = type(exc).__name__ + ":" + str(exc)
                if "PRIMARY_CITATION_IDENTITY_REGRESSION" in error:
                    raise PhaseFailure("PRIMARY_CITATION_IDENTITY_REGRESSION") from exc
        else:
            error = "TERMINAL_METADATA_TRANSPORT_FAILURE"
        meta_state = identity["metadata_state"] if identity else "UNRESOLVED"
        date_state = identity["date_state"] if identity else "UNRESOLVED"
        publication_year = identity["publication_year"] if identity else None
        type_result = publication_type_state(identity["publication_types"], accepted, excluded) if identity else (
            {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "METADATA_UNAVAILABLE"})
        correction_result = correction.classify(identity["publication_types"],
                                                 identity["correction_relationships"]) if identity else (
            {"state": "CORRECTION_REFERENCE_UNRESOLVED", "reason": "METADATA_UNAVAILABLE",
             "unresolved_reasons": ["METADATA_UNAVAILABLE"]})
        deferred = (correction_result["state"] == "CORRECTION_REFERENCE_UNRESOLVED" and
                    correction_result.get("unresolved_reasons") ==
                    ["REF_TYPE:UpdateOf:INDEPENDENT_SOURCE_NOT_YET_ELIGIBLE"])
        metadata_records.append({"pmid": pmid, "state": meta_state,
            "pmcid": identity["pmcid"] if identity else None,
            "doi": identity["doi"] if identity else None,
            "publication_year": publication_year,
            "publication_types": identity["publication_types"] if identity else [],
            "correction_relationships": identity["correction_relationships"] if identity else [],
            "raw_response_sha256": master.sha(raw) if raw is not None else None,
            "attempts": attempts, "error": error,
            "identity_unresolved_reasons": identity["metadata_unresolved_reasons"] if identity else []})
        identities.append({"pmid": pmid, "state": meta_state,
            "direct_article_ids": identity["direct_primary_article_ids"] if identity else [],
            "reference_article_ids_audit_only": identity["reference_article_ids"] if identity else [],
            "reference_ids_used_as_primary": False,
            "matching_current_citation_records": identity["matching_pubmed_article_count"] if identity else 0,
            "error": error})
        dates.append({"pmid": pmid, "publication_year": publication_year,
                      "state": date_state})
        types.append({"pmid": pmid, **type_result})
        corrections.append({"pmid": pmid, "result": correction_result,
                            "deferred_state": DEFERRED_UPDATEOF if deferred else None,
                            "final_admission_decided_in_19a": not deferred})
        if (seen_by_pmid[pmid] == "NO_ALPHA3_18_SOURCE_MATCH" and meta_state == "RESOLVED" and
            date_state == "ELIGIBLE" and type_result["state"] == "PRELIMINARY_TYPE_ACCEPTED" and
            (correction_result["state"] == "CORRECTION_REFERENCE_CLEAR" or deferred)):
            require(identity is not None and identity["pmcid"] is not None,
                    "PRE_OA_IDENTITY_STATE_INCONSISTENT")
            pre_oa.append({"pmid": pmid, "pmcid": identity["pmcid"], "doi": identity["doi"],
                           "sample_ordinal": row["ordinal"],
                           "raw_metadata_sha256": master.sha(raw),
                           "correction_reference_preliminary_state": correction_result["state"],
                           "updateof_deferred_to_19b": deferred})
        counts["sampled_metadata_records"] += 1
        if row["ordinal"] % 12 == 0:
            print(json.dumps({"stage": "metadata", "completed": row["ordinal"],
                              "total": len(sampled)}, sort_keys=True), flush=True)
    write_jsonl("sampled_source_metadata_records.jsonl", metadata_records)
    write_jsonl("primary_identity_validation.jsonl", identities)
    write_jsonl("publication_date_results.jsonl", dates)
    write_jsonl("publication_type_results.jsonl", types)
    write_jsonl("correction_reference_results.jsonl", corrections)
    counts["metadata_date_ineligible"] = sum(r["state"] == "INELIGIBLE" for r in dates)
    counts["metadata_date_unresolved"] = sum(r["state"] == "UNRESOLVED" for r in dates)
    counts["publication_type_ineligible"] = sum(r["state"] == "SOURCE_TYPE_INELIGIBLE" for r in types)
    counts["publication_type_unresolved"] = sum(r["state"] == "SOURCE_TYPE_UNRESOLVED" for r in types)
    counts["correction_reference_clear"] = sum(r["result"]["state"] == "CORRECTION_REFERENCE_CLEAR"
                                               for r in corrections)
    counts["correction_reference_ineligible"] = sum(r["result"]["state"] == "CORRECTION_REFERENCE_INELIGIBLE"
                                                    for r in corrections)
    counts["correction_reference_unresolved"] = sum(r["result"]["state"] == "CORRECTION_REFERENCE_UNRESOLVED"
                                                    for r in corrections)
    counts["updateof_deferred_to_19b"] = sum(r["deferred_state"] == DEFERRED_UPDATEOF
                                              for r in corrections)
    write_json("metadata_completion_barrier.json", {
        "crossed": len(metadata_records) == len(sampled) == len(identities) == len(dates) == len(types) == len(corrections),
        "sampled_source_count": len(sampled),
        "defined_updateof_deferred_states_handled": True,
        "oa_requests_before_freeze": 0})
    require(prereg.load(OUT / "metadata_completion_barrier.json")["crossed"],
            "METADATA_COMPLETION_BARRIER_FAILED")
    write_jsonl("alpha3_19_post_metadata_pre_oa_source_manifest.jsonl", pre_oa)
    marker("alpha3_19_post_metadata_pre_oa_source_manifest_sha256",
           master.digest(OUT / "alpha3_19_post_metadata_pre_oa_source_manifest.jsonl"))
    counts["post_metadata_pre_oa_source_count"] = len(pre_oa)
    metadata_by_pmid = {r["pmid"]: r for r in metadata_records}
    sample_by_pmid = {r["pmid"]: r for r in sampled}
    date_by_pmid = {r["pmid"]: r for r in dates}
    type_by_pmid = {r["pmid"]: r for r in types}
    correction_by_pmid = {r["pmid"]: r for r in corrections}
    print(json.dumps({"stage": "pre_oa_freeze", "sources": len(pre_oa)}, sort_keys=True), flush=True)

    oa_requests = [{"ordinal": i, "pmid": row["pmid"], "pmcid": row["pmcid"],
        "endpoint": prereg.ES, "parameters": {"db": "pmc", "retmode": "json",
        "retmax": "1", "term": source_policy.oa_subset_esearch_term(row["pmcid"])}}
        for i, row in enumerate(pre_oa, 1)]
    write_jsonl("oa_subset_request_manifest.jsonl", oa_requests)
    oa_results = []
    jats_eligible = []
    for row in oa_requests:
        key = f"{row['ordinal']:03d}_{row['pmid']}"
        raw, attempts = transport.get("PMC_OA_SUBSET", key, prereg.ES, row["parameters"],
                                      "oa_subset_raw_responses")
        verdict = esearch.validate_response(attempts[-1]["status"] if raw is not None else None,
                                            raw or b"", 0, 1)
        subset = historical_transport.parse_subset(raw, row["pmcid"]) if (
            raw is not None and verdict["state"] in esearch.VALID_STATES) else None
        state_name = ("OA_SUBSET_ELIGIBLE" if subset is True else
                      "OA_SUBSET_INELIGIBLE" if subset is False else "OA_SUBSET_UNRESOLVED")
        oa_results.append({"pmid": row["pmid"], "pmcid": row["pmcid"],
                           "state": state_name, "validity": verdict,
                           "raw_response_sha256": master.sha(raw) if raw is not None else None,
                           "attempts": attempts})
        if subset is True:
            jats_eligible.append(row)
    write_jsonl("oa_subset_results.jsonl", oa_results)
    counts["oa_subset_eligible"] = sum(r["state"] == "OA_SUBSET_ELIGIBLE" for r in oa_results)
    counts["oa_subset_ineligible"] = sum(r["state"] == "OA_SUBSET_INELIGIBLE" for r in oa_results)
    counts["oa_subset_unresolved"] = sum(r["state"] == "OA_SUBSET_UNRESOLVED" for r in oa_results)
    print(json.dumps({"stage": "oa_subset", "eligible": counts["oa_subset_eligible"],
                      "ineligible": counts["oa_subset_ineligible"],
                      "unresolved": counts["oa_subset_unresolved"]}, sort_keys=True), flush=True)

    jats_manifest = [{"ordinal": i, "pmid": row["pmid"], "pmcid": row["pmcid"],
        "endpoint": prereg.EF,
        "parameters": {"db": "pmc", "retmode": "xml", "id": row["pmcid"][3:]}}
        for i, row in enumerate(jats_eligible, 1)]
    write_jsonl("pmc_jats_request_manifest.jsonl", jats_manifest)
    pre_oa_by_pmid = {r["pmid"]: r for r in pre_oa}
    jats_results = []
    jats_failures = []
    handoff = []
    for row in jats_manifest:
        key = f"{row['ordinal']:03d}_{row['pmid']}"
        raw, attempts = transport.get("PMC_JATS", key, prereg.EF, row["parameters"],
                                      "pmc_jats_raw_responses")
        counts["pmc_jats_requested"] += 1
        canonical = None
        error = None
        if raw is not None:
            try:
                canonical = canonical_jats(raw, row["pmcid"])
            except (ET.ParseError, ValueError) as exc:
                error = type(exc).__name__ + ":" + str(exc)
        else:
            error = "TERMINAL_JATS_TRANSPORT_FAILURE"
        if canonical is None:
            counts["pmc_jats_failed"] += 1
            jats_failures.append({"pmid": row["pmid"], "pmcid": row["pmcid"],
                "reason": error, "attempts": attempts,
                "raw_response_sha256": master.sha(raw) if raw is not None else None})
        else:
            canonical_path = f"pmc_jats_canonical/{key}.xml"
            write_bytes(canonical_path, canonical)
            token = "src_" + secrets.token_hex(32)
            source = pre_oa_by_pmid[row["pmid"]]
            metadata = metadata_by_pmid[row["pmid"]]
            sample = sample_by_pmid[row["pmid"]]
            handoff.append({"source_token": token, "pmid": row["pmid"],
                "pmcid": row["pmcid"], "doi": source["doi"],
                "sample_ordinal": source["sample_ordinal"],
                "owner_stratum": sample["owner_stratum"],
                "all_strata": sample["all_strata"],
                "seen_source_state": seen_by_pmid[row["pmid"]],
                "publication_year": date_by_pmid[row["pmid"]]["publication_year"],
                "publication_date_state": date_by_pmid[row["pmid"]]["state"],
                "publication_type_state": type_by_pmid[row["pmid"]]["state"],
                "publication_types": metadata["publication_types"],
                "correction_relationships": metadata["correction_relationships"],
                "raw_metadata_sha256": source["raw_metadata_sha256"],
                "raw_metadata_path": metadata["attempts"][-1]["raw_path"],
                "correction_reference_preliminary_state": source["correction_reference_preliminary_state"],
                "correction_reference_preliminary_result": correction_by_pmid[row["pmid"]]["result"],
                "updateof_deferred_to_19b": source["updateof_deferred_to_19b"],
                "oa_subset_state": "OA_SUBSET_ELIGIBLE",
                "raw_jats_path": attempts[-1]["raw_path"],
                "raw_jats_sha256": master.sha(raw),
                "canonical_jats_path": canonical_path,
                "canonical_jats_sha256": master.sha(canonical),
                "transport_attempts": attempts,
                "license_state": "NOT_EVALUATED_IN_19A",
                "structural_source_type_state": "NOT_EVALUATED_IN_19A"})
            counts["pmc_jats_success"] += 1
        jats_results.append({"pmid": row["pmid"], "pmcid": row["pmcid"],
            "success": canonical is not None, "error": error,
            "raw_response_sha256": master.sha(raw) if raw is not None else None,
            "canonical_jats_sha256": master.sha(canonical) if canonical is not None else None,
            "attempts": attempts})
        if row["ordinal"] % 10 == 0:
            print(json.dumps({"stage": "pmc_jats", "completed": row["ordinal"],
                              "total": len(jats_manifest)}, sort_keys=True), flush=True)
    write_jsonl("pmc_jats_acquisition_results.jsonl", jats_results)
    write_jsonl("pmc_jats_failure_records.jsonl", jats_failures)
    write_jsonl("alpha3_19a_jats_handoff_manifest.jsonl", handoff)
    marker("alpha3_19a_jats_handoff_manifest_sha256",
           master.digest(OUT / "alpha3_19a_jats_handoff_manifest.jsonl"))
    counts["jats_handoff_source_count"] = len(handoff)
    counts["jats_handoff_manifest_frozen"] = True
    require(counts["pmc_jats_requested"] == counts["pmc_jats_success"] + counts["pmc_jats_failed"] and
            len(handoff) == counts["pmc_jats_success"] and
            all(master.digest(OUT / row["raw_jats_path"]) == row["raw_jats_sha256"] and
                master.digest(OUT / row["canonical_jats_path"]) == row["canonical_jats_sha256"]
                for row in handoff),
            "JATS_HANDOFF_COMPLETENESS_FAILURE")


def finalize(status: str, failure_code: str | None, counts: dict,
             transport: historical_transport.Transport | None):
    if transport is not None:
        write_jsonl("ncbi_transport_attempts.jsonl", transport.log)
    attempts = transport.log if transport is not None else []
    endpoints = {record["endpoint"] for record in attempts}
    ncbi_only = endpoints <= {prereg.ES, prereg.EF} and all(
        urllib.parse.urlsplit(endpoint).hostname == "eutils.ncbi.nlm.nih.gov" for endpoint in endpoints)
    write_json("network_scope_audit.json", {"network_scope_ncbi_only": ncbi_only,
        "allowed_endpoints": [prereg.ES, prereg.EF],
        "observed_endpoints": sorted(endpoints),
        "ncbi_network_attempts": transport.calls if transport is not None else 0,
        "non_ncbi_network_calls": 0})
    completed = status == "completed"
    write_json("scientific_content_nonuse_audit.json", {
        "titles_abstracts_fulltext_used_for_sampling_or_preference": False,
        "structural_metadata_gates_only": True,
        "source_topup_or_replacement": False,
        "license_interpretation_executed": False,
        "source_type_execution_executed": False})
    write_json("search_plan_firewall_audit.json", {
        "search_plan_queries_or_results_used": False,
        "development_labels_used": False,
        "known_paper_information_used": False,
        "P0_P1_P2_outcomes_used": False})
    write_json("protocol_compliance_audit.json", {
        "alpha3_19a_execution_manifest_verified": True,
        "source_query_changes": 0,
        "sampling_seed_matches_master": True,
        "historical_contamination_gate_after_sampling":
            (OUT / "deterministic_source_sampling_results.jsonl").exists() and
            (OUT / "historical_source_contamination_results.jsonl").exists(),
        "six_source_frames_frozen": counts["six_source_frames_frozen"],
        "metadata_completion_barrier_crossed": (OUT / "metadata_completion_barrier.json").exists(),
        "defined_updateof_deferred_states_handled":
            (OUT / "correction_reference_results.jsonl").exists(),
        "jats_handoff_manifest_frozen": counts["jats_handoff_manifest_frozen"],
        "network_scope_ncbi_only": ncbi_only,
        "license_or_source_type_or_builder_executed": False,
        "failure_code": failure_code})
    safety = {"deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
              "non_ncbi_network_calls": 0,
              "license_interpretation_executed": False,
              "source_type_execution_executed": False,
              "construction_document_generation_executed": False,
              "builder_requests_generated": False,
              "actual_builder_scientific_call_count": None,
              "historical_assets_modified": False}
    write_json("scientific_state_safety_audit.json", safety)
    summary = {"status": status, "failure_code": failure_code,
        "alpha3_19a_execution_manifest_verified": True,
        "source_query_count": 6, "source_query_changes": 0,
        "network_scope_ncbi_only": ncbi_only,
        "sampling_after_all_frames": counts["six_source_frames_frozen"] if counts["sampled_source_count"] is not None else False,
        "sampling_seed_matches_master": True,
        "dynamic_source_replacement_used": False,
        "historical_contamination_gate_after_sampling":
            (OUT / "historical_source_contamination_results.jsonl").exists(),
        "primary_citation_identity_v1_used": (OUT / "primary_identity_validation.jsonl").exists(),
        "reference_article_ids_excluded": True,
        "metadata_completion_barrier_crossed": (OUT / "metadata_completion_barrier.json").exists(),
        "defined_updateof_deferred_states_handled":
            (OUT / "correction_reference_results.jsonl").exists(),
        "pmc_oa_subset_verification_used": (OUT / "oa_subset_results.jsonl").exists(),
        "builder_call_budget_known": False,
        "next_stage_recommendation": NEXT_PASS if completed else NEXT_FAIL,
        **counts, **safety}
    write_json("validation.json", {"status": status, "failure_code": failure_code,
        "required_completion_artifacts_present": completed and all((OUT / name).exists() for name in (
            "six_source_frames_sha256", "alpha3_19_sampling_universe_sha256",
            "alpha3_19_post_metadata_pre_oa_source_manifest_sha256",
            "alpha3_19a_jats_handoff_manifest_sha256")),
        "network_scope_ncbi_only": ncbi_only,
        "historical_assets_modified": False})
    write_json("summary.json", summary)
    marker(ROOT_MARKER, root_hash())
    print(json.dumps({"status": status, "failure_code": failure_code,
                      "root_sha256": (OUT / ROOT_MARKER).read_text().strip(),
                      **counts}, sort_keys=True), flush=True)


def main():
    state = preflight()  # absolutely no network or run-directory creation before this gate
    OUT.mkdir()
    write_json("authoritative_manifest_verification.json", {
        "master_root_sha256": prereg.MASTER_SHA,
        "prereg_root_sha256": EXPECTED_PREREG,
        "source_query_set_sha256": EXPECTED_QUERY_SET,
        "execution_manifest_sha256": EXPECTED_MANIFEST,
        "sampling_seed_contract_sha256": state["manifest"]["sampling_seed"]["sha256"],
        "historical_registry_sha256": state["seen_registry_sha256"],
        "all_manifest_references_verified_before_network": True})
    policy = prereg.load(master.A4 / "alpha3_18a4_source_acquisition_execution_manifest_v2.json")[
        "active_source_frame_policy_v2"]
    transport = historical_transport.Transport(OUT, policy)
    counts = {"source_frames_completed": 0, "six_source_frames_frozen": False,
        "raw_source_records": 0, "deduplicated_source_records": None,
        "sampled_source_count": None, "alpha3_18_seen_source_matches": None,
        "sampled_metadata_records": 0, "metadata_date_ineligible": None,
        "metadata_date_unresolved": None, "publication_type_ineligible": None,
        "publication_type_unresolved": None, "correction_reference_clear": None,
        "correction_reference_ineligible": None, "correction_reference_unresolved": None,
        "updateof_deferred_to_19b": None, "post_metadata_pre_oa_source_count": None,
        "oa_subset_eligible": None, "oa_subset_ineligible": None,
        "oa_subset_unresolved": None, "pmc_jats_requested": 0,
        "pmc_jats_success": 0, "pmc_jats_failed": 0,
        "jats_handoff_source_count": None, "jats_handoff_manifest_frozen": False}
    try:
        run(state, transport, counts)
    except Exception as exc:
        finalize("failed", type(exc).__name__ + ":" + str(exc), counts, transport)
        return
    finalize("completed", None, counts, transport)


if __name__ == "__main__":
    main()
