from code_engine.normalization.core_eligibility import core_graph_eligibility
from code_engine.normalization.intervention_semantics import apply_evidence_semantics
from code_engine.normalization.composite_endpoints import decompose_endpoint


def _base(**overrides):
    row = {
        "observation_id": "O1",
        "paper_id": "P1",
        "subject_raw": "X",
        "subject_canonical_id": "GENE:X",
        "subject_canonical_name": "X",
        "subject_normalization_status": "resolved",
        "object_raw": "Y",
        "object_canonical_id": "GO:Y",
        "object_canonical_name": "Y",
        "object_normalization_status": "resolved",
        "relation_raw": "increases",
        "relation_family": "positive_regulation",
        "direction": "positive",
        "graph_observation_eligible": True,
        "evidence_sentence": "X increases Y.",
    }
    row.update(overrides)
    return row


def test_direct_causal_positive_enters_strict_core():
    row = apply_evidence_semantics(_base())
    gate = core_graph_eligibility(row)
    assert row["scientific_edge_layer"] == "strict_causal_core"
    assert row["derived_causal_sign"] == 1
    assert gate["eligible"] is True
    assert gate["sign"] == 1


def test_loss_of_function_inverts_observed_decrease_to_positive_causal_direction():
    row = apply_evidence_semantics(_base(
        subject_raw="Irf1",
        subject_canonical_id="EntrezGene:3659",
        subject_canonical_name="IRF1",
        object_raw="cell migration",
        object_canonical_id="GO:0016477",
        object_canonical_name="cell migration",
        relation_raw="RNAi-mediated ablation of ... reduces",
        relation_family="negative_regulation",
        direction="negative",
        evidence_sentence="RNAi-mediated ablation of Irf1 reduces cell migration.",
    ))
    gate = core_graph_eligibility(row)
    assert row["evidence_design"] == "loss_of_function"
    assert row["derived_causal_sign"] == 1
    assert row["causal_direction_provenance"] == "loss_of_function_sign_inversion"
    assert gate["eligible"] is True
    assert gate["formal_relation"] == "increases"


def test_loss_of_function_observed_increase_derives_negative():
    row = apply_evidence_semantics(_base(
        subject_raw="X",
        relation_raw="knockdown of X increases",
        relation_family="positive_regulation",
        direction="positive",
        evidence_sentence="Knockdown of X increases Y.",
    ))
    assert row["derived_causal_sign"] == -1
    assert row["causal_direction_provenance"] == "loss_of_function_sign_inversion"


def test_gain_of_function_direction_matches_observed_outcome():
    increased = apply_evidence_semantics(_base(
        subject_raw="X",
        relation_raw="overexpression of X increases",
        direction="positive",
        evidence_sentence="Overexpression of X increases Y.",
    ))
    decreased = apply_evidence_semantics(_base(
        subject_raw="X",
        relation_raw="overexpression of X decreases",
        direction="negative",
        evidence_sentence="Overexpression of X decreases Y.",
    ))
    assert increased["derived_causal_sign"] == 1
    assert decreased["derived_causal_sign"] == -1


def test_intervention_condition_endpoint_is_retained_but_not_core():
    row = apply_evidence_semantics(_base(
        subject_raw="CCAT-1-silenced colon cancer cells",
        subject_canonical_id="RUN:abc",
        subject_canonical_name="CCAT-1-SILENCED COLON CANCER CELLS",
        object_raw="P-AKT",
        object_canonical_id="UniProt:Q60823",
        object_canonical_name="AKT2_MOUSE",
        relation_raw="decreased",
        relation_family="regulation",
        direction="negative",
        evidence_sentence="CCAT-1-silenced colon cancer cells showed decreased P-AKT.",
    ))
    gate = core_graph_eligibility(row)
    assert row["intervention_target"] == "CCAT-1"
    assert row["intervention_type"] == "silencing"
    assert row["sample_context"] == "colon cancer cells"
    assert row["measurement_dimension"] == "phosphorylation"
    assert row["derived_causal_sign"] == 1
    assert row["scientific_edge_layer"] == "causal_reviewable"
    assert gate["eligible"] is False
    assert "endpoint_unresolved_fallback" in gate["reasons"]
    assert "intervention_condition_endpoint" in gate["reasons"]
    assert "unsupported_isoform_projection" in gate["reasons"]


def test_rescue_is_supported_layer_and_not_default_strict_core():
    row = apply_evidence_semantics(_base(
        subject_raw="Overexpressed FLOT2",
        subject_canonical_id="EntrezGene:2319",
        subject_canonical_name="FLOT2",
        object_raw="metastasis",
        object_canonical_id="EFO:0009708",
        object_canonical_name="metastasis",
        relation_raw="could restore the inhibition effects of miR-185-5p mimic on",
        relation_family="negative_regulation",
        direction="negative",
        evidence_sentence="Overexpressed FLOT2 could restore the inhibition effects of miR-185-5p mimic on metastasis.",
    ))
    gate = core_graph_eligibility(row)
    assert row["scientific_edge_layer"] == "rescue_supported"
    assert row["derived_causal_sign"] == 1
    assert row["inference_type"] == "rescue_inferred"
    assert gate["eligible"] is False


def test_association_and_differential_expression_do_not_enter_causal_core():
    association = apply_evidence_semantics(_base(
        relation_raw="association",
        relation_family="association_only",
        direction="unknown",
        evidence_sentence="X is associated with Y.",
    ))
    differential = apply_evidence_semantics(_base(
        subject_raw="EphB1",
        subject_canonical_id="EntrezGene:2047",
        subject_canonical_name="EPHB1",
        object_raw="NSCLC biopsies",
        object_canonical_id="RUN:sample",
        object_canonical_name="NSCLC biopsies",
        relation_raw="increased expression of EphB1 was detected in NSCLC biopsies",
        relation_family="positive_regulation",
        direction="positive",
        evidence_sentence="Increased expression of EphB1 was detected in NSCLC biopsies compared to non-cancer controls.",
    ))
    assert association["scientific_edge_layer"] == "association"
    assert differential["scientific_edge_layer"] == "differential_expression"
    assert core_graph_eligibility(association)["eligible"] is False
    diff_gate = core_graph_eligibility(differential)
    assert diff_gate["eligible"] is False
    assert "sample_context_endpoint" in diff_gate["reasons"]
    assert "non_causal_evidence_design" in diff_gate["reasons"]


def test_phosphorylated_prefix_decomposition_preserves_dimension():
    p_akt = decompose_endpoint("P-AKT")
    p_myc = decompose_endpoint("P-C-MYC")
    assert p_akt.measurement_dimension == "phosphorylation"
    assert p_akt.measured_entity_raw == "AKT"
    assert p_myc.measurement_dimension == "phosphorylation"
    assert p_myc.measured_entity_raw == "C-MYC"
