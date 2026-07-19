import json
import tempfile
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts
from code_engine.normalization.adjudicator import adjudicate_entity_candidates
from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest
from code_engine.normalization.llm_entity_cleaner import LLMEntityCleaner
from code_engine.normalization.resolver import ResolverCascade


class RouteClient:
    def __init__(self, records):
        self.records = records
        self.calls = 0
        self.network_call_cost = 1

    def search(self, surface, request=None, ontologies=None):
        self.calls += 1
        return self.records


def test_cleaner_preserves_and_refines_assay_readout_entity_types():
    with tempfile.TemporaryDirectory() as tmp:
        resolver = ResolverCascade(
            run_dir=tmp,
            execute=True,
            network_enabled=True,
            entity_network_lookup=True,
            entity_llm_cleaner=True,
            external_clients={
                "uniprot": RouteClient([{"canonical_id": "UniProt:P12830", "canonical_name": "E-cadherin", "entity_type": "protein", "score": 0.9}]),
                "mygene": RouteClient([{"canonical_id": "EntrezGene:999", "canonical_name": "CDH1", "entity_type": "gene", "score": 0.9}]),
            },
        )
        decision = resolver.resolve_entity(
            "E-cadherin expression",
            {"expected_entity_type": "assay_readout", "context_text": "Western blot showed E-cadherin expression.", "mention_role": "subject"},
        )
        trace = decision.cleaner_trace["type_traces"][0]
        assert trace["cleaned_mention"] == "E-cadherin"
        assert trace["final_expected_entity_type"] == "protein"
        assert decision.cleaner_trace["cleaned_head_entities"][0]["ontology_routes"]

        vimentin = resolver.resolve_entity(
            "Vimentin protein level",
            {"expected_entity_type": "assay_readout", "context_text": "Vimentin protein level was measured by immunoblot."},
        )
        assert vimentin.cleaner_trace["type_traces"][0]["final_expected_entity_type"] == "protein"

        cdh1 = resolver.resolve_entity(
            "CDH1 mRNA expression",
            {"expected_entity_type": "assay_readout", "context_text": "CDH1 mRNA expression was measured by qPCR."},
        )
        assert cdh1.cleaner_trace["type_traces"][0]["final_expected_entity_type"] == "gene"

        il6 = resolver.resolve_entity(
            "After 48 h IL-6",
            {"expected_entity_type": "assay_readout", "context_text": "After 48 h IL-6 secretion was measured."},
        )
        assert il6.cleaner_trace["cleaned_head_entities"][0]["surface"] == "IL-6"
        assert "48 h" not in il6.cleaner_trace["cleaned_head_entities"][0]["surface"]
        assert il6.cleaner_trace["cleaned_head_entities"][0]["ontology_routes"]

        pathway = LLMEntityCleaner(enabled=True).clean("PI3K/AKT pathway activation")
        assert pathway.cleaned_head_entities[0].surface == "PI3K/AKT signaling pathway"
        assert pathway.cleaned_head_entities[0].entity_type == "pathway"


def test_species_and_granularity_fail_closed():
    human_request = EntityResolutionRequest(surface="IL-6", l1_entity_type_hint="protein", species_context="human")
    human = EntityCandidate(
        surface="IL-6", normalized_surface="il6", candidate_id="H", canonical_id="UniProt:P05231",
        canonical_name="IL6_HUMAN", entity_type="protein", source="external", provider_name="UniProtCandidateProvider",
        is_grounded=True, overall_score=0.85, candidate_species="human",
    )
    assert adjudicate_entity_candidates(human_request, [human]).normalization_status == "accepted_external_grounded"

    bovine = human.model_copy(update={"candidate_id": "B", "canonical_id": "UniProt:P26895", "canonical_name": "IL6_BOVIN", "candidate_species": "bovine"})
    rejected = adjudicate_entity_candidates(human_request, [bovine])
    assert rejected.normalization_status == "rejected_external_candidate"
    assert rejected.selected_candidate.species_match_status == "incompatible"

    tgfb_request = EntityResolutionRequest(surface="TGF-β", l1_entity_type_hint="protein_family", mention_granularity="protein_family")
    tgfb1 = EntityCandidate(
        surface="TGF-β", normalized_surface="tgfb1", candidate_id="T", canonical_id="UniProt:P01137",
        canonical_name="TGFB1", entity_type="protein", source="external", provider_name="UniProtCandidateProvider",
        is_grounded=True, overall_score=0.95,
    )
    tgfb_result = adjudicate_entity_candidates(tgfb_request, [tgfb1])
    assert tgfb_result.normalization_status == "ambiguous_external_candidate"
    assert tgfb_result.selected_candidate.granularity_status == "narrower"


def test_resolved_endpoint_propagates_to_observation_and_merged_graph():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifacts = root / "artifacts"
        artifacts.mkdir()
        row = {
            "observation_id": "O1", "claim_id": "C1", "evidence_id": "E1", "paper_id": "P1",
            "subject_raw": "drug", "subject_canonical_id": "CHEM:D", "subject_canonical_name": "Drug",
            "subject_normalization_status": "resolved", "subject_resolution_decision_id": "O1:subject",
            "object_raw": "target", "object_canonical_id": "GENE:T", "object_canonical_name": "Target",
            "object_normalization_status": "resolved", "object_resolution_decision_id": "O1:object",
            "relation_family": "regulation", "polarity_type": "effect", "direction": "increase",
            "evidence_sentence": "Drug increases Target.", "canonical_graph_eligible": True,
            "allow_high_confidence_graph_use": True,
        }
        (artifacts / "l2_abstract_observations.json").write_text(json.dumps([row]))
        result = build_merged_evidence_graph_from_run_artifacts(root, include_fulltext=False, include_hypotheses=False)
        subject_edges = [e for e in result["edges"] if e["edge_type"] == "observation_subject_entity"]
        object_edges = [e for e in result["edges"] if e["edge_type"] == "observation_object_entity"]
        assert subject_edges[0]["attributes"]["subject_canonical_id"] == "CHEM:D"
        assert object_edges[0]["attributes"]["object_canonical_id"] == "GENE:T"
        assert result["contract_report"]["observation_to_graph_propagation_failures"] == 0

        row["subject_canonical_id"] = ""
        (artifacts / "l2_abstract_observations.json").write_text(json.dumps([row]))
        failed = build_merged_evidence_graph_from_run_artifacts(root, include_fulltext=False, include_hypotheses=False)
        assert failed["contract_report"]["resolved_endpoint_missing_observation_canonical_id_failures"] == 1
