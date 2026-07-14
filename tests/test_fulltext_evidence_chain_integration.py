import json
from pathlib import Path

import pytest

from code_engine.fulltext.reasoning_trace import (
    evidence_chains_from_traces,
    extract_direct_fulltext_evidence_chains,
    link_claims_to_evidence_chains,
    normalize_evidence_chain_entities,
    run_fulltext_context_consolidation_stage,
    run_fulltext_reasoning_trace_stage,
)
from code_engine.integration.atlas_handoff import canonical_json, sha256_file
from code_engine.schemas.evidence_chain import (
    CausalDesign,
    ClaimEvidenceLink,
    EvidenceAnchor,
    ExperimentalEvidenceChain,
    validate_claim_evidence_references,
)
from code_engine.system_b.adapters.fulltext_reentry_v5 import FulltextReentryV5Adapter


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _artifact_spec(path: Path, relative: str, *, required=False):
    return {
        "relative_path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "record_count": sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) if path.suffix == ".jsonl" else None,
        "required": required,
    }


def test_evidence_chain_schema_validation_rules():
    chain = ExperimentalEvidenceChain(
        chain_id="chain_1",
        evidence_anchors=[EvidenceAnchor(sentence_id="s1", sentence_text="Treatment increased endpoint.")],
        causal_design=CausalDesign(evidence_type="intervention", causal_strength="intervention_support"),
        extraction_confidence=0.9,
        validation_status="valid",
    )
    assert chain.schema_version == "experimental_evidence_chain_v1"

    with pytest.raises(ValueError, match="high-confidence"):
        ExperimentalEvidenceChain(chain_id="bad", extraction_confidence=0.9, validation_status="partial")
    with pytest.raises(ValueError):
        CausalDesign(evidence_type="intervention", causal_strength="causes_everything")
    with pytest.raises(ValueError):
        ClaimEvidenceLink(link_id="l", claim_id="c", chain_id="x", relation="supports", link_confidence=0.2)


def test_claim_evidence_link_reference_validation():
    link = ClaimEvidenceLink(link_id="l1", claim_id="c1", chain_id="chain_1", relation="supports", link_confidence=0.8)
    validate_claim_evidence_references([link], claim_ids={"c1"}, chain_ids={"chain_1"})
    with pytest.raises(ValueError, match="missing ids"):
        validate_claim_evidence_references([link], claim_ids={"other"}, chain_ids={"chain_1"})


