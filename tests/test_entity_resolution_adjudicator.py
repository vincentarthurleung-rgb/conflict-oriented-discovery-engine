import unittest

from code_engine.graph.abstract_conflict_screening import _usable
from code_engine.normalization.adjudicator import adjudicate_entity_candidates
from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest


def candidate(
    cid="GENE:1",
    score=.9,
    *,
    name="GENE1",
    etype="gene",
    curated=False,
    grounded=True,
    provider="MyGeneCandidateProvider",
    llm=False,
    species=None,
    granularity=None,
    aliases=None,
    ortholog=None,
):
    supporting_context = {}
    if ortholog:
        supporting_context["ortholog_provenance"] = ortholog
    return EntityCandidate(
        surface=name,
        normalized_surface=name.casefold(),
        candidate_id=f"{provider}:{cid}",
        canonical_id=None if llm else cid,
        canonical_name=None if llm else name,
        entity_type=etype,
        source="external_provider",
        provider_name=provider,
        match_score=score,
        type_score=.9,
        source_reliability=.9,
        context_score=.5,
        overall_score=score,
        is_curated=curated,
        is_grounded=grounded,
        is_llm_suggested=llm,
        candidate_species=species,
        candidate_granularity=granularity,
        aliases=aliases or [],
        supporting_context=supporting_context,
    )


