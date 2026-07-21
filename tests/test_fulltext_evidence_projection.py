from code_engine.fulltext.evidence_projection import (
    aggregate_canonical_edges,
    bind_observation_context,
    build_conflict_bundles,
    build_reasoning_chain,
    readjudicate_entity,
    species_compatibility,
)
from code_engine.fulltext.profiles import ABSTRACT_L2_PROJECTION, FULLTEXT_EVIDENCE_PROJECTION
from code_engine.normalization.candidates import EntityCandidate
from code_engine.normalization.formal_relations import normalize_formal_relation


def candidate(cid="EntrezGene:100", name="COPS8", species="human"):
    return EntityCandidate(
        surface="COPS8", normalized_surface="cops8", candidate_id=cid,
        canonical_id=cid, canonical_name=name, entity_type="gene", source="curated",
        provider_name="LocalCuratedProvider", match_type="exact", match_score=1,
        type_score=1, source_reliability=1, context_score=1, overall_score=.99,
        final_score=.99, normalized_string_score=1, label_match_score=1,
        is_grounded=True, is_curated=True, curated_registry_support=True,
        provider_exact_match=True, candidate_species=species, candidate_granularity="gene",
        mention_granularity="gene", granularity_match_score=1,
    )


def base(**values):
    row = {
        "observation_id": "ft1", "claim_id": "ft1", "paper_id": "P1", "pmid": "1",
        "subject_raw": "COPS8", "subject": "COPS8", "subject_canonical_id": "EntrezGene:100",
        "subject_canonical_name": "COPS8", "subject_normalization_status": "resolved",
        "subject_endpoint": {"canonical_id": "EntrezGene:100", "canonical_name": "COPS8", "resolution_status": "resolved"},
        "object_raw": "EMT", "object": "EMT", "object_canonical_id": "GO:0001837",
        "object_canonical_name": "EMT", "object_normalization_status": "resolved",
        "object_endpoint": {"canonical_id": "GO:0001837", "canonical_name": "EMT", "resolution_status": "resolved"},
        "relation_raw": "increases", "relation_family": "positive_regulation", "direction": "positive",
        "graph_observation_eligible": True, "evidence_sentence": "Overexpression of COPS8 increases EMT markers.",
        "section_type": "results", "chunk_id": "chunk1",
    }
    row.update(values)
    return row


def test_abstract_and_fulltext_profiles_are_scientifically_separate():
    assert ABSTRACT_L2_PROJECTION.entity_decision_scope == "candidate"
    assert FULLTEXT_EVIDENCE_PROJECTION.entity_decision_scope == "final_for_fulltext"
    assert FULLTEXT_EVIDENCE_PROJECTION.requires_reasoning_chain_for_intervention is True


def test_fulltext_context_overrules_wrong_species_prior_and_preserves_lineage():
    old = base(subject_canonical_id="UniProt:DUSP3_CAPHI", subject_canonical_name="DUSP3_CAPHI")
    updated, lineage = readjudicate_entity(old, "subject", {"species": "human", "species_source": "cell_line_registry"}, [], None)
    assert updated["subject_canonical_id"] == ""
    assert lineage["previous_canonical_id"] == "UniProt:DUSP3_CAPHI"
    assert lineage["fulltext_entity_decision"] == "ambiguous"
    assert lineage["changed"] is True
    assert lineage["adjudication_profile"] == "fulltext_evidence_projection"


def test_fulltext_cached_candidate_can_change_canonical_id():
    old = base(subject_canonical_id="UniProt:TIPE_DROME", subject_canonical_name="TIPE_DROME")
    human = candidate("EntrezGene:51330", "TNFAIP8", "human").model_copy(update={"surface": "COPS8"})
    updated, lineage = readjudicate_entity(old, "subject", {"species": "human"}, [human], None)
    assert updated["subject_canonical_id"] == "EntrezGene:51330"
    assert lineage["changed"] is True
    assert lineage["species_compatibility"] == "compatible"


def test_species_unknown_does_not_accept_species_specific_top_hit():
    updated, lineage = readjudicate_entity(base(subject_canonical_id=""), "subject", {}, [candidate()], None)
    assert updated["subject_canonical_id"] == ""
    assert lineage["fulltext_entity_decision"] == "ambiguous"
    assert species_compatibility("mouse", "human", {"source": "ortholog-registry"})[0] == "ortholog_projected"


def test_context_binding_is_observation_scoped_and_chain_enriched():
    context, audit = bind_observation_context(
        base(context={"cell_line": "HCT116", "species": "human"}),
        {"consolidated_context": {"tissue": [{"value": "colon"}]}},
        {"experimental_system": {"species": "mouse", "cell_line": "CT26"}},
    )
    assert context["species"] == "human"
    assert context["cell_line"] == "HCT116"
    assert context["tissue"] == "colon"
    assert any(x["source"] == "evidence_span" for x in audit)


def test_cops8_gof_and_lof_share_authoritative_positive_edge():
    gof, gof_chain = build_reasoning_chain(base(), {"species": "human"}, None)
    lof, lof_chain = build_reasoning_chain(base(
        observation_id="ft2", claim_id="ft2", chunk_id="chunk2",
        relation_raw="silencing COPS8 decreases", relation_family="negative_regulation", direction="negative",
        evidence_sentence="Silencing COPS8 decreases EMT markers and blocks EMT.",
    ), {"species": "human"}, None)
    assert gof["derived_causal_sign"] == lof["derived_causal_sign"] == 1
    assert gof["final_formal_polarity"] == lof["final_formal_polarity"] == "positive"
    assert gof_chain["chain_complete"] and lof_chain["chain_complete"]
    for row in (gof, lof):
        row.update(formal_core_graph_eligible=True, conflict_eligible=True)
    edges, _ = aggregate_canonical_edges([gof, lof])
    assert len(edges) == 1
    assert edges[0]["evidence_count"] == 2
    bundles = build_conflict_bundles(edges)
    assert bundles[0]["adjudication"] == "concordant_support"


def test_derived_sign_cannot_be_overwritten_by_lexical_projection():
    relation = normalize_formal_relation({"derived_causal_sign": 1, "core_projection_relation": "decreases"})
    assert relation.relation == "increases"


def test_polarity_not_part_of_conflict_bundle_identity():
    common = {
        "subject_canonical_id": "G:X", "object_canonical_id": "GO:Y", "relation_axis": "regulation",
        "measurement_dimension": "phenotype", "context_class": "ctx", "conflict_eligible": True,
        "evidence_count": 1,
    }
    bundles = build_conflict_bundles([
        {**common, "canonical_edge_id": "pos", "polarity": "positive"},
        {**common, "canonical_edge_id": "neg", "polarity": "negative"},
    ])
    assert len(bundles) == 1
    assert bundles[0]["adjudication"] == "true_conflict_candidate"


def test_same_paper_different_endpoint_is_not_deduplicated():
    one = base(formal_core_graph_eligible=True, conflict_eligible=True, final_formal_polarity="positive", measurement_dimension="phenotype", evidence_family_id="ef1")
    two = {**one, "observation_id": "ft2", "object_canonical_id": "GO:MIGRATION", "object_raw": "migration"}
    edges, merges = aggregate_canonical_edges([one, two])
    assert len(edges) == 2
    assert merges == []