def test_fulltext_processing_generates_chains_links_and_linked_context(tmp_path):
    artifacts = tmp_path / "artifacts"
    claim = {
        "claim_id": "claim_1",
        "case_id": "case",
        "paper_id": "P1",
        "pmcid": "PMC1",
        "source_scope": "fulltext",
        "subject": "ketamine",
        "predicate": "activates",
        "object": "mTOR",
        "evidence_sentence": "Ketamine activated mTOR signaling.",
        "context": {"species": "mouse"},
    }
    _write_jsonl(artifacts / "l35_fulltext_l1_claims.jsonl", [claim])
    _write_jsonl(artifacts / "l35_fulltext_oa_candidate_papers.jsonl", [{"paper_id": "P1", "pmcid": "PMC1", "case_id": "case"}])
    _write_json(artifacts / "fulltext/pmc_oa/PMC1/article_text.json", {
        "sections": [
            {"section_title": "Results", "section_type": "results", "text": "Ketamine treatment increased mTOR phosphorylation in mouse hippocampus compared with vehicle control. Rapamycin blockade abolished the behavioral response."},
            {"section_title": "Methods", "section_type": "methods", "text": "Mice received ketamine at 10 mg/kg and phosphorylation was measured by western blot."},
        ]
    })

    def extractor(_prompt, ctx):
        passages = ctx["passages"]
        by_text = {p["text"]: p["sentence_ids"][0] for p in passages}
        first_text = next(text for text in by_text if "increased mTOR phosphorylation" in text)
        method_text = next(text for text in by_text if "10 mg/kg" in text)
        return {
            "trace_status": "complete",
            "reasoning_steps": [
                {"role": "experimental_intervention", "reported_text": first_text, "sentence_ids": [by_text[first_text]], "provenance_type": "reported"},
                {"role": "comparison_or_control", "reported_text": first_text, "sentence_ids": [by_text[first_text]], "provenance_type": "reported"},
                {"role": "measurement", "reported_text": method_text, "sentence_ids": [by_text[method_text]], "provenance_type": "reported"},
                {"role": "observation", "reported_text": first_text, "sentence_ids": [by_text[first_text]], "provenance_type": "reported"},
                {"role": "blocking_experiment", "reported_text": "Rapamycin blockade abolished the behavioral response.", "sentence_ids": [next(p["sentence_ids"][0] for p in passages if "abolished" in p["text"])], "provenance_type": "reported"},
            ],
            "experimental_context": {"species": ["mouse"], "model_system": ["hippocampus"], "intervention_target": ["ketamine"], "control_group": ["vehicle"], "dose": ["10 mg/kg"], "assay_method": ["western blot"], "measured_endpoint": ["mTOR phosphorylation"]},
            "author_conclusion": {"text": "mTOR activation is required.", "certainty": "asserted"},
        }

    summary = run_fulltext_reasoning_trace_stage(tmp_path, case_id="case", api_enabled=True, network_enabled=True, extractor=extractor)
    assert summary["evidence_chain_count"] == 1
    assert summary["claim_evidence_link_count"] == 1
    chains = [json.loads(line) for line in (artifacts / "experimental_evidence_chains.jsonl").read_text().splitlines()]
    links = [json.loads(line) for line in (artifacts / "claim_evidence_links.jsonl").read_text().splitlines()]
    assert chains[0]["causal_design"]["causal_strength"] == "necessity_support"
    assert links[0]["claim_id"] == "claim_1"
    assert links[0]["relation"] == "supports"

    context_summary = run_fulltext_context_consolidation_stage(tmp_path, case_id="case")
    assert context_summary["context_enriched_claim_count"] == 1
    consolidated = json.loads((artifacts / "fulltext_context_consolidations.jsonl").read_text().splitlines()[0])
    assert consolidated["consolidated_context"]["species"][0]["source_type"] == "explicit_claim_context"
    assert any(item["source_type"] == "evidence_chain_context" and item["value"] == "10 mg/kg" for item in consolidated["consolidated_context"]["dose"])
    assert chains[0]["extraction_origin"] == "direct_fulltext"
    assert "normalized_entities" in chains[0]


def test_direct_fulltext_builds_multiple_independent_chains(tmp_path):
    artifacts = tmp_path / "artifacts"
    paper = {"paper_id": "P1", "pmcid": "PMC1", "case_id": "case"}
    claims = [
        {"claim_id": "c1", "paper_id": "P1", "pmcid": "PMC1", "source_scope": "fulltext", "section_type": "results", "subject": "IL-6", "predicate": "induces", "object": "EMT", "evidence_sentence": "IL-6 treatment induced EMT in SK-BR-3 cells."},
        {"claim_id": "c2", "paper_id": "P1", "pmcid": "PMC1", "source_scope": "fulltext", "section_type": "results", "subject": "siRNA", "predicate": "reduces", "object": "invasion", "evidence_sentence": "LAGE3 knockdown reduced invasion in TNBC cells."},
    ]
    _write_json(artifacts / "fulltext/pmc_oa/PMC1/article_text.json", {
        "sections": [{"section_title": "Results", "section_type": "results", "text": "IL-6 treatment induced EMT in SK-BR-3 cells. LAGE3 knockdown reduced invasion in TNBC cells."}]
    })
    chains = extract_direct_fulltext_evidence_chains(claims, [paper], artifacts)
    assert len(chains) == 2
    assert {chain["claim_id"] for chain in chains} == {"c1", "c2"}
    assert all(chain["extraction_origin"] == "direct_fulltext" for chain in chains)


