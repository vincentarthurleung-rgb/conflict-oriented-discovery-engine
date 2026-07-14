from code_engine.fulltext.experimental_parameters import extract_parameters
from code_engine.fulltext.reasoning_trace import (
    _mention_candidates,
    link_claims_to_evidence_chains,
    score_claim_chain_link,
    unlinked_reason_for_claim,
)


def _types(text: str) -> dict[str, str]:
    return {row.raw_text: row.parameter_type for row in extract_parameters(text, context=text)}


def test_parameter_classifier_keeps_wavelength_out_of_dose():
    observed = _types(
        "10 mg/kg ketamine, 10 μM ketamine, treated for 24 h, 24 h after treatment, "
        "absorbance at 570 nm, OD570, 37 °C, 12000 ×g, p < 0.05"
    )
    assert observed["10 mg/kg"] == "dose"
    assert observed["10 μM"] == "concentration"
    assert observed["24 h"] in {"duration", "timepoint"}
    assert observed["570 nm"] == "wavelength"
    assert observed["OD570"] == "assay_readout"
    assert observed["37 °C"] == "temperature"
    assert observed["12000 ×g"] == "centrifugation_speed"
    assert observed["p < 0.05"] == "statistical_value"
    assert observed["570 nm"] != "dose"


def test_entity_mention_extraction_filters_parameters_and_keeps_entities():
    assert _mention_candidates("ketamine 10 mg/kg", role="intervention_agent")[0]["mention_text"] == "ketamine"
    mentions = _mention_candidates("mTOR phosphorylation measured at 570 nm", role="assay_endpoint")
    assert any(row["mention_text"] == "mTOR phosphorylation" for row in mentions)
    assert all("570" not in row["mention_text"] for row in mentions)


def _claim(claim_id: str, subject: str, obj: str, sentence: str) -> dict:
    return {
        "claim_id": claim_id,
        "paper_id": "P1",
        "subject": subject,
        "object": obj,
        "predicate": "regulates",
        "evidence_sentence": sentence,
        "source_scope": "fulltext",
    }


def _chain(chain_id: str, claim_id: str, agent: str, endpoint: str, direction: str, sentence: str) -> dict:
    return {
        "chain_id": chain_id,
        "claim_id": claim_id,
        "paper_id": "P1",
        "source_document_id": "P1",
        "validation_status": "valid",
        "interventions": [{"agent_raw": agent}],
        "measurements": [{"endpoint": endpoint, "parameters": [{"raw_text": "570 nm", "parameter_type": "wavelength"}]}],
        "observed_results": [{"endpoint": endpoint, "direction": direction, "effect_description": sentence}],
        "author_interpretation": {"text": sentence},
        "evidence_anchors": [{"anchor_id": f"a_{chain_id}", "sentence_id": f"s_{chain_id}", "sentence_text": sentence}],
    }


def test_linking_is_scored_multiway_and_not_fixed_confidence():
    claims = [
        _claim("c1", "TGF-β1", "EMT", "TGF-β1 increased EMT markers."),
        _claim("c2", "TGF-β1", "migration", "TGF-β1 increased migration."),
    ]
    chains = [
        _chain("ch1", "c1", "TGF-β1", "EMT markers", "increase", "TGF-β1 increased EMT markers."),
        _chain("ch2", "c1", "TGF-β1", "migration", "increase", "TGF-β1 increased migration."),
    ]
    links = link_claims_to_evidence_chains(claims, chains)
    assert len([row for row in links if row["claim_id"] == "c1"]) >= 1
    assert len([row for row in links if row["chain_id"] == "ch2"]) >= 1
    assert {row["link_confidence"] for row in links} != {0.75}
    assert all(row["score_components"] for row in links)


def test_unrelated_same_paper_below_threshold_can_remain_unlinked():
    claim = _claim("c3", "PD-L1", "immune evasion", "PD-L1 promoted immune evasion.")
    chain = _chain("ch3", "other", "ketamine", "cell viability", "decrease", "Ketamine decreased cell viability.")
    score = score_claim_chain_link(claim, chain)
    assert score["score"] < 0.34
    reason = unlinked_reason_for_claim(claim, [score])
    assert reason["primary_reason"] in {"insufficient_matching_evidence", "no_compatible_chain"}

