"""Offline engineering controls; altered claims are NOT scientific evidence."""
import copy
import json
from pathlib import Path
import socket

import pytest
from pydantic import ValidationError

from code_engine.discovery.ai_review_shadow import (
    AIReview, LABEL, NAMESPACE, REVIEW_FIELDS, bind_review, compare_shadow_pair,
    content_hash, load_bound_packet, persist_shadow, plan_model_reviews,
)
from code_engine.fulltext.evidence_projection import project_fulltext_run
from code_engine.fulltext.experimental_projection_handoff import prepare_experimental_handoff
from code_engine.normalization.core_eligibility import core_graph_eligibility
from code_engine.normalization.experimental_admission import experimental_admission_blocks

BASE=Path(__file__).resolve().parents[1]/"runs/20261016_code_comparable_evidence_discovery_review_integration_seen_offline"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def fail(*args,**kwargs):raise AssertionError("network_forbidden_in_shadow_tests")
    for name in ("connect","connect_ex"):monkeypatch.setattr(socket.socket,name,fail)
    monkeypatch.setattr(socket,"getaddrinfo",fail)
    monkeypatch.setattr(socket,"create_connection",fail)


@pytest.fixture
def bundles(tmp_path):
    prompt=tmp_path/"prompt.txt";prompt.write_text("SYNTHETIC ENGINEERING CONTROL PROMPT; NOT A SCIENTIFIC REVIEW")
    return [load_bound_packet(BASE/p/"evidence_packet.json",prompt,BASE/p/"v3_core_draft.json") for p in ("PMC4024011","PMC7749157")]


def control_review(b):
    """Artificial supported judgments exercise software only, never persisted as science."""
    refs=[b.packet["evidence_spans"][0]["evidence_span_id"]]
    def facet(v):return {"value":v,"evidence_refs":refs,"uncertainty":"SYNTHETIC TEST CONTROL; not a scientific judgment"}
    return {"packet_id":b.packet["packet_id"],"input_hashes":b.input_hashes,
        "V3_observation_id":b.observation_id,"Core_revision_id":b.revision_id,
        "reviewer_kind":"interactive_assistant","model_family":"SYNTHETIC_TEST_CONTROL",
        "model_identity_basis":"Synthetic unit-test control, not a real model review.",
        "independence_status":"shared_context_not_independent","independence_limitations":"No independent assessment; synthetic software control.",
        "prompt_version":"TEST_ONLY","reviewed_at":"2026-10-17T00:00:00+00:00",
        "fields":[{"field":k,"verdict":"SUPPORTED","evidence_refs":refs,"reasoning_summary":"Synthetic control to exercise this field; not scientific evidence.","uncertainty":"TEST ONLY; no scientific conclusion"} for k in REVIEW_FIELDS],
        "claim":{"measured_entity":facet("HIF-1α"),"endpoint":facet("protein abundance"),"measurement_type":facet("Western blot"),
            "factor":facet("reduced oxygen exposure"),"study_design":"interventional","direction":"positive",
            "direction_evidence_refs":refs,"direction_interpretation":"Synthetic control direction; not a scientific result.",
            "context":{"system":facet(b.packet["experiment"]["cells"]),"time":facet(b.packet["experiment"]["factor"])},
            "measurement_classification_status":"existing_contract"}}


def test_real_sources_bind_and_control_pair_is_non_authoritative(bundles):
    reviews=[bind_review(b,control_review(b)) for b in bundles]
    result=compare_shadow_pair(*bundles,*reviews)
    assert result["alignment_status"]=="DIRECTIONALLY_CONCORDANT_CONTEXT_DIVERGENT"
    assert result["hypotheses"]==[] and not result["provisional_contradiction"]
    assert result["namespace"]==NAMESPACE and result["authority_label"]==LABEL
    assert result["derived_causal_sign"] is None
    assert not result["production_candidate_qualification_invoked"]


@pytest.mark.parametrize("change",["missing_field","duplicate_field","unknown_ref","stale_packet","stale_revision","global_pass","false_independence","naive_timestamp"])
def test_invalid_or_unbound_reviews_fail(bundles,change):
    b=bundles[0];r=control_review(b)
    if change=="missing_field":r["fields"].pop()
    if change=="duplicate_field":r["fields"][-1]=r["fields"][0]
    if change=="unknown_ref":r["fields"][0]["evidence_refs"]=["TEST:unknown"]
    if change=="stale_packet":r["input_hashes"]={**r["input_hashes"],"packet":"0"*64}
    if change=="stale_revision":r["Core_revision_id"]="TEST:stale"
    if change=="global_pass":r["PASS"]=True
    if change=="false_independence":r["independence_status"]="separate_model_diagnostic_only"
    if change=="naive_timestamp":r["reviewed_at"]="2026-10-17T00:00:00"
    with pytest.raises(ValueError):bind_review(b,r)


