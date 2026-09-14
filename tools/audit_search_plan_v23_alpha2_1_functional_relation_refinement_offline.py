#!/usr/bin/env python3
"""Freeze the outcome-informed alpha2 audit before any V1_1 production code exists."""

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from code_engine.search.functional_relation_evidence_v1 import (
    EVIDENCE_STATES,
    decide_functional_relation_evidence_v1,
)

if __package__:
    from . import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    from . import run_search_plan_v23_alpha2_functional_relation_shadow_offline as alpha2
else:
    import run_search_plan_v23_alpha1_biological_unit_shadow_offline as alpha1
    import run_search_plan_v23_alpha2_functional_relation_shadow_offline as alpha2


ROOT = alpha1.ROOT
RUN = ROOT / "runs/20260914_search_plan_v23_alpha2_1_functional_relation_refinement_offline"
ALPHA2_RUN = alpha2.RUN
ALPHA2_SHADOW = "18c6f6bdf6bfb81dcdc0a700e920a98441b92dbbb5fb015c0298d4633a500e24"
ALPHA2_ROOT = "3597f5443279a6475ba336e17e24da3031cb04cec44f2b8222992843c00c1270"
ALPHA1_1_ROOT = "f5906384c549c31c167aeb511f9a4e37c597dbd93ac1ba530e6b2debd687831c"
STATUS = "seen_heldout_v1_retrospective_development_only"
AUDIT_FILES = {
    "alpha2_direct_blocker_audit.json", "alpha2_direct_blocker_audit.md",
    "alpha2_direct_unresolved_audit.json", "alpha2_direct_unresolved_audit.md",
    "alpha2_state_reachability_audit.json", "current_study_relation_parser_audit.json",
    "alpha2_refinement_decision.json",
}


BLOCKER_DIAGNOSES = {
    "heldout_rrpv1_0012": ("TRUE_PREACQUISITION_AMBIGUITY", "B", "Upstream NEK7 mutation co-changed NLRP3 activation and IL-1β secretion without isolating the target edge.", "mutant mice and macrophages"),
    "heldout_rrpv1_0013": ("TRUE_PREACQUISITION_AMBIGUITY", "B", "Cathepsin perturbations affected both NLRP3 activation and secretion; NLRP3-specific necessity was not shown.", "selectively block particle-induced nlrp3"),
    "heldout_rrpv1_0014": ("TRUE_PREACQUISITION_AMBIGUITY", "B", "Zinc depletion was an upstream intervention that induced both target state and endpoint.", "depletion of zinc from macrophages"),
    "heldout_rrpv1_0018": ("MISSED_NECESSITY_EVIDENCE", "A", "The current result explicitly described NLRP3-dependent caspase activation and IL-1β secretion.", "nlrp3- and asc"),
    "heldout_rrpv1_0019": ("TRUE_PREACQUISITION_AMBIGUITY", "B", "Current experiments isolated NEK7 necessity, not the frozen NLRP3-to-secretion edge.", "in the absence of nek7"),
    "heldout_rrpv1_0020": ("MISSED_FUNCTIONAL_CHAIN", "A", "Adjacent current-result sentences tied one compound to IL-1β suppression, specific NLRP3 inhibition, and direct NLRP3 binding.", "britannin specifically inhibited"),
    "heldout_rrpv1_0031": ("TRUE_PREACQUISITION_AMBIGUITY", "B", "TRPM2 and downstream-effector perturbations did not isolate GLP-1 receptor activation itself.", "silencing of trpm2"),
    "heldout_rrpv1_0039": ("TRUE_PREACQUISITION_AMBIGUITY", "B", "The proposed V1bR-glucagon-GLP-1R chain lacked target-specific necessity or rescue evidence.", "further studies indicated"),
    "heldout_rrpv1_0042": ("MISSED_NECESSITY_EVIDENCE", "A", "AXL activation and AXL-knockout alleviation of resistance were linked in the same current mechanistic result.", "axl knockout alleviating"),
    "heldout_rrpv1_0043": ("OVERSTRICT_MULTI_TARGET_RULE", "A", "A preceding sentence reported separate CDCP1-or-AXL silencing; the later dual experiment must not shadow isolated AXL evidence.", "silencing of cdcp1 or axl"),
    "heldout_rrpv1_0061": ("TRUE_PREACQUISITION_AMBIGUITY", "B", "Purine-pathway interventions co-induced AMPK activation and uptake without target-specific necessity.", "6-mercaptopurine"),
    "heldout_rrpv1_0063": ("MISSED_NECESSITY_EVIDENCE", "A", "The uptake effect was explicitly abrogated by a specific AMPK inhibitor.", "both effects were abrogated"),
    "heldout_rrpv1_0064": ("MISSED_NECESSITY_EVIDENCE", "A", "A bounded result sequence reported AMPK activation, uptake potentiation, and loss of effects in AMPK-subunit-deficient systems.", "these effects were abolished"),
    "heldout_rrpv1_0067": ("MISSED_NECESSITY_EVIDENCE", "A", "The same current-result sentence stated that increased uptake was dependent on AMPK activation.", "dependent on ampk activation"),
}


