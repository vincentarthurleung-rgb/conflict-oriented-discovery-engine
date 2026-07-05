"""UI-ready, case-aware display projection over the complete clean KG."""
from __future__ import annotations
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GENERIC = {"cancer", "cell", "cells", "tumor", "tumour", "expression", "level", "levels", "activity", "effect", "effects", "role", "roles", "protein", "gene", "patient", "patients", "disease", "process", "pathway", "response", "mechanism", "treatment", "therapy"}
ARTIFACT_TERMS = ("lincs", "reactome", "enrichr", "pubmed", "pmid", "pmcid", "case_bundle", "fulltext_l1", "review_queue")

def display_label(label: str) -> tuple[str, list[str], str, str]:
    value = str(label).strip().translate(str.maketrans({"α": "alpha", "β": "beta", "γ": "gamma", "κ": "kappa", "–": "-", "—": "-"}))
    reasons = []
    if value != str(label).strip(): reasons.append("greek_or_unicode_normalization")
    cleaned = re.sub(r"\s*\(\d+\)\s*$", "", value)
    if cleaned != value: reasons.append("numeric_parenthetical_suffix")
    cleaned = " ".join(cleaned.split())
    return cleaned, reasons, "|".join(reasons) or "none", "low"

def _genericity(label: str) -> tuple[float, list[str]]:
    normalized = " ".join(label.casefold().split())
    if normalized in GENERIC: return 1.0, ["exact_generic_term"]
    tokens = normalized.split()
    fraction = sum(x in GENERIC for x in tokens) / len(tokens) if tokens else 1.0
    return (round(min(.65, fraction * .45), 4), ["contains_generic_term"] if fraction else [])

def _ui_group(entity_type: str) -> str:
    if entity_type in {"gene", "protein"}: return "gene_protein"
    if entity_type in {"compound", "drug", "treatment"}: return "compound"
    if entity_type == "biological_process": return "process"
    if entity_type in {"cell_type", "tissue", "condition", "organism"}: return "context"
    return entity_type if entity_type in {"disease", "phenotype"} else "unknown"

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")

def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()} for row in rows)

