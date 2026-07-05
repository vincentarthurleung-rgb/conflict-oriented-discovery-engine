"""Offline quality audit for System B clean KG artifacts."""
from __future__ import annotations
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .clean_kg import canonicalize_entity

CONTAMINATION_TERMS = ("lincs", "reactome", "enrichr", "pubmed", "pmid", "pmcid", "case_bundle", "fulltext_l1", "review_queue")

def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file(): return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try: value = json.loads(line)
        except json.JSONDecodeError: continue
        if isinstance(value, dict): rows.append(value)
    return rows

def _csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in x.items()} for x in rows)

def _normalization_candidates(entities: list[dict]) -> list[dict]:
    result, seen = [], set()
    def add(a, la, b, lb, reason, action):
        key = (a, la, b, lb, reason)
        if key not in seen: seen.add(key); result.append({"entity_id_a": a, "label_a": la, "entity_id_b": b, "label_b": lb, "reason": reason, "recommended_action": action})
    for entity in entities:
        aliases = entity.get("aliases") or [entity["label"]]
        for alias in aliases:
            if alias == entity["label"]: continue
            if re.search(r"\(\d+\)\s*$", alias): reason = "parenthetical_suffix"
            elif any(x in alias for x in "αβκ"): reason = "greek_symbol_variant"
            elif alias.casefold() == entity["label"].casefold(): reason = "case_only_difference"
            else: reason = "punctuation_difference"
            add(entity["entity_id"], entity["label"], entity["entity_id"], alias, reason, "already_safely_merged_as_alias")
    buckets = defaultdict(list)
    for entity in entities: buckets[re.sub(r"[\s-]+", "", canonicalize_entity(entity["label"]))].append(entity)
    for group in buckets.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                reason = "hyphen_difference" if "-" in a["label"] + b["label"] else "spacing_difference"
                add(a["entity_id"], a["label"], b["entity_id"], b["label"], reason, "manual_review")
    return result

