"""Clean biomedical KG projection for System B navigation and audit views."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .review_queue import discover_bundles
from .display_kg import prepare_display_kg

BIOMEDICAL_TYPES = {"gene", "protein", "compound", "drug", "pathway", "biological_process", "disease", "phenotype", "cell_type", "tissue", "treatment", "condition", "organism", "unknown_biomedical_entity"}
BLOCKED_LABELS = {"lincs", "reactome", "enrichr", "pubmed post-cutoff", "pubmed validator", "validator", "case_bundle", "case_id", "claim", "paper", "pmid", "pmcid", "fulltext_l1", "abstract_l1", "review_queue", "pipeline_stage", "hypothesis_summary"}
EVIDENCE_SOURCES = (
    ("l2_reviewable_graph_observations.jsonl", "abstract_reviewable_observation", "abstract"),
    ("l35_fulltext_discovery_observations.jsonl", "fulltext_reviewable_observation", "fulltext"),
    ("l35_fulltext_discovery_l1_claims.jsonl", "fulltext_l1_claim", "fulltext"),
)
CONFLICT_SOURCES = ("weak_conflict_candidates.jsonl", "non_comparable_direction_pairs.jsonl", "hypothesis_candidates.jsonl")
VALIDATOR_SOURCES = (
    "l7_pubmed_post_cutoff_summary.json", "l7_pubmed_post_cutoff_results.jsonl", "l7_reactome_summary.json",
    "l7_reactome_results.jsonl", "l7_enrichr_summary.json", "l7_enrichr_results.jsonl",
    "l35_fulltext_conflict_confirmation_summary.json", "l35_fulltext_conflict_confirmations.jsonl",
    "l7_lincs_summary.json", "l7_lincs_results.jsonl",
)
ENTITY_FIELDS = ("entity_id", "label", "canonical_label", "entity_type", "aliases", "source_case_ids", "evidence_count", "abstract_evidence_count", "fulltext_evidence_count", "results_section_evidence_count", "degree", "in_degree", "out_degree")
TRIPLE_FIELDS = ("triple_id", "subject_id", "subject_label", "subject_type", "relation", "relation_normalized", "direction", "object_id", "object_label", "object_type", "context_summary", "context_count", "case_ids", "source_scopes", "evidence_count", "abstract_evidence_count", "fulltext_evidence_count", "results_section_evidence_count", "manual_valid_count", "manual_invalid_count", "conflict_status", "validator_badges", "review_priority_score_max", "seed_neighborhood_score_max")


def _hash(prefix: str, *values: Any) -> str:
    raw = "\x1f".join(str(v) for v in values).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:20]}"


def canonicalize_entity(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).translate(str.maketrans({"α": "alpha", "β": "beta", "κ": "kappa", "–": "-", "—": "-", "’": "'", "“": '"', "”": '"'}))
    text = re.sub(r"[\s,;:.]+$", "", text.strip())
    text = re.sub(r"\s*\(\d+\)\s*$", "", text)
    text = re.sub(r"[\s,;:.]+$", "", text)
    return " ".join(text.replace("_", " ").casefold().split())


def _canon(value: Any) -> str:
    return canonicalize_entity(value)


def normalize_relation(value: Any) -> str:
    relation = _canon(value)
    groups = {
        "promotes": {"increase", "increases", "increased", "upregulate", "upregulates", "upregulated", "promote", "promotes", "promoted", "induce", "induces", "induced"},
        "inhibits": {"decrease", "decreases", "decreased", "downregulate", "downregulates", "downregulated", "suppress", "suppresses", "suppressed", "inhibit", "inhibits", "inhibited"},
        "regulates": {"regulate", "regulates", "regulated", "modulate", "modulates", "modulated", "affect", "affects", "affected"},
        "associated_with": {"associated with", "associates with", "correlates with", "correlated with"},
    }
    for normalized, variants in groups.items():
        if relation in variants:
            return normalized
    return relation or "unknown_relation"


def _read(path: Path) -> list[tuple[int, dict[str, Any]]]:
    if not path.is_file(): return []
    try:
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8")); return [(1, value)] if isinstance(value, dict) else []
        rows = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip(): continue
            try: value = json.loads(line)
            except json.JSONDecodeError: continue
            if isinstance(value, dict): rows.append((number, value))
        return rows
    except (OSError, json.JSONDecodeError): return []


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if row.get(key) is not None: return row[key]
    return None


def _entity_type(row: dict[str, Any], side: str, label: Any) -> tuple[str, str]:
    value = _canon(_pick(row, f"{side}_type", f"{side}_entity_type"))
    aliases = {"chemical": "compound", "small molecule": "compound", "process": "biological_process", "cell": "cell_type", "unknown": "unknown_biomedical_entity"}
    value = aliases.get(value, value)
    if value in BIOMEDICAL_TYPES and value != "unknown_biomedical_entity": return value, "exact_rule"
    text = canonicalize_entity(label); token = re.sub(r"[^A-Za-z0-9]", "", str(label))
    processes = ("apoptosis", "ferroptosis", "proliferation", "migration", "invasion", "inflammation", "glycolysis", "oxidative stress", "lipid peroxidation")
    phenotypes = ("therapy response", "resistance", "survival", "tumor growth", "tumour growth", "tumor progression", "metastasis")
    diseases = ("cancer", "carcinoma", "leukemia", "lymphoma", "melanoma", "sarcoma", "disease")
    compounds = ("curcumin", "mangostin", "sorafenib", "erastin", "sulfasalazine")
    if any(term in text for term in processes) or text.endswith("phagy"): return "biological_process", "lexical_rule"
    if any(term in text for term in phenotypes): return "phenotype", "lexical_rule"
    if any(term in text for term in diseases): return "disease", "lexical_rule"
    if "signaling" in text or text.endswith(" pathway"): return "pathway", "lexical_rule"
    if any(term in text for term in compounds) or text.endswith(("formin", "mab", "nib", "azole", "mycin")): return "compound", "lexical_rule"
    if 2 <= len(token) <= 10 and any(c.isdigit() for c in token) and any(c.isalpha() for c in token) and token.upper() == token: return "gene", "lexical_rule"
    if re.fullmatch(r"(?:NF-?kB|HIF-?1(?:alpha)?|IL-?\d+|TNF-?(?:alpha)?)", str(label), re.I): return "protein", "lexical_rule"
    return "unknown_biomedical_entity", "fallback_unknown"


def _blocked(label: Any) -> tuple[bool, bool]:
    canonical = _canon(label)
    validator = canonical in {"lincs", "reactome", "enrichr", "pubmed post-cutoff", "pubmed validator", "validator"}
    nonbio = not canonical or canonical in BLOCKED_LABELS or canonical.startswith("pmid ") or canonical.startswith("pmcid ")
    return validator, nonbio


def _context_text(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in sorted(value.items()) if v not in (None, "", [], {}))
    return str(value or "").strip()


def _validator_name(filename: str) -> str:
    for name in ("pubmed_post_cutoff", "reactome", "enrichr", "lincs"):
        if name in filename: return name
    return "other"


def _status(row: dict[str, Any]) -> str:
    text = _canon(_pick(row, "status", "validation_status", "result", "interpretation"))
    if "unavailable" in text or "skip" in text: return "unavailable"
    if "not supportive" in text or "not_supportive" in text: return "not_supportive"
    if "support" in text or "match" in text: return "supportive"
    if "mixed" in text: return "mixed"
    return "available" if row else "unknown"


def build_clean_kg(roots: Iterable[str | Path], output_root: str | Path, *, max_chain_depth: int = 3,
                   min_evidence_count: int = 1, include_review_queue: str | Path | None = None,
                   write_jsonl: bool = True, write_csv: bool = True, overwrite: bool = False,
                   max_display_entities: int = 500, max_display_triples: int = 500,
                   max_display_chains: int = 1500, max_display_triples_per_case: int = 150,
                   max_display_chains_per_case: int = 300) -> dict[str, Any]:
    output = Path(output_root)
    if output.exists() and any(output.iterdir()) and not overwrite: raise FileExistsError(f"output root is not empty: {output}; pass --overwrite")
    output.mkdir(parents=True, exist_ok=True)
    bundles = discover_bundles(roots); entities: dict[tuple[str, str], dict[str, Any]] = {}; triples: dict[tuple[str, str, str], dict[str, Any]] = {}
    links, contexts, validators, conflicts, missing, warnings = [], [], [], [], {}, []
    blocked_validator = blocked_nonbio = 0
    for bundle in bundles:
        manifest = _read(bundle / "case_bundle_manifest.json"); case_id = str(manifest[0][1].get("case_id", bundle.name)) if manifest else bundle.name
        case_missing = []
        for filename, item_type, default_scope in EVIDENCE_SOURCES:
            path = bundle / filename
            if not path.is_file(): case_missing.append(filename); continue
            for line, row in _read(path):
                subject = _pick(row, "subject", "subject_raw", "subject_canonical_name"); obj = _pick(row, "object", "object_raw", "object_canonical_name")
                relation = _pick(row, "relation", "predicate", "relation_raw", "relation_family")
                if not subject or not obj or not relation: continue
                sbv, sbn = _blocked(subject); obv, obn = _blocked(obj)
                if sbv or obv: blocked_validator += int(sbv) + int(obv); continue
                if sbn or obn: blocked_nonbio += int(sbn) + int(obn); continue
                (st, ss), (ot, os) = _entity_type(row, "subject", subject), _entity_type(row, "object", obj); sc, oc = _canon(subject), _canon(obj)
                for canonical, label, etype, inference_source in ((sc, subject, st, ss), (oc, obj, ot, os)):
                    key = (canonical, etype)
                    if key not in entities: entities[key] = {"entity_id": _hash("ent", canonical, etype), "label": str(label), "canonical_label": canonical, "entity_type": etype, "type_inference_source": inference_source, "aliases": set(), "source_case_ids": set(), "evidence_count": 0, "abstract_evidence_count": 0, "fulltext_evidence_count": 0, "results_section_evidence_count": 0, "degree": 0, "in_degree": 0, "out_degree": 0}
                    entities[key]["aliases"].add(str(label)); entities[key]["source_case_ids"].add(case_id)
                    if len(re.sub(r"\s*\(\d+\)\s*$", "", str(label))) < len(re.sub(r"\s*\(\d+\)\s*$", "", entities[key]["label"])) or (re.search(r"\(\d+\)\s*$", entities[key]["label"]) and not re.search(r"\(\d+\)\s*$", str(label))): entities[key]["label"] = str(label)
                normalized = normalize_relation(relation); key = (sc, normalized, oc); scope = _canon(row.get("source_scope")) or default_scope
                section = _canon(_pick(row, "section_title", "section", "section_type")); is_results = "result" in section
                if key not in triples:
                    triples[key] = {"triple_id": _hash("tri", *key), "subject_id": entities[(sc, st)]["entity_id"], "subject_label": str(subject), "subject_type": st, "relation": str(relation), "relation_normalized": normalized, "direction": row.get("direction"), "object_id": entities[(oc, ot)]["entity_id"], "object_label": str(obj), "object_type": ot, "contexts": set(), "case_ids": set(), "source_scopes": set(), "evidence_count": 0, "abstract_evidence_count": 0, "fulltext_evidence_count": 0, "results_section_evidence_count": 0, "manual_valid_count": None, "manual_invalid_count": None, "conflict_status": "none", "validator_badges": set(), "review_priority_score_max": None, "seed_neighborhood_score_max": None}
                triple = triples[key]; triple["case_ids"].add(case_id); triple["source_scopes"].add(scope)
                triple["evidence_count"] += 1; triple["abstract_evidence_count"] += int(scope == "abstract"); triple["fulltext_evidence_count"] += int("full" in scope); triple["results_section_evidence_count"] += int(is_results)
                context = _context_text(row.get("context"));
                if context: triple["contexts"].add(context); contexts.append({"triple_id": triple["triple_id"], "case_id": case_id, "context_text": context, "context_type": "unknown", "source_file": filename, "source_line": line})
                for score in ("review_priority_score", "seed_neighborhood_score"):
                    try: triple[f"{score}_max"] = max(x for x in (triple[f"{score}_max"], float(row[score])) if x is not None)
                    except (KeyError, TypeError, ValueError): pass
                links.append({"triple_id": triple["triple_id"], "case_id": case_id, "source_file": filename, "source_line": line, "item_type": item_type, "source_scope": scope, "pmid": row.get("pmid"), "pmcid": row.get("pmcid"), "paper_title": _pick(row, "paper_title", "title"), "section_title": _pick(row, "section_title", "section"), "evidence_sentence": _pick(row, "evidence_sentence", "evidence", "sentence"), "claim_text": _pick(row, "claim_text", "claim"), "subject": subject, "relation": relation, "object": obj, "direction": row.get("direction"), "context": row.get("context"), "anchor_strength": row.get("anchor_strength"), "seed_neighborhood_score": row.get("seed_neighborhood_score"), "review_priority_score": _pick(row, "review_priority_score", "score")})
        for filename in VALIDATOR_SOURCES:
            path = bundle / filename
            if not path.is_file(): continue
            rows = _read(path); name = _validator_name(filename)
            summary = f"{len(rows)} record(s) in {filename}"
            if path.suffix == ".json" and rows: summary = json.dumps(rows[0][1], ensure_ascii=False, sort_keys=True)[:1000]
            validators.append({"case_id": case_id, "validator_name": name, "target_type": "case", "target_id": None, "target_label": case_id, "status": _status(rows[0][1] if rows else {}), "summary": summary, "source_file": filename})
        for filename in CONFLICT_SOURCES:
            path = bundle / filename
            if not path.is_file(): case_missing.append(filename); continue
            for line, row in _read(path): conflicts.append(_conflict_record(case_id, filename, line, row, triples))
        summary_path = bundle / "hypothesis_summary.json"
        if summary_path.is_file():
            for line, row in _read(summary_path):
                count = _pick(row, "formal_hypothesis_count", "hypothesis_count") or 0
                if count: conflicts.append(_conflict_record(case_id, "hypothesis_summary.json", line, row, triples, "formal_hypothesis"))
        if case_missing: missing[case_id] = sorted(set(case_missing))
    retained_ids = {x["triple_id"] for x in triples.values() if x["evidence_count"] >= min_evidence_count}
    triples = {key: value for key, value in triples.items() if value["triple_id"] in retained_ids}; links = [x for x in links if x["triple_id"] in retained_ids]; contexts = [x for x in contexts if x["triple_id"] in retained_ids]
    used_entities = {x[k] for x in triples.values() for k in ("subject_id", "object_id")}; entities = {k: v for k, v in entities.items() if v["entity_id"] in used_entities}
    _apply_conflicts(conflicts, triples); _apply_degrees(entities, triples, links)
    entity_rows = [_final_entity(x) for x in entities.values()]; triple_rows = [_score_triple(_final_triple(x)) for x in triples.values()]
    chains, truncated = _chains(entity_rows, triple_rows, max_chain_depth)
    if truncated: warnings.append(f"chain paths truncated: {truncated}")
    if include_review_queue: _apply_manual_annotations(Path(include_review_queue), triple_rows, warnings)
    display_triples = [x for x in triple_rows if x["display_priority_score"] >= 0.35 and x["noise_risk_score"] < 0.65 and not (x["subject_type"] == x["object_type"] == "unknown_biomedical_entity")]
    display_entity_ids = {x[key] for x in display_triples for key in ("subject_id", "object_id")}; display_entities = [x for x in entity_rows if x["entity_id"] in display_entity_ids]
    display_chains = [x for x in chains if x["display_recommended"]]
    summary = _write(output, entity_rows, triple_rows, links, contexts, validators, conflicts, chains, display_entities, display_triples, display_chains, write_jsonl, write_csv,
                     len(bundles), missing, warnings, blocked_validator, blocked_nonbio, truncated)
    prepare_display_kg(output, entity_rows, triple_rows, chains, links, validators, conflicts,
        max_entities=max_display_entities, max_triples=max_display_triples, max_chains=max_display_chains,
        max_triples_per_case=max_display_triples_per_case, max_chains_per_case=max_display_chains_per_case)
    return summary


def _conflict_record(case_id: str, filename: str, line: int, row: dict[str, Any], triples: dict, forced: str | None = None) -> dict[str, Any]:
    kind = forced or ("non_comparable_direction_pair" if "non_comparable" in filename else "weak_candidate" if "weak" in filename else "formal_hypothesis")
    candidate = _canon(row.get("candidate_type"));
    if candidate in {"mechanism split", "mechanism_split"}: kind = "mechanism_split"
    if candidate in {"context split", "context_split"}: kind = "context_split"
    linked = []
    observations = [_pick(row, "observation_a", "observation_1"), _pick(row, "observation_b", "observation_2"), row]
    for obs in observations:
        if not isinstance(obs, dict): continue
        key = (_canon(_pick(obs, "subject", "subject_raw")), normalize_relation(_pick(obs, "relation", "predicate", "relation_raw")), _canon(_pick(obs, "object", "object_raw")))
        if key in triples: linked.append(triples[key]["triple_id"])
    return {"record_id": _hash("conf", case_id, filename, line), "case_id": case_id, "record_type": kind, "subject": row.get("subject"), "relation": _pick(row, "relation", "predicate"), "object": row.get("object"), "direction": row.get("direction"), "candidate_type": row.get("candidate_type"), "comparability_label": row.get("comparability_label"), "rejection_reason": _pick(row, "rejection_reason", "reason"), "linked_triple_ids": sorted(set(linked)), "observation_a_preview": _preview(_pick(row, "observation_a", "observation_1")), "observation_b_preview": _preview(_pick(row, "observation_b", "observation_2")), "source_file": filename, "source_line": line}


def _preview(value: Any) -> str | None:
    return None if value is None else (value[:500] if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)[:500])


def _apply_conflicts(conflicts: list[dict], triples: dict) -> None:
    rank = {"none": 0, "has_formal_hypothesis": 1, "has_weak_candidate": 2, "has_non_comparable": 3, "has_mechanism_split": 4, "has_context_split": 5}
    statuses = {"weak_candidate": "has_weak_candidate", "non_comparable_direction_pair": "has_non_comparable", "mechanism_split": "has_mechanism_split", "context_split": "has_context_split", "formal_hypothesis": "has_formal_hypothesis"}
    by_id = {x["triple_id"]: x for x in triples.values()}
    for record in conflicts:
        status = statuses[record["record_type"]]
        for tid in record["linked_triple_ids"]:
            if tid in by_id and rank[status] > rank[by_id[tid]["conflict_status"]]: by_id[tid]["conflict_status"] = status


def _apply_degrees(entities: dict, triples: dict, links: list[dict]) -> None:
    by_id = {x["entity_id"]: x for x in entities.values()}; link_counts = Counter(x["triple_id"] for x in links)
    for triple in triples.values():
        s, o = by_id[triple["subject_id"]], by_id[triple["object_id"]]; s["out_degree"] += 1; o["in_degree"] += 1
        for entity in (s, o):
            entity["evidence_count"] += link_counts[triple["triple_id"]]; entity["abstract_evidence_count"] += triple["abstract_evidence_count"]; entity["fulltext_evidence_count"] += triple["fulltext_evidence_count"]; entity["results_section_evidence_count"] += triple["results_section_evidence_count"]
    for entity in by_id.values(): entity["degree"] = entity["in_degree"] + entity["out_degree"]


def _final_entity(row: dict) -> dict:
    row = dict(row); row["aliases"] = sorted(row["aliases"]); row["source_case_ids"] = sorted(row["source_case_ids"]); return row


def _final_triple(row: dict) -> dict:
    row = dict(row); values = sorted(row.pop("contexts")); row["context_summary"] = " | ".join(values[:5]); row["context_count"] = len(values)
    for key in ("case_ids", "source_scopes", "validator_badges"): row[key] = sorted(row[key])
    return row


def _score_triple(row: dict) -> dict:
    generic = {"cancer", "cell", "cells", "effect", "level", "expression", "activity", "role", "unknown"}
    labels = (_canon(row["subject_label"]), _canon(row["object_label"])); types = (row["subject_type"], row["object_type"])
    evidence = min(1.0, 0.18 * math.log2(row["evidence_count"] + 1) + 0.12 * math.log2(row["fulltext_evidence_count"] + 1) + 0.2 * math.log2(row["results_section_evidence_count"] + 1) + 0.08 * len(row["case_ids"]))
    specificity = 0.25 * sum(t != "unknown_biomedical_entity" for t in types) + 0.15 * sum(label not in generic and len(label) > 2 for label in labels)
    noise = 0.2 * sum(t == "unknown_biomedical_entity" for t in types) + 0.18 * sum(label in generic for label in labels)
    flags = []
    for name, label in zip(("subject", "object"), labels):
        if len(label.split()) > 14 or len(label) > 120: noise += 0.25; flags.append(f"{name}_sentence_like")
        if label in generic: flags.append(f"generic_{name}")
    if types[0] == types[1] == "unknown_biomedical_entity": flags.append("both_entities_unknown")
    if row["relation_normalized"] in {"regulates", "associated_with", "unknown_relation", "affects", "involved in"}: noise += 0.1; flags.append("generic_relation")
    noise = min(1.0, noise); seed_proxy = min(1.0, max(row.get("review_priority_score_max") or 0, row.get("seed_neighborhood_score_max") or 0))
    display = max(0.0, min(1.0, 0.38 * evidence + 0.28 * specificity + 0.2 * seed_proxy + 0.08 * int(row["fulltext_evidence_count"] > 0) + 0.06 * int(row["results_section_evidence_count"] > 0) - 0.42 * noise))
    row.update({"triple_quality_score": round(max(0.0, min(1.0, 0.45 * evidence + 0.3 * specificity + 0.25 * seed_proxy - 0.3 * noise)), 4), "seed_relevance_proxy": round(seed_proxy, 4), "evidence_strength_score": round(evidence, 4), "specificity_score": round(min(1.0, specificity), 4), "noise_risk_score": round(noise, 4), "display_priority_score": round(display, 4), "quality_flags": sorted(set(flags))})
    return row


def _chains(entities: list[dict], triples: list[dict], max_depth: int) -> tuple[list[dict], int]:
    by_entity = {x["entity_id"]: x for x in entities}; by_triple = {x["triple_id"]: x for x in triples}; outgoing = defaultdict(list)
    for triple in triples: outgoing[triple["subject_id"]].append(triple)
    truncated = 0
    for key in outgoing:
        outgoing[key].sort(key=lambda x: (-x["evidence_count"], x["triple_id"])); truncated += max(0, len(outgoing[key]) - 20); outgoing[key] = outgoing[key][:20]
    chains = []
    def walk(start: str, current: str, tids: list[str], eids: list[str]) -> None:
        if tids:
            path = [by_triple[x] for x in tids]; chains.append({"chain_id": _hash("chain", *tids), "start_entity_id": start, "start_label": by_entity[start]["label"], "end_entity_id": current, "end_label": by_entity[current]["label"], "depth": len(tids), "triple_ids": list(tids), "entity_path": [by_entity[x]["label"] for x in eids], "relation_path": [x["relation_normalized"] for x in path], "evidence_count_sum": sum(x["evidence_count"] for x in path), "fulltext_evidence_count_sum": sum(x["fulltext_evidence_count"] for x in path), "results_section_evidence_count_sum": sum(x["results_section_evidence_count"] for x in path), "conflict_statuses": sorted({x["conflict_status"] for x in path if x["conflict_status"] != "none"}), "case_ids": sorted({case for x in path for case in x["case_ids"]})})
        if len(tids) >= max_depth: return
        for triple in outgoing[current]:
            nxt = triple["object_id"]
            if nxt not in eids: walk(start, nxt, tids + [triple["triple_id"]], eids + [nxt])
    for entity_id in sorted(by_entity): walk(entity_id, entity_id, [], [entity_id])
    for chain in chains:
        path = [by_triple[x] for x in chain["triple_ids"]]; entity_ids = [path[0]["subject_id"]] + [x["object_id"] for x in path]; unknown = sum(by_entity[x]["entity_type"] == "unknown_biomedical_entity" for x in entity_ids)
        generic = sum(_canon(x) in {"cancer", "cells", "effect", "expression", "activity"} for x in chain["entity_path"])
        risk = min(1.0, sum(x["noise_risk_score"] for x in path) / len(path) + 0.08 * generic + 0.04 * unknown)
        quality = max(0.0, min(1.0, sum(x["display_priority_score"] for x in path) / len(path) + 0.08 * int(chain["fulltext_evidence_count_sum"] > 0) + 0.08 * int(chain["results_section_evidence_count_sum"] > 0) - 0.35 * risk))
        flags = (["contains_high_noise_edge"] if any(x["noise_risk_score"] >= 0.65 for x in path) else []) + (["generic_entity_path"] if generic else [])
        chain.update({"chain_quality_score": round(quality, 4), "chain_noise_risk_score": round(risk, 4), "display_recommended": quality >= 0.35 and risk < 0.65, "chain_flags": flags})
    return chains, truncated


def _apply_manual_annotations(path: Path, triples: list[dict], warnings: list[str]) -> None:
    if not path.is_file(): warnings.append(f"review queue not found: {path}"); return
    warnings.append("manual annotations loaded only when rows contain triple_id and final_label")
    by_id = {x["triple_id"]: x for x in triples}
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("triple_id") not in by_id or not row.get("final_label"): continue
                triple = by_id[row["triple_id"]]; valid = row["final_label"].strip().upper() == "VALID"
                key = "manual_valid_count" if valid else "manual_invalid_count"; triple[key] = (triple[key] or 0) + 1
    except OSError as exc: warnings.append(f"manual annotations unreadable: {exc}")


def _json_safe(row: dict) -> dict:
    return {k: (json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v) for k, v in row.items()}


def _write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(_json_safe(x) for x in rows)


def _write(root: Path, entities: list[dict], triples: list[dict], links: list[dict], contexts: list[dict], validators: list[dict], conflicts: list[dict], chains: list[dict], display_entities: list[dict], display_triples: list[dict], display_chains: list[dict], write_jsonl: bool, write_csv: bool, cases: int, missing: dict, warnings: list, blocked_validator: int, blocked_nonbio: int, truncated: int) -> dict:
    artifacts = {"clean_entities.jsonl": entities, "clean_triples.jsonl": triples, "clean_entities_display.jsonl": display_entities, "clean_triples_display.jsonl": display_triples, "triple_evidence_links.jsonl": links, "triple_contexts.jsonl": contexts, "chain_index.jsonl": chains, "validator_annotations.jsonl": validators, "conflict_lens_records.jsonl": conflicts}
    if write_jsonl:
        for name, rows in artifacts.items(): (root / name).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    if write_csv:
        _write_csv(root / "clean_entities.csv", entities, tuple(entities[0]) if entities else ENTITY_FIELDS); _write_csv(root / "clean_triples.csv", triples, tuple(triples[0]) if triples else TRIPLE_FIELDS)
        _write_csv(root / "clean_entities_display.csv", display_entities, tuple(entities[0]) if entities else ENTITY_FIELDS); _write_csv(root / "clean_triples_display.csv", display_triples, tuple(triples[0]) if triples else TRIPLE_FIELDS)
    entity_index = {x["entity_id"]: x for x in entities}; relation_index = {name: [x["triple_id"] for x in triples if x["relation_normalized"] == name] for name in sorted({x["relation_normalized"] for x in triples})}
    (root / "entity_index.json").write_text(json.dumps(entity_index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"); (root / "relation_index.json").write_text(json.dumps(relation_index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {"cases_discovered": cases, "entities_total": len(entities), "display_entities_total": len(display_entities), "triples_total": len(triples), "display_triples_total": len(display_triples), "evidence_links_total": len(links), "contexts_total": len(contexts), "validator_annotations_total": len(validators), "conflict_lens_records_total": len(conflicts), "chains_total": len(chains), "display_chains_total": len(display_chains), "entities_by_type": dict(sorted(Counter(x["entity_type"] for x in entities).items())), "relations_by_type": dict(sorted(Counter(x["relation_normalized"] for x in triples).items())), "triples_by_conflict_status": dict(sorted(Counter(x["conflict_status"] for x in triples).items())), "top_entities_by_degree": sorted(({"entity_id": x["entity_id"], "label": x["label"], "degree": x["degree"]} for x in entities), key=lambda x: (-x["degree"], x["label"]))[:20], "top_triples_by_evidence_count": sorted(({"triple_id": x["triple_id"], "subject": x["subject_label"], "relation": x["relation_normalized"], "object": x["object_label"], "evidence_count": x["evidence_count"]} for x in triples), key=lambda x: (-x["evidence_count"], x["triple_id"]))[:20], "top_display_triples": sorted(({"triple_id": x["triple_id"], "subject": x["subject_label"], "relation": x["relation_normalized"], "object": x["object_label"], "display_priority_score": x["display_priority_score"]} for x in display_triples), key=lambda x: (-x["display_priority_score"], x["triple_id"]))[:20], "warnings": warnings, "missing_files": missing, "validator_nodes_blocked_count": blocked_validator, "non_biomedical_nodes_blocked_count": blocked_nonbio, "truncated_paths": truncated}
    (root / "clean_kg_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = ["# Clean KG Summary", "", "> Biomedical entities and relations only. Validators, evidence, papers, and conflicts remain annotations or overlays.", ""] + [f"- {key}: {summary[key]}" for key in ("cases_discovered", "entities_total", "triples_total", "evidence_links_total", "contexts_total", "validator_annotations_total", "conflict_lens_records_total", "chains_total", "validator_nodes_blocked_count", "non_biomedical_nodes_blocked_count", "truncated_paths")]
    (root / "clean_kg_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8"); return summary
