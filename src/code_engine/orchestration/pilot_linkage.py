"""Versioned provisional Pilot linkage sidecar; no scientific promotion or transport.

Source applicability is retained as an explicitly supplied assessment. Exact
bindings verify its integrity, never independently certify its scientific meaning.
"""
from copy import deepcopy
from pathlib import Path
import json
import xml.etree.ElementTree as ET

from code_engine.discovery.ai_review_shadow import content_hash, file_hash
from code_engine.extraction_assets.experimental_core.assembly import assemble_v3
from code_engine.extraction_assets.experimental_core.linkage_candidates import (
    candidate_input, produce_candidates, candidate_v2_diagnostic,
)
from code_engine.extraction_assets.experimental_core.source_envelope import build_resolution_envelope
from code_engine.extraction_assets.experimental_core.source_resolution_models import SourceResolutionEnvelope
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import TrustedDraftContextV3
from code_engine.fulltext.source_windows import mapped_evidence_segments, extraction_block
from code_engine.orchestration.component_probe import conditional_linkage_request
from scripts.search_plan_v24_alpha318a1_source_contracts import node_text

VERSION = "pilot_source_grounded_linkage_stage_v1"


def pinned_json(pin):
    path = Path(pin["path"])
    if file_hash(path) != pin["sha256"]:
        raise ValueError("linkage_input_artifact_hash_mismatch")
    return json.loads(path.read_text())


def _xml_node(path, xpath):
    root = ET.parse(path).getroot()
    if not xpath.startswith("/" + root.tag + "/"):
        raise ValueError("linkage_original_xpath_mismatch")
    node = root.find("./" + xpath.split("/", 2)[2])
    if node is None:
        raise ValueError("linkage_original_xpath_missing")
    return node