UNRESOLVED_DIAGNOSES = {
    "heldout_rrpv1_0011": ("CHAIN_REQUIRES_MULTISENTENCE_LINKING", "B", "An anaphoric process link connected activation and release, but target-specific necessity for the endpoint was not visible."),
    "heldout_rrpv1_0016": ("GENUINELY_UNRESOLVED_PREACQUISITION", "B", "The abstract investigated upstream infection mechanisms and did not isolate the frozen target edge."),
    "heldout_rrpv1_0022": ("ENDPOINT_LINK_NOT_RECOGNIZED", "B", "The reported generic collagen synthesis did not safely resolve the frozen collagen-I endpoint without endpoint-equivalence inference."),
    "heldout_rrpv1_0023": ("DIRECTION_NOT_RESOLVED", "B", "Oxy210 inhibited genes during TGF-β stimulation; the visible contrast did not isolate the target-direction effect."),
    "heldout_rrpv1_0024": ("PERTURBATION_SURFACE_NOT_RECOGNIZED", "A", "A TGF-β receptor inhibitor reversed the collagen increase and reduced SMAD phosphorylation in one result sentence."),
    "heldout_rrpv1_0025": ("LEXICAL_NORMALIZATION_GAP", "B", "Type-I collagen wording and TGF-pathway restoration were visible, but repairing endpoint identity is outside relation-parser authority."),
    "heldout_rrpv1_0026": ("GENUINELY_UNRESOLVED_PREACQUISITION", "B", "TNC induced both pathway activation and collagen, without target-specific necessity or rescue."),
    "heldout_rrpv1_0027": ("GENUINELY_UNRESOLVED_PREACQUISITION", "B", "A combination intervention inhibited a TGF-induced endpoint but did not isolate TGF signaling as the manipulated subject."),
    "heldout_rrpv1_0029": ("GENUINELY_UNRESOLVED_PREACQUISITION", "B", "The abstract proposed an indirect IL-6-to-TGF pathway without target-specific necessity for collagen-I response."),
    "heldout_rrpv1_0037": ("PERTURBATION_SURFACE_NOT_RECOGNIZED", "A", "Exact receptor-agonist language and enhanced GSIS were present, but protect/preserve and agonist grammar were not linked."),
    "heldout_rrpv1_0038": ("CHAIN_REQUIRES_MULTISENTENCE_LINKING", "A", "Adjacent result sentences tied one named receptor agonist to receptor engagement and potentiated GSIS."),
    "heldout_rrpv1_0044": ("GENUINELY_UNRESOLVED_PREACQUISITION", "B", "AXL degradation was linked to EGFR-TKI response, but exact osimertinib response was not locally resolved."),
    "heldout_rrpv1_0050": ("GENUINELY_UNRESOLVED_PREACQUISITION", "B", "BET-class inhibition and BRD4 binding were separated from the venetoclax combination result without bounded exact-subject linkage."),
    "heldout_rrpv1_0054": ("PERTURBATION_SURFACE_NOT_RECOGNIZED", "A", "The exact subject was the grammatical causal agent in a current-study sentence that increased the exact endpoint."),
    "heldout_rrpv1_0070": ("PERTURBATION_SURFACE_NOT_RECOGNIZED", "A", "Constitutively active, dominant-interfering, shRNA, and deficient-cell evidence was visible but unsupported by V1 grammar."),
}