@pytest.mark.parametrize("flag",["scientific_authorization","human_gold","strict_core_eligible","formal_core_graph_eligible"])
@pytest.mark.parametrize("value",[True,"false",0])
def test_schema_cannot_confer_or_coerce_formal_authority(bundles,flag,value):
    r=control_review(bundles[0]);r[flag]=value
    with pytest.raises(ValidationError):AIReview.model_validate(r)


@pytest.mark.parametrize("problem",["source","span","revision"])
def test_changed_frozen_inputs_fail_binding(tmp_path,problem):
    packet=json.loads((BASE/"PMC4024011/evidence_packet.json").read_text())
    draft=json.loads((BASE/"PMC4024011/v3_core_draft.json").read_text())
    if problem=="source":
        source=tmp_path/"source.json";source.write_text("{}")
        packet["source"]["article_path"]=str(source)
    if problem=="span":packet["evidence_spans"][0]["text"]="TEST tampering"
    if problem=="revision":packet["Core_revision_id"]="TEST wrong revision"
    p=tmp_path/"packet.json";p.write_text(json.dumps(packet));d=tmp_path/"draft.json";d.write_text(json.dumps(draft))
    prompt=tmp_path/"prompt.txt";prompt.write_text("test prompt")
    with pytest.raises(ValueError):load_bound_packet(p,prompt,d)


@pytest.mark.parametrize("direction",["no_increase","not_significant","unknown"])
def test_null_or_missing_direction_does_not_become_negative(bundles,direction):
    raw=[control_review(b) for b in bundles];raw[1]["claim"]["direction"]=direction
    result=compare_shadow_pair(*bundles,*[bind_review(b,r) for b,r in zip(bundles,raw)])
    assert not result["direction_opposed"] and not result["provisional_contradiction"]
    assert not result["hypotheses"]


def test_review_uncertainty_and_endpoint_mismatch_are_not_hidden(bundles):
    raw=[control_review(b) for b in bundles];raw[1]["fields"][0]["verdict"]="UNCERTAIN"
    r=compare_shadow_pair(*bundles,*[bind_review(b,x) for b,x in zip(bundles,raw)])
    assert r["alignment_status"]=="UNCERTAIN"
    raw[1]["claim"]["measured_entity"]["value"]="TEST different analyte"
    r=compare_shadow_pair(*bundles,*[bind_review(b,x) for b,x in zip(bundles,raw)])
    assert r["alignment_status"]=="NOT_SUFFICIENTLY_COMPARABLE" and not r["hypotheses"]


def test_unsupported_review_and_same_publication_cannot_become_conflicts(bundles):
    raw=[control_review(b) for b in bundles];raw[1]["fields"][-1]["verdict"]="UNSUPPORTED"
    reviewed=[bind_review(b,r) for b,r in zip(bundles,raw)]
    result=compare_shadow_pair(*bundles,*reviewed)
    assert result["alignment_status"]=="NOT_SUPPORTED_BY_REVIEW" and not result["hypotheses"]
    with pytest.raises(ValueError,match="independent_papers_required"):
        compare_shadow_pair(bundles[0],bundles[0],reviewed[0],reviewed[0])


def test_JATS_derivative_must_match_original_paragraph(tmp_path):
    from code_engine.discovery.ai_review_shadow import file_hash
    xml=tmp_path/"original.xml"
    xml.write_text('<article><front><article-meta><article-id pub-id-type="pmcid">TEST_PMC</article-id><article-id pub-id-type="pmid">TEST_PMID</article-id></article-meta></front><body><p>Engineering control text only.</p></body></article>')
    text="Engineering control text only."
    source=tmp_path/"projection.json"
    source.write_text(json.dumps({"pmcid":"TEST_PMC","pmid":"TEST_PMID","sections":[{"text":text,"source_xml_paragraph_index":0}]}))
    import hashlib
    packet={"packet_id":"TEST_ONLY","source":{"pmcid":"TEST_PMC","pmid":"TEST_PMID","article_path":str(source),
        "article_sha256":file_hash(source),"format":"frozen_jats_paragraph_projection","original_xml_path":str(xml),"original_xml_sha256":file_hash(xml)},
        "evidence_spans":[{"evidence_span_id":"TEST_SPAN","section_index":0,"text":text,"char_start":0,"char_end":len(text),
            "text_hash":hashlib.sha256(text.encode()).hexdigest(),"source_section_text_sha256":hashlib.sha256(text.encode()).hexdigest()}]}
    p=tmp_path/"packet.json";p.write_text(json.dumps(packet));prompt=tmp_path/"prompt.txt";prompt.write_text("test only")
    assert load_bound_packet(p,prompt).input_hashes["original_xml"]==file_hash(xml)
    xml.write_text(xml.read_text().replace("control text","tampered text"))
    with pytest.raises(ValueError,match="original_xml_hash_mismatch"):load_bound_packet(p,prompt)