def _supplement(assembled, lineage, spec):
    """Check supplied source-review bindings, including original XML and windows.

    Methods applicability still needs scientific review. We check the exact
    declared region and endpoint binding, not Methods topic similarity.
    """
    blocks = deepcopy(lineage["source_blocks"])
    if not spec:
        return blocks, [], {}, None
    catalog = pinned_json(spec["catalog"])
    binding = pinned_json(spec["binding"])
    f = assembled["envelope"]["ExperimentalObservationV3"]
    core = assembled["envelope"]["ExperimentalCore"]
    if (binding["observation_identity"] != f["observation_id"] or
            binding["core_revision_identity"] != core["revision"]["identity"] or
            binding["experiment_scope_identity"] != f["experiment"]["experiment_id"]):
        raise ValueError("linkage_supplement_scope_mismatch")
    if binding["catalog_sha256"] != spec["catalog"]["sha256"]:
        raise ValueError("linkage_supplement_catalog_mismatch")
    ctx = TrustedDraftContextV3(**lineage["hydration_context"])
    article = json.loads(Path(ctx.source_artifact).read_text())
    if file_hash(Path(ctx.source_artifact)) != ctx.fulltext_source_hash:
        raise ValueError("linkage_original_source_hash_mismatch")
    spans = []
    for ref in binding["evidence_refs"]:
        span = catalog["spans"][ref]
        origin = catalog["lineage"][ref]
        block = catalog["source_blocks"][span["block_id"]]
        if span["block_id"] in blocks and blocks[span["block_id"]] != block:
            raise ValueError("linkage_source_block_collision")
        if "original_xml_path" in origin:
            xml = Path(origin["original_xml_path"])
            if (file_hash(xml) != origin["original_xml_sha256"] or
                    article.get("original_xml_sha256") != origin["original_xml_sha256"]):
                raise ValueError("linkage_original_XML_hash_mismatch")
            node = _xml_node(xml, origin["source_xpath"])
            if node_text(node) != block:
                raise ValueError("linkage_source_region_projection_mismatch")
            if "section_index" in origin:
                section = article["sections"][origin["section_index"]]
                if section["source_xpath"] != origin["source_xpath"] or section["text"] != block:
                    raise ValueError("linkage_methods_region_binding_mismatch")
        else:
            if (origin.get("source_sha256") != ctx.fulltext_source_hash or
                    span["block_id"] != ctx.block_id or block != ctx.block_text):
                raise ValueError("linkage_results_source_binding_mismatch")
            # Existing source-window adapter checks source coordinates and text.
            window = lineage.get("window")
            if window is None:
                raise ValueError("linkage_supplement_original_window_required")
            mapped = mapped_evidence_segments(window, span, block=extraction_block(window, ctx.pmcid, ctx.pmid))
            for piece in mapped:
                section = article["sections"][piece["section_index"]]["text"]
                if section[piece["char_start"]:piece["char_end"]] != piece["text"]:
                    raise ValueError("linkage_results_original_coordinate_mismatch")
        blocks[span["block_id"]] = block
        spans.append(span)
    refs = {s["evidence_span_id"] for s in spans}
    component_ids = {x["identity"] for k in ("factors", "measurements", "results") for x in core[k]}
    for component, anchors in binding.get("component_evidence", {}).items():
        if component not in component_ids or not anchors or not set(anchors) <= refs:
            raise ValueError("linkage_component_evidence_binding_mismatch")
    for use in binding.get("cross_region_applicability", []):
        if (use["experiment_scope_identity"] != f["experiment"]["experiment_id"] or
                use["measurement_identity"] not in {m["identity"] for m in core["measurements"]} or
                use["evidence_ref"] not in refs or not use["support_explanation"]):
            raise ValueError("linkage_cross_region_applicability_mismatch")
        span = catalog["spans"][use["evidence_ref"]]
        origin = catalog["lineage"][use["evidence_ref"]]
        if content_hash(span) != use["span_sha256"]:
            raise ValueError("linkage_cross_region_span_mismatch")
        if use["kind"] == "figure_caption":
            xml = origin["original_xml_path"]
            figure_path = origin["source_xpath"].split("/caption[", 1)[0]
            figure = _xml_node(xml, figure_path)
            result_node = _xml_node(xml, use["results_xpath"])
            if not any(x.get("rid") == figure.get("id") and x.get("ref-type") == "fig"
                       and node_text(x) == use["explicit_xref_text"] for x in result_node.iter("xref")):
                raise ValueError("linkage_explicit_figure_binding_mismatch")
            if span["text"] != use["exact_applicable_text"]:
                raise ValueError("linkage_figure_panel_binding_mismatch")
        elif use["kind"] == "methods":
            if (origin.get("source_xpath") != use["methods_xpath"] or
                    span["text"] != use["exact_applicable_text"] or span["source_role"] != "methods"):
                raise ValueError("linkage_methods_applicability_binding_mismatch")
        else:
            raise ValueError("linkage_unsupported_applicability_kind")
    return blocks, spans, binding.get("component_evidence", {}), binding