def audit_clean_kg(clean_kg_root: str | Path, output_root: str | Path, *, top_n: int = 50, write_csv: bool = True, write_json: bool = True, overwrite: bool = False) -> dict:
    root, output = Path(clean_kg_root), Path(output_root)
    if output.exists() and any(output.iterdir()) and not overwrite: raise FileExistsError(f"output root is not empty: {output}; pass --overwrite")
    output.mkdir(parents=True, exist_ok=True); warnings = []
    entities = _jsonl(root / "clean_entities.jsonl"); triples = _jsonl(root / "clean_triples.jsonl"); links = _jsonl(root / "triple_evidence_links.jsonl"); chains = _jsonl(root / "chain_index.jsonl")
    display_entities = _jsonl(root / "clean_entities_display.jsonl"); display_triples = _jsonl(root / "clean_triples_display.jsonl")
    for name, rows in (("clean_entities.jsonl", entities), ("clean_triples.jsonl", triples), ("triple_evidence_links.jsonl", links)):
        if not (root / name).is_file(): warnings.append(f"missing optional/input file: {name}")
    unknown = [x for x in entities if x.get("entity_type") == "unknown_biomedical_entity"]
    contamination = [x for x in entities if any(term in str(x.get("label", "")).casefold() for term in CONTAMINATION_TERMS)]
    suffix = [x for x in entities if re.search(r"\(\d+\)\s*$", str(x.get("label", "")))]
    single = [x for x in entities if len(str(x.get("label", "")).strip()) == 1]
    symbolic = [x for x in entities if re.fullmatch(r"[\W\d_]+", str(x.get("label", "")))]
    candidates = _normalization_candidates(entities)
    top_unknown_degree = sorted(unknown, key=lambda x: (-int(x.get("degree") or 0), x.get("label", "")))[:top_n]
    top_unknown_evidence = sorted(unknown, key=lambda x: (-int(x.get("evidence_count") or 0), x.get("label", "")))[:top_n]
    entity_audit = [{"entity_id": x.get("entity_id"), "label": x.get("label"), "canonical_label": x.get("canonical_label"), "entity_type": x.get("entity_type"), "type_inference_source": x.get("type_inference_source", "unknown"), "degree": x.get("degree"), "evidence_count": x.get("evidence_count"), "audit_flags": "|".join((["unknown_type"] if x in unknown else []) + (["parenthetical_suffix"] if x in suffix else []) + (["contamination_term"] if x in contamination else []))} for x in entities]
    triple_audit = sorted(({k: x.get(k) for k in ("triple_id", "subject_label", "relation_normalized", "object_label", "evidence_count", "fulltext_evidence_count", "results_section_evidence_count", "triple_quality_score", "seed_relevance_proxy", "evidence_strength_score", "specificity_score", "noise_risk_score", "display_priority_score", "quality_flags")} for x in triples), key=lambda x: -(x.get("display_priority_score") or 0))
    chain_audit = sorted(({k: x.get(k) for k in ("chain_id", "depth", "entity_path", "relation_path", "chain_quality_score", "chain_noise_risk_score", "display_recommended", "chain_flags")} for x in chains), key=lambda x: -(x.get("chain_quality_score") or 0))
    display_triple_ids = {x.get("triple_id") for x in display_triples}
    report = {"entities_total": len(entities), "entities_by_type": dict(sorted(Counter(x.get("entity_type", "missing") for x in entities).items())), "unknown_entity_count": len(unknown), "unknown_entity_fraction": round(len(unknown) / len(entities), 6) if entities else 0, "display_entities_total": len(display_entities), "triples_total": len(triples), "display_triples_total": len(display_triples), "chains_total": len(chains), "display_chains_total": sum(x.get("display_recommended") is True for x in chains), "top_unknown_entities_by_degree": top_unknown_degree, "top_unknown_entities_by_evidence_count": top_unknown_evidence, "single_character_entities": single, "numeric_or_symbolic_entities": symbolic, "entities_with_parenthetical_suffix": suffix, "possible_duplicate_entities": candidates, "possible_validator_or_artifact_entities": contamination, "validator_artifact_terms_found_in_main_graph": len(contamination), "validator_artifact_status": "not_found_in_main_graph" if not contamination else "HARD_WARNING", "normalization_candidates_count": len(candidates), "top_display_entities": sorted(display_entities, key=lambda x: (-int(x.get("degree") or 0), x.get("label", "")))[:top_n], "top_display_triples": [x for x in triple_audit if x.get("triple_id") in display_triple_ids][:top_n], "top_display_chains": [x for x in chain_audit if x.get("display_recommended")][:top_n], "warnings": warnings}
    noise = {"validator_artifact_terms_found_in_main_graph": len(contamination), "validator_artifact_status": report["validator_artifact_status"], "contaminating_entities": contamination, "high_noise_triples_count": sum((x.get("noise_risk_score") or 0) >= .65 for x in triples), "non_display_triples_count": len(triples) - len(display_triples), "non_display_chains_count": len(chains) - report["display_chains_total"], "warnings": warnings}
    if write_csv:
        _csv(output / "entity_type_audit.csv", entity_audit); _csv(output / "unknown_entity_review_queue.csv", top_unknown_degree, list(entities[0]) if entities else [])
        _csv(output / "entity_normalization_candidates.csv", candidates, ["entity_id_a", "label_a", "entity_id_b", "label_b", "reason", "recommended_action"]); _csv(output / "triple_quality_audit.csv", triple_audit); _csv(output / "chain_quality_audit.csv", chain_audit); _csv(output / "top_display_chains.csv", report["top_display_chains"])
    if write_json:
        (output / "kg_quality_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"); (output / "graph_noise_report.json").write_text(json.dumps(noise, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = ["# KG Quality Audit", "", f"- Entities: {len(entities)}", f"- Unknown entities: {len(unknown)} ({report['unknown_entity_fraction']:.1%})", f"- Display entities: {len(display_entities)}", f"- Triples/display triples: {len(triples)}/{len(display_triples)}", f"- Chains/display chains: {len(chains)}/{report['display_chains_total']}", f"- Validator/artifact terms in main graph: {len(contamination)}", f"- Normalization candidates: {len(candidates)}", "", "Typing is a conservative UI-layer inference, not medical ontology normalization."]
    (output / "kg_quality_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8"); (output / "graph_noise_report.md").write_text("# Graph Noise Report\n\n" + ("No validator/artifact terms were found in the main graph.\n" if not contamination else f"Hard warning: {len(contamination)} contaminating entities found.\n"), encoding="utf-8")
    return report