def prepare_display_kg(output: Path, entities: list[dict], triples: list[dict], chains: list[dict], links: list[dict], validators: list[dict], conflicts: list[dict], *, max_entities: int = 500, max_triples: int = 500, max_chains: int = 1500, max_triples_per_case: int = 150, max_chains_per_case: int = 300) -> dict[str, Any]:
    labels, label_by_original, label_report, entity_v2 = {}, {}, [], []
    for entity in entities:
        shown, reasons, reason, risk = display_label(entity["label"]); labels[entity["entity_id"]] = shown; label_by_original[entity["label"]] = shown
        aliases = sorted(set(entity.get("aliases", [])) | {entity["label"], shown})
        if reasons: label_report.append({"entity_id": entity["entity_id"], "original_label": entity["label"], "canonical_label": entity["canonical_label"], "display_label": shown, "aliases": aliases, "normalization_reason": reason, "risk_level": risk})
        genericity, downrank = _genericity(shown); unknown_penalty = .45 if entity["entity_type"] == "unknown_biomedical_entity" else 0
        priority = max(0.0, min(1.0, .45 * min(1, math.log2(entity.get("evidence_count", 0) + 1) / 5) + .3 * min(1, math.log2(entity.get("degree", 0) + 1) / 5) + .25 * int(entity["entity_type"] != "unknown_biomedical_entity") - .55 * genericity - unknown_penalty))
        badges = (["fulltext_supported"] if entity.get("fulltext_evidence_count", 0) else []) + (["results_supported"] if entity.get("results_section_evidence_count", 0) else []) + (["multi_case"] if len(entity.get("source_case_ids", [])) > 1 else [])
        entity_v2.append({"entity_id": entity["entity_id"], "label": entity["label"], "display_label": shown, "canonical_label": entity["canonical_label"], "aliases": aliases, "entity_type": entity["entity_type"], "degree": entity["degree"], "in_degree": entity["in_degree"], "out_degree": entity["out_degree"], "evidence_count": entity["evidence_count"], "fulltext_evidence_count": entity["fulltext_evidence_count"], "results_section_evidence_count": entity["results_section_evidence_count"], "source_case_ids": entity["source_case_ids"], "genericity_score": genericity, "display_downrank_reason": downrank + (["unknown_type"] if unknown_penalty else []), "display_priority_score": round(priority, 4), "display_recommended": priority >= .15 and genericity < 1, "ui_group": _ui_group(entity["entity_type"]), "ui_badges": badges})
    entity_v2.sort(key=lambda x: (-x["display_priority_score"], -x["degree"], x["display_label"])); entity_before = sum(x["display_recommended"] for x in entity_v2)
    selected_entities = [x for x in entity_v2 if x["display_recommended"]][:max_entities]; selected_ids = {x["entity_id"] for x in selected_entities}
    conflict_ids = {tid for x in conflicts for tid in x.get("linked_triple_ids", [])}; validator_cases = {x["case_id"] for x in validators}
    triple_v2 = []
    for triple in triples:
        sg, sr = _genericity(labels[triple["subject_id"]]); og, or_ = _genericity(labels[triple["object_id"]]); score = max(0.0, min(1.0, triple["display_priority_score"] - .35 * sg - .35 * og))
        reasons = (["generic_subject"] if sg else []) + (["generic_object"] if og else []) + (["entity_outside_display_limit"] if triple["subject_id"] not in selected_ids or triple["object_id"] not in selected_ids else [])
        recommended = score >= .35 and sg < 1 and og < 1 and triple["subject_id"] in selected_ids and triple["object_id"] in selected_ids
        badges = (["fulltext_supported"] if triple["fulltext_evidence_count"] else []) + (["results_supported"] if triple["results_section_evidence_count"] else []) + (["multi_case"] if len(triple["case_ids"]) > 1 else []) + (["has_conflict_lens_record"] if triple["triple_id"] in conflict_ids else []) + (["validator_annotation_available"] if any(c in validator_cases for c in triple["case_ids"]) else [])
        triple_v2.append({"triple_id": triple["triple_id"], "subject_id": triple["subject_id"], "subject_display_label": labels[triple["subject_id"]], "relation_normalized": triple["relation_normalized"], "object_id": triple["object_id"], "object_display_label": labels[triple["object_id"]], "direction": triple["direction"], "evidence_count": triple["evidence_count"], "fulltext_evidence_count": triple["fulltext_evidence_count"], "results_section_evidence_count": triple["results_section_evidence_count"], "case_ids": triple["case_ids"], "conflict_status": triple["conflict_status"], "generic_subject_penalty": sg, "generic_object_penalty": og, "display_priority_score_v2": round(score, 4), "display_recommended_v2": recommended, "display_filter_reason": reasons, "ui_edge_label": triple["relation_normalized"], "ui_edge_weight": round(1 + math.log2(triple["evidence_count"] + 1), 4), "ui_badges": badges})
    triple_v2.sort(key=lambda x: (-x["display_priority_score_v2"], -x["evidence_count"], x["triple_id"])); triple_before = sum(x["display_recommended_v2"] for x in triple_v2); selected_triples = [x for x in triple_v2 if x["display_recommended_v2"]][:max_triples]; selected_tids = {x["triple_id"] for x in selected_triples}
    chain_v2 = []
    for chain in chains:
        available = all(x in selected_tids for x in chain["triple_ids"]); score = chain["chain_quality_score"]
        chain_v2.append({**chain, "entity_path": [label_by_original.get(x, display_label(x)[0]) for x in chain["entity_path"]], "display_recommended_v2": available and score >= .4, "display_filter_reason": [] if available else ["contains_non_display_triple"]})
    chain_v2.sort(key=lambda x: (-x["chain_quality_score"], x["chain_id"])); chain_before = sum(x["display_recommended_v2"] for x in chain_v2); selected_chains = [x for x in chain_v2 if x["display_recommended_v2"]][:max_chains]
    case_triples = _case_triples(selected_triples, links, max_triples_per_case); case_chains = _case_chains(selected_chains, case_triples, max_chains_per_case)
    unknown_review = _unknown_review(entity_v2, triple_v2, 100)
    downrank = [{"entity_id": x["entity_id"], "display_label": x["display_label"], "genericity_score": x["genericity_score"], "display_downrank_reason": x["display_downrank_reason"], "display_priority_score": x["display_priority_score"]} for x in entity_v2 if x["genericity_score"] > 0]
    for name, rows in (("display_entities_v2", selected_entities), ("display_triples_v2", selected_triples), ("display_chains_v2", selected_chains)):
        _write_jsonl(output / f"{name}.jsonl", rows); _write_csv(output / f"{name}.csv", rows)
    _write_jsonl(output / "case_focused_triples.jsonl", case_triples); _write_jsonl(output / "case_focused_chains.jsonl", case_chains)
    _write_csv(output / "top_unknown_display_entities.csv", unknown_review); _write_csv(output / "generic_entity_downranking_report.csv", downrank); _write_csv(output / "display_label_normalization_report.csv", label_report)
    contamination = sum(any(term in x["label"].casefold() for term in ARTIFACT_TERMS) for x in entities)
    summary = {"entities_total": len(entities), "unknown_entity_count": sum(x["entity_type"] == "unknown_biomedical_entity" for x in entities), "unknown_entity_fraction": round(sum(x["entity_type"] == "unknown_biomedical_entity" for x in entities) / len(entities), 6) if entities else 0, "display_entities_v1_count": sum(x.get("display_recommended", False) for x in entity_v2), "display_entities_before_limit": entity_before, "display_entities_after_limit": len(selected_entities), "display_entities_v2_count": len(selected_entities), "display_unknown_entity_count": sum(x["entity_type"] == "unknown_biomedical_entity" for x in selected_entities), "display_unknown_entity_fraction": round(sum(x["entity_type"] == "unknown_biomedical_entity" for x in selected_entities) / len(selected_entities), 6) if selected_entities else 0, "triples_total": len(triples), "display_triples_v1_count": sum(x.get("display_priority_score", 0) >= .35 for x in triples), "display_triples_before_limit": triple_before, "display_triples_after_limit": len(selected_triples), "display_triples_v2_count": len(selected_triples), "chains_total": len(chains), "display_chains_v1_count": sum(x.get("display_recommended", False) for x in chains), "display_chains_before_limit": chain_before, "display_chains_after_limit": len(selected_chains), "display_chains_v2_count": len(selected_chains), "truncated_by_display_limit": entity_before > len(selected_entities) or triple_before > len(selected_triples) or chain_before > len(selected_chains), "validator_artifact_terms_found_in_main_graph": contamination, "top_display_entities_v2": selected_entities[:20], "top_display_triples_v2": selected_triples[:20], "top_case_focused_triples": case_triples[:20], "top_case_focused_chains": case_chains[:20], "top_unknown_display_entities": unknown_review[:20], "generic_entities_downranked_count": len(downrank), "display_labels_normalized_count": len(label_report), "warnings": ["Display scores are navigation heuristics, not scientific confidence."]}
    (output / "kg_display_quality_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "kg_display_quality_summary.md").write_text(f"# KG Display Quality Summary\n\n- Display entities: {len(selected_entities)}\n- Display triples: {len(selected_triples)}\n- Display chains: {len(selected_chains)}\n- Display unknown fraction: {summary['display_unknown_entity_fraction']:.1%}\n- Normalized labels: {len(label_report)}\n\nDisplay scores are navigation heuristics, not scientific confidence.\n", encoding="utf-8")
    return summary

def _case_triples(triples: list[dict], links: list[dict], limit: int) -> list[dict]:
    stats = defaultdict(lambda: Counter())
    for link in links:
        key = (link["case_id"], link["triple_id"]); stats[key]["evidence"] += 1; stats[key]["fulltext"] += int("full" in str(link.get("source_scope", ""))); stats[key]["results"] += int("result" in str(link.get("section_title", "")).casefold()); stats[key]["seed_max"] = max(stats[key]["seed_max"], link.get("seed_neighborhood_score") or 0, link.get("review_priority_score") or 0)
    by_id = {x["triple_id"]: x for x in triples}; grouped = defaultdict(list)
    for (case, tid), values in stats.items():
        if tid not in by_id: continue
        triple = by_id[tid]; score = min(1.0, .1 * math.log2(values["evidence"] + 1) + .06 * math.log2(values["fulltext"] + 1) + .05 * math.log2(values["results"] + 1) + .3 * values["seed_max"] + .25 * triple["display_priority_score_v2"])
        grouped[case].append({"case_id": case, "triple_id": tid, "subject_label": triple["subject_display_label"], "relation_normalized": triple["relation_normalized"], "object_label": triple["object_display_label"], "case_evidence_count": values["evidence"], "case_fulltext_evidence_count": values["fulltext"], "case_results_section_evidence_count": values["results"], "case_seed_relevance_proxy": round(values["seed_max"], 4), "case_display_priority_score": round(score, 4), "case_display_rank": 0, "display_recommended": score >= .35})
    output = []
    for case in sorted(grouped):
        rows = sorted(grouped[case], key=lambda x: (-x["case_display_priority_score"], x["triple_id"]))[:limit]
        for rank, row in enumerate(rows, 1): row["case_display_rank"] = rank
        output.extend(rows)
    return output

def _case_chains(chains: list[dict], case_triples: list[dict], limit: int) -> list[dict]:
    scores = {(x["case_id"], x["triple_id"]): x for x in case_triples}; cases = sorted({x[0] for x in scores}); output = []
    for case in cases:
        rows = []
        for chain in chains:
            matched = [scores[(case, tid)] for tid in chain["triple_ids"] if (case, tid) in scores]
            if len(matched) != len(chain["triple_ids"]): continue
            quality = sum(x["case_display_priority_score"] for x in matched) / len(matched)
            rows.append({"case_id": case, "chain_id": chain["chain_id"], "entity_path": chain["entity_path"], "relation_path": chain["relation_path"], "triple_ids": chain["triple_ids"], "case_evidence_count_sum": sum(x["case_evidence_count"] for x in matched), "case_fulltext_evidence_count_sum": sum(x["case_fulltext_evidence_count"] for x in matched), "case_chain_quality_score": round(quality, 4), "case_display_rank": 0, "display_recommended": quality >= .4})
        rows.sort(key=lambda x: (-x["case_chain_quality_score"], x["chain_id"])); rows = rows[:limit]
        for rank, row in enumerate(rows, 1): row["case_display_rank"] = rank
        output.extend(rows)
    return output

def _unknown_review(entities: list[dict], triples: list[dict], limit: int) -> list[dict]:
    adjacent = defaultdict(list)
    for triple in triples: adjacent[triple["subject_id"]].append(triple); adjacent[triple["object_id"]].append(triple)
    rows = []
    for entity in entities:
        if entity["entity_type"] != "unknown_biomedical_entity" or not (entity["display_recommended"] or entity["degree"] >= 5): continue
        edges = sorted(adjacent[entity["entity_id"]], key=lambda x: -x["display_priority_score_v2"]); neighbors = [x["object_display_label"] if x["subject_id"] == entity["entity_id"] else x["subject_display_label"] for x in edges[:5]]
        token = re.sub(r"[^A-Za-z0-9]", "", entity["label"]); action, suggested, reason = "review_type", "unknown_biomedical_entity", "high-degree/display unknown"
        if token.isupper() and 2 <= len(token) <= 10: action, suggested, reason = "possible_gene_or_protein", "gene_or_protein", "short uppercase abbreviation; manual review required"
        rows.append({**{k: entity[k] for k in ("entity_id", "label", "canonical_label", "display_label", "degree", "in_degree", "out_degree", "evidence_count", "fulltext_evidence_count", "results_section_evidence_count", "source_case_ids")}, "top_neighbor_entities": neighbors, "top_relations": [x["relation_normalized"] for x in edges[:5]], "example_triples": [x["triple_id"] for x in edges[:5]], "suggested_type": suggested, "suggested_action": action, "reason": reason})
    return sorted(rows, key=lambda x: (-x["degree"], -x["evidence_count"], x["display_label"]))[:limit]