UNRESOLVED_NEEDLES = {
    "heldout_rrpv1_0011": "this process promoted il-1 beta release",
    "heldout_rrpv1_0016": "depends on a p2x7-independent",
    "heldout_rrpv1_0022": "tgf- beta induced collagen synthesis",
    "heldout_rrpv1_0023": "following tgf- beta stimulation",
    "heldout_rrpv1_0024": "an inhibitor of transforming growth factor-beta",
    "heldout_rrpv1_0025": "restoration of t beta rii",
    "heldout_rrpv1_0026": "by activating the tgf- beta signaling pathway",
    "heldout_rrpv1_0027": "tgf- beta induced collagen-i expression",
    "heldout_rrpv1_0029": "effect is indirect and mediated",
    "heldout_rrpv1_0037": "glucagon-like peptide 1 receptor agonists",
    "heldout_rrpv1_0038": "ecc5004 potentiated gsis",
    "heldout_rrpv1_0044": "an axl degrader",
    "heldout_rrpv1_0050": "cotreatment with abbv-075 and venetoclax",
    "heldout_rrpv1_0054": "we show here that brain-derived neurotrophic factor",
    "heldout_rrpv1_0070": "constitutively active ampk",
}


def _json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def verify_upstreams():
    alpha2_manifest = json.loads((ALPHA2_RUN / "implementation_manifest.json").read_bytes())
    pairs = []
    for component in alpha2_manifest["aggregate_components"]:
        actual = alpha1.frozen.sha256(ALPHA2_RUN / component["path"])
        alpha1.frozen.require(actual == component["sha256"], f"alpha2 component mismatch: {component['path']}")
        pairs.append([component["path"], actual])
    root = alpha1.frozen.digest(alpha1.frozen.canonical_json(pairs))
    shadow = alpha1.frozen.sha256(ALPHA2_RUN / "v23_alpha2_relation_shadow_decisions.jsonl")
    alpha1.frozen.require(root == ALPHA2_ROOT == alpha2_manifest["v23_alpha2_functional_relation_shadow_sha256"], "alpha2 root mismatch")
    alpha1.frozen.require(shadow == ALPHA2_SHADOW, "alpha2 shadow mismatch")
    alpha1.frozen.require(alpha2.verify_alpha1_1_root()["root"] == ALPHA1_1_ROOT, "alpha1.1 root mismatch")
    return {"v23_alpha2_relation_shadow_decisions_sha256": shadow,
            "v23_alpha2_functional_relation_shadow_sha256": root,
            "v23_alpha1_1_biological_unit_refinement_sha256": ALPHA1_1_ROOT}


def _sentences(item):
    from code_engine.search.functional_relation_evidence_v1 import _sentences as split
    return split(item["title"], item["abstract"])


def _find_sentence(item, needle):
    matches = [row for row in _sentences(item) if needle in row["text"]]
    alpha1.frozen.require(matches, f"audit evidence sentence missing: {item['packet_id']} {needle}")
    return matches[0]


def _inputs_and_labels():
    inputs = {row["packet_id"]: row for row in alpha1.parse_preacquisition_batches()}
    shadows = {row["packet_id"]: row for row in alpha1.frozen.read_jsonl(ALPHA2_RUN / "v23_alpha2_relation_shadow_decisions.jsonl")}
    labels = {row["packet_id"]: row for row in alpha1.frozen.read_jsonl(alpha1.ERROR_RUN / "heldout_v1_v23_development_error_matrix.jsonl")}
    return inputs, shadows, labels


