import tempfile
from pathlib import Path

from code_engine.normalization.resolver import ResolverCascade


class FakeOLSClient:
    network_call_cost = 1

    def __init__(self):
        self.calls = 0

    def search(self, surface, request=None, *, ontologies=None):
        self.calls += 1
        if surface.casefold() in {"emt", "epithelial to mesenchymal transition"}:
            return [{
                "obo_id": "GO:0001837",
                "iri": "http://purl.obolibrary.org/obo/GO_0001837",
                "ontology_name": "go",
                "ontology_prefix": "GO",
                "label": "epithelial to mesenchymal transition",
                "exact_synonyms": ["EMT", "epithelial-mesenchymal transition"],
                "description": ["A transition where an epithelial cell becomes mesenchymal."],
            }]
        if surface.casefold() == "hepatocellular carcinoma":
            return [{
                "obo_id": "MONDO:0007256",
                "iri": "http://purl.obolibrary.org/obo/MONDO_0007256",
                "ontology_name": "mondo",
                "ontology_prefix": "MONDO",
                "label": "hepatocellular carcinoma",
                "exact_synonyms": ["HCC"],
                "description": ["A malignant tumor that arises from hepatocytes."],
            }]
        return []


def test_ols_provider_resolves_biological_process_and_disease():
    with tempfile.TemporaryDirectory() as tmp:
        ols = FakeOLSClient()
        resolver = ResolverCascade(
            run_dir=Path(tmp),
            execute=True,
            network_enabled=True,
            entity_network_lookup=True,
            external_clients={"ols": ols},
        )
        emt = resolver.resolve_entity("EMT", {"expected_entity_type": "biological_process"})
        disease = resolver.resolve_entity("hepatocellular carcinoma", {"expected_entity_type": "disease"})
        assert emt.normalization_status == "resolved"
        assert emt.canonical_id == "GO:0001837"
        assert disease.normalization_status == "resolved"
        assert disease.canonical_id == "MONDO:0007256"


def test_non_entity_parameters_are_rejected_before_provider_lookup():
    ols = FakeOLSClient()
    resolver = ResolverCascade(
        execute=True,
        network_enabled=True,
        entity_network_lookup=True,
        external_clients={"ols": ols},
    )
    decision = resolver.resolve_entity("570 nm", {"expected_entity_type": "unknown"})
    assert decision.normalization_status == "rejected"
    assert decision.entity_resolution_status == "not_entity"
    assert ols.calls == 0


def test_external_provider_query_cache_deduplicates_repeated_surface():
    ols = FakeOLSClient()
    resolver = ResolverCascade(
        execute=True,
        network_enabled=True,
        entity_network_lookup=True,
        external_clients={"ols": ols},
    )
    resolver.resolve_entity("EMT", {"expected_entity_type": "biological_process"})
    resolver.resolve_entity("EMT", {"expected_entity_type": "biological_process"})
    assert ols.calls == 1


def test_external_candidate_without_surface_match_fails_closed():
    class NoisyUniProt:
        network_call_cost = 1

        def search(self, surface, request=None):
            return [{
                "provider_record_id": "A0A341B891",
                "canonical_id": "UniProt:A0A341B891",
                "canonical_name": "A0A341B891_NEOAA",
                "normalized_surface": "a0a341b891_neoaa",
                "entity_type": "protein",
                "aliases": ["UNRELATED"],
                "score": 0.82,
            }]

    resolver = ResolverCascade(
        execute=True,
        network_enabled=True,
        entity_network_lookup=True,
        external_clients={"uniprot": NoisyUniProt()},
    )
    decision = resolver.resolve_entity("NOISYFAKE", {"expected_entity_type": "protein"})
    assert decision.entity_resolution_status == "ambiguous_external_candidate"
    assert not decision.allow_high_confidence_graph_use