def test_linking_does_not_create_same_paper_cartesian_supports():
    claims = [{"claim_id": "c1"}, {"claim_id": "c2"}]
    chains = [{"chain_id": "chain_1", "claim_id": "c1", "paper_id": "P", "validation_status": "partial", "evidence_anchors": [{"anchor_id": "a"}]}]
    links = link_claims_to_evidence_chains(claims, chains)
    assert len(links) == 1
    assert links[0]["claim_id"] == "c1"


def test_context_consolidation_only_consumes_linked_chains():
    traces = [{
        "reasoning_trace_id": "rt1",
        "claim_id": "c1",
        "paper_id": "P",
        "source_scope": "fulltext",
        "trace_status": "complete",
        "reasoning_steps": [{"role": "experimental_intervention", "reported_text": "Drug increased endpoint.", "sentence_ids": ["s1"], "section_title": "Results"}],
        "experimental_context": {"intervention_target": ["drug"], "dose": ["10 mg/kg"]},
    }, {
        "reasoning_trace_id": "rt2",
        "claim_id": "c2",
        "paper_id": "P",
        "source_scope": "fulltext",
        "trace_status": "complete",
        "reasoning_steps": [{"role": "experimental_intervention", "reported_text": "Cells received 100 uM drug.", "sentence_ids": ["s2"], "section_title": "Results"}],
        "experimental_context": {"intervention_target": ["drug"], "dose": ["100 uM"]},
    }]
    chains = evidence_chains_from_traces(traces)
    links = link_claims_to_evidence_chains([{"claim_id": "c1"}], [c for c in chains if c["claim_id"] == "c1"])
    assert len(links) == 1
    assert all(link["claim_id"] == "c1" for link in links)


def test_chain_entity_normalization_uses_resolver_without_network_or_llm(tmp_path, monkeypatch):
    calls = []

    class Decision:
        raw_text = "IL-6"
        normalized_surface = "il 6"
        canonical_id = "GENE:IL6"
        canonical_name = "IL6"
        entity_type = "gene"
        normalization_status = "resolved"
        resolver = "entity_resolution_hub_v1"
        confidence = 0.91

    class FakeResolver:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def resolve_entity(self, raw_text, context=None, allow_fallback=False):
            decision = Decision()
            decision.raw_text = raw_text
            return decision

    monkeypatch.setattr("code_engine.fulltext.reasoning_trace.ResolverCascade", FakeResolver)
    chains = [{
        "chain_id": "chain_1",
        "claim_id": "c1",
        "paper_id": "P",
        "interventions": [{"agent_raw": "IL-6"}],
        "experimental_system": {"cell_line": "SK-BR-3"},
        "measurements": [{"endpoint": "EMT"}],
        "observed_results": [{"endpoint": "EMT"}],
        "evidence_anchors": [{"sentence_text": "IL-6 induced EMT."}],
    }]
    normalized, counts = normalize_evidence_chain_entities(chains, run_dir=tmp_path)
    assert calls
    assert calls[0]["entity_network_lookup"] is False
    assert calls[0]["entity_llm_cleaner"] is False
    assert normalized[0]["interventions"][0]["canonical_id"] == "GENE:IL6"
    assert normalized[0]["normalized_entities"][0]["resolution_status"] == "resolved"
    assert counts["entity_resolved_count"] >= 1