def _base_record(pid, inputs, shadows, labels):
    item, shadow, label = inputs[pid], shadows[pid], labels[pid]
    decision, target = shadow["decision"], item["scientific_target"]
    alpha1.frozen.require(label["relevance_state"] == "DIRECTLY_RELEVANT", f"audit packet is not frozen direct: {pid}")
    return {
        "packet_id": pid, "case_id": label["case_id"], "tier": label["tier"],
        "target_subject": target["subject"], "target_relation_family": target["relation_family"],
        "target_endpoint": target["object"],
        "preacquisition_source_sentences_used_by_alpha2": decision["source_evidence_spans_or_sentences"],
        "evidence_role": decision["evidence_role"],
        "subject_perturbation_specificity": decision["subject_perturbation_specificity"],
        "response_link_state": decision["response_link_state"],
        "perturbation_polarity": decision["perturbation_polarity"],
        "endpoint_response_direction": decision["endpoint_response_direction"],
        "direction_compatibility": decision["direction_compatibility"],
        "reason_codes": decision["reason_codes"], "alpha2_evidence_state": decision["evidence_state"],
        "frozen_retrospective_relevance_state": label["relevance_state"],
    }


def blocker_audit():
    inputs, shadows, labels = _inputs_and_labels()
    records = []
    for pid, (diagnosis, fixability, rationale, needle) in BLOCKER_DIAGNOSES.items():
        row = _base_record(pid, inputs, shadows, labels)
        alpha1.frozen.require(row["alpha2_evidence_state"] in alpha2.BLOCKER_STATES, f"not alpha2 blocker: {pid}")
        row.update({"development_diagnosis": diagnosis, "generic_fixability": fixability,
                    "diagnostic_rationale": rationale,
                    "audit_supporting_preacquisition_sentence": _find_sentence(inputs[pid], needle)})
        records.append(row)
    counts = Counter(row["development_diagnosis"] for row in records)
    return {"development_status": STATUS, "audit_name": "alpha2_direct_blocker_audit",
            "packet_count": 14, "diagnosis_counts": dict(sorted(counts.items())),
            "generic_fixable_count": sum(row["generic_fixability"] == "A" for row in records),
            "genuinely_unavailable_or_not_safely_fixable_count": sum(row["generic_fixability"] == "B" for row in records),
            "labels_modified": False, "records": records}


def unresolved_audit():
    inputs, shadows, labels = _inputs_and_labels()
    records = []
    for pid, (diagnosis, fixability, rationale) in UNRESOLVED_DIAGNOSES.items():
        row = _base_record(pid, inputs, shadows, labels)
        alpha1.frozen.require(row["alpha2_evidence_state"] == "UNRESOLVED", f"not alpha2 unresolved: {pid}")
        row.update({"unresolved_diagnosis": diagnosis, "generic_fixability": fixability,
                    "diagnostic_rationale": rationale,
                    "audit_supporting_preacquisition_sentence": _find_sentence(inputs[pid], UNRESOLVED_NEEDLES[pid])})
        records.append(row)
    counts = Counter(row["unresolved_diagnosis"] for row in records)
    return {"development_status": STATUS, "audit_name": "alpha2_direct_unresolved_audit",
            "packet_count": 15, "diagnosis_counts": dict(sorted(counts.items())),
            "generic_fixable_count": sum(row["generic_fixability"] == "A" for row in records),
            "genuinely_unavailable_or_not_safely_fixable_count": sum(row["generic_fixability"] == "B" for row in records),
            "force_resolution": False, "records": records}


