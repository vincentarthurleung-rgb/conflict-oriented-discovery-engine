import json
import tempfile
from pathlib import Path

from code_engine.evidence_graph.builders import build_merged_evidence_graph_from_run_artifacts
from code_engine.normalization.core_eligibility import core_graph_eligibility
from code_engine.normalization.composite_endpoints import decompose_endpoint, projection_relation
from code_engine.workflow.steps import run_l2_abstract_step


class RouteClient:
    def __init__(self, records):
        self.records = records
        self.calls = 0
        self.network_call_cost = 1

    def search(self, surface, request=None, ontologies=None):
        self.calls += 1
        return self.records


def test_endpoint_decomposition_rules_are_conservative():
    assert decompose_endpoint("Snail expression").measured_entity_raw == "Snail"
    assert decompose_endpoint("Snail expression").measurement_dimension == "expression"
    assert decompose_endpoint("E-cadherin expression").measured_entity_raw == "E-cadherin"

    vimentin = decompose_endpoint("Vimentin protein level")
    assert vimentin.measured_entity_raw == "Vimentin"
    assert vimentin.measurement_dimension == "abundance"
    assert vimentin.molecular_layer == "protein"

    assert decompose_endpoint("mTOR phosphorylation").measurement_dimension == "phosphorylation"
    phospho = decompose_endpoint("phosphorylated AKT")
    assert phospho.measured_entity_raw == "AKT"
    assert phospho.measurement_state == "phosphorylated"

    viability = decompose_endpoint("cell viability")
    assert viability.endpoint_decomposition_status == "unsupported"
    assert viability.non_molecular_readout is True

    absorbance = decompose_endpoint("absorbance at 570 nm")
    assert absorbance.endpoint_decomposition_status == "unsupported"
    assert absorbance.non_molecular_readout is True


def test_projection_rules_preserve_measurement_semantics():
    endpoint = decompose_endpoint("Snail expression").to_endpoint_fields()
    assert projection_relation({"relation_raw": "increases"}, endpoint) == ("increases_expression_of", None)
    assert projection_relation({"relation_raw": "decreases"}, endpoint) == ("decreases_expression_of", None)

    phospho = decompose_endpoint("mTOR phosphorylation").to_endpoint_fields()
    assert projection_relation({"relation_raw": "increases"}, phospho) == ("increases_phosphorylation_of", None)

    unsupported = dict(endpoint, measurement_dimension="other")
    assert projection_relation({"relation_raw": "associated with"}, unsupported)[1] == "relation_projection_not_supported"


def test_l2_composite_endpoint_projection_propagates_measured_entity_to_graph():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifacts = root / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "general_biomedical"}))
        (artifacts / "semantic_search_intent.json").write_text(json.dumps({
            "seed_triple": {
                "subject": {"name": "TGF-β"},
                "object": {"name": "Snail expression"},
                "relation": {"name": "increases", "family": "increases"},
                "context": {},
            }
        }))
        (artifacts / "intake.json").write_text(json.dumps({}))
        claim = {
            "claim_id": "C1",
            "evidence_id": "E1",
            "paper_id": "P1",
            "subject_raw": "TGF-β",
            "subject_type": "protein_family",
            "object_raw": "Snail expression",
            "object_type": "assay_readout",
            "relation_raw": "increases",
            "relation_family": "increases",
            "direction": "positive",
            "evidence_sentence": "TGF-β increases Snail expression.",
        }
        (artifacts / "abstract_l1_claims.jsonl").write_text(json.dumps(claim) + "\n")
        registry = root / "registry.json"
        registry.write_text(json.dumps({
            "version": "test_composite_endpoint_registry",
            "entities": [
                {
                    "canonical_id": "FAMILY:TGFB",
                    "canonical_name": "TGF-beta family",
                    "entity_type": "protein_family",
                    "semantic_level": "protein_family",
                    "aliases": ["TGF-β", "TGF-beta"],
                    "relations": [],
                },
                {
                    "canonical_id": "EntrezGene:6615",
                    "canonical_name": "SNAI1",
                    "entity_type": "gene",
                    "semantic_level": "gene_or_protein",
                    "aliases": ["Snail", "SNAI1"],
                    "relations": [],
                },
            ],
        }))

        run_l2_abstract_step(
            run_dir=root,
            execute=True,
            network=True,
            api=False,
            entity_network_lookup=True,
            entity_registry_path=registry,
        )

        observations = json.loads((artifacts / "l2_abstract_observations.json").read_text())
        obs = observations[0]
        assert obs["object_raw"] == "Snail expression"
        assert obs["object_canonical_id"] == ""
        assert obs["object_endpoint"]["measured_entity_raw"] == "Snail"
        assert obs["object_endpoint"]["measured_entity_canonical_id"] == "EntrezGene:6615"
        assert obs["object_endpoint"]["measurement_dimension"] == "expression"
        assert obs["core_projection_status"] == "projected"
        assert obs["core_projection_relation"] == "increases_expression_of"
        assert obs["formal_core_graph_eligible"] is True
        assert obs["projected_object_canonical_id"] == "EntrezGene:6615"
        core_rows = [json.loads(line) for line in (artifacts / "l2_core_graph_observations.jsonl").read_text().splitlines() if line.strip()]
        assert len(core_rows) == 1
        assert core_rows[0]["object_canonical_id"] == "EntrezGene:6615"
        assert core_rows[0]["measurement_dimension"] == "expression"

        graph = build_merged_evidence_graph_from_run_artifacts(root, include_fulltext=False, include_hypotheses=False)
        projected = [edge for edge in graph["edges"] if edge["edge_type"] == "projected_core_relation"]
        assert projected
        assert projected[0]["attributes"]["object_canonical_id"] == "EntrezGene:6615"
        assert projected[0]["attributes"]["relation"] == "increases_expression_of"
        assert graph["contract_report"]["observation_to_graph_propagation_failures"] == 0