class AdjudicatorTests(unittest.TestCase):
    def request(self, **kwargs):
        base = {"surface": "GENE1", "l1_entity_type_hint": "gene", "species_context": "human", "mention_granularity": "gene"}
        base.update(kwargs)
        return EntityResolutionRequest(**base)

    def test_three_state_basics(self):
        accepted = adjudicate_entity_candidates(self.request(), [candidate(species="human", granularity="gene")])
        self.assertEqual(accepted.decision, "accepted")
        self.assertEqual(accepted.normalization_status, "accepted_external_grounded")
        self.assertTrue(accepted.allow_high_confidence_graph_use)

        ambiguous = adjudicate_entity_candidates(self.request(), [candidate(score=.58, species=None, granularity="gene")])
        self.assertEqual(ambiguous.normalization_status, "ambiguous_external_candidate")
        self.assertTrue(ambiguous.available_for_review)
        self.assertFalse(ambiguous.allow_high_confidence_graph_use)

        rejected = adjudicate_entity_candidates(self.request(surface="25 nM"), [candidate()])
        self.assertEqual(rejected.normalization_status, "rejected_external_candidate")
        self.assertIn("rejected_measurement_only", rejected.hard_exclusions)

    def test_double_threshold_and_hard_reject_priority(self):
        policy = {"accept_threshold": .82, "ambiguous_threshold": .55, "high_confidence_threshold": .82, "external_grounded_min_score": .75}
        self.assertEqual(adjudicate_entity_candidates(self.request(), [candidate(score=.9, species="human", granularity="gene")], policy).decision, "accepted")
        self.assertEqual(adjudicate_entity_candidates(self.request(), [candidate(score=.57, species=None, granularity="gene")], policy).decision, "ambiguous")
        self.assertEqual(adjudicate_entity_candidates(self.request(), [candidate(score=.3, species=None, granularity="gene")], policy).decision, "rejected")
        hard = adjudicate_entity_candidates(self.request(l1_entity_type_hint="gene"), [candidate(score=.95, etype="compound", name="drug")], policy)
        self.assertEqual(hard.decision, "rejected")
        self.assertIn("rejected_type_incompatible", hard.hard_exclusions)

    def test_species_semantics(self):
        exact = adjudicate_entity_candidates(self.request(species_context="human"), [candidate(species="human", granularity="gene")])
        self.assertIn("accepted_species_exact", exact.decision_reasons)

        ortholog = adjudicate_entity_candidates(
            self.request(species_context="mouse"),
            [candidate(species="human", granularity="gene", ortholog={"source": "registry", "mapping_id": "M1"})],
        )
        self.assertEqual(ortholog.decision, "accepted")
        self.assertIn("accepted_ortholog_supported", ortholog.decision_reasons)

        unspecified = adjudicate_entity_candidates(self.request(species_context="mouse"), [candidate(score=.6, species=None, granularity="gene")])
        self.assertEqual(unspecified.decision, "ambiguous")
        self.assertIn("ambiguous_species_unspecified", unspecified.decision_reasons)

        incompatible = adjudicate_entity_candidates(self.request(species_context="mouse"), [candidate(species="human", granularity="gene")])
        self.assertEqual(incompatible.decision, "rejected")
        self.assertIn("rejected_species_incompatible", incompatible.hard_exclusions)

    def test_granularity_and_measurement_dimension(self):
        phospho = adjudicate_entity_candidates(
            self.request(surface="phospho-AKT", l1_entity_type_hint="protein", mention_granularity="protein_family", relation="increases_phosphorylation_of", measurement_dimension="phosphorylation"),
            [candidate(cid="GENE:AKT1", name="AKT1", etype="protein", score=.78, species="human", granularity="protein")],
        )
        self.assertEqual(phospho.decision, "ambiguous")
        self.assertIn("ambiguous_granularity_narrower", phospho.decision_reasons)

        pathway = adjudicate_entity_candidates(
            self.request(surface="PI3K/AKT pathway", l1_entity_type_hint="pathway", mention_granularity="pathway"),
            [candidate(name="AKT1", etype="gene", species="human", granularity="gene")],
        )
        self.assertEqual(pathway.decision, "rejected")
        self.assertIn("rejected_granularity_incompatible", pathway.hard_exclusions)

    def test_relation_aware_type(self):
        expression = adjudicate_entity_candidates(
            self.request(relation="increases_expression_of", l1_entity_type_hint="gene", mention_granularity="gene"),
            [candidate(etype="gene", species="human", granularity="gene")],
        )
        self.assertEqual(expression.decision, "accepted")

        phenotype_gene = adjudicate_entity_candidates(
            self.request(surface="cell proliferation", relation="inhibits_proliferation", l1_entity_type_hint="phenotype", mention_granularity="phenotype"),
            [candidate(etype="gene", species="human", granularity="gene")],
        )
        self.assertEqual(phenotype_gene.decision, "rejected")
        self.assertIn("rejected_relation_type_incompatible", phenotype_gene.hard_exclusions)

        weak = adjudicate_entity_candidates(
            self.request(relation="increases_expression_of", l1_entity_type_hint="gene_or_protein", mention_granularity="gene_or_protein"),
            [candidate(score=.82, etype="pathway", species="human", granularity="pathway")],
        )
        self.assertEqual(weak.decision, "ambiguous")
        self.assertIn("ambiguous_relation_type_weak", weak.decision_reasons)

    def test_provider_agreement_margin_and_downstream_gate(self):
        agreed = adjudicate_entity_candidates(
            self.request(),
            [
                candidate(cid="GENE:1", score=.76, species="human", granularity="gene", provider="MyGeneCandidateProvider"),
                candidate(cid="GENE:1", score=.72, species="human", granularity="gene", provider="UniProtCandidateProvider"),
            ],
        )
        self.assertEqual(agreed.decision, "accepted")
        self.assertIn("accepted_multi_provider_agreement", agreed.decision_reasons)

        close = adjudicate_entity_candidates(
            self.request(),
            [
                candidate(cid="GENE:1", score=.9, species="human", granularity="gene"),
                candidate(cid="GENE:2", score=.89, species="human", granularity="gene", provider="UniProtCandidateProvider"),
            ],
        )
        self.assertEqual(close.decision, "ambiguous")
        self.assertIn("ambiguous_provider_disagreement", close.decision_reasons)
        self.assertFalse(close.allow_high_confidence_graph_use)
        self.assertFalse(_usable({"normalization_status": "ambiguous_external_candidate", "allow_high_confidence_graph_use": False}))
        self.assertFalse(_usable({"normalization_status": "rejected_external_candidate", "allow_high_confidence_graph_use": False}))


if __name__ == "__main__":
    unittest.main()