def state_reachability_audit():
    observed = json.loads((ALPHA2_RUN / "shadow_decision_validation.json").read_bytes())["evidence_state_counts"]
    details = {
        "DIRECT_FUNCTIONAL": (True, ["test_direct_positive_perturbation", "test_direct_inverse_perturbation"], "evaluated before chain and weaker states", ["none after direction-compatible exact evidence"]),
        "FUNCTIONAL_CHAIN": (True, ["test_functional_mechanistic_chain"], "after direct and before multi/association", ["DIRECT_FUNCTIONAL when evidence is same-sentence direct", "UNRESOLVED when direction is unresolved"]),
        "ASSOCIATION_ONLY": (True, ["test_correlation_only", "test_cochange_without_subject_perturbation"], "after direct/chain/multi", ["V1 incorrectly absorbs unrecognized co-change parser uncertainty"]),
        "BACKGROUND_ONLY": (True, ["test_background_proposition_only"], "after all current-study states", ["current-study evidence", "UNRESOLVED when role lacks deterministic background marker"]),
        "MULTI_TARGET_AMBIGUOUS": (True, ["test_multi_target_intervention"], "after direct/chain but before association", ["stronger isolated target-specific evidence was not globally preferred in V1"]),
        "UNRESOLVED": (True, ["test_insufficient_abstract_is_unresolved", "test_direction_conflict"], "fail-closed terminal state", []),
    }
    states = {}
    for state in EVIDENCE_STATES:
        reachable, tests, precedence, shadowing = details[state]
        states[state] = {"reachable_by_logic": reachable, "generic_test_coverage": tests,
                         "observed_count": observed[state], "precedence_rules": precedence,
                         "possible_shadowing_states": shadowing}
    return {"development_status": STATUS, "audit_name": "alpha2_state_reachability_audit",
            "all_public_states_accounted_for": True,
            "functional_chain_zero_diagnosis": "reachable and tested; no alpha2 corpus record satisfied its strict adjacent perturbation-plus-linked-response implementation",
            "background_only_zero_diagnosis": "reachable and tested; no record had an exclusively deterministic prior-work target proposition after current evidence precedence",
            "states": states}


def _probe(name, text, expected, target=None):
    policy = json.loads((ROOT / "configs/search_plans/functional_relation_evidence_policy_v1.json").read_bytes())
    target = target or {"subject": "Kinase X", "relation_family": "increases", "object": "marker Y",
                        "measurement_target": "marker Y", "measurement_property_endpoint": "abundance",
                        "acceptable_endpoint_evidence": ["marker Y"]}
    result = decide_functional_relation_evidence_v1("generic_audit_probe", target, title="", abstract=text,
                                                     publication_metadata={}, policy=policy)
    return {"probe_id": name, "source_text": text, "alpha2_state": result.evidence_state,
            "expected_generic_semantics": expected, "recognized_as_expected": result.evidence_state == expected,
            "evidence_role": result.evidence_role, "reason_codes": list(result.reason_codes)}


def parser_audit():
    probes = [
        _probe("treatment", "Treatment with Kinase X increased marker Y.", "DIRECT_FUNCTIONAL"),
        _probe("knockdown", "Kinase X knockdown reduced marker Y.", "DIRECT_FUNCTIONAL"),
        _probe("knockout", "Kinase X knockout abolished marker Y induction.", "DIRECT_FUNCTIONAL"),
        _probe("silencing", "Silencing Kinase X suppressed marker Y.", "DIRECT_FUNCTIONAL"),
        _probe("constitutive", "Constitutively active Kinase X increased marker Y.", "DIRECT_FUNCTIONAL"),
        _probe("dominant_negative", "Dominant-negative Kinase X reduced marker Y.", "DIRECT_FUNCTIONAL"),
        _probe("deficient", "Kinase X-deficient cells failed to induce marker Y.", "DIRECT_FUNCTIONAL"),
        _probe("blocking", "Blocking Kinase X prevented marker Y induction.", "DIRECT_FUNCTIONAL"),
        _probe("reversal", "The marker Y response was reversed by inhibition of Kinase X.", "DIRECT_FUNCTIONAL"),
        _probe("loss", "Loss of Kinase X abolished marker Y.", "DIRECT_FUNCTIONAL"),
        _probe("rescue", "Re-expression of Kinase X restored marker Y.", "DIRECT_FUNCTIONAL"),
        _probe("adjacent", "We inhibited Kinase X. This treatment reduced marker Y.", "FUNCTIONAL_CHAIN"),
        _probe("unrelated_adjacent", "We inhibited Kinase X. An unrelated treatment reduced marker Y.", "UNRESOLVED"),
        _probe("cochange_uncertainty", "Treatment Z increased Kinase X and marker Y.", "UNRESOLVED"),
        _probe("association", "Kinase X correlated with marker Y.", "ASSOCIATION_ONLY"),
        _probe("background", "Previous studies showed that Kinase X increased marker Y.", "BACKGROUND_ONLY"),
    ]
    return {"development_status": STATUS, "audit_name": "current_study_relation_parser_audit",
            "same_sentence_linking_supported": True, "adjacent_sentence_linking_supported": "limited V1 chain form only",
            "same_abstract_result_clause_linking_supported": False,
            "probe_count": len(probes), "recognized_count": sum(row["recognized_as_expected"] for row in probes),
            "main_generic_failures": [
                "constitutive-active, dominant-negative, deficient-cell, failed-to, prevent, and reversal grammar gaps",
                "V1 maps co-change parser uncertainty to ASSOCIATION_ONLY without positive association language",
                "bounded repeated-intervention adjacent composition is absent",
                "global strongest target-specific evidence does not override a weaker multi-target sentence",
            ], "probes": probes}