def prepare_stage(envelope, lineage, *, supplement=None, question_domain=None,
                  model="deepseek-flash", max_output_tokens=8192, input_token_ceiling=40000):
    if not lineage:
        raise ValueError("original_V3_response_lineage_unavailable")
    for name in ("response", "validated"):
        pinned_json(lineage[name])
    ctx = TrustedDraftContextV3(**lineage["hydration_context"])
    assembled = assemble_v3(envelope["ExperimentalObservationV3"], source_artifact=ctx.source_artifact,
                            source_blocks=lineage["source_blocks"])
    if assembled["envelope"] != envelope:
        raise ValueError("linkage_current_core_not_exact_V3_assembly")
    blocks, extras, component_evidence, binding = _supplement(assembled, lineage, supplement)
    prepared = conditional_linkage_request(
        assembled, source_artifact=ctx.source_artifact, source_blocks=blocks,
        actual_v3_response_file=lineage["response"]["path"], validated_v3_file=lineage["validated"]["path"],
        hydration_context=ctx, additional_evidence=extras, question_domain=question_domain,
        model=model, max_output_tokens=max_output_tokens, input_token_ceiling=input_token_ceiling)
    packet = candidate_input(assembled, source_artifact=ctx.source_artifact, source_blocks=blocks,
                              additional_evidence=extras)
    core = envelope["ExperimentalCore"]
    context = {"source_document_identity": ctx.source_document_id, "source_block_identity": ctx.block_id,
               "primary_result_sentence": envelope["ExperimentalObservationV3"]["observation"]["observed_result"],
               "spans": packet["evidence_spans"], "source_text_authority": "authoritative_historical_snapshot",
               "historical_provider_input_authority": "incomplete",
               "methods_text_refs": [s["evidence_span_id"] for s in extras if s["source_role"] == "methods"],
               "figure_caption_refs": [x["evidence_ref"] for x in (binding or {}).get("cross_region_applicability", []) if x["kind"] == "figure_caption"],
               "group_definition_refs": sorted({r for v in component_evidence.values() for r in v})}
    envelopes = [SourceResolutionEnvelope.model_validate(build_resolution_envelope(
        task_type=task, observation=core["revision"], result=core["results"][0],
        factors=core["factors"], measurements=core["measurements"], source_context=context,
        scope_audit={"completeness": "partial", "identity": VERSION + ":unreviewed_source_scope"},
        provenance=core["revision"]["provenance"])).model_dump(mode="json")
        for task in ("factor_application", "comparator", "measurement_method")]
    return {"schema_version": VERSION, "assembled": assembled, "source_artifact": ctx.source_artifact,
            "source_blocks": blocks, "additional_evidence": extras, "component_evidence": component_evidence,
            "source_applicability_assessment": binding, "source_resolution_envelopes": envelopes,
            "lineage": deepcopy(lineage), "input": packet, "prepared_request": prepared,
            "scientific_authorization": False, "human_gold": False, "strict_core_eligible": False}


def assess_stage(prepared, response, *, proposal_origin):
    """Retain a whole response plus per-proposal rejection; never alter native Core."""
    if not isinstance(response, dict):
        raise ValueError("linkage_response_object_required")
    accepted, rejected = [], []
    base = {k: v for k, v in response.items() if k != "proposals"}
    packet = prepared["input"]
    evidence = {x["identity"]: set(x["evidence_anchor_ids"]) for rows in packet["components"].values() for x in rows}
    for identity, refs in prepared["component_evidence"].items():
        evidence[identity].update(refs)
    kwargs = {k: prepared[k] for k in ("source_artifact", "source_blocks", "additional_evidence")}
    # Validate response-level schema/revision even for zero proposals.
    produce_candidates(prepared["assembled"], {**base, "proposals": []}, proposal_origin=proposal_origin, **kwargs)
    for index, proposal in enumerate(response.get("proposals", [])):
        try:
            produce_candidates(prepared["assembled"], {**base, "proposals": [proposal]}, proposal_origin=proposal_origin, **kwargs)
            if proposal["relation_type"] in ("factor_applies_to_measurement", "result_compared_against_factor", "result_uses_baseline"):
                factor = proposal["source_ref"] if proposal["relation_type"] == "factor_applies_to_measurement" else proposal["target_ref"]
                if not evidence[factor].intersection(proposal["evidence_refs"]):
                    raise ValueError("factor_or_comparator_source_evidence_missing")
            if proposal in accepted:
                raise ValueError("duplicate_linkage_proposal")
            accepted.append(proposal)
        except (ValueError, KeyError, TypeError) as error:
            rejected.append({"proposal_index": index, "proposal": proposal, "reason": type(error).__name__ + ":" + str(error)})
    sidecar = produce_candidates(prepared["assembled"], {**base, "proposals": accepted}, proposal_origin=proposal_origin, **kwargs)
    return {"schema_version": VERSION, "status": "candidates_structurally_verified" if accepted else "zero_accepted_candidates",
            "original_response": response, "proposal_origin": proposal_origin, "rejected_proposals": rejected,
            "sidecar": sidecar, "v2_diagnostic": candidate_v2_diagnostic(prepared["assembled"], sidecar),
            "model_proposed": proposal_origin == "provider_linkage_response",
            "source_grounding_assessment_status": "supplied_AI_provisional_assessment" if prepared["source_applicability_assessment"] else "not_independently_verified",
            "materialized_links": 0, "independent_scientific_authorization": False,
            "scientific_authorization": False, "human_gold": False, "strict_core_eligible": False}