def test_adapter_projects_evidence_chains_without_kg_experiment_nodes(tmp_path):
    run = tmp_path / "run"
    artifacts = run / "artifacts"
    lane = {"evidence_lane": "core_seed_relation", "claim_id": "claim_1", "subject": "ketamine", "object": "mTOR", "relation_raw": "activates", "direction": "positive", "source_scope": "fulltext", "retained": True, "exploratory_graph_eligible": True, "conflict_eligible": False, "relation_class": "causal_regulation", "evidence_sentence": "Ketamine activated mTOR.", "pmid": "1"}
    _write_jsonl(artifacts / "fulltext_core_seed_observations.jsonl", [lane])
    for name in ("fulltext_seed_neighborhood_observations.jsonl", "fulltext_reviewable_relations.jsonl", "fulltext_off_seed_relations.jsonl"):
        _write_jsonl(artifacts / name, [])
    _write_jsonl(artifacts / "experimental_evidence_chains.jsonl", [{
        "schema_version": "experimental_evidence_chain_v1",
        "chain_id": "chain_1",
        "claim_id": "claim_1",
        "paper_id": "P",
        "experimental_system": {"species": "mouse"},
        "interventions": [{"agent_raw": "ketamine", "dose": "10 mg/kg"}],
        "comparators": [{"comparator_type": "vehicle", "description": "vehicle"}],
        "measurements": [{"assay": "western blot", "endpoint": "mTOR"}],
        "observed_results": [{"endpoint": "mTOR", "direction": "increase", "effect_description": "increased"}],
        "author_interpretation": {"text": "required", "certainty": "asserted"},
        "causal_design": {"evidence_type": "intervention", "causal_strength": "intervention_support", "classification_basis": ["intervention"]},
        "evidence_anchors": [{"anchor_id": "a1", "sentence_id": "s1", "sentence_text": "Ketamine activated mTOR."}],
        "extraction_confidence": 0.8,
        "validation_status": "valid",
    }])
    _write_jsonl(artifacts / "claim_evidence_links.jsonl", [{"schema_version": "claim_evidence_link_v1", "link_id": "link_1", "claim_id": "claim_1", "chain_id": "chain_1", "paper_id": "P", "relation": "supports", "link_method": "shared_result_anchor", "link_confidence": 0.8, "link_basis": ["anchor"], "evidence_anchor_ids": ["a1"]}])
    _write_jsonl(artifacts / "fulltext_context_consolidations.jsonl", [{"claim_id": "claim_1", "linked_chain_ids": ["chain_1"], "consolidated_context": {"species": [{"value": "mouse", "source_type": "evidence_chain_context", "source_ids": ["chain_1"], "confidence": 0.8, "agreement_status": "single_source"}]}}])

    artifacts_spec = {
        "lane_core_seed_relation": _artifact_spec(artifacts / "fulltext_core_seed_observations.jsonl", "artifacts/fulltext_core_seed_observations.jsonl", required=True),
        "lane_seed_neighborhood_mechanism": _artifact_spec(artifacts / "fulltext_seed_neighborhood_observations.jsonl", "artifacts/fulltext_seed_neighborhood_observations.jsonl", required=True),
        "lane_reviewable_context_relation": _artifact_spec(artifacts / "fulltext_reviewable_relations.jsonl", "artifacts/fulltext_reviewable_relations.jsonl", required=True),
        "lane_off_seed_relation": _artifact_spec(artifacts / "fulltext_off_seed_relations.jsonl", "artifacts/fulltext_off_seed_relations.jsonl", required=True),
        "experimental_evidence_chains": _artifact_spec(artifacts / "experimental_evidence_chains.jsonl", "artifacts/experimental_evidence_chains.jsonl"),
        "claim_evidence_links": _artifact_spec(artifacts / "claim_evidence_links.jsonl", "artifacts/claim_evidence_links.jsonl"),
        "fulltext_context_consolidations": _artifact_spec(artifacts / "fulltext_context_consolidations.jsonl", "artifacts/fulltext_context_consolidations.jsonl"),
    }
    validated = {"manifest": {"case_id": "case", "source_run_id": "run", "artifacts": artifacts_spec}, "run_dir": run}
    project = FulltextReentryV5Adapter().project(validated, prediction_run_id="pred")
    assert project["dossier_evidence"][0]["evidence_chains"][0]["chain"]["chain_id"] == "chain_1"
    assert project["display"]["display_chains_v2"] == []
    assert all("chain_1" not in row.get("triple_id", "") for row in project["display"]["display_triples_v2"])