def refinement_decision():
    changes = [
        {"change_id": "REL_V1_1_ASSOCIATION_POSITIVE_ONLY", "diagnosed_failure_mechanism": "COCHANGE_ONLY was used as a fallback for parser uncertainty", "affected_development_packets": sorted(pid for pid in BLOCKER_DIAGNOSES if pid != "heldout_rrpv1_0043"), "generic_scope": "all functional targets", "scientific_rationale": "association requires affirmative association language", "risk": "more UNRESOLVED records", "implemented": True, "reason": "required to preserve fail-closed semantics"},
        {"change_id": "REL_V1_1_PERTURBATION_GRAMMAR", "diagnosed_failure_mechanism": "bounded target perturbation forms were not recognized", "affected_development_packets": ["heldout_rrpv1_0024", "heldout_rrpv1_0037", "heldout_rrpv1_0054", "heldout_rrpv1_0070"], "generic_scope": "generic activation, inhibition, loss, rescue, and subject-causal grammar", "scientific_rationale": "recognize explicit experimental grammar without external pharmacology", "risk": "grammatical-agent false positives", "implemented": True, "reason": "guarded by exact subject, endpoint, current role, and direction"},
        {"change_id": "REL_V1_1_NECESSITY_RESCUE", "diagnosed_failure_mechanism": "dependent-on and abrogation evidence was not aggregated", "affected_development_packets": ["heldout_rrpv1_0018", "heldout_rrpv1_0020", "heldout_rrpv1_0042", "heldout_rrpv1_0063", "heldout_rrpv1_0064", "heldout_rrpv1_0067"], "generic_scope": "exact-subject necessity and rescue evidence", "scientific_rationale": "inverse perturbation can establish a positive target relation", "risk": "dependency attribution across entities", "implemented": True, "reason": "require exact target and endpoint linkage"},
        {"change_id": "REL_V1_1_BOUNDED_COMPOSITION", "diagnosed_failure_mechanism": "same experiment split across adjacent result sentences", "affected_development_packets": ["heldout_rrpv1_0020", "heldout_rrpv1_0038", "heldout_rrpv1_0042", "heldout_rrpv1_0064"], "generic_scope": "same sentence or adjacent current-result sentences sharing an explicit intervention", "scientific_rationale": "preserve local experiment structure without long-range inference", "risk": "false anaphora", "implemented": True, "reason": "composition requires repeated intervention or explicit this-effect linkage"},
        {"change_id": "REL_V1_1_STRONGEST_SPECIFIC_EVIDENCE", "diagnosed_failure_mechanism": "later dual-target evidence shadowed isolated target perturbation", "affected_development_packets": ["heldout_rrpv1_0043"], "generic_scope": "global evidence aggregation", "scientific_rationale": "resolved exact-subject evidence outranks unresolved multi-target evidence", "risk": "incorrectly treating joint interventions as separate", "implemented": True, "reason": "only explicit alternative single-target grammar qualifies"},
        {"change_id": "REL_V1_1_ENDPOINT_EQUIVALENCE", "diagnosed_failure_mechanism": "some endpoint lexical forms were not resolved", "affected_development_packets": ["heldout_rrpv1_0022", "heldout_rrpv1_0025"], "generic_scope": "endpoint identity", "scientific_rationale": "belongs to endpoint authority, not relation evidence", "risk": "scope violation", "implemented": False, "reason": "do not make relation parsing responsible for endpoint equivalence"},
        {"change_id": "REL_V1_1_BACKGROUND_ROLE", "diagnosed_failure_mechanism": "BACKGROUND_ONLY observed count was zero", "affected_development_packets": [], "generic_scope": "background role", "scientific_rationale": "state is already reachable and tested", "risk": "false section inference", "implemented": False, "reason": "no generic defect established"},
    ]
    return {"development_status": STATUS, "audit_name": "alpha2_refinement_decision",
            "outcome_informed_cycle": 1, "maximum_cycles_on_heldout_v1": 1,
            "functional_relation_tuning_closed_after_this_cycle": True,
            "production_policy_selected": None, "changes": changes}