def test_plain_resolved_registered_relation_enters_formal_core_gate():
    obs = {
        "observation_id": "O1",
        "paper_id": "P1",
        "subject_raw": "Drug",
        "subject_canonical_id": "CHEM:DRUG",
        "subject_canonical_name": "Drug",
        "subject_normalization_status": "resolved",
        "object_raw": "Target",
        "object_canonical_id": "GENE:TARGET",
        "object_canonical_name": "Target",
        "object_normalization_status": "resolved",
        "relation_family": "activation",
        "direction": "positive",
        "graph_observation_eligible": True,
    }
    gate = core_graph_eligibility(obs)
    assert gate["eligible"] is True
    assert gate["reason"] == "eligible_and_emitted"


def test_unregistered_projected_relation_has_explicit_exclusion_reason():
    obs = {
        "observation_id": "O1",
        "subject_canonical_id": "CHEM:DRUG",
        "subject_normalization_status": "resolved",
        "object_canonical_id": "",
        "object_normalization_status": "resolved",
        "object_endpoint": {
            "endpoint_decomposition_status": "decomposed",
            "measured_entity_canonical_id": "GENE:TARGET",
            "measured_entity_canonical_name": "Target",
            "measurement_dimension": "expression",
            "core_projection_status": "projected",
            "core_projection_relation": "unsupported_expression_relation",
        },
        "core_projection_status": "projected",
        "core_projection_relation": "unsupported_expression_relation",
        "direction": "positive",
        "graph_observation_eligible": True,
    }
    gate = core_graph_eligibility(obs)
    assert gate["eligible"] is False
    assert gate["reason"] == "projection_relation_not_registered"


def test_non_molecular_readout_is_retained_without_forced_resolution():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifacts = root / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "general_biomedical"}))
        (artifacts / "semantic_search_intent.json").write_text(json.dumps({}))
        (artifacts / "intake.json").write_text(json.dumps({}))
        claim = {
            "claim_id": "C1",
            "evidence_id": "E1",
            "paper_id": "P1",
            "subject_raw": "drug",
            "subject_type": "compound",
            "object_raw": "cell viability",
            "object_type": "assay_readout",
            "relation_raw": "reduces",
            "relation_family": "decreases",
            "direction": "negative",
            "evidence_sentence": "The drug reduces cell viability.",
        }
        (artifacts / "abstract_l1_claims.jsonl").write_text(json.dumps(claim) + "\n")
        run_l2_abstract_step(run_dir=root, execute=False, network=False, api=False)
        obs = json.loads((artifacts / "l2_abstract_observations.json").read_text())[0]
        assert obs["retained"] is False or obs["object_endpoint"]["core_projection_reason"] == "non_molecular_readout"
        assert obs["object_endpoint"]["measured_entity_canonical_id"] is None