def test_hypothesis_control_requires_supported_opposition_and_has_both_evidence_sets(bundles):
    raw=[control_review(b) for b in bundles];raw[1]["claim"]["direction"]="negative"
    result=compare_shadow_pair(*bundles,*[bind_review(b,r) for b,r in zip(bundles,raw)])
    assert result["provisional_contradiction"]
    hyp=result["hypotheses"][0]
    assert hyp["supporting_evidence_refs"] and hyp["contradicting_evidence_refs"] and hyp["test"]
    assert hyp["authority_label"]==LABEL and hyp["validated_hypothesis"] is False
    raw[1]["fields"][4]["verdict"]="PARTIALLY_SUPPORTED"
    result=compare_shadow_pair(*bundles,*[bind_review(b,r) for b,r in zip(bundles,raw)])
    assert not result["provisional_contradiction"] and not result["hypotheses"]


def test_output_is_content_addressed_and_immutable(tmp_path,bundles):
    r=bind_review(bundles[0],control_review(bundles[0])).model_dump(mode="json")
    a=persist_shadow(tmp_path,r);assert a==persist_shadow(tmp_path,r)
    assert a["canonical_output_sha256"]==content_hash(r)
    Path(a["path"]).write_text("TEST tampering")
    with pytest.raises(ValueError):persist_shadow(tmp_path,r)


@pytest.mark.parametrize("marker",[
    {"namespace":NAMESPACE},{"authority_label":LABEL},{"execution_path":"shadow"},
    {"schema_version":"shadow_evidence_alignment_v1"},
    {"review_import":{"results":[{"namespace":NAMESPACE}]}},
])
def test_direct_formal_gate_and_native_handoff_reject_shadow_even_with_flags(marker):
    native=json.loads((BASE/"PMC4024011/v3_core_draft.json").read_text())
    native.update(marker,scientific_authorization=True,human_gold=True,strict_core_eligible=True,formal_core_graph_eligible=True)
    assert experimental_admission_blocks(native)==["shadow_artifact_has_no_formal_scientific_authority"]
    assert core_graph_eligibility(native)["eligible"] is False
    with pytest.raises(ValueError,match="shadow_artifact_forbidden"):
        prepare_experimental_handoff(native,Path("test"))


@pytest.mark.parametrize("lane",["l2_fulltext_observations.jsonl","l35_fulltext_l1_claims.jsonl"])
def test_formal_projection_import_lanes_reject_wrapped_shadow(tmp_path,lane):
    source=tmp_path/"input/artifacts";source.mkdir(parents=True)
    # Deliberate adversarial flags are a software test, not scientific approval.
    attack={"scientific_authorization":True,"human_gold":True,"formal_core_graph_eligible":True,
        "payload":{"namespace":NAMESPACE,"authority_label":LABEL}}
    (source/lane).write_text(json.dumps(attack)+"\n")
    with pytest.raises(ValueError,match="shadow_artifact_forbidden"):
        project_fulltext_run(source.parent,tmp_path/"outputs")
    assert not (tmp_path/"outputs").exists()


def test_budget_is_plan_only_and_requires_both_prices():
    plan=plan_model_reviews(["a"*400,"b"*800],max_output_tokens=20,input_usd_per_million=1)
    assert plan["planned_calls"]==2 and plan["estimated_total_input_tokens"]==300
    assert plan["estimated_total_usd"] is None and plan["max_total_output_tokens"]==40
    priced=plan_model_reviews(["a"*400],max_output_tokens=20,input_usd_per_million=1,output_usd_per_million=2)
    assert priced["estimated_total_usd"]==pytest.approx(.00014)
    assert priced["actual_api_calls"]==0 and not priced["automatic_execution_authorized"]