def _markdown(title, audit, diagnosis_key):
    lines = [f"# {title}", "", f"development_status: `{STATUS}`", "",
             f"packet_count: {audit['packet_count']}", ""]
    for row in audit["records"]:
        lines.extend([f"## {row['packet_id']}", "",
                      f"- case/tier: `{row['case_id']}` / `{row['tier']}`",
                      f"- target: `{row['target_subject']} -> {row['target_relation_family']} -> {row['target_endpoint']}`",
                      f"- alpha2 state: `{row['alpha2_evidence_state']}`",
                      f"- diagnosis: `{row[diagnosis_key]}`",
                      f"- generic fixability: `{row['generic_fixability']}`",
                      f"- rationale: {row['diagnostic_rationale']}", ""])
    return ("\n".join(lines) + "\n").encode()


def build_outputs():
    verify_upstreams()
    blocker = blocker_audit()
    unresolved = unresolved_audit()
    outputs = {
        "alpha2_direct_blocker_audit.json": _json(blocker),
        "alpha2_direct_blocker_audit.md": _markdown("Alpha2 direct blocker audit", blocker, "development_diagnosis"),
        "alpha2_direct_unresolved_audit.json": _json(unresolved),
        "alpha2_direct_unresolved_audit.md": _markdown("Alpha2 direct unresolved audit", unresolved, "unresolved_diagnosis"),
        "alpha2_state_reachability_audit.json": _json(state_reachability_audit()),
        "current_study_relation_parser_audit.json": _json(parser_audit()),
        "alpha2_refinement_decision.json": _json(refinement_decision()),
    }
    alpha1.frozen.require(set(outputs) == AUDIT_FILES, "alpha2.1 audit membership mismatch")
    return outputs


def freeze_audits():
    outputs_a, outputs_b = build_outputs(), build_outputs()
    alpha1.frozen.require(outputs_a == outputs_b, "alpha2.1 audit replay mismatch")
    RUN.mkdir(exist_ok=True)
    for name, body in outputs_a.items():
        path = RUN / name
        if path.exists():
            alpha1.frozen.require(not path.is_symlink() and path.read_bytes() == body,
                                  f"existing alpha2.1 audit differs: {name}")
        else:
            with path.open("xb") as handle:
                handle.write(body)
        alpha1.frozen.require(path.read_bytes() == body, f"alpha2.1 audit write failed: {name}")
    alpha1.frozen.require({path.name for path in RUN.iterdir()} == AUDIT_FILES,
                          "unexpected file before V1_1 implementation")
    return outputs_a


def main():
    outputs = freeze_audits()
    print(json.dumps({"status": "audits_frozen_before_v1_1", "files": sorted(outputs),
                      "direct_blockers": 14, "direct_unresolved": 15}, indent=2))


if __name__ == "__main__":
    main()
